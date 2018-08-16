from typing import Dict, List, Collection, Optional
from . import FanControl, FanZone, Fan
from ..util.ipmitool import IPMITool, IPMIError
from ..util.collections import defaultdict
from middlewared.utils import Popen, run
from enum import IntEnum, Enum, unique
from io import StringIO
import functools
import logging
import subprocess

logger = logging.getLogger(__name__)

async def get_fan_control(dry_run: bool = False) -> FanControl:
    fctl = IPMIFanControl(dry_run = dry_run)
    await fctl.update()
    return fctl

ipmitool = IPMITool()

@unique
class ZoneId(IntEnum):
    CPU = 0
    PERIPHERAL = 1

@unique
class FanMode(Enum):
    STANDARD = 0
    FULL = 1
    OPTIMAL = 2
    HEAVY_IO = 4

class IPMIFan(Fan):
    rpm: int

    async def get_rpm(self) -> int:
        return self.rpm

    def __repr__(self) -> str:
        return f"<IPMIFan {self.name} @ {self.rpm} RPM>"

    def __str__(self) -> str:
        return f"{self.name} @ {self.rpm} RPM"

class IPMIFanZone(FanZone[ZoneId, IPMIFan]):
    fans_by_name: Dict[str, IPMIFan]
    _last_duty: Optional[int]

    @property
    def fans(self) -> Collection[IPMIFan]:
        return self.fans_by_name.values()

    def get_fan(self, fan_name: str) -> IPMIFan:
        return self.fans_by_name[fan_name]

    def __init__(self, zone_id: ZoneId, dry_run: bool = False) -> None:
        super().__init__(zone_id)
        self.fans_by_name = defaultdict(IPMIFan)
        self.dry_run = dry_run
        self._last_duty = None

    def __repr__(self) -> str:
        return f"<IPMIFanZone {self.zone_id.name} fans={self.fans}>"

    def __str__(self) -> str:
        return f"Zone {self.zone_id.name}: " + ''.join('\n\t\t' + str(fan) for fan in self.fans)

    async def get_duty(self) -> int:
        output = await ipmitool.raw_read('0x30', '0x70', '0x66', '0', str(self.zone_id.value))
        return int(output, base=16)

    async def set_duty(self, duty: int, force: bool = False) -> None:
        assert 0 <= duty <= 100
        if not force and duty == self._last_duty:
            logger.debug("[%s] %sDuty is already at %d", self.zone_id, "(dry-run) " if self.dry_run else "", duty)
            return

        if self.dry_run:
            logger.info("[%s] (dry-run) Would set duty to %d", self.zone_id, duty)
        else:
            logger.debug("[%s] Setting duty to %d", self.zone_id, duty)
            await ipmitool.raw('0x30', '0x70', '0x66', '1', str(self.zone_id.value), str(duty))
        self._last_duty = duty

class IPMIFanControl(FanControl[FanMode, ZoneId, IPMIFanZone]):
    zones_by_id: Dict[ZoneId, IPMIFanZone]
    
    @property
    def zones(self) -> Collection[IPMIFanZone]:
        return self.zones_by_id.values()

    def get_zone(self, zone_id: ZoneId) -> IPMIFanZone:
        return self.zones_by_id[zone_id]

    def __init__(self, dry_run: bool = False) -> None:
        super().__init__()
        self.zones_by_id = defaultdict(functools.partial(IPMIFanZone, dry_run=dry_run))
        self.dry_run = dry_run

    def __repr__(self) -> str:
        return f"<IPMIFanControl zones={self.zones}>"

    def __str__(self) -> str:
        return 'Fan Zones: ' + ''.join('\n\t' + str(zone) for zone in self.zones)

    async def get_mode(self) -> FanMode:
        output = await ipmitool.raw_read('0x30', '0x45', '0')
        return FanMode(int(output))

    async def set_mode(self, mode: FanMode) -> None:
        if self.dry_run:
            logger.info("(dry-run) Would set fan mode to %s", mode)
        else:
            logger.info("Setting fan mode to %s", mode)
            await ipmitool.raw('0x30', '0x45', '1', str(mode.value))

    async def set_manual_mode(self) -> FanMode:
        current_mode = await self.get_mode()
        await self.set_mode(FanMode.FULL)
        return current_mode

    async def update(self) -> None:
        '''Populates and updates all zones and fans with current values.

           NOTE: This method does not remove vanishing fans, should that ever happen.'''

        fan_iterator = ipmitool.sdr_type('Fan')
        async for fan_name, zone_id, rpm in self._parse_sensors_fans(fan_iterator):
            zone = self.zones_by_id[zone_id]
            fan = zone.fans_by_name[fan_name]
            fan.rpm = rpm

    @staticmethod
    async def _parse_sensors_fans(fan_iterator):
        async for fan in fan_iterator:
            fan_name = fan.name
            if len(fan_name) != 4:
                raise IPMIError(f"Unexpected fan name '{fan_name}', expected FAN[A-Z] or FAN[1-9]")
            idx = fan_name[3]
            if 'A' <= idx <= 'Z':
                zone_id = ZoneId.PERIPHERAL
            elif '0' <= idx <= '9':
                zone_id = ZoneId.CPU
            else:
                raise IPMIError(f"Unexpected fan name '{fan_name}', expected FAN[A-Z] or FAN[1-9]")

            rpm = int(float(fan.value))
            if fan.unit != 'RPM':
                raise IPMIError(f"Unexpected unit for fan speed '{fan.unit}', expected 'RPM'")
            yield (fan_name, zone_id, rpm)


