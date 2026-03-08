"""Config flow for the Ademco RS232 Alarm Panel integration."""

from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

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
    return DEFAULT_NAME


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


def _stringify_form_value(value: Any) -> str:
    """Convert stored config data into a stable JSON string for forms."""
    if not value:
        return "[]"
    return json.dumps(value, separators=(", ", ": "))


def _build_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the config form schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(CONF_DEVICE, default=defaults.get(CONF_DEVICE, "")): str,
            vol.Required(CONF_BAUD, default=defaults.get(CONF_BAUD, "1200")): str,
            vol.Optional(
                CONF_DOORS,
                default=_stringify_form_value(defaults.get(CONF_DOORS)),
            ): str,
            vol.Optional(
                CONF_WINDOWS,
                default=_stringify_form_value(defaults.get(CONF_WINDOWS)),
            ): str,
            vol.Optional(
                CONF_MOTIONS,
                default=_stringify_form_value(defaults.get(CONF_MOTIONS)),
            ): str,
            vol.Optional(
                CONF_PROBLEMS,
                default=_stringify_form_value(defaults.get(CONF_PROBLEMS)),
            ): str,
            vol.Optional(
                CONF_GARAGE_DOORS,
                default=_stringify_form_value(defaults.get(CONF_GARAGE_DOORS)),
            ): str,
        }
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ademco."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a user-initiated flow."""
        return await self._async_handle_config_step(user_input)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow."""
        return await self._async_handle_config_step(
            user_input,
            self._get_reconfigure_entry().data,
        )

    async def _async_handle_config_step(
        self,
        user_input: dict[str, Any] | None = None,
        defaults: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle create and reconfigure flows."""
        if self.source != config_entries.SOURCE_RECONFIGURE and self._async_current_entries():
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
                normalized = _normalize_entry_data(data)
                if self.source == config_entries.SOURCE_RECONFIGURE:
                    return self.async_update_reload_and_abort(
                        self._get_reconfigure_entry(),
                        title=_default_title(normalized),
                        data=normalized,
                    )
                return self.async_create_entry(
                    title=_default_title(normalized),
                    data=normalized,
                )

        step_id = "reconfigure" if self.source == config_entries.SOURCE_RECONFIGURE else "user"
        return self.async_show_form(
            step_id=step_id,
            data_schema=_build_schema(defaults),
            errors=errors,
        )
