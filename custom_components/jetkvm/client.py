"""API client for JetKVM devices.

Communicates with the nc-based HTTP server installed on the JetKVM
via api-setup.sh.  The server runs on port 8800 and exposes:

    GET /health       -> {"status": "ok"}
    GET /temperature  -> {"temperature": 45.2}
    GET /device_info  -> {"deviceModel": "JetKVM", "hostname": "...", ...}

The server is supervised by a watchdog that auto-restarts after each
request (nc is single-shot) and survives SSH disconnects via setsid.
"""
import asyncio
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8800
HEALTH_PATH = "/health"
TEMPERATURE_PATH = "/temperature"
DEVICE_INFO_PATH = "/device_info"

# nc serves one request at a time, so we need delays between retries
_REQUEST_DELAY = 1.0
_MAX_RETRIES = 3


class JetKVMError(Exception):
    """Base exception for JetKVM API errors."""


class JetKVMConnectionError(JetKVMError):
    """Cannot reach the JetKVM API server."""


class JetKVMClient:
    """Client for the JetKVM BusyBox httpd API (port 8800)."""

    def __init__(self, host: str, port: int = DEFAULT_PORT) -> None:
        self._host = host.rstrip("/")
        self._port = port
        self._base_url = f"http://{self._host}:{self._port}"
        self._session: aiohttp.ClientSession | None = None

    @property
    def host(self) -> str:
        return self._host

    # -- session management --------------------------------------------------

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

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
                        import json
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

    # -- public API ----------------------------------------------------------

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
        """Return device info dict from /cgi-bin/device_info."""
        return await self._get_json(DEVICE_INFO_PATH)

    async def get_all_data(self) -> dict:
        """Fetch all data needed by the coordinator.

        Uses /cgi-bin/device_info which already includes temperature.
        """
        return await self.get_device_info()

    async def validate_connection(self) -> dict:
        """Validate connectivity.  Returns device_info on success.

        Raises JetKVMConnectionError if the device is unreachable or
        running an outdated api-setup.sh.
        """
        data = await self.get_device_info()
        if "error" in data or "deviceModel" not in data:
            raise JetKVMConnectionError(
                f"JetKVM API at {self._base_url} returned unexpected data: {data}. "
                "Please re-run the setup script on your JetKVM device."
            )
        return data

