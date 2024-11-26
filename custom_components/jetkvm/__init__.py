import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import PLATFORMS
from JetKVM.JetKVM import JetKVM

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    portfolio_id = entry.data["Address"]

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True




