"""Alarm control panel platform for Ademco partitions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelState,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AdemcoConfigEntry
from .entity import AdemcoEntity

if TYPE_CHECKING:
    from .ademco import Partition, Zone


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AdemcoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ademco partition entities from a config entry."""
    runtime_data = entry.runtime_data
    panel = runtime_data.panel
    known_partition_ids: set[int] = set()

    @callback
    def async_add_new_partitions() -> None:
        entities: list[AdemcoPartition] = []
        for partition in sorted(panel.partitions, key=lambda item: item.partionNum):
            partition_id = partition.partionNum
            if partition_id in known_partition_ids:
                continue
            known_partition_ids.add(partition_id)
            entities.append(
                AdemcoPartition(
                    panel,
                    runtime_data.device_id,
                    runtime_data.device_name,
                    partition,
                )
            )
        if entities:
            async_add_entities(entities)

    remove_callback = panel.registerCallback(async_add_new_partitions)
    entry.async_on_unload(remove_callback)
    async_add_new_partitions()


class AdemcoPartition(AdemcoEntity, AlarmControlPanelEntity):
    """Representation of an Ademco alarm partition."""

    _attr_should_poll = False

    def __init__(
        self,
        panel,
        device_id: str,
        device_name: str,
        partition: Partition,
    ) -> None:
        """Initialize an Ademco partition entity."""
        super().__init__(panel, device_id, device_name)
        self._partition = partition
        self._zone_callbacks: dict[int, Callable[[], None]] = {}
        self._attr_unique_id = f"ademco.partition{self._partition.partionNum}"

    async def async_added_to_hass(self) -> None:
        """Register for panel and zone updates."""
        await super().async_added_to_hass()
        self._refresh_zone_callbacks()

    async def async_will_remove_from_hass(self) -> None:
        """Remove zone callbacks."""
        self._clear_zone_callbacks()
        await super().async_will_remove_from_hass()

    @property
    def name(self) -> str:
        """Return the partition name."""
        return f"Partition {self._partition.partionNum}"

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the current partition state."""
        if not self.available:
            return None
        if any(zone.alarm for zone in self._tracked_zones()):
            return AlarmControlPanelState.TRIGGERED

        status = self._partition.armStatus
        if status == "A":
            return AlarmControlPanelState.ARMED_AWAY
        if status == "H":
            return AlarmControlPanelState.ARMED_HOME
        if status in {"D", "N"}:
            return AlarmControlPanelState.DISARMED
        return None

    @property
    def extra_state_attributes(self) -> dict[str, int | str | bool]:
        """Return extra partition attributes."""
        return {
            "partition_id": self._partition.partionNum,
            "raw_status": self._partition.armStatus,
            "ready": self._partition.ready,
            "tracked_zone_count": len(self._tracked_zones()),
        }

    @callback
    def _handle_panel_update(self) -> None:
        """Refresh zone subscriptions and state after panel updates."""
        self._refresh_zone_callbacks()
        super()._handle_panel_update()

    @callback
    def _handle_zone_update(self) -> None:
        """Refresh entity state after a tracked zone updates."""
        self.async_write_ha_state()

    def _tracked_zones(self) -> list[Zone]:
        return [
            zone
            for zone in self._panel.zones
            if zone.partition_id == self._partition.partionNum
        ]

    def _clear_zone_callbacks(self) -> None:
        for remove_callback in self._zone_callbacks.values():
            remove_callback()
        self._zone_callbacks = {}

    @callback
    def _refresh_zone_callbacks(self) -> None:
        tracked_zone_ids = {
            zone.zoneNum for zone in self._tracked_zones()
        }

        for zone_id in list(self._zone_callbacks):
            if zone_id not in tracked_zone_ids:
                self._zone_callbacks.pop(zone_id)()

        for zone in self._tracked_zones():
            if zone.zoneNum in self._zone_callbacks:
                continue
            self._zone_callbacks[zone.zoneNum] = zone.registerCallback(
                self._handle_zone_update
            )
