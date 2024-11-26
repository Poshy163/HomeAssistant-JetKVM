import logging
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
)

from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


async def process_value(value, default=None):
    if value is None or (isinstance(value, str) and value.strip() == ''):
        return default
    return value


async def safe_get(dictionary, key, default=None):
    if dictionary is None:
        return default
    return await process_value(dictionary.get(key), default)


async def safe_calculate(val1, val2):
    if val1 is None or val2 is None:
        return None
    else:
        return val1 - val2


class JetKVMCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, client) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
        self.client = client

    async def _async_update_data(self):
        try:
            jsondata = await self.client.getdata()
            if jsondata is not None:
                # get data from kvm list
                kvmdata = {}
                kvmdata["IP_Address"] = await process_value(jsondata.get("IPAddress"))

                self.data.update(kvmdata)
            else:
                self.data = None
                return self.data

        except Exception as e:
            _LOGGER.error(e)
            self.data = None
            return self.data
