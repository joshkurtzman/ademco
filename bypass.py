"""Shared bypass helpers for Ademco zone entities."""

from __future__ import annotations

from collections.abc import Mapping

from homeassistant.exceptions import HomeAssistantError

from .const import CONF_PARTITIONS

BYPASS_ZONE_TYPES = {"door", "window", "motion"}


def build_partition_configs(config: Mapping[str, object]) -> dict[int, dict[str, object]]:
    """Build partition config lookup keyed by partition id."""
    return {
        int(item["id"]): item
        for item in config.get(CONF_PARTITIONS, [])
        if isinstance(item, Mapping) and str(item.get("id", "")).isdigit()
    }


def supports_bypass(
    zone_type: str,
    partition_id: int,
    partition_configs: Mapping[int, Mapping[str, object]],
) -> bool:
    """Return whether the zone supports bypass control."""
    partition_config = partition_configs.get(partition_id, {})
    return zone_type in BYPASS_ZONE_TYPES and bool(partition_config.get("userNumber"))


def validate_bypass_request(
    name: str,
    zone_type: str,
    partition_id: int,
    partition_configs: Mapping[int, Mapping[str, object]],
) -> None:
    """Raise if the entity is not configured for bypass control."""
    if not supports_bypass(zone_type, partition_id, partition_configs):
        raise HomeAssistantError(f"{name} is not configured for Ademco bypass control")
    if partition_id <= 0:
        raise HomeAssistantError(f"{name} has no valid partition")
