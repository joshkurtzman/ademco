"""Binary sensor platform for Ademco zones."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import callback
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AdemcoConfigEntry
from .const import CONF_DOORS, CONF_MOTIONS, CONF_PROBLEMS, CONF_WINDOWS
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

    for zone_config in config.get(CONF_DOORS, []):
        entities.append(
            AdemcoZone(
                panel,
                runtime_data.device_id,
                runtime_data.device_name,
                panel.getZone(zone_config["id"]),
                zone_config,
                "door",
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
            )
        )

    async_add_entities(entities)


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
    ) -> None:
        """Initialize an Ademco zone entity."""
        super().__init__(panel, device_id, device_name)
        self._zone = zone
        self._config = config
        self._zone_type = device_class
        self._attr_device_class = BinarySensorDeviceClass(device_class)
        self._attr_unique_id = f"ademco.zone{self._zone.zoneNum}"
        self._remove_zone_callback = None

    async def async_added_to_hass(self) -> None:
        """Register zone update callbacks when enabled."""
        await super().async_added_to_hass()
        self._remove_zone_callback = self._zone.registerCallback(self._handle_zone_update)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks."""
        if self._remove_zone_callback is not None:
            self._remove_zone_callback()
            self._remove_zone_callback = None
        await super().async_will_remove_from_hass()

    @callback
    def _handle_zone_update(self) -> None:
        """Write state after a zone update."""
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        """Return extra state attributes for the zone."""
        return {
            "bypassed": self._zone.bypassed,
            "alarm": self._zone.alarm,
            "trouble": self._zone.trouble,
        }

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
        return self._zone.opened
