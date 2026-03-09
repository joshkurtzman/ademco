"""Binary sensor platform for Ademco zones."""

from __future__ import annotations

from typing import TYPE_CHECKING

import voluptuous as vol

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)

from . import AdemcoConfigEntry
from .const import (
    CONF_DOORS,
    CONF_MOTIONS,
    CONF_PARTITIONS,
    CONF_PROBLEMS,
    CONF_WINDOWS,
)
from .entity import AdemcoEntity

if TYPE_CHECKING:
    from .ademco import Zone


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdemcoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ademco binary sensors from a config entry."""
    entities = []
    runtime_data = entry.runtime_data
    panel = runtime_data.panel
    config = runtime_data.config
    partition_configs = {
        int(item["id"]): item
        for item in config.get(CONF_PARTITIONS, [])
        if str(item.get("id", "")).isdigit()
    }
    platform = async_get_current_platform()

    for zone_config in config.get(CONF_DOORS, []):
        entities.append(
            AdemcoZone(
                panel,
                runtime_data.device_id,
                runtime_data.device_name,
                panel.getZone(zone_config["id"]),
                zone_config,
                "door",
                partition_configs,
            )
        )

    for zone_config in config.get(CONF_WINDOWS, []):
        entities.append(
            AdemcoZone(
                panel,
                runtime_data.device_id,
                runtime_data.device_name,
                panel.getZone(zone_config["id"]),
                zone_config,
                "window",
                partition_configs,
            )
        )
    for zone_config in config.get(CONF_MOTIONS, []):
        entities.append(
            AdemcoZone(
                panel,
                runtime_data.device_id,
                runtime_data.device_name,
                panel.getZone(zone_config["id"]),
                zone_config,
                "motion",
                partition_configs,
            )
        )
    for zone_config in config.get(CONF_PROBLEMS, []):
        entities.append(
            AdemcoZone(
                panel,
                runtime_data.device_id,
                runtime_data.device_name,
                panel.getZone(zone_config["id"]),
                zone_config,
                "problem",
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


class AdemcoZone(AdemcoEntity, BinarySensorEntity):
    """Representation of an Ademco zone."""

    _attr_should_poll = False

    def __init__(
        self,
        panel,
        device_id: str,
        device_name: str,
        zone: Zone,
        config: dict[str, str],
        device_class: str,
        partition_configs: dict[int, dict[str, str]],
    ) -> None:
        """Initialize an Ademco zone entity."""
        super().__init__(panel, device_id, device_name)
        self._zone = zone
        self._config = config
        self._zone_type = device_class
        self._partition_configs = partition_configs
        self._attr_device_class = BinarySensorDeviceClass(device_class)
        self._attr_unique_id = f"ademco.zone{self._zone.zoneNum}"
        self._zone.latchSeconds = int(config.get("latchSeconds", "0") or 0)
        self._latch_seconds = self._zone.latchSeconds
        self._latched_on = False
        self._was_open = self._zone.opened
        self._remove_latch_timer = None
        self._remove_zone_callback = None

    async def async_added_to_hass(self) -> None:
        """Register zone update callbacks when enabled."""
        await super().async_added_to_hass()
        self._remove_zone_callback = self._zone.registerCallback(self._handle_zone_update)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks."""
        self._cancel_latch_timer()
        if self._remove_zone_callback is not None:
            self._remove_zone_callback()
            self._remove_zone_callback = None
        await super().async_will_remove_from_hass()

    def _cancel_latch_timer(self) -> None:
        """Cancel any pending latch clear timer."""
        if self._remove_latch_timer is not None:
            self._remove_latch_timer()
            self._remove_latch_timer = None

    @callback
    def _clear_latch(self, _now=None) -> None:
        """Clear the temporary latched-on state."""
        self._remove_latch_timer = None
        if not self._zone.opened and self._latched_on:
            self._latched_on = False
            self.async_write_ha_state()

    @callback
    def _handle_zone_update(self) -> None:
        """Write state after a zone update."""
        is_open = self._zone.opened
        if is_open:
            self._cancel_latch_timer()
            self._latched_on = False
        elif self._was_open and self._latch_seconds > 0:
            self._latched_on = True
            self._cancel_latch_timer()
            self._remove_latch_timer = async_call_later(
                self.hass,
                self._latch_seconds,
                self._clear_latch,
            )

        self._was_open = is_open
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        """Return extra state attributes for the zone."""
        attributes = {
            "bypassed": self._zone.bypassed,
            "alarm": self._zone.alarm,
            "trouble": self._zone.trouble,
            "partition_id": self._zone.partition_id,
            "controllable_bypass": self._supports_bypass,
        }
        if self._latch_seconds > 0:
            attributes["latched"] = self._latched_on
            attributes["latchSeconds"] = self._latch_seconds
        return attributes

    @property
    def name(self):
        """Return the legacy-compatible zone name."""
        suffix = {
            "door": "Door",
            "window": "Window",
            "motion": "Motion",
            "problem": "Problem",
        }[self._zone_type]
        zone_name = self._config.get("name", "").strip()
        if not zone_name:
            return f"Zone {self._zone.zoneNum} {suffix}"
        return f"{zone_name} {suffix}"

    @property
    def is_on(self) -> bool:
        """Return if the zone is currently active/open."""
        return self._zone.opened or self._latched_on

    @property
    def _supports_bypass(self) -> bool:
        partition_config = self._partition_configs.get(self._zone.partition_id, {})
        return self._zone_type in {"door", "window", "motion"} and bool(
            partition_config.get("userNumber")
        )

    async def async_bypass_zone(self, code: str) -> None:
        """Bypass this zone using the partition's configured user number."""
        if not self._supports_bypass:
            raise HomeAssistantError(
                f"{self.name} is not configured for Ademco bypass control"
            )
        if self._zone.partition_id <= 0:
            raise HomeAssistantError(f"{self.name} has no valid partition")
        self._panel.bypassZone(self._zone.partition_id, code, self._zone.zoneNum)

    async def async_unbypass_zone(self, code: str) -> None:
        """Unbypass this zone using the same Ademco keypad toggle sequence."""
        if not self._supports_bypass:
            raise HomeAssistantError(
                f"{self.name} is not configured for Ademco bypass control"
            )
        if self._zone.partition_id <= 0:
            raise HomeAssistantError(f"{self.name} has no valid partition")
        if not self._zone.bypassed:
            raise HomeAssistantError(f"{self.name} is not currently bypassed")
        self._panel.bypassZone(self._zone.partition_id, code, self._zone.zoneNum)
