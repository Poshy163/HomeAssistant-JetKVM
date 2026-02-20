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
    def native_value(self) -> float | str | datetime | None:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.key)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info to link this entity to the device registry."""
        data = self._entry.data
        serial = data.get("serial_number", "")

        identifiers = set()
        if serial:
            identifiers.add((DOMAIN, serial))
        else:
            identifiers.add((DOMAIN, self._entry.entry_id))

        return DeviceInfo(identifiers=identifiers)

