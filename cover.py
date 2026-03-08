"""Cover platform for Ademco garage door outputs."""

from __future__ import annotations

import asyncio
import logging

from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AdemcoConfigEntry
from .ademco import Output, Zone
from .const import CONF_GARAGE_DOORS
from .entity import AdemcoEntity

log = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdemcoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ademco garage door covers from a config entry."""
    entities = []
    runtime_data = entry.runtime_data
    panel = runtime_data.panel
    config = runtime_data.config

    for garage_config in config.get(CONF_GARAGE_DOORS, []):
        entities.append(
            AdemcoGarageDoor(
                panel,
                runtime_data.device_id,
                runtime_data.device_name,
                panel.getZone(garage_config["id"]),
                panel.getOutput(garage_config["output"]),
                garage_config,
            )
        )

    async_add_entities(entities)


class AdemcoGarageDoor(AdemcoEntity, CoverEntity):
    """Representation of an Ademco garage door cover."""

    _attr_should_poll = False
    _attr_device_class = CoverDeviceClass.GARAGE
    _attr_supported_features = CoverEntityFeature.OPEN | CoverEntityFeature.CLOSE

    def __init__(
        self,
        panel,
        device_id: str,
        device_name: str,
        zone: Zone,
        output: Output,
        config: dict[str, str],
    ) -> None:
        """Initialize an Ademco garage door."""
        super().__init__(panel, device_id, device_name)
        self._zone = zone
        self._output = output
        self._config = config
        self._status = CoverState.OPEN if zone.opened else CoverState.CLOSED
        self._attr_unique_id = (
            f"garage_output_{self._output.outputId}_zone_{self._zone.zoneNum}"
        )
        self._remove_zone_callback = None

    async def async_added_to_hass(self) -> None:
        """Register zone updates when the entity is added."""
        await super().async_added_to_hass()
        self._remove_zone_callback = self._zone.registerCallback(self._update_status)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks."""
        if self._remove_zone_callback is not None:
            self._remove_zone_callback()
            self._remove_zone_callback = None
        await super().async_will_remove_from_hass()

    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
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
    def current_cover_position(self):
        """Return 100 when open and 0 when closed."""
        if self._zone.opened:
            return 100
        return 0

    @property
    def is_opening(self):
        if self._status == CoverState.OPENING:
            return True
        return False

    @property
    def is_closing(self):
        if self._status == CoverState.CLOSING:
            return True
        return False
    
    @property
    def is_closed(self):
        return self._zone.closed

    def _update_status(self):
        if self._zone.opened:
            self._status = CoverState.OPEN
        else:
            self._status = CoverState.CLOSED
        self.schedule_update_ha_state()

    async def toggleRelay(self):
        self._output.turnOn()
        await asyncio.sleep(1.5)
        self._output.turnOff()

    async def async_open_cover(self, **kwargs):
        if self._status == CoverState.CLOSED:
            self._status = CoverState.OPENING
            self.schedule_update_ha_state()
            await self.toggleRelay()
            for _ in range(0, 10):
                await asyncio.sleep(1)
                if self._status == CoverState.OPEN:
                    break
            log.critical("Garage door: {} did not open after 10 seconds".format(self.name))
            self._update_status()

        else:
            log.info("Could not open {} - State is {}".format(self.name, self._status))

            
    async def async_close_cover(self, **kwargs):
        if self._status == CoverState.OPEN:
            self._status = CoverState.CLOSING
            self.schedule_update_ha_state()
            await self.toggleRelay()
            for _ in range(0, 10):
                await asyncio.sleep(1)
                if self._status == CoverState.CLOSED:
                    break
            log.critical("Garage door: {} did not close after 10 seconds".format(self.name))
            self._update_status()

        else:
            log.info("Could not close {} - State is {}".format(self.name, self._status))
