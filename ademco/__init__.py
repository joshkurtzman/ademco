from asyncio.streams import StreamReader, StreamWriter
from asyncio.transports import Transport
from typing import Dict, List
import asyncio
import serial_asyncio
from serial import SerialException
from asyncio import CancelledError
import logging
import sys
import datetime
import traceback

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)

REFRESH_INTERVAL = 3600


class AdemcoError(Exception):
    def __init__(self, panelClass: "AlarmPanel"):
        # TODO LOG trace and status of module
        # traceback.print_exception(*exc_info)
        log.critical("AdemcoError - Restarting")
        panelClass.loop.create_task(panelClass.restart())


def twos_comp(val, bits):
    """compute the 2's complement of int value val"""
    if (val & (1 << (bits - 1))) != 0:  # if sign bit is set e.g., 8bit: 128-255
        val = val - (1 << bits)  # compute negative value
    return val


def checksum(s: str) -> str:
    tot = 0
    for l in s:
        tot = tot + ord(l)
    tot = ((tot % 256) * -1) % 256
    i = "%.2X" % (twos_comp(tot, 256))
    return i


class AlarmPanel:
    def __init__(self, config: dict, loop=asyncio.get_event_loop()) -> None:
        self.SERIAL_PORT = config.get("device", "/dev/ttyUSB0")
        self.BAUD_RATE = config.get("baud", "1200")

        #TODO Load last status instead of assume closed
        self._zones: Dict[int, Zone] = {}
        for z in range(1, 97):
            self._zones[z] = Zone(self, z)

        self._outputs: Dict[int, Output] = {}
        for o in range(1, 9):
            self._outputs[o] = Output(self, o)

        self._partitions: Dict[int, Partition] = {}
        self._partitionReport = None
        self.loop = loop
        self.reader: StreamReader = None
        self.writer: StreamWriter = None
        self.writeQueue = asyncio.Queue()
        self.is_initialized = False

        log.debug("Initializing Main")
        loop.create_task(self.main())

    async def restart(self):
        # reset everything on errrors
        self.reader = None
        self.writer = None
        self.is_initialized = False
        self.writeQueue = None
        self.loop.create_task(self.main())

    async def main(self):

        FirstLoop = True
        self.loop.create_task(self.monitorWriteQueue())
        self.loop.create_task(self.listen())
        while True:
            if not self.reader or not self.writer:
                if not self.SERIAL_PORT:
                    log.info("No serial port configured")
                    await asyncio.sleep(300)
                    continue

                log.debug(
                    "Connecting to: {}  Baud: {}".format(
                        self.SERIAL_PORT, self.BAUD_RATE
                    )
                )
                try:
                    (
                        self.reader,
                        self.writer,
                    ) = await serial_asyncio.open_serial_connection(
                        url=self.SERIAL_PORT, baudrate=self.BAUD_RATE
                    )
                    self.writer.write(b"\r\n")
                # except (SerialException, OSError, FileNotFoundError):
                except:
                    log.exception("Caught Serial Exception")
                    await asyncio.sleep(2)
                    break

                log.debug("Ademco Connected")
            if FirstLoop:
                self.loop.create_task(self.refreshStatus())
                FirstLoop = False
            await asyncio.sleep(60)

    async def refreshStatus(self):
        while True:

            self.zoneStatusRequest()
            await asyncio.sleep(3)
            #sometimes first attempt doesn't work.
            while not self.is_initialized:
                self.zoneStatusRequest()
                await asyncio.sleep(5)
            self.outputStatusRequest()
            await asyncio.sleep(2)
            self.zonePartitionRequest()

            # await asyncio.sleep(2)
            # self.armingStatusRequest()
            # TODO check that data has been received

            await asyncio.sleep(REFRESH_INTERVAL)

    @property
    def zones(self) -> List["Zone"]:
        return [i for i in self._zones.values()]

    def getZone(self, zoneId: int) -> "Zone":
        return self._zones.get(int(zoneId))

    def getOutput(self, id: int) -> "output":
        return self._outputs.get(int(id))

    async def listen(self):
        while True:
            if self.reader:
                try:
                    line = await self.reader.readline()
                    self.handleMessage(line)
                except CancelledError:
                    break
                except:
                    # traceback.print_exception(*exc_info)
                    log.exception("Listen function threw exception")
                    await asyncio.sleep(2)
            else:
                await asyncio.sleep(1)

    def sendCommand(self, command: str):
        message = bytes(command + checksum(command), "utf-8") + b"\r\n"
        self.writeQueue.put_nowait(message)

    async def monitorWriteQueue(self):
        while True:
            if self.writer:
                try:
                    i = await self.writeQueue.get()
                    log.debug("Sending Message: {}".format(i))
                    self.writer.write(i)
                    await self.writer.drain()
                    await asyncio.sleep(1)
                except CancelledError:
                    break
                except:
                    log.exception("Unexpected error in monitorWriteQueue:")
            else:
                await asyncio.sleep(2)

    def armAway(self, userCode):
        self.sendCommand(" ")

    def armHome(self, userCode):
        self.sendCommand(" ")

    def disam(self, userCode):
        self.sendCommand(" ")

    def armingStatusRequest(self):
        self.sendCommand("08as00")

    def zoneStatusRequest(self):
        self.sendCommand("08zs00")

    def zonePartitionRequest(self):
        self.sendCommand("08zp00")

    def outputStatusRequest(self):
        self.sendCommand("08cs00")

    def handleMessage(self, message: bytes):
        message = message.lstrip(
            b"P"
        )  # Remove Ps that occasionally get sent without newlines
        message = message.decode("ASCII")
        message = message.rstrip("\r\n")
        if not message:  # If the P was received without new line skip it silently
            return
        log.debug("Received Message: {} ".format(message))
        if not message[-2:] == checksum(message[:-2]):
            log.critical(
                "Received invalid checksum: {}, Calculated: {}".format(
                    message, checksum(message[:-2])
                )
            )
            return
        length = int(message[0:2], 16)  # convert overall packet length to int
        messageType = message[2:4]
        dataLen = (
            length - 8
        )  # length =  packetLength:2 + packetType:2 + reserved:2    Don't include checksum:2
        data = message[4 : 4 + dataLen]
        mapping = {
            "ZS": self.processZoneStatusReport,
            "ZP": self.processZonePartionReport,
            "CS": self.processOutputStatusReport,
            "AS": self.processArmingStatusReport,
            "NQ": self.processSystemEvent,
            "OK": self.processOK,
        }
        if messageType in mapping.keys():
            mapping[messageType](data)
        else:
            log.critical("Unhandled message type receieved:" + message)

    def processOK(self, data):
        # No need to do anything with OK
        pass

    def processZoneStatusReport(self, data):
        for z, s in enumerate(data):
            self._zones[z+1].proccessStatus(int(s))
            self.is_initialized = True

    def processArmingStatusReport(self, data):
        print("ArmingStatus:" + data)
        for p, s in enumerate(data):
            if not p in self._partitions.keys():
                self._partitions[p+1] = Partition(self, int(p+1), int(s))

    def processZonePartionReport(self, data):
        self._partitionReport = data

    def processOutputStatusReport(self, data):
        for o, s in enumerate(data):
            if s == "U":
                continue
            if not o + 1 in self._outputs.keys():
                self._outputs[o + 1] = Output(self, int(o + 1), s)

    def processSystemEvent(self, data):
        et = data[0:2]
        zoneOrUser = int(data[2:4], 16)+1
        # min = int(data[4:6])
        # hour = int(data[6:8])
        # day = int(data[8:10])
        # month = int(data[10:12])
        # time = datetime.time(min,hour)

        desc = ""

        if et == "00":
            desc = "Perimeter Alarm"

        # "01": "Entry/Exit Alarm",
        # "04": "Interior Follower Alarm",
        # "06": "Fire Alarm",
        # "07": "Audible Panic Alarm",
        # "08": "Silent Panic Alarm",
        # "09": "24-Hr. Auxiliary",
        # "0C": "Duress Alarm",
        # "0E": "Other Alarm Restores",
        # "0F": "RF Low Battery",
        # "10": "RF Low Battery Restore",
        # "15": "Arm-Stay/Home",
        # "16": "Disarm",
        # "18": "Arm",
        # "1A": "Low Battery",
        # "1B": "Low Battery Restore",
        # "1C": "AC Fail",
        # "1D": "AC Restore",
        # "20": "Alarm Cancel",
        # "23": "Day/Night Alarm",
        # "24": "Day/Night Restore",
        # "27": "Fail To Disarm",
        # "28": "Fail To Arm",

        elif et == "11":
            desc = "Other Trouble"
            self.getZone(zoneOrUser).trouble = True
        elif et == "12":
            desc = "Other Trouble Restore"
            self.getZone(zoneOrUser).trouble = False
        elif et == "21":
            desc = "Other Bypass"
            self.getZone(zoneOrUser).bypassed = True
        elif et == "22":
            desc = "Other Unbypass"
            self.getZone(zoneOrUser).bypassed = False
        elif et == "2B":
            desc = "Faults"
            self.getZone(zoneOrUser).opened = True
        elif et == "2C":
            desc = "FaultRestore"
            self.getZone(zoneOrUser).opened = False

        log.debug("Zone:{} - {}:{}".format(zoneOrUser, et, desc))

        # log.critical("Unhandled Device Type for system event" + data)


