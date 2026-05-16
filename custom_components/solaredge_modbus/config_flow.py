"""Config flow for solaredge modbus integration."""

import ipaddress
import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant, callback

from .const import (
    CONF_MAX_EXPORT_CONTROL_SITE_LIMIT,
    CONF_MODBUS_ADDRESS,
    CONF_POWER_CONTROL,
    CONF_READ_BATTERY1,
    CONF_READ_BATTERY2,
    CONF_READ_BATTERY3,
    CONF_READ_METER1,
    CONF_READ_METER2,
    CONF_READ_METER3,
    DEFAULT_MAX_EXPORT_CONTROL_SITE_LIMIT,
    DEFAULT_MODBUS_ADDRESS,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_POWER_CONTROL,
    DEFAULT_READ_BATTERY1,
    DEFAULT_READ_BATTERY2,
    DEFAULT_READ_BATTERY3,
    DEFAULT_READ_METER1,
    DEFAULT_READ_METER2,
    DEFAULT_READ_METER3,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

DATA_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): str,
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Optional(CONF_MODBUS_ADDRESS, default=DEFAULT_MODBUS_ADDRESS): int,
        vol.Optional(CONF_POWER_CONTROL, default=DEFAULT_POWER_CONTROL): bool,
        vol.Optional(CONF_READ_METER1, default=DEFAULT_READ_METER1): bool,
        vol.Optional(CONF_READ_METER2, default=DEFAULT_READ_METER2): bool,
        vol.Optional(CONF_READ_METER3, default=DEFAULT_READ_METER3): bool,
        vol.Optional(CONF_READ_BATTERY1, default=DEFAULT_READ_BATTERY1): bool,
        vol.Optional(CONF_READ_BATTERY2, default=DEFAULT_READ_BATTERY2): bool,
        vol.Optional(CONF_READ_BATTERY3, default=DEFAULT_READ_BATTERY3): bool,
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): int,
        vol.Optional(
            CONF_MAX_EXPORT_CONTROL_SITE_LIMIT,
            default=DEFAULT_MAX_EXPORT_CONTROL_SITE_LIMIT,
        ): int,
    }
)


def host_valid(host):
    """Return True if hostname or IP address is valid."""
    try:
        if ipaddress.ip_address(host).version == (4 or 6):
            return True
    except ValueError:
        disallowed = re.compile(r"[^a-zA-Z\d\-]")
        return all(x and not disallowed.search(x) for x in host.split("."))


@callback
def solaredge_modbus_entries(hass: HomeAssistant):
    """Return the hosts already configured."""
    return {
        entry.data[CONF_HOST] for entry in hass.config_entries.async_entries(DOMAIN)
    }


class SolaredgeModbusConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Solaredge Modbus configflow."""

    VERSION = 2
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def _host_in_configuration_exists(self, host) -> bool:
        """Return True if host exists in configuration."""
        if host in solaredge_modbus_entries(self.hass):
            return True
        return False

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            if self._host_in_configuration_exists(host):
                errors[CONF_HOST] = "already_configured"
            elif not host_valid(user_input[CONF_HOST]):
                errors[CONF_HOST] = "invalid host IP"
            else:
                await self.async_set_unique_id(user_input[CONF_HOST])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=DATA_SCHEMA, errors=errors
        )

    async def async_step_reconfigure(self, user_input=None):
        """Handle reconfiguration of an existing entry.

        Allows the user to change host, port, meter/battery settings,
        scan interval and all other options without removing and
        re-adding the integration.
        """
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        current = entry.data

        errors = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            # Allow same host (current entry) — only block a *different* host
            # that is already used by another entry
            other_hosts = {
                e.data[CONF_HOST]
                for e in self.hass.config_entries.async_entries(DOMAIN)
                if e.entry_id != entry.entry_id
            }
            if host in other_hosts:
                errors[CONF_HOST] = "already_configured"
            elif not host_valid(host):
                errors[CONF_HOST] = "invalid host IP"
            else:
                return self.async_update_reload_and_abort(
                    entry,
                    data=user_input,
                    reason="reconfigure_successful",
                )

        # Pre-fill the form with the current configuration
        reconfigure_schema = vol.Schema(
            {
                vol.Optional(CONF_NAME, default=current.get(CONF_NAME, DEFAULT_NAME)): str,
                vol.Required(CONF_HOST, default=current.get(CONF_HOST, "")): str,
                vol.Required(CONF_PORT, default=current.get(CONF_PORT, DEFAULT_PORT)): int,
                vol.Optional(CONF_MODBUS_ADDRESS, default=current.get(CONF_MODBUS_ADDRESS, DEFAULT_MODBUS_ADDRESS)): int,
                vol.Optional(CONF_POWER_CONTROL, default=current.get(CONF_POWER_CONTROL, DEFAULT_POWER_CONTROL)): bool,
                vol.Optional(CONF_READ_METER1, default=current.get(CONF_READ_METER1, DEFAULT_READ_METER1)): bool,
                vol.Optional(CONF_READ_METER2, default=current.get(CONF_READ_METER2, DEFAULT_READ_METER2)): bool,
                vol.Optional(CONF_READ_METER3, default=current.get(CONF_READ_METER3, DEFAULT_READ_METER3)): bool,
                vol.Optional(CONF_READ_BATTERY1, default=current.get(CONF_READ_BATTERY1, DEFAULT_READ_BATTERY1)): bool,
                vol.Optional(CONF_READ_BATTERY2, default=current.get(CONF_READ_BATTERY2, DEFAULT_READ_BATTERY2)): bool,
                vol.Optional(CONF_READ_BATTERY3, default=current.get(CONF_READ_BATTERY3, DEFAULT_READ_BATTERY3)): bool,
                vol.Optional(CONF_SCAN_INTERVAL, default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)): int,
                vol.Optional(
                    CONF_MAX_EXPORT_CONTROL_SITE_LIMIT,
                    default=current.get(CONF_MAX_EXPORT_CONTROL_SITE_LIMIT, DEFAULT_MAX_EXPORT_CONTROL_SITE_LIMIT),
                ): int,
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=reconfigure_schema,
            errors=errors,
        )
