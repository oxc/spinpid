from __future__ import annotations

import functools
import logging
from enum import IntEnum, Enum, unique
from typing import Collection, Optional, Iterator

from spinpid.interfaces.ipmi.ipmitool import IPMITool, IPMIError
from .. import TearDown, FanInterface
from ..fan import Fan, FanZone
from ...util.collections import defaultdict
from ...util.throttle import throttle

logger = logging.getLogger(__name__)


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


class IPMIFanZone(FanZone):
    fans_by_name: dict[str, Fan]
    _last_duty: Optional[int]

    def __init__(self, zone_id: ZoneId, interface: IPMIFanInterface) -> None:
        super().__init__(zone_name=zone_id.name)
        self.interface = interface
        self.zone_id = zone_id
        self.fans_by_name = defaultdict(Fan)
        self._last_duty = None

    @property
    def fans(self) -> Collection[Fan]:
        return self.fans_by_name.values()

    def __repr__(self) -> str:
        return f"<IPMIFanZone {self.name} fans={self.fans}>"

    async def get_duty(self) -> int:
        output = await self.interface.ipmitool.raw_read('0x30', '0x70', '0x66', '0', str(self.zone_id.value))
        return int(output, base=16)

    async def _do_set_duty(self, duty: int) -> None:
        await self.interface.ipmitool.raw('0x30', '0x70', '0x66', '1', str(self.zone_id.value), str(duty))

    async def update(self) -> None:
        await self.interface.update()

class IPMIFanInterface(FanInterface):
    zones_by_id: dict[ZoneId, IPMIFanZone]

    def __init__(self, dry_run: bool = False) -> None:
        super().__init__(dry_run=dry_run)
        self.ipmitool = IPMITool()
        self.zones_by_id = defaultdict(functools.partial(IPMIFanZone, interface=self))

    def get_fan_zone(self, channel: str, **kwargs) -> IPMIFanZone:
        if channel == 'cpu':
            return self.zones_by_id[ZoneId.CPU]
        if channel == 'peripheral':
            return self.zones_by_id[ZoneId.PERIPHERAL]
        raise ValueError(f"Invalid channel '{channel}', expected 'cpu' or 'peripheral'")

    @property
    def zones(self) -> Collection[IPMIFanZone]:
        return self.zones_by_id.values()

    def __repr__(self) -> str:
        return f"<IPMIFanControl zones={self.zones}>"

    def __str__(self) -> str:
        return 'Fan Zones: ' + ''.join('\n\t' + str(zone) for zone in self.zones)

    async def get_mode(self) -> FanMode:
        output = await self.ipmitool.raw_read('0x30', '0x45', '0')
        return FanMode(int(output))

    async def set_mode(self, mode: FanMode) -> None:
        if self.dry_run:
            logger.info("(dry-run) Would set fan mode to %s", mode)
        else:
            logger.info("Setting fan mode to %s", mode)
            await self.ipmitool.raw('0x30', '0x45', '1', str(mode.value))

    async def setup(self) -> TearDown:
        old_mode = await self.get_mode()
        await self.set_mode(FanMode.FULL)

        async def teardown() -> None:
            await self.set_mode(old_mode)

        return teardown

    @throttle(seconds=0.5)
    async def update(self) -> None:
        """Populates and updates all zones and fans with current values.

           NOTE: This method does not remove vanishing fans, should that ever happen."""

        fan_iterator = await self.ipmitool.sdr_type('Fan')
        for fan_name, zone_id, rpm in self._parse_sensors_fans(fan_iterator):
            zone = self.zones_by_id[zone_id]
            fan = zone.fans_by_name[fan_name]
            fan.rpm = rpm

    @staticmethod
    def _parse_sensors_fans(fan_iterator) -> Iterator[tuple[str, ZoneId, int]]:
        for fan in fan_iterator:
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

            fan_value = fan.value
            if fan_value is None:
                continue

            rpm = int(float(fan_value))
            if fan.unit != 'RPM':
                raise IPMIError(f"Unexpected unit for fan speed '{fan.unit}', expected 'RPM'")
            yield fan_name, zone_id, rpm
