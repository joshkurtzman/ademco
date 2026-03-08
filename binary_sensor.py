"""Binary sensor platform for Ademco zones."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AdemcoConfigEntry
from .ademco import Zone
from .const import CONF_DOORS, CONF_MOTIONS, CONF_PROBLEMS, CONF_WINDOWS
from .entity import AdemcoEntity


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
        self._attr_device_class = device_class
        self._attr_unique_id = f"zone_{self._zone.zoneNum}_{device_class}"
        self._remove_zone_callback = None

    async def async_added_to_hass(self) -> None:
        """Register zone update callbacks when enabled."""
        await super().async_added_to_hass()
        self._remove_zone_callback = self._zone.registerCallback(
            self.schedule_update_ha_state
        )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks."""
        if self._remove_zone_callback is not None:
            self._remove_zone_callback()
            self._remove_zone_callback = None
        await super().async_will_remove_from_hass()

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
        """Return the entity name relative to the panel device."""
        return self._config.get("name")

    @property
    def is_on(self) -> bool:
        """Return if the zone is currently active/open."""
        return self._zone.opened
