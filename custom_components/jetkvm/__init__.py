"""The JetKVM integration."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import PLATFORMS, DOMAIN
from .client import JetKVMClient
from .coordinator import JetKVMCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up JetKVM from a config entry."""
    host = entry.data["host"]

    client = JetKVMClient(host=host)
    coordinator = JetKVMCoordinator(hass, client=client)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "coordinator": coordinator,
        "client": client,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a JetKVM config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        client: JetKVMClient = data["client"]
        await client.close()

    return unload_ok

