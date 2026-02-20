"""API client for JetKVM devices.

Communicates with:
1. The nc-based HTTP server installed on the JetKVM via api-setup.sh
   (port 8800) for sensor data.
2. The native JetKVM Go application (port 80) for WebRTC video
   streaming (requires authentication).

Sensor endpoints (port 8800):
    GET /health       -> {"status": "ok"}
    GET /temperature  -> {"temperature": 45.2}
    GET /device_info  -> full device info JSON

WebRTC endpoints (port 80, authenticated):
    POST /auth/login-local  -> session cookie
    POST /webrtc/session    -> SDP answer (base64)
"""
import asyncio
import base64
import contextlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8800
HEALTH_PATH = "/health"
TEMPERATURE_PATH = "/temperature"
DEVICE_INFO_PATH = "/device_info"

NATIVE_PORT = 80
AUTH_PATH = "/auth/login-local"
WEBRTC_SESSION_PATH = "/webrtc/session"
WEBRTC_SIGNALING_PATH = "/webrtc/signaling/client"

# nc serves one request at a time, so we need delays between retries
_REQUEST_DELAY = 1.0
_MAX_RETRIES = 3


class JetKVMError(Exception):
    """Base exception for JetKVM API errors."""


class JetKVMConnectionError(JetKVMError):
    """Cannot reach the JetKVM API server."""


class JetKVMAuthError(JetKVMError):
    """Authentication with the native JetKVM API failed."""


RemoteCandidateCallback = Callable[[dict[str, Any]], Awaitable[None] | None]


@dataclass
class _WebRTCWSSession:
    ws: aiohttp.ClientWebSocketResponse
    reader_task: asyncio.Task[None] | None
    on_remote_candidate: RemoteCandidateCallback | None


