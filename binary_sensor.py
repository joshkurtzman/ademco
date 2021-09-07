import homeassistant
from homeassistant.components.binary_sensor import BinarySensorEntity
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

log.debug("ademco LOADING BINARY SENSOR")


def setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: Callable[[Sequence[BinarySensorEntity], bool], None],
    discovery_info: Optional[DiscoveryInfoType] = None,
) -> None:
    entities = []
    panel = hass.data[DOMAIN]["panel"]
    config = hass.data[DOMAIN]["config"]

    for x in config.get("doors"):
        log.debug("ADEMCO" + str(x))
        entities.append(AdemcoZone(panel.getZone(x["id"]), x, "door"))

    for x in config.get("windows"):
        log.debug("ADEMCO" + str(x))
        entities.append(
            AdemcoZone(panel.getZone(x["id"]), x, "window")
        )
    for x in config.get("motions"):
        log.debug("ADEMCO" + str(x))
        entities.append(
            AdemcoZone(panel.getZone(x["id"]), x, "motion")
        )

    async_add_entities(entities)
    return True


class AdemcoZone(BinarySensorEntity):
    def __init__(
        self, zone: Zone, config: str, deviceClass: str, output: Output = None
    ) -> None:
        super.__init__
        self._zone = zone
        self._config = config
        self.deviceClass = deviceClass
        self._zone.registerCallback(self.schedule_update_ha_state)

        if self.deviceClass == "garage_door":
            if not output:
                raise Exception("Output is required for garage door")
            self.output = output

    @property
    def should_poll(self):
        return False

    @property
    def identifiers(self):
        return (DOMAIN, self.unique_id)


    @property
    def unique_id(self):
        return "{}.zone{}".format(DOMAIN,self._zone.zoneNum)

    def nameSuffix(self) -> str:
        map = {
            "door": " Door",
            "window": " Window",
            "garage_door": " Garage Door",
            "motion": " Motion",
        }
        return map.get(self.deviceClass, "")
    
    @property
    def extra_state_attributes(self):
        return {
                "bypassed":self._zone.bypassed, 
                "alarm":self._zone.alarm, 
                "trouble":self._zone.trouble }

    @property
    def name(self):
        return "{} {}".format(self._config.get("name"), self.nameSuffix())

    @property
    def is_on(self) -> bool:
        return self._zone.opened

    @property
    def device_class(self):
        """Return the device class."""
        return self.deviceClass
