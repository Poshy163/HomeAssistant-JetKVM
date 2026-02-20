"""Sensor platform for JetKVM integration."""
import logging
from datetime import datetime

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
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
    def native_value(self) -> float | datetime | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this JetKVM device."""
        device_data = self.coordinator.device_info or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"JetKVM ({self._entry.data.get('host', 'Unknown')})",
            manufacturer="JetKVM",
            model=device_data.get("deviceModel", "JetKVM"),
            sw_version=device_data.get("firmwareVersion"),
            hw_version=device_data.get("hardwareVersion"),
            serial_number=device_data.get("serialNumber"),
        )