class JetKVMClient:
    """Client for the JetKVM BusyBox httpd API (port 8800) and native API (port 80)."""

    def __init__(self, host: str, port: int = DEFAULT_PORT, password: str = "") -> None:
        self._host = host.rstrip("/")
        self._port = port
        self._password = password
        self._base_url = f"http://{self._host}:{self._port}"
        self._native_url = f"http://{self._host}:{NATIVE_PORT}"
        self._session: aiohttp.ClientSession | None = None
        self._native_session: aiohttp.ClientSession | None = None
        self._authenticated = False
        self._webrtc_ws_sessions: dict[str, _WebRTCWSSession] = {}

    @property
    def host(self) -> str:
        return self._host

    @property
    def has_password(self) -> bool:
        """Return True if a password is configured for native API access."""
        return bool(self._password)

    # -- session management --------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _get_native_session(self) -> aiohttp.ClientSession:
        """Get or create the session for the native JetKVM API (port 80).

        Uses unsafe=True on the CookieJar so cookies are sent to bare
        IP addresses (aiohttp's default jar rejects them per RFC 6265).
        """
        if self._native_session is None or self._native_session.closed:
            jar = aiohttp.CookieJar(unsafe=True)
            self._native_session = aiohttp.ClientSession(cookie_jar=jar)
            self._authenticated = False
        return self._native_session

    async def close(self) -> None:
        for session_id in list(self._webrtc_ws_sessions):
            await self.async_close_webrtc_session(session_id)
        if self._session and not self._session.closed:
            await self._session.close()
        if self._native_session and not self._native_session.closed:
            await self._native_session.close()

    def _native_ws_url(self) -> str:
        """Return the native WebSocket URL for signaling."""
        return f"ws://{self._host}{WEBRTC_SIGNALING_PATH}"

    # -- low-level GET -------------------------------------------------------

    async def _get_json(self, path: str) -> dict:
        """HTTP GET and parse JSON response.

        Retries up to _MAX_RETRIES times with a small delay between attempts.
        """
        session = await self._get_session()
        url = f"{self._base_url}{path}"
        last_err = None

        for attempt in range(1, _MAX_RETRIES + 1):
            _LOGGER.debug("JetKVM API request: GET %s (attempt %d)", url, attempt)
            try:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    _LOGGER.debug("JetKVM API response: %s %s", resp.status, url)
                    if resp.status != 200:
                        raise JetKVMError(
                            f"HTTP {resp.status} from {url}"
                        )
                    raw_text = await resp.text()
                    _LOGGER.debug("JetKVM API raw response: %s", raw_text[:500])
                    try:
                        data = json.loads(raw_text)
                    except (json.JSONDecodeError, ValueError) as json_err:
                        _LOGGER.warning(
                            "JetKVM API returned invalid JSON from %s (attempt %d): %s — raw: %s",
                            url, attempt, json_err, raw_text[:200],
                        )
                        last_err = json_err
                        if attempt < _MAX_RETRIES:
                            await asyncio.sleep(_REQUEST_DELAY)
                        continue
                    _LOGGER.debug("JetKVM API data: %s", data)
                    return data
            except (aiohttp.ClientConnectorError, aiohttp.ClientError, TimeoutError, OSError) as err:
                last_err = err
                _LOGGER.debug(
                    "JetKVM API attempt %d failed for %s: %s", attempt, url, err
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_REQUEST_DELAY)

        # All retries exhausted
        raise JetKVMConnectionError(
            f"Cannot connect to JetKVM API at {url} after {_MAX_RETRIES} attempts – "
            f"have you run api-setup.sh on the device? ({last_err})"
        )

    # -- public API (port 8800) ----------------------------------------------

    async def check_health(self) -> bool:
        """Return True if the API server is reachable and healthy."""
        data = await self._get_json(HEALTH_PATH)
        if data.get("status") == "ok":
            return True
        _LOGGER.warning(
            "JetKVM API returned unexpected data for %s: %s — "
            "the device may be running an outdated api-setup.sh.",
            HEALTH_PATH, data,
        )
        return False

    async def get_temperature(self) -> float | None:
        """Return the SoC temperature in °C, or None."""
        data = await self._get_json(TEMPERATURE_PATH)
        if "error" in data:
            _LOGGER.warning("JetKVM temperature error: %s", data["error"])
            return None
        return float(data["temperature"])

    async def get_device_info(self) -> dict:
        """Return device info dict from /device_info."""
        return await self._get_json(DEVICE_INFO_PATH)

    async def get_all_data(self) -> dict:
        """Fetch all data needed by the coordinator."""
        return await self.get_device_info()

    async def validate_connection(self) -> dict:
        """Validate connectivity.  Returns device_info on success."""
        data = await self.get_device_info()
        if "error" in data or "deviceModel" not in data:
            raise JetKVMConnectionError(
                f"JetKVM API at {self._base_url} returned unexpected data: {data}. "
                "Please re-run the setup script on your JetKVM device."
            )
        return data

    # -- native API (port 80) — auth + WebRTC --------------------------------

    async def _authenticate(self) -> None:
        """Authenticate with the JetKVM native API and store session cookie."""
        if not self._password:
            raise JetKVMAuthError(
                "No password configured — video stream requires the JetKVM device password."
            )

        session = await self._get_native_session()
        url = f"{self._native_url}{AUTH_PATH}"
        _LOGGER.debug("JetKVM native auth: POST %s", url)

        try:
            async with session.post(
                url,
                json={"password": self._password},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                body = await resp.text()
                if resp.status == 401:
                    _LOGGER.debug("JetKVM native auth: 401 — password rejected")
                    raise JetKVMAuthError("Invalid password for JetKVM device.")
                if resp.status != 200:
                    _LOGGER.debug("JetKVM native auth: HTTP %s — %s", resp.status, body[:200])
                    raise JetKVMAuthError(f"Auth failed with HTTP {resp.status}")

                # Log cookie names (not values) for debugging
                cookie_names = [c.key for c in session.cookie_jar]
                _LOGGER.debug(
                    "JetKVM native auth: success (status %s, cookies: %s)",
                    resp.status, cookie_names,
                )
                self._authenticated = True
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, TimeoutError, OSError) as err:
            raise JetKVMConnectionError(
                f"Cannot connect to JetKVM native API at {url}: {err}"
            ) from err

    async def _ensure_authenticated(self) -> None:
        """Ensure we have a valid session cookie, re-authenticating if needed."""
        if not self._authenticated:
            await self._authenticate()

    async def async_check_password(self) -> bool:
        """Test if the configured password is valid. Returns True on success."""
        try:
            await self._authenticate()
            return True
        except JetKVMAuthError:
            return False

    async def _async_webrtc_offer_http(self, offer_sdp: str) -> str:
        """Exchange a WebRTC offer through legacy HTTP signaling."""
        url = f"{self._native_url}{WEBRTC_SESSION_PATH}"

        # Package the offer the way the JetKVM firmware expects
        offer_obj = {"type": "offer", "sdp": offer_sdp}
        sd_b64 = base64.b64encode(json.dumps(offer_obj).encode()).decode()
        payload = {"sd": sd_b64}

        last_err: Exception | None = None

        for attempt in range(1, 4):
            # (Re-)authenticate before each attempt if needed
            await self._ensure_authenticated()
            session = await self._get_native_session()

            _LOGGER.debug(
                "JetKVM WebRTC session: POST %s (attempt %d)", url, attempt
            )
            try:
                async with session.post(
                    url,
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 401:
                        _LOGGER.debug(
                            "JetKVM WebRTC session: 401 on attempt %d, will re-authenticate",
                            attempt,
                        )
                        self._authenticated = False
                        last_err = JetKVMAuthError(
                            f"HTTP 401 from {url} on attempt {attempt}"
                        )
                        continue

                    if resp.status != 200:
                        body = await resp.text()
                        raise JetKVMError(
                            f"WebRTC session failed: HTTP {resp.status}: {body[:200]}"
                        )

                    data = await resp.json(content_type=None)
                    _LOGGER.debug("JetKVM WebRTC session: response data keys: %s", list(data.keys()))

                    answer_b64 = data.get("sd", "")
                    if not answer_b64:
                        raise JetKVMError(
                            f"WebRTC session returned empty SDP answer: {data}"
                        )

                    # Decode the answer
                    answer_json = base64.b64decode(answer_b64).decode()
                    answer_obj = json.loads(answer_json)
                    answer_sdp = answer_obj.get("sdp", "")
                    if not answer_sdp:
                        raise JetKVMError(f"WebRTC answer has no SDP: {answer_obj}")

                    _LOGGER.debug(
                        "JetKVM WebRTC session: got SDP answer (%d bytes)", len(answer_sdp)
                    )
                    return answer_sdp

            except (JetKVMError, JetKVMAuthError):
                raise
            except (aiohttp.ClientConnectorError, aiohttp.ClientError, TimeoutError, OSError) as err:
                _LOGGER.debug(
                    "JetKVM WebRTC session: connection error on attempt %d: %s",
                    attempt, err,
                )
                last_err = err
                self._authenticated = False
                if attempt < 3:
                    await asyncio.sleep(1)
                    continue
                raise JetKVMConnectionError(
                    f"Cannot connect to JetKVM native API at {url}: {err}"
                ) from err

        raise JetKVMAuthError(
            f"Failed to authenticate for WebRTC session after 3 attempts. "
            f"Last error: {last_err}"
        )

    async def _async_webrtc_offer_ws(
        self,
        offer_sdp: str,
        session_id: str | None,
        on_remote_candidate: RemoteCandidateCallback | None = None,
    ) -> str:
        """Exchange a WebRTC offer through new WebSocket signaling."""
        await self._ensure_authenticated()
        session = await self._get_native_session()
        ws_url = self._native_ws_url()

        _LOGGER.debug("JetKVM WebRTC signaling: connecting to %s", ws_url)
        try:
            ws = await session.ws_connect(ws_url, timeout=10)
        except (aiohttp.ClientConnectorError, aiohttp.ClientError, TimeoutError, OSError) as err:
            raise JetKVMConnectionError(
                f"Cannot connect to JetKVM signaling WebSocket at {ws_url}: {err}"
            ) from err

        keep_open = False
        try:
            offer_obj = {"type": "offer", "sdp": offer_sdp}
            offer_b64 = base64.b64encode(json.dumps(offer_obj).encode()).decode()
            await ws.send_json({"type": "offer", "data": {"sd": offer_b64}})

            for _ in range(50):
                msg = await ws.receive(timeout=10)
                if msg.type == aiohttp.WSMsgType.TEXT:
                    if msg.data == "pong":
                        continue
                    payload = json.loads(msg.data)
                    msg_type = payload.get("type")

                    if msg_type != "answer":
                        continue

                    answer_b64 = payload.get("data", "")
                    answer_json = base64.b64decode(answer_b64).decode()
                    answer_obj = json.loads(answer_json)
                    answer_sdp = answer_obj.get("sdp", "")
                    if not answer_sdp:
                        raise JetKVMError(f"WebRTC answer has no SDP: {answer_obj}")

                    if session_id:
                        reader_task = asyncio.create_task(
                            self._async_ws_reader(session_id),
                            name=f"jetkvm-webrtc-{session_id}",
                        )
                        self._webrtc_ws_sessions[session_id] = _WebRTCWSSession(
                            ws=ws,
                            reader_task=reader_task,
                            on_remote_candidate=on_remote_candidate,
                        )
                        keep_open = True

                    _LOGGER.debug(
                        "JetKVM WebRTC signaling: got SDP answer via WS (%d bytes)",
                        len(answer_sdp),
                    )
                    return answer_sdp

                if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE):
                    break
                if msg.type == aiohttp.WSMsgType.ERROR:
                    break

            raise JetKVMError("WebRTC signaling did not return an SDP answer")
        finally:
            if not keep_open:
                with contextlib.suppress(Exception):
                    await ws.close()

    async def _async_ws_reader(self, session_id: str) -> None:
        """Read signaling events after answer and forward remote ICE candidates."""
        ws_session = self._webrtc_ws_sessions.get(session_id)
        if ws_session is None:
            return

        ws = ws_session.ws
        callback = ws_session.on_remote_candidate

        try:
            while not ws.closed:
                msg = await ws.receive()
                if msg.type != aiohttp.WSMsgType.TEXT:
                    if msg.type in (aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.CLOSE):
                        break
                    if msg.type == aiohttp.WSMsgType.ERROR:
                        break
                    continue

                if msg.data == "pong":
                    continue

                payload = json.loads(msg.data)
                if payload.get("type") != "new-ice-candidate":
                    continue

                candidate = payload.get("data")
                if not isinstance(candidate, dict) or callback is None:
                    continue

                maybe_awaitable = callback(candidate)
                if maybe_awaitable is not None:
                    await maybe_awaitable
        except Exception as err:
            _LOGGER.debug("JetKVM WebRTC signaling reader stopped (%s): %s", session_id, err)

    async def async_webrtc_offer(
        self,
        offer_sdp: str,
        session_id: str | None = None,
        on_remote_candidate: RemoteCandidateCallback | None = None,
    ) -> str:
        """Exchange a WebRTC SDP offer for an SDP answer.

        The JetKVM native API expects:
            POST /webrtc/session
            Body: {"sd": base64(JSON({"type":"offer","sdp":"..."}))}

        Returns the SDP answer string.
        """
        try:
            return await self._async_webrtc_offer_ws(
                offer_sdp,
                session_id=session_id,
                on_remote_candidate=on_remote_candidate,
            )
        except JetKVMError as err:
            _LOGGER.debug(
                "JetKVM WebRTC session: WS signaling failed (%s), trying legacy HTTP signaling",
                err,
            )
            return await self._async_webrtc_offer_http(offer_sdp)

    @staticmethod
    def _candidate_to_dict(candidate: Any) -> dict[str, Any]:
        """Normalize an ICE candidate object to a plain dict."""
        if isinstance(candidate, dict):
            return candidate

        payload: dict[str, Any] = {}
        for key in ("candidate", "sdpMid", "sdpMLineIndex", "usernameFragment"):
            value = getattr(candidate, key, None)
            if value is not None:
                payload[key] = value

        if payload:
            return payload

        return {"candidate": str(candidate)}

    async def async_webrtc_candidate(self, session_id: str, candidate: Any) -> None:
        """Send an ICE candidate over WebSocket signaling when available."""
        ws_session = self._webrtc_ws_sessions.get(session_id)
        if ws_session is None or ws_session.ws.closed:
            return

        try:
            payload = self._candidate_to_dict(candidate)
            await ws_session.ws.send_json({"type": "new-ice-candidate", "data": payload})
        except Exception as err:
            _LOGGER.debug("JetKVM WebRTC signaling: failed to send candidate: %s", err)

    async def async_close_webrtc_session(self, session_id: str) -> None:
        """Close an active WebRTC signaling session if one exists."""
        ws_session = self._webrtc_ws_sessions.pop(session_id, None)
        if ws_session is None:
            return
        if ws_session.reader_task is not None:
            ws_session.reader_task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await ws_session.reader_task
        with contextlib.suppress(Exception):
            await ws_session.ws.close()
