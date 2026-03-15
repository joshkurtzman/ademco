"""Shared entity helpers for the Ademco integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN, MANUFACTURER, MODEL

if TYPE_CHECKING:
    from .ademco import AlarmPanel


class AdemcoEntity(Entity):
    """Base entity for Ademco entities attached to a panel device."""

    _attr_has_entity_name = False
    _attr_should_poll = False

    def __init__(self, panel: AlarmPanel, device_id: str, device_name: str) -> None:
        """Initialize the shared entity state."""
        self._panel = panel
        self._remove_panel_callback = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            manufacturer=MANUFACTURER,
            model=MODEL,
            name=device_name,
        )

    @property
    def available(self) -> bool:
        """Return if the backing panel connection is available."""
        return self._panel.available

    async def async_added_to_hass(self) -> None:
        """Register for panel availability updates."""
        self._remove_panel_callback = self._panel.registerCallback(
            self._handle_panel_update
        )

    async def async_will_remove_from_hass(self) -> None:
        """Remove panel availability callbacks."""
        if self._remove_panel_callback is not None:
            self._remove_panel_callback()
            self._remove_panel_callback = None

    @callback
    def _handle_panel_update(self) -> None:
        """Write state after a panel-level update."""
        self.async_write_ha_state()
