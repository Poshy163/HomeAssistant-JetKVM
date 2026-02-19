"""Sensor descriptions for JetKVM integration."""
from dataclasses import dataclass
from typing import Callable, List, Union

from homeassistant.components.sensor import (
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature


@dataclass
class JetKVMSensorDescription(SensorEntityDescription):
    """Describes a JetKVM sensor."""
    sub_key: str = None
    extension_key: str = None
    native_value: Union[Callable[[Union[str, int, float]], Union[str, int, float]], None] = None


SENSOR_DESCRIPTIONS: List[JetKVMSensorDescription] = [
    JetKVMSensorDescription(
        name="SoC Temperature",
        key="temperature",
        entity_name="soc_temperature",
        icon="mdi:thermometer",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
    ),
]


