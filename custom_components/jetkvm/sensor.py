from homeassistant.const import CURRENCY_DOLLAR
from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity import Entity
from .const import DOMAIN
import logging
from .enum import SENSOR_DESCRIPTIONS
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .coordinator import JetKVMCoordinator
from homeassistant.helpers.event import async_track_time_interval

_LOGGER: logging.Logger = logging.getLogger(__package__)

MARKET_SENSORS = []
CASH_SENSORS = []


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]

    coordinator: JetKVMCoordinator = data["coordinator"]

    sensors = []

    for sensor in SENSOR_DESCRIPTIONS:
        sensors.append(SharesightSensor(sensor, entry, coordinator))

    async_add_entities(sensors, True)


class SharesightSensor(CoordinatorEntity, Entity):
    def __init__(self, sensor, entry, coordinator):
        super().__init__(coordinator)
        self._state_class = sensor.state_class
        self._coordinator = coordinator
        self._entity_category = sensor.entity_category
        self._name = str(sensor.name)
        self._extension_key = sensor.extension_key
        self._suggested_display_precision = sensor.suggested_display_precision
        self._key = sensor.key
        self._icon = sensor.icon
        self._entry = entry
        self._device_class = sensor.device_class
        self._sub_key = sensor.sub_key
        self._unique_id = sensor.entity_name

    @callback
    def _handle_coordinator_update(self):
        try:
            self._state = self._coordinator.data[self._key]

        except (KeyError, IndexError) as e:
            _LOGGER.error(f"Error accessing data for key '{self._key}': {e}: Defaulting to None")
            self._state = None
        self.async_write_ha_state()

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return self._icon

    @property
    def entity_category(self):
        return self._entity_category

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def unit_of_measurement(self):
        return self._native_unit_of_measurement

    @property
    def suggested_display_precision(self):
        return self._suggested_display_precision

    @property
    def state_class(self):
        return self._state_class

    @property
    def device_class(self):
        return self._device_class
