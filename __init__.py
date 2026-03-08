"""The Ademco RS232 Alarm Panel integration."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ID, CONF_NAME
from homeassistant.core import HomeAssistant
import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_BAUD,
    CONF_DEVICE,
    CONF_DOORS,
    CONF_GARAGE_DOORS,
    CONF_MOTIONS,
    CONF_PROBLEMS,
    CONF_WINDOWS,
    DEFAULT_NAME,
    DOMAIN,
    PLATFORMS,
)

import logging

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .ademco import AlarmPanel


ZONE_CONFIG = vol.Schema(
    {
        vol.Required(CONF_ID): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Optional("latchSeconds", default=0): cv.string,
    }
)
OUTPUT_CONFIG = vol.Schema(
    {
        vol.Required(CONF_ID): cv.string,
        vol.Required(CONF_NAME): cv.string,
        vol.Required("output"): cv.string,
    }
)
CONFIG_SCHEMA = vol.Schema(
    {
        vol.Required(DOMAIN): {
            vol.Optional(CONF_DEVICE): cv.string,
            vol.Required(CONF_BAUD, default=1200): cv.string,
            vol.Optional(CONF_MOTIONS): vol.All(cv.ensure_list, [ZONE_CONFIG]),
            vol.Optional(CONF_DOORS): vol.All(cv.ensure_list, [ZONE_CONFIG]),
            vol.Optional(CONF_WINDOWS): vol.All(cv.ensure_list, [ZONE_CONFIG]),
            vol.Optional(CONF_PROBLEMS): vol.All(cv.ensure_list, [ZONE_CONFIG]),
            vol.Optional(CONF_GARAGE_DOORS): vol.All(cv.ensure_list, [OUTPUT_CONFIG]),
        }
    },
    extra=vol.ALLOW_EXTRA,
)


@dataclass
class AdemcoRuntimeData:
    """Runtime data stored on the config entry."""

    panel: "AlarmPanel"
    config: dict
    device_id: str
    device_name: str


type AdemcoConfigEntry = ConfigEntry[AdemcoRuntimeData]


async def async_setup(hass: HomeAssistant, config) -> bool:
    """Set up the integration and import YAML if present."""
    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": "import"},
                data=config[DOMAIN],
            )
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AdemcoConfigEntry) -> bool:
    """Set up Ademco from a config entry."""
    from .ademco import AlarmPanel

    config = dict(entry.data)
    panel = AlarmPanel(config, loop=hass.loop)
    await panel.async_start()

    device_id = config.get(CONF_DEVICE) or entry.entry_id
    device_name = entry.title or DEFAULT_NAME

    entry.runtime_data = AdemcoRuntimeData(
        panel=panel,
        config=config,
        device_id=device_id,
        device_name=device_name,
    )

    log.debug(
        "Configured Ademco panel on %s with %s motion, %s door, %s window, %s garage door, %s problem zones",
        config.get(CONF_DEVICE),
        len(config.get(CONF_MOTIONS, [])),
        len(config.get(CONF_DOORS, [])),
        len(config.get(CONF_WINDOWS, [])),
        len(config.get(CONF_GARAGE_DOORS, [])),
        len(config.get(CONF_PROBLEMS, [])),
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AdemcoConfigEntry) -> bool:
    """Unload an Ademco config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.panel.async_stop()
    return unload_ok
