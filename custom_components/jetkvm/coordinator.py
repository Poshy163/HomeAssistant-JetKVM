"""DataUpdateCoordinator for JetKVM."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN, SCAN_INTERVAL
from .client import JetKVMClient, JetKVMError

_LOGGER = logging.getLogger(__name__)


class JetKVMCoordinator(DataUpdateCoordinator):
    """Coordinator to manage fetching data from JetKVM."""

    def __init__(self, hass: HomeAssistant, client: JetKVMClient) -> None:
        """Initialize the coordinator."""
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.client = client
        self.device_info: dict = {}

    async def _async_update_data(self) -> dict:
        """Fetch data from the JetKVM device."""
        try:
            data = await self.client.get_all_data()

            # Store raw response for device registry info
            self.device_info = data

            # Build the dict the sensors read from
            result = {}

            if "temperature" in data:
                result["temperature"] = data["temperature"]

            return result

        except JetKVMError as err:
            raise UpdateFailed(f"Error communicating with JetKVM: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err

