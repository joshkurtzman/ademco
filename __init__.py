"""The Ademco RS232 Alarm Panel integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_DEVICE,
    CONF_NAME,
    DEFAULT_NAME,
    DOMAIN,
    PLATFORMS,
)

import logging

log = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .ademco import AlarmPanel


@dataclass
class AdemcoRuntimeData:
    """Runtime data stored on the config entry."""

    panel: "AlarmPanel"
    config: dict
    device_id: str
    device_name: str


type AdemcoConfigEntry = ConfigEntry[AdemcoRuntimeData]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the integration."""
    if DOMAIN in config:
        log.warning(
            "The '%s:' YAML configuration block is no longer used. "
            "Manage Ademco from Settings -> Devices & services and remove the "
            "YAML block from configuration.yaml.",
            DOMAIN,
        )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: AdemcoConfigEntry) -> bool:
    """Set up Ademco from a config entry."""
    from .ademco import AlarmPanel

    config = dict(entry.data)
    panel_name = str(config.get(CONF_NAME, "")).strip()
    if not panel_name:
        panel_name = (
            entry.title
            if entry.title and entry.title != config.get(CONF_DEVICE)
            else DEFAULT_NAME
        )
        config[CONF_NAME] = panel_name
        hass.config_entries.async_update_entry(entry, data=config, title=panel_name)
    elif entry.title != panel_name:
        hass.config_entries.async_update_entry(entry, title=panel_name)

    panel = AlarmPanel(config, loop=hass.loop)

    device_id = config.get(CONF_DEVICE) or entry.entry_id
    device_name = panel_name

    entry.runtime_data = AdemcoRuntimeData(
        panel=panel,
        config=config,
        device_id=device_id,
        device_name=device_name,
    )

    try:
        await panel.async_start()
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception:
        await panel.async_stop()
        raise

    log.debug(
        "Configured Ademco panel on %s",
        config.get(CONF_DEVICE),
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: AdemcoConfigEntry) -> bool:
    """Unload an Ademco config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await entry.runtime_data.panel.async_stop()
    return unload_ok
