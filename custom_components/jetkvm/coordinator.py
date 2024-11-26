import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class JetKVMCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, client) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.client = client

    async def _async_update_data(self):
        try:
            self.data = {}
            return self.data

        except Exception as e:
            _LOGGER.error(e)
            self.data = None
            return self.data
