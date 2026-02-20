"""Config flow for JetKVM integration."""
import voluptuous as vol
from homeassistant import config_entries
import logging

from .const import DOMAIN
from .client import JetKVMClient, JetKVMConnectionError, JetKVMAuthError

_LOGGER = logging.getLogger(__name__)

DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Optional("password", default=""): str,
    }
)


def _options_schema(current_password: str) -> vol.Schema:
    """Build the options form schema."""
    return vol.Schema(
        {
            vol.Optional("password", default=current_password): str,
        }
    )


class JetKVMConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for JetKVM."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Create the options flow."""
        return JetKVMOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input["host"]
            password = user_input.get("password", "")
            _LOGGER.debug("JetKVM setup: attempting connection to %s", host)

            client = JetKVMClient(host=host, password=password)
            try:
                device_info = await client.validate_connection()
                _LOGGER.debug("JetKVM setup: connection successful, device_info=%s", device_info)

                # Validate password against native API if provided
                if password:
                    pw_ok = await client.async_check_password()
                    if not pw_ok:
                        _LOGGER.warning("JetKVM setup: password is invalid, video stream will be disabled")
                        errors["base"] = "invalid_auth"
                        await client.close()
                        return self.async_show_form(
                            step_id="user", data_schema=DATA_SCHEMA, errors=errors
                        )
                    _LOGGER.debug("JetKVM setup: password validated for video stream")

                await client.close()

                # Use serial number as unique ID, fall back to hostname
                unique_id = device_info.get("serial_number") or device_info.get("hostname", host)
                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured()

                # Store device metadata alongside host for device registry
                entry_data = {
                    **user_input,
                    "serial_number": device_info.get("serial_number", ""),
                    "mac_address": device_info.get("mac_address", ""),
                    "model": device_info.get("deviceModel", "JetKVM"),
                    "hostname": device_info.get("hostname", ""),
                    "kernel_version": device_info.get("kernel_version", ""),
                    "kernel_build": device_info.get("kernel_build", ""),
                }

                title = device_info.get("hostname") or host
                return self.async_create_entry(title=title, data=entry_data)

            except JetKVMConnectionError as err:
                _LOGGER.error("JetKVM setup: connection failed: %s", err)
                errors["base"] = "cannot_connect"
            except JetKVMAuthError as err:
                _LOGGER.warning("JetKVM setup: authentication failed: %s", err)
                errors["base"] = "invalid_auth"
            except Exception as err:
                _LOGGER.exception("JetKVM setup: unexpected error: %s", err)
                errors["base"] = "unknown"
            finally:
                await client.close()

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )


class JetKVMOptionsFlow(config_entries.OptionsFlow):
    """Handle JetKVM options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize JetKVM options flow."""
        self._entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage JetKVM options."""
        errors = {}

        current_password = self._entry.options.get(
            "password", self._entry.data.get("password", "")
        )

        if user_input is not None:
            password = user_input.get("password", "")
            host = self._entry.data["host"]
            client = JetKVMClient(host=host, password=password)

            try:
                if password:
                    pw_ok = await client.async_check_password()
                    if not pw_ok:
                        _LOGGER.warning(
                            "JetKVM options: password rejected for %s", host
                        )
                        errors["base"] = "invalid_auth"
                    else:
                        _LOGGER.debug("JetKVM options: password validated for %s", host)

                if not errors:
                    return self.async_create_entry(title="", data={"password": password})

            except JetKVMConnectionError as err:
                _LOGGER.error("JetKVM options: connection failed: %s", err)
                errors["base"] = "cannot_connect"
            except JetKVMAuthError as err:
                _LOGGER.warning("JetKVM options: authentication failed: %s", err)
                errors["base"] = "invalid_auth"
            except Exception as err:
                _LOGGER.exception("JetKVM options: unexpected error: %s", err)
                errors["base"] = "unknown"
            finally:
                await client.close()

            current_password = password

        return self.async_show_form(
            step_id="init",
            data_schema=_options_schema(current_password),
            errors=errors,
        )

