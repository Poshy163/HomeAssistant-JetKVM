"""Sensor platform for JetKVM integration."""
import logging
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import (
    CONNECTION_NETWORK_MAC,
    DeviceInfo,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import JetKVMCoordinator
from .enum import SENSOR_DESCRIPTIONS, JetKVMSensorDescription

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up JetKVM sensors from a config entry."""
    coordinator: JetKVMCoordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        JetKVMSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class JetKVMSensor(CoordinatorEntity[JetKVMCoordinator], SensorEntity):
    """Representation of a JetKVM sensor."""

    _attr_has_entity_name = True
    entity_description: JetKVMSensorDescription

    def __init__(
        self,
        coordinator: JetKVMCoordinator,
        entry: ConfigEntry,
        description: JetKVMSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._entry = entry

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | str | datetime | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this JetKVM device."""
        device_data = self.coordinator.device_info or {}
        serial = device_data.get("serial_number", "")
        mac = device_data.get("mac_address", "")

        # Build identifier set — prefer serial, fall back to entry_id
        identifiers = set()
        if serial:
            identifiers.add((DOMAIN, serial))
        else:
            identifiers.add((DOMAIN, self._entry.entry_id))

        # Build connections set for MAC address
        connections = set()
        if mac:
            connections.add((CONNECTION_NETWORK_MAC, mac))

        # Kernel version as firmware version
        sw_version = device_data.get("kernel_version")
        kernel_build = device_data.get("kernel_build")
        if sw_version and kernel_build:
            sw_version = f"{sw_version} ({kernel_build})"

        return DeviceInfo(
            identifiers=identifiers,
            connections=connections,
            name=f"JetKVM ({device_data.get('hostname', self._entry.data.get('host', 'Unknown'))})",
            manufacturer="JetKVM",
            model=device_data.get("deviceModel", "JetKVM"),
            serial_number=serial or None,
            sw_version=sw_version,
            configuration_url=f"http://{self._entry.data.get('host', '')}",
        )

