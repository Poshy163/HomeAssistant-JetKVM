"""The JetKVM integration."""
import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers import device_registry as dr

from .const import PLATFORMS, DOMAIN
from .client import JetKVMClient
from .coordinator import JetKVMCoordinator

_LOGGER = logging.getLogger(__name__)


def _build_device_info(entry: ConfigEntry, live_data: dict | None = None) -> dict:
    """Build device registry kwargs from config entry data + optional live data."""
    data = entry.data
    live = live_data or {}

    serial = live.get("serial_number") or data.get("serial_number", "")
    mac = live.get("mac_address") or data.get("mac_address", "")
    hostname = live.get("hostname") or data.get("hostname", "")
    model = live.get("deviceModel") or data.get("model", "JetKVM")
    host = data.get("host", "")

    # Build sw_version from kernel info
    kernel_version = live.get("kernel_version") or data.get("kernel_version", "")
    kernel_build = live.get("kernel_build") or data.get("kernel_build", "")
    sw_version = kernel_version
    if sw_version and kernel_build:
        sw_version = f"{sw_version} ({kernel_build})"

    # Identifiers — prefer serial, fall back to entry_id
    identifiers = set()
    if serial:
        identifiers.add((DOMAIN, serial))
    else:
        identifiers.add((DOMAIN, entry.entry_id))

    # Connections — MAC address
    connections = set()
    if mac:
        connections.add((dr.CONNECTION_NETWORK_MAC, mac))

    info: dict = {
        "identifiers": identifiers,
        "connections": connections,
        "name": f"JetKVM ({hostname or host})",
        "manufacturer": "JetKVM",
        "model": model,
        "configuration_url": f"http://{host}",
    }
    if serial:
        info["serial_number"] = serial
    if sw_version:
        info["sw_version"] = sw_version

    return info


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

    # Register / update device in the device registry
    device_reg = dr.async_get(hass)
    device_info = _build_device_info(entry, coordinator.device_info)
    device_reg.async_get_or_create(config_entry_id=entry.entry_id, **device_info)

    # Update device info whenever coordinator refreshes (firmware, api_version, etc.)
    async def _update_device_on_refresh() -> None:
        """Update device registry with latest data from the coordinator."""
        live = coordinator.device_info or {}
        if not live:
            return
        updated = _build_device_info(entry, live)
        device_reg.async_get_or_create(config_entry_id=entry.entry_id, **updated)

    entry.async_on_unload(
        coordinator.async_add_listener(_update_device_on_refresh)
    )

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

