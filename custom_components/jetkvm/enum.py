"""Sensor descriptions for JetKVM integration."""
from dataclasses import dataclass
from typing import List

from homeassistant.components.sensor import (
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature


@dataclass(frozen=True, kw_only=True)
class JetKVMSensorDescription(SensorEntityDescription):
    """Describes a JetKVM sensor."""


SENSOR_DESCRIPTIONS: List[JetKVMSensorDescription] = [
    JetKVMSensorDescription(
        key="temperature",
        translation_key="soc_temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JetKVMSensorDescription(
        key="last_boot",
        translation_key="last_boot",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


