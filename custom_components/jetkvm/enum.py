"""Sensor descriptions for JetKVM integration."""
from dataclasses import dataclass
from typing import List

from homeassistant.components.sensor import (
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, PERCENTAGE


@dataclass(frozen=True, kw_only=True)
class JetKVMSensorDescription(SensorEntityDescription):
    """Describes a JetKVM sensor."""


SENSOR_DESCRIPTIONS: List[JetKVMSensorDescription] = [
    # ---- Diagnostic sensors ----
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
    JetKVMSensorDescription(
        key="uptime_seconds",
        translation_key="uptime",
        icon="mdi:timer-outline",
        native_unit_of_measurement="s",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JetKVMSensorDescription(
        key="mem_used_pct",
        translation_key="memory_usage",
        icon="mdi:memory",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JetKVMSensorDescription(
        key="mem_available_kb",
        translation_key="memory_available",
        icon="mdi:memory",
        native_unit_of_measurement="kB",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JetKVMSensorDescription(
        key="disk_used_pct",
        translation_key="disk_usage",
        icon="mdi:harddisk",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JetKVMSensorDescription(
        key="disk_available_kb",
        translation_key="disk_available",
        icon="mdi:harddisk",
        native_unit_of_measurement="kB",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JetKVMSensorDescription(
        key="load_average",
        translation_key="cpu_load",
        icon="mdi:chip",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JetKVMSensorDescription(
        key="network_state",
        translation_key="network_state",
        icon="mdi:ethernet",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    JetKVMSensorDescription(
        key="api_version",
        translation_key="api_version",
        icon="mdi:package-up",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
]

