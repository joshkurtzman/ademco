"""Alarm control panel platform for Ademco partitions."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
    AlarmControlPanelState,
    CodeFormat,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AdemcoConfigEntry
from .const import CONF_PARTITIONS
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
    partition_configs = {
        int(item["id"]): item
        for item in runtime_data.config.get(CONF_PARTITIONS, [])
        if str(item.get("id", "")).isdigit()
    }
    known_partition_ids: set[int] = set()

    @callback
    def async_add_new_partitions() -> None:
        entities: list[AdemcoPartition] = []
        active_partition_ids = set(panel.active_partition_ids)
        if not active_partition_ids:
            return

        for partition in sorted(panel.partitions, key=lambda item: item.partionNum):
            partition_id = partition.partionNum
            if partition_id not in active_partition_ids:
                continue
            if partition_id in known_partition_ids:
                continue
            known_partition_ids.add(partition_id)
            entities.append(
                AdemcoPartition(
                    panel,
                    runtime_data.device_id,
                    runtime_data.device_name,
                    partition,
                    partition_configs.get(partition_id),
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
        config: dict[str, str] | None,
    ) -> None:
        """Initialize an Ademco partition entity."""
        super().__init__(panel, device_id, device_name)
        self._partition = partition
        self._config = config or {}
        self._zone_callbacks: dict[int, Callable[[], None]] = {}
        self._pending_state: AlarmControlPanelState | None = None
        self._pending_target: AlarmControlPanelState | None = None
        self._attr_unique_id = f"ademco.partition{self._partition.partionNum}"
        if self._config.get("userNumber"):
            self._attr_supported_features = (
                AlarmControlPanelEntityFeature.ARM_AWAY
                | AlarmControlPanelEntityFeature.ARM_HOME
            )
        else:
            self._attr_supported_features = AlarmControlPanelEntityFeature(0)

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
        partition_name = self._config.get("name", "").strip()
        if partition_name:
            return partition_name
        return f"Partition {self._partition.partionNum}"

    @property
    def code_format(self) -> CodeFormat | None:
        """Return the required code format for controllable partitions."""
        if self._config.get("userNumber"):
            return CodeFormat.NUMBER
        return None

    @property
    def alarm_state(self) -> AlarmControlPanelState | None:
        """Return the current partition state."""
        if not self.available:
            return None
        actual_state = self._actual_alarm_state()
        if (
            self._pending_state is not None
            and self._pending_target is not None
            and actual_state != self._pending_target
        ):
            return self._pending_state
        return actual_state

    def _actual_alarm_state(self) -> AlarmControlPanelState | None:
        """Return the current partition state from panel memory."""
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
            "controllable": bool(self._config.get("userNumber")),
        }

    async def async_alarm_disarm(self, code: str | None = None) -> None:
        """Disarm this partition using the configured user number."""
        self._send_partition_command("disarm", code)

    async def async_alarm_arm_away(self, code: str | None = None) -> None:
        """Arm this partition away using the configured user number."""
        self._send_partition_command("away", code)

    async def async_alarm_arm_home(self, code: str | None = None) -> None:
        """Arm this partition home/stay using the configured user number."""
        self._send_partition_command("home", code)

    @callback
    def _handle_panel_update(self) -> None:
        """Refresh zone subscriptions and state after panel updates."""
        self._refresh_zone_callbacks()
        self._update_pending_state()
        super()._handle_panel_update()

    @callback
    def _handle_zone_update(self) -> None:
        """Refresh entity state after a tracked zone updates."""
        self._update_pending_state()
        self.async_write_ha_state()

    def _tracked_zones(self) -> list[Zone]:
        return [
            zone
            for zone in self._panel.zones
            if zone.partition_id == self._partition.partionNum
        ]

    def _send_partition_command(self, action: str, code: str | None) -> None:
        """Send a partition control command when configured and valid."""
        user_number = self._config.get("userNumber", "").strip()
        if not user_number:
            raise HomeAssistantError(
                f"Partition {self._partition.partionNum} is not configured for control"
            )
        if code is None:
            raise HomeAssistantError("A 4-digit user code is required")

        if action == "away":
            self._panel.armAway(user_number, code)
            self._pending_state = AlarmControlPanelState.ARMING
            self._pending_target = AlarmControlPanelState.ARMED_AWAY
            return
        if action == "home":
            self._panel.armHome(user_number, code)
            self._pending_state = AlarmControlPanelState.ARMING
            self._pending_target = AlarmControlPanelState.ARMED_HOME
            return
        self._panel.disam(user_number, code)
        self._pending_state = AlarmControlPanelState.DISARMING
        self._pending_target = AlarmControlPanelState.DISARMED

    @callback
    def _update_pending_state(self) -> None:
        """Clear transitional state once the panel reaches its target state."""
        if self._pending_target is None:
            return
        actual_state = self._actual_alarm_state()
        if actual_state in {self._pending_target, AlarmControlPanelState.TRIGGERED}:
            self._pending_state = None
            self._pending_target = None

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
