"""Config flow for JetKVM integration."""
import voluptuous as vol
from homeassistant import config_entries
import logging

from .const import DOMAIN
from .client import JetKVMClient, JetKVMConnectionError

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
    }
)


class JetKVMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JetKVM."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input["host"]
            _LOGGER.debug("JetKVM setup: attempting connection to %s", host)

            client = JetKVMClient(host=host)
            try:
                device_info = await client.validate_connection()
                _LOGGER.debug("JetKVM setup: connection successful, device_info=%s", device_info)
                await client.close()

                # Use hostname or ip as unique ID
                unique_id = device_info.get("hostname", host)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                title = f"JetKVM ({host})"
                return self.async_create_entry(title=title, data=user_input)

            except JetKVMConnectionError as err:
                _LOGGER.error("JetKVM setup: connection failed: %s", err)
                errors["base"] = "cannot_connect"
            except Exception as err:
                _LOGGER.exception("JetKVM setup: unexpected error: %s", err)
                errors["base"] = "unknown"
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

