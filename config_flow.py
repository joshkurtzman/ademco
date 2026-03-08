"""Config flow for the Ademco RS232 Alarm Panel integration."""

from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

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
)


def _default_title(data: dict[str, Any]) -> str:
    """Build a friendly entry title."""
    return data.get(CONF_DEVICE) or DEFAULT_NAME


def _normalize_zone_list(value: Any) -> list[dict[str, str]]:
    """Validate YAML/imported zone definitions."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError
    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError
        zone_id = item.get("id")
        name = item.get("name")
        if zone_id is None or name is None:
            raise ValueError
        zone: dict[str, str] = {"id": str(zone_id), "name": str(name)}
        latch_seconds = item.get("latchSeconds")
        if latch_seconds is not None:
            zone["latchSeconds"] = str(latch_seconds)
        normalized.append(zone)
    return normalized


def _normalize_garage_doors(value: Any) -> list[dict[str, str]]:
    """Validate YAML/imported garage door definitions."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError
    normalized: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError
        zone_id = item.get("id")
        name = item.get("name")
        output = item.get("output")
        if zone_id is None or name is None or output is None:
            raise ValueError
        normalized.append(
            {"id": str(zone_id), "name": str(name), "output": str(output)}
        )
    return normalized


def _parse_json_list(raw_value: str, garage_doors: bool = False) -> list[dict[str, str]]:
    """Parse JSON arrays entered through the UI."""
    if not raw_value.strip():
        return []
    value = json.loads(raw_value)
    if garage_doors:
        return _normalize_garage_doors(value)
    return _normalize_zone_list(value)


def _normalize_entry_data(data: dict[str, Any]) -> dict[str, Any]:
    """Normalize config entry data from a flow step."""
    return {
        CONF_DEVICE: str(data.get(CONF_DEVICE, "")).strip(),
        CONF_BAUD: str(data.get(CONF_BAUD, "1200")).strip() or "1200",
        CONF_DOORS: _normalize_zone_list(data.get(CONF_DOORS, [])),
        CONF_WINDOWS: _normalize_zone_list(data.get(CONF_WINDOWS, [])),
        CONF_MOTIONS: _normalize_zone_list(data.get(CONF_MOTIONS, [])),
        CONF_PROBLEMS: _normalize_zone_list(data.get(CONF_PROBLEMS, [])),
        CONF_GARAGE_DOORS: _normalize_garage_doors(data.get(CONF_GARAGE_DOORS, [])),
    }


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ademco."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a user-initiated flow."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                data = {
                    CONF_DEVICE: user_input[CONF_DEVICE],
                    CONF_BAUD: user_input[CONF_BAUD],
                    CONF_DOORS: _parse_json_list(user_input.get(CONF_DOORS, "[]")),
                    CONF_WINDOWS: _parse_json_list(user_input.get(CONF_WINDOWS, "[]")),
                    CONF_MOTIONS: _parse_json_list(user_input.get(CONF_MOTIONS, "[]")),
                    CONF_PROBLEMS: _parse_json_list(user_input.get(CONF_PROBLEMS, "[]")),
                    CONF_GARAGE_DOORS: _parse_json_list(
                        user_input.get(CONF_GARAGE_DOORS, "[]"),
                        garage_doors=True,
                    ),
                }
            except JSONDecodeError:
                errors["base"] = "invalid_json"
            except ValueError:
                errors["base"] = "invalid_config"
            else:
                return self.async_create_entry(
                    title=_default_title(data),
                    data=_normalize_entry_data(data),
                )

        schema = vol.Schema(
            {
                vol.Optional(CONF_DEVICE, default=""): str,
                vol.Required(CONF_BAUD, default="1200"): str,
                vol.Optional(CONF_DOORS, default="[]"): str,
                vol.Optional(CONF_WINDOWS, default="[]"): str,
                vol.Optional(CONF_MOTIONS, default="[]"): str,
                vol.Optional(CONF_PROBLEMS, default="[]"): str,
                vol.Optional(CONF_GARAGE_DOORS, default="[]"): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    async def async_step_import(self, import_config: dict[str, Any]) -> FlowResult:
        """Import configuration from YAML."""
        try:
            data = _normalize_entry_data(import_config)
        except ValueError:
            return self.async_abort(reason="invalid_config")

        if existing_entries := self._async_current_entries():
            self.hass.config_entries.async_update_entry(
                existing_entries[0],
                data=data,
                title=_default_title(data),
            )
            return self.async_abort(reason="already_configured")

        return self.async_create_entry(title=_default_title(data), data=data)
