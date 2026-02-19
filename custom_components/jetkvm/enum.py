"""Sensor descriptions for JetKVM integration."""
from dataclasses import dataclass
from typing import List

from homeassistant.components.sensor import (
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime


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
        key="uptime_seconds",
        translation_key="uptime",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]


