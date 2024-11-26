from datetime import timedelta
from homeassistant.const import Platform

SCAN_INTERVAL = timedelta(minutes=5)
PLATFORMS = [Platform.SENSOR]
DOMAIN = "jetkvm"
