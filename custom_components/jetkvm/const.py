from datetime import timedelta
from homeassistant.const import Platform

SCAN_INTERVAL = timedelta(seconds=60)
PLATFORMS = [Platform.SENSOR, Platform.CAMERA]
DOMAIN = "jetkvm"
