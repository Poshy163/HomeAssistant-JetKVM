"""Sensor platform for JetKVM integration."""
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .enum import SENSOR_DESCRIPTIONS, JetKVMSensorDescription
from .coordinator import JetKVMCoordinator

import logging

_LOGGER: logging.Logger = logging.getLogger(__package__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up JetKVM sensors from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator: JetKVMCoordinator = data["coordinator"]

    sensors = []
    for sensor_desc in SENSOR_DESCRIPTIONS:
        sensors.append(JetKVMSensor(sensor_desc, entry, coordinator))

    async_add_entities(sensors, True)


class JetKVMSensor(CoordinatorEntity, Entity):
    """Representation of a JetKVM sensor."""

    def __init__(
        self,
        description: JetKVMSensorDescription,
        entry,
        coordinator: JetKVMCoordinator,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._coordinator = coordinator
        self._entry = entry
        self._description = description
        self._key = description.key
        self._attr_name = description.name
        self._attr_icon = description.icon
        self._attr_device_class = description.device_class
        self._attr_state_class = description.state_class
        self._attr_native_unit_of_measurement = description.native_unit_of_measurement
        self._attr_suggested_display_precision = description.suggested_display_precision
        self._attr_entity_category = description.entity_category
        self._attr_unique_id = f"{entry.entry_id}_{description.entity_name}"
        self._state = None

    @callback
    def _handle_coordinator_update(self):
        """Handle updated data from the coordinator."""
        try:
            if self._coordinator.data is not None:
                self._state = self._coordinator.data.get(self._key)
            else:
                self._state = None
        except (KeyError, IndexError) as err:
            _LOGGER.error(
                "Error accessing data for key '%s': %s. Defaulting to None",
                self._key,
                err,
            )
            self._state = None
        self.async_write_ha_state()

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this JetKVM device."""
        device_data = self._coordinator.device_info or {}
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=f"JetKVM ({self._entry.data.get('host', 'Unknown')})",
            manufacturer="JetKVM",
            model=device_data.get("deviceModel", "JetKVM"),
            sw_version=device_data.get("firmwareVersion"),
            hw_version=device_data.get("hardwareVersion"),
            serial_number=device_data.get("serialNumber"),
        )

