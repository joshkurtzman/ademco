"""Config flow for Ademco RS232 Alarm Panel integration."""
from __future__ import annotations
from ademco.ademco import AlarmPanel

import logging
from typing import Any
#from typing_extensions import Required

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

import serial_async

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# # TODO adjust the data schema to the data that you need
# STEP_PANEL_DATA_SCHEMA = vol.Schema(
#     {
#         vol.Required("USB_DEVICE"): str,
#         vol.Required("BAUD",default="1200"): int,
#     }
# )

# STEP_ZONE_DATA_SCHEMA = vol.Schema(
#     {
#         vol.Required("ZONE_ID"):int,
#         vol.Required("ZONE_NAME"):str,
#         vol.Required("ZONE_TYPE"):str

#     }
# )

class PlaceholderHub:
    """Placeholder class to make tests pass.

    TODO Remove this placeholder class and replace with things from your PyPI package.
    """

    def __init__(self, host: str) -> None:
        """Initialize."""
        self.host = host

    async def authenticate(self, username: str, password: str) -> bool:
        """Test if we can authenticate with the host."""
        return True


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """
    # TODO validate the data can be used to set up a connection.

    # If your PyPI package is not built with async, pass your methods
    # to the executor:
    # await hass.async_add_executor_job(
    #     your_validate_func, data["username"], data["password"]
    # )
    from serial import SerialException
    try:
        panel = AlarmPanel(data)
    except SerialException:
        raise CannotConnect

    # If you cannot connect:
    # throw CannotConnect
    # If the authentication is wrong:
    # InvalidAuth
    # Return info that you want to store in the config entry.
    return {"title": "Name of the device"}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ademco RS232 Alarm Panel."""

    VERSION = 1

    async def async_step_panel(
                    self, user_input: dict[str, Any] | None = None
                    ) -> FlowResult:
        
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="panel", data_schema=STEP_PANEL_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="panel", data_schema=STEP_PANEL_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

