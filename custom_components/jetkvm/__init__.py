import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .const import PLATFORMS, DOMAIN
from JetKVM.JetKVM import JetKVM

from .coordinator import JetKVMCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    portfolio_id = entry.data["connectionAddress"]

    client = JetKVM()
    local_coordinator = JetKVMCoordinator(hass, portfolio_id, client=client)
    await local_coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "jetkvm_client": client
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True