class Partition:
    def __init__(self, alarmPanel: AlarmPanel, partitionNum: int, status: str):
        self._alarmPanel = AlarmPanel
        self.partionNum: int = partitionNum
        self.armStatus: str = status

    def armed(self) -> bool:
        if self.armStatus in ["A", "H"]:
            return True
        else:
            return False

    def proccessStatus(self, status: str):
        if status not in ["A", "H", "D"]:
            log.critical("Invalid partition status received {}".format(status))
        if status != self.armStatus:
            self.armStatus = status
            # TODO trigger update notification


class Zone:
    def __init__(self, alarmPanel: AlarmPanel, zoneNum: int, zoneStatus:int= None) -> None:
        self._alarmPanel = alarmPanel
        self.zoneNum = zoneNum
        self.bitStatus = ["0","0","0","0"]
        self.callbackList = []
        if zoneStatus:
            self.proccessStatus(zoneStatus)  # binary form of status


    def proccessStatus(self, status: int):
        """Input is zone status from zone report"""
        """0-Closed, 1-Open, 2-Trouble, 4-Alarm, 8-Bypassed"""
        bs = list(format(int(status), "04b"))
        if not bs == self.bitStatus:
            self.bitStatus = bs
            #log.debug("Zone"+str(self.zoneNum)+str(self.bitStatus))
            self._updated()
    
    def _updated(self):
        for cb in self.callbackList:
            cb()
    
    def registerCallback(self, cb):
        self.callbackList.append(cb)

    @property
    def partionId(self) -> int:
        return self._alarmPanel._partitionReport[self.zoneNum - 1]

    @property
    def opened(self) -> bool:
        if self.bitStatus[3] == "1":
            return True
        return False
        

    @opened.setter
    def opened(self, val: bool):
        if val:
            self.bitStatus[3] = "1"
        else:
            self.bitStatus[3] = "0"
        self._updated()

    @property
    def closed(self) -> bool:
        if self.bitStatus[3] == "0":
            return True
        return False

    @closed.setter
    def closed(self, val: bool):
        if val:
            self.bitStatus[3] = "0"
        else:
            self.bitStatus[3] = "1"
        self._updated()

    @property
    def trouble(self) -> bool:
        if self.bitStatus[2] == "1":
            return True
        return False

    @trouble.setter
    def trouble(self, val: bool):
        if val:
            self.bitStatus[2] = "1"
        else:
            self.bitStatus[2] = "0"
        self._updated()

    @property
    def alarm(self) -> bool:
        if self.bitStatus[1] == "1":
            return True
        return False

    @alarm.setter
    def alarm(self, val: bool):
        if val:
            self.bitStatus[1] = "1"
        else:
            self.bitStatus[1] = "0"
        self._updated()

    @property
    def bypassed(self) -> bool:
        if self.bitStatus[0] == "1":
            return True
        return False

    @bypassed.setter
    def bypassed(self, val: bool):
        if val:
            self.bitStatus[0] = "1"
        else:
            self.bitStatus[0] = "0"
        self._updated()


class Output:
    def __init__(self, alarmPanel: AlarmPanel, outputId: int, status: int = 0) -> None:
        self._alarmPanel = alarmPanel
        self.outputId = outputId
        self._status = int(status)  # binary form of status

    @property
    def isOff(self) -> bool:
        if self._status == 0:
            return True
        return False

    @property
    def isOn(self) -> bool:
        if self._status == 1:
            return True
        return False

    def turnOn(self):
        c = "0Acn{:0>2}00".format(self.outputId)
        self._alarmPanel.sendCommand(c)
        self._status = 1

    def turnOff(self):
        c = "0Acf{:0>2}00".format(self.outputId)
        self._alarmPanel.sendCommand(c)
        self._status = 0


# loop= asyncio.get_event_loop()
# loop.set_debug(True)
# alarmpanel = AlarmPanel({},loop)
# loop.run_forever()
