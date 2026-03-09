"""Provides device triggers for Ademco binary sensors."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.device_automation.const import (
    CONF_TURNED_OFF,
    CONF_TURNED_ON,
)
from homeassistant.components.homeassistant.triggers import state as state_trigger
from homeassistant.const import CONF_ENTITY_ID, CONF_FOR, CONF_TYPE
from homeassistant.helpers import config_validation as cv, entity_registry as er

from .const import DOMAIN

CONF_MOTION = "motion"
CONF_NO_MOTION = "no_motion"
CONF_OPENED = "opened"
CONF_NOT_OPENED = "not_opened"
CONF_PROBLEM = "problem"
CONF_NO_PROBLEM = "no_problem"

TURNED_ON = [
    CONF_MOTION,
    CONF_OPENED,
    CONF_PROBLEM,
    CONF_TURNED_ON,
]

TURNED_OFF = [
    CONF_NO_MOTION,
    CONF_NOT_OPENED,
    CONF_NO_PROBLEM,
    CONF_TURNED_OFF,
]

ENTITY_TRIGGERS: dict[BinarySensorDeviceClass | str, list[dict[str, str]]] = {
    BinarySensorDeviceClass.DOOR: [
        {CONF_TYPE: CONF_OPENED},
        {CONF_TYPE: CONF_NOT_OPENED},
    ],
    BinarySensorDeviceClass.WINDOW: [
        {CONF_TYPE: CONF_OPENED},
        {CONF_TYPE: CONF_NOT_OPENED},
    ],
    BinarySensorDeviceClass.MOTION: [
        {CONF_TYPE: CONF_MOTION},
        {CONF_TYPE: CONF_NO_MOTION},
    ],
    BinarySensorDeviceClass.PROBLEM: [
        {CONF_TYPE: CONF_PROBLEM},
        {CONF_TYPE: CONF_NO_PROBLEM},
    ],
    "none": [{CONF_TYPE: CONF_TURNED_ON}, {CONF_TYPE: CONF_TURNED_OFF}],
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_ENTITY_ID): cv.entity_id,
        vol.Required(CONF_TYPE): vol.In(TURNED_OFF + TURNED_ON),
        vol.Optional(CONF_FOR): cv.positive_time_period_dict,
    }
)


async def async_attach_trigger(hass, config, action, automation_info):
    """Listen for state changes based on configuration."""
    to_state = "on" if config[CONF_TYPE] in TURNED_ON else "off"

    state_config = {
        state_trigger.CONF_PLATFORM: "state",
        state_trigger.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
        state_trigger.CONF_TO: to_state,
    }
    if CONF_FOR in config:
        state_config[CONF_FOR] = config[CONF_FOR]

    state_config = state_trigger.TRIGGER_SCHEMA(state_config)
    return await state_trigger.async_attach_trigger(
        hass, state_config, action, automation_info, platform_type="device"
    )


async def async_get_triggers(hass, device_id):
    """List available triggers for Ademco binary sensors on a device."""
    triggers = []
    entity_registry = er.async_get(hass)

    for entry in er.async_entries_for_device(entity_registry, device_id):
        if entry.domain != "binary_sensor":
            continue
        if entry.platform != DOMAIN:
            continue

        device_class = entry.device_class or "none"
        templates = ENTITY_TRIGGERS.get(device_class, ENTITY_TRIGGERS["none"])

        triggers.extend(
            {
                **automation,
                "platform": "device",
                "device_id": device_id,
                "entity_id": entry.entity_id,
                "domain": DOMAIN,
            }
            for automation in templates
        )

    return triggers


async def async_get_trigger_capabilities(hass, config):
    """List trigger capabilities."""
    return {
        "extra_fields": vol.Schema(
            {vol.Optional(CONF_FOR): cv.positive_time_period_dict}
        )
    }
