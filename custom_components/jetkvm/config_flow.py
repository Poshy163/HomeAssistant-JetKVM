import voluptuous as vol
from homeassistant import config_entries
import logging
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SharesightConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        data_schema = vol.Schema({
            vol.Required("Address"): str,
        })

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)
