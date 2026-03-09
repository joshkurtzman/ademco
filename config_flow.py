"""Config flow for the Ademco RS232 Alarm Panel integration."""

from __future__ import annotations

import json
from json import JSONDecodeError
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

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

TEXT_SELECTOR = TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT))


def _default_title(data: dict[str, Any]) -> str:
    """Build a friendly entry title."""
    return DEFAULT_NAME


def _normalize_zone_list(value: Any) -> list[dict[str, str]]:
    """Validate stored zone definitions."""
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
    """Validate stored garage door definitions."""
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


def _parse_zone_line(line: str) -> dict[str, str]:
    """Parse a single zone line in the form id:name[:latchSeconds]."""
    parts = [part.strip() for part in line.split(":", 2)]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        raise ValueError

    zone: dict[str, str] = {"id": parts[0], "name": parts[1]}
    if len(parts) == 3 and parts[2]:
        zone["latchSeconds"] = parts[2]
    return zone


def _parse_garage_line(line: str) -> dict[str, str]:
    """Parse a single garage line in the form zone:name:output."""
    parts = [part.strip() for part in line.split(":", 2)]
    if len(parts) != 3 or not parts[0] or not parts[1] or not parts[2]:
        raise ValueError

    return {"id": parts[0], "name": parts[1], "output": parts[2]}


def _parse_mapping_text(raw_value: str, garage_doors: bool = False) -> list[dict[str, str]]:
    """Parse multiline mapping text or legacy JSON arrays from the UI."""
    raw_value = raw_value.strip()
    if not raw_value:
        return []

    if raw_value.startswith("["):
        value = json.loads(raw_value)
        if garage_doors:
            return _normalize_garage_doors(value)
        return _normalize_zone_list(value)

    parsed: list[dict[str, str]] = []
    parser = _parse_garage_line if garage_doors else _parse_zone_line
    for line in raw_value.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parsed.append(parser(stripped))

    if garage_doors:
        return _normalize_garage_doors(parsed)
    return _normalize_zone_list(parsed)


def _serialize_zone_lines(value: Any) -> str:
    """Render stored zone data as multiline text for the UI."""
    lines: list[str] = []
    for item in _normalize_zone_list(value):
        line = f"{item['id']}:{item['name']}"
        if "latchSeconds" in item:
            line = f"{line}:{item['latchSeconds']}"
        lines.append(line)
    return "\n".join(lines)


def _serialize_garage_lines(value: Any) -> str:
    """Render stored garage data as multiline text for the UI."""
    lines = [
        f"{item['id']}:{item['name']}:{item['output']}"
        for item in _normalize_garage_doors(value)
    ]
    return "\n".join(lines)


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


def _build_connection_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the connection settings form schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(CONF_DEVICE, default=defaults.get(CONF_DEVICE, "")): TEXT_SELECTOR,
            vol.Required(CONF_BAUD, default=defaults.get(CONF_BAUD, "1200")): TEXT_SELECTOR,
        }
    )


def _build_zone_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the zone mappings form schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_DOORS,
                default=_serialize_zone_lines(defaults.get(CONF_DOORS)),
            ): TEXT_SELECTOR,
            vol.Optional(
                CONF_WINDOWS,
                default=_serialize_zone_lines(defaults.get(CONF_WINDOWS)),
            ): TEXT_SELECTOR,
            vol.Optional(
                CONF_MOTIONS,
                default=_serialize_zone_lines(defaults.get(CONF_MOTIONS)),
            ): TEXT_SELECTOR,
            vol.Optional(
                CONF_PROBLEMS,
                default=_serialize_zone_lines(defaults.get(CONF_PROBLEMS)),
            ): TEXT_SELECTOR,
        }
    )


def _build_garage_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the garage door mappings form schema."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Optional(
                CONF_GARAGE_DOORS,
                default=_serialize_garage_lines(defaults.get(CONF_GARAGE_DOORS)),
            ): TEXT_SELECTOR,
        }
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Ademco."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._config: dict[str, Any] = {}

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a user-initiated flow."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            self._config = {
                CONF_DEVICE: user_input.get(CONF_DEVICE, ""),
                CONF_BAUD: user_input.get(CONF_BAUD, "1200"),
            }
            return await self.async_step_zones()

        self._config = {}
        return self.async_show_form(
            step_id="user",
            data_schema=_build_connection_schema(),
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle a reconfiguration flow."""
        defaults = dict(self._get_reconfigure_entry().data)
        if user_input is not None:
            self._config = {**defaults, **user_input}
            return await self.async_step_zones()

        self._config = defaults
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_build_connection_schema(defaults),
        )

    async def async_step_zones(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the zone mapping step."""
        defaults = self._config
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._config.update(
                    {
                        CONF_DOORS: _parse_mapping_text(user_input.get(CONF_DOORS, "")),
                        CONF_WINDOWS: _parse_mapping_text(
                            user_input.get(CONF_WINDOWS, "")
                        ),
                        CONF_MOTIONS: _parse_mapping_text(
                            user_input.get(CONF_MOTIONS, "")
                        ),
                        CONF_PROBLEMS: _parse_mapping_text(
                            user_input.get(CONF_PROBLEMS, "")
                        ),
                    }
                )
            except JSONDecodeError:
                errors["base"] = "invalid_json"
            except ValueError:
                errors["base"] = "invalid_mapping"
            else:
                return await self.async_step_garage_doors()

        return self.async_show_form(
            step_id="zones",
            data_schema=_build_zone_schema(defaults),
            errors=errors,
        )

    async def async_step_garage_doors(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the garage door mapping step."""
        defaults = self._config
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                self._config[CONF_GARAGE_DOORS] = _parse_mapping_text(
                    user_input.get(CONF_GARAGE_DOORS, ""),
                    garage_doors=True,
                )
            except JSONDecodeError:
                errors["base"] = "invalid_json"
            except ValueError:
                errors["base"] = "invalid_mapping"
            else:
                normalized = _normalize_entry_data(self._config)
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

        return self.async_show_form(
            step_id="garage_doors",
            data_schema=_build_garage_schema(defaults),
            errors=errors,
        )
