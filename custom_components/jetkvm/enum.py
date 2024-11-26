from dataclasses import dataclass
from typing import Callable, List, Union
from homeassistant.components.sensor import SensorEntityDescription, SensorDeviceClass, SensorStateClass


@dataclass
class JetKVMSensorDescription(SensorEntityDescription):
    sub_key: str = None
    extension_key: str = None
    native_value: Union[Callable[[Union[str, int, float]], Union[str, int, float]], None] = None


SENSOR_DESCRIPTIONS: List[JetKVMSensorDescription] = [
    JetKVMSensorDescription(
        name="IP Address",
        key="IP_Address",
        entity_name="local_ip_address",
        icon="mdi:ip"
    )
]
