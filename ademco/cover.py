import homeassistant
from homeassistant.components.cover import CoverEntity, DEVICE_CLASS_GARAGE, SUPPORT_OPEN, SUPPORT_CLOSE, STATE_CLOSED, STATE_CLOSING, STATE_OPEN, STATE_OPENING
from .ademco import Zone, Output
import logging
import asyncio

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
from homeassistant.core import HomeAssistant
from .const import DOMAIN
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)
from typing import Callable, Optional, Sequence

log.debug("ademco loading output relays")


def setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable[[Sequence[CoverEntity], bool], None],
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:

    entities = []
    panel = hass.data[DOMAIN]["panel"]
    config = hass.data[DOMAIN]["config"]

    for x in config.get("garagedoors"):
        log.debug("ADEMCO" + str(x))
        entities.append(
            AdemcoGarageDoor(
                panel.getZone(x["id"]),
                panel.getOutput(x["output"]),
                x
            )
        )

    async_add_entities(entities)
    return True


class AdemcoGarageDoor(CoverEntity):
    def __init__(
        self, zone: Zone, output: Output, config: str) -> None:
        super.__init__
        self._zone = zone
        self._output = output
        self._config = config
        self._status = STATE_OPEN if zone.opened  else STATE_CLOSED
        self._zone.registerCallback(self._updateStatus)
    @property
    def should_poll(self):
        return False
        
    @property
    def identifiers(self):
        return (DOMAIN, self.unique_id)

    @property
    def unique_id(self):
        return "{}.zone{}".format(DOMAIN,self._zone.zoneNum)
    
    @property
    def extra_state_attributes(self):
        return {
                "bypassed":self._zone.bypassed, 
                "alarm":self._zone.alarm, 
                "trouble":self._zone.trouble }

    @property
    def name(self):
        return "{} Garage Door".format(self._config.get("name"))

    @property
    def is_on(self) -> bool:
        return self._zone.opened

    @property
    def device_class(self):
        return DEVICE_CLASS_GARAGE

    @property
    def supported_features(self) -> int:
        return SUPPORT_OPEN | SUPPORT_CLOSE

    @property
    def current_cover_position(self):
        if self._zone.opened:
            return 100
        return 0

    @property
    def is_opening(self):
        if self._status == STATE_OPENING:
            return True
        return False

    @property
    def is_closing(self):
        if self._status == STATE_CLOSING:
            return True
        return False
    
    @property
    def is_closed(self):
        return self._zone.closed

    def _updateStatus(self):
        if self._zone.opened:
            self._status = STATE_OPEN
        else:
            self._status = STATE_CLOSED
        self.schedule_update_ha_state()

    async def toggleRelay(self):
        self._output.turnOn()
        await asyncio.sleep(1.5)
        self._output.turnOff()

    async def async_open_cover(self, **kwargs):
        if self._status == STATE_CLOSED:
            self._status = STATE_OPENING
            self.schedule_update_ha_state()
            await self.toggleRelay()
            for i in range(0,10):
                await asyncio.sleep(1)
                if self._status == STATE_OPEN:
                    break
            log.critical("Garage door: {} did not open after 10 seconds".format(self.name))
            self._updateStatus()

        else:
            log.info("Could not open {} - State is {}".format(self.name, self._status))

            
    async def async_close_cover(self, **kwargs):
        if self._status == STATE_OPEN:
            self._status = STATE_CLOSING
            self.schedule_update_ha_state()
            await self.toggleRelay()
            for i in range(0,10):
                await asyncio.sleep(1)
                if self._status == STATE_CLOSED:
                    break
            log.critical("Garage door: {} did not close after 10 seconds".format(self.name))
            self._updateStatus()

        else:
            log.info("Could not close {} - State is {}".format(self.name, self._status))

            

    # @property
    # def assumed_state(self) -> bool:
    #     return self._zone._alarmPanel.is_initialized