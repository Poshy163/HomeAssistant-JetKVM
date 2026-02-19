"""API client for JetKVM devices.

Communicates with the lightweight BusyBox httpd server installed on the
JetKVM via api-setup.sh.  The server runs on port 8800 and exposes:

    GET /cgi-bin/health       -> {"status": "ok"}
    GET /cgi-bin/temperature  -> {"temperature": 45.2}
    GET /cgi-bin/device_info  -> {"deviceModel": "JetKVM", "hostname": "...", ...}
"""
import logging

import aiohttp

_LOGGER = logging.getLogger(__name__)

DEFAULT_PORT = 8800
HEALTH_PATH = "/cgi-bin/health"
TEMPERATURE_PATH = "/cgi-bin/temperature"
DEVICE_INFO_PATH = "/cgi-bin/device_info"


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
        """HTTP GET and parse JSON response."""
        session = await self._get_session()
        url = f"{self._base_url}{path}"
        try:
            async with session.get(
                url, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status != 200:
                    raise JetKVMError(
                        f"HTTP {resp.status} from {url}"
                    )
                return await resp.json(content_type=None)
        except aiohttp.ClientConnectorError as err:
            raise JetKVMConnectionError(
                f"Cannot connect to JetKVM API at {url} – "
                f"have you run api-setup.sh on the device? ({err})"
            ) from err
        except aiohttp.ClientError as err:
            raise JetKVMConnectionError(
                f"Communication error with JetKVM at {url}: {err}"
            ) from err
        except TimeoutError as err:
            raise JetKVMConnectionError(
                f"Timeout connecting to JetKVM at {url}"
            ) from err

    # -- public API ----------------------------------------------------------

    async def check_health(self) -> bool:
        """Return True if the API server is reachable."""
        data = await self._get_json(HEALTH_PATH)
        return data.get("status") == "ok"

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
        """Validate connectivity.  Returns device_info on success."""
        await self.check_health()
        return await self.get_device_info()

