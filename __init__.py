"""The Ademco RS232 Alarm Panel integration."""
from __future__ import annotations
from homeassistant.components.http import CONFIG_SCHEMA

# from homeassistant.helpers.config_validation import PLATFORM_SCHEMA

from homeassistant.helpers.discovery import load_platform, async_load_platform
from homeassistant.helpers.entity_component import async_update_entity

# from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
import voluptuous as vol
from homeassistant.helpers import config_validation as cv, device_registry as dr



from .const import DOMAIN
import asyncio
from .ademco import AlarmPanel, Zone, Output

PLATFORMS = ["binary_sensor"]  # ,"alarm_control_panel", "switch"]
import logging

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


ZONE_CONFIG = vol.Schema(
    {vol.Required("id"): cv.string, 
     vol.Required("name"): cv.string}
)
GARAGE_CONFIG = vol.Schema(
    {
        vol.Required("id"): cv.string,
        vol.Required("name"): cv.string,
        vol.Required("output"): cv.string,
    }
)
CONFIG_SCHEMA = CONFIG_SCHEMA.extend(
    {
        vol.Required(DOMAIN): {
            vol.Optional("device"): cv.string,
            vol.Required("baud", default=1200): cv.string,
            vol.Optional("motions"): vol.All(cv.ensure_list, [ZONE_CONFIG]),
            vol.Optional("doors"): vol.All(cv.ensure_list, [ZONE_CONFIG]),
            vol.Optional("windows"): vol.All(cv.ensure_list, [ZONE_CONFIG]),
            vol.Optional("problems"): vol.All(cv.ensure_list, [ZONE_CONFIG]),
            vol.Optional("garagedoors"): vol.All(cv.ensure_list, [GARAGE_CONFIG]),
        }
    }
)


async def async_setup(hass: HomeAssistant, config):
    c = config["ademco"]
    # hass.states.async_set("ademco", "Paulus")
    # log.debug(str(config))
    panel = AlarmPanel(c, loop=hass.loop)
    hass.data[DOMAIN] = {"panel": panel, "config": c}

    log.debug("Zones" + str(panel.zones))
    log.debug("AdemcoConfig:" + str(c))


    hass.async_create_task(async_load_platform(hass, "binary_sensor", DOMAIN, {}, c))
    hass.async_create_task(async_load_platform(hass, "cover", DOMAIN, {}, c))
    # hass.data[DOMAIN] = {}

    # for door in config['garagedoor']:
    #    sensors.append(AdemcoZone(panel.get(door['id']), door['name'], "garage_door"))

    # hass.add_entities(entities)

    # for zone in panel.zones:
    # print(zone.zoneNum)
    # hass.states.async_set("ademco.zone"+str(zone.zoneNum), zone.opened, attributes={"trouble": zone.trouble, "alarm": zone.alarm, "bypassed": zone.bypassed})

    # Return boolean to indicate that initialization was successful.
    return True



# TODO UNLOAD module to disconnect serial to prevent error on reconnect


# async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Set up Ademco RS232 Alarm Panel from a config entry."""
#     # Store an API object for your platforms to access
#     hass.data[DOMAIN]


#     hass.config_entries.async_setup_platforms(entry, PLATFORMS)

#     return True


# async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
#     """Unload a config entry."""
#     unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
#     hass.data[DOMAIN].writer.close()
#     hass.data[DOMAIN].reader.close()
#     #await hass.data[DOMAIN].writer.wait_closed()
#     #await hass.data[DOMAIN].reader.wait_closed()
#     if unload_ok:
#         hass.data[DOMAIN].pop(entry.entry_id)

#     return unload_ok
