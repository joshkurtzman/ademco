"""Switch platform for Ademco zone bypass control."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from . import AdemcoConfigEntry
from .bypass import build_partition_configs, supports_bypass, validate_bypass_request
from .const import CONF_DOORS, CONF_MOTIONS, CONF_WINDOWS
from .entity import AdemcoEntity

if TYPE_CHECKING:
    from .ademco import Zone


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdemcoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ademco bypass switches from a config entry."""
    entities = []
    runtime_data = entry.runtime_data
    panel = runtime_data.panel
    config = runtime_data.config
    partition_configs = build_partition_configs(config)
    platform = async_get_current_platform()

    for zone_type, key in (
        ("door", CONF_DOORS),
        ("window", CONF_WINDOWS),
        ("motion", CONF_MOTIONS),
    ):
        for zone_config in config.get(key, []):
            entities.append(
                AdemcoZoneBypassSwitch(
                    panel,
                    runtime_data.device_id,
                    runtime_data.device_name,
                    panel.getZone(zone_config["id"]),
                    zone_config,
                    zone_type,
                    partition_configs,
                )
            )

    async_add_entities(entities)
    platform.async_register_entity_service(
        "ademco_bypass",
        {vol.Required("code"): str},
        "async_bypass_zone",
    )
    platform.async_register_entity_service(
        "ademco_unbypass",
        {vol.Required("code"): str},
        "async_unbypass_zone",
    )


class AdemcoZoneBypassSwitch(AdemcoEntity, SwitchEntity):
    """Representation of an Ademco zone bypass switch."""

    _attr_should_poll = False
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        panel,
        device_id: str,
        device_name: str,
        zone: Zone,
        config: dict[str, str],
        zone_type: str,
        partition_configs: dict[int, dict[str, str]],
    ) -> None:
        """Initialize an Ademco bypass switch."""
        super().__init__(panel, device_id, device_name)
        self._zone = zone
        self._config = config
        self._zone_type = zone_type
        self._partition_configs = partition_configs
        self._remove_zone_callback = None
        self._attr_unique_id = f"ademco.zone{self._zone.zoneNum}_bypass"

    async def async_added_to_hass(self) -> None:
        """Register zone updates when the entity is added."""
        await super().async_added_to_hass()
        self._remove_zone_callback = self._zone.registerCallback(
            self._handle_zone_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks."""
        if self._remove_zone_callback is not None:
            self._remove_zone_callback()
            self._remove_zone_callback = None
        await super().async_will_remove_from_hass()

    @property
    def name(self) -> str:
        """Return the zone bypass switch name."""
        suffix = {
            "door": "Door",
            "window": "Window",
            "motion": "Motion",
        }[self._zone_type]
        zone_name = self._config.get("name", "").strip()
        if not zone_name:
            return f"Zone {self._zone.zoneNum} {suffix} Bypass"
        return f"{zone_name} {suffix} Bypass"

    @property
    def icon(self) -> str:
        """Return a context-specific icon."""
        return "mdi:shield-off" if self.is_on else "mdi:shield-check-outline"

    @property
    def is_on(self) -> bool:
        """Return whether the zone is currently bypassed."""
        return self._zone.bypassed

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra state attributes for the bypass switch."""
        return {
            "partition_id": self._zone.partition_id,
            "zone_open": self._zone.opened,
            "controllable_bypass": self._supports_bypass,
            "requires_code": True,
        }

    @property
    def _supports_bypass(self) -> bool:
        return supports_bypass(
            self._zone_type,
            self._zone.partition_id,
            self._partition_configs,
        )

    async def async_turn_on(self, **kwargs) -> None:
        """Direct UI toggles need a user code, so require the custom entity service."""
        if self.is_on:
            return
        raise HomeAssistantError(
            f"{self.name} requires a user code. Use switch.ademco_bypass with code."
        )

    async def async_turn_off(self, **kwargs) -> None:
        """Direct UI toggles need a user code, so require the custom entity service."""
        if not self.is_on:
            return
        raise HomeAssistantError(
            f"{self.name} requires a user code. Use switch.ademco_unbypass with code."
        )

    async def async_bypass_zone(self, code: str) -> None:
        """Bypass this zone using the partition's configured user number."""
        validate_bypass_request(
            self.name,
            self._zone_type,
            self._zone.partition_id,
            self._partition_configs,
        )
        self._panel.bypassZone(self._zone.partition_id, code, self._zone.zoneNum)

    async def async_unbypass_zone(self, code: str) -> None:
        """Unbypass this zone using the same Ademco keypad toggle sequence."""
        validate_bypass_request(
            self.name,
            self._zone_type,
            self._zone.partition_id,
            self._partition_configs,
        )
        if not self._zone.bypassed:
            raise HomeAssistantError(f"{self.name} is not currently bypassed")
        self._panel.bypassZone(self._zone.partition_id, code, self._zone.zoneNum)

    @callback
    def _handle_zone_update(self) -> None:
        """Write state after a zone update."""
        self.async_write_ha_state()
