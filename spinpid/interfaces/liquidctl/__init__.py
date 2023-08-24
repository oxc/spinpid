from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Union

import liquidctl

from spinpid.controller.config import ConfigError
from spinpid.interfaces import FanInterface, TearDown, FanZone, TemperatureSensor, SensorInterface
from spinpid.interfaces.fan import Fan, SingleFanZone
from spinpid.interfaces.sensor import Temperature
from spinpid.util.collections import defaultdict
from spinpid.util.throttle import throttle

logger = logging.getLogger(__name__)

LiquidCTLDevice = liquidctl.driver.base.BaseDriver

_re_fan_channel = re.compile(r"fan(\d+)")

_re_temp_value = re.compile(r"Temp sensor (\d+)")
_re_fan_value = re.compile(r"Fan (\d+) speed")

def find_liquidctl_device(address, name) -> LiquidCTLDevice:
    devices: list[LiquidCTLDevice] = list(liquidctl.find_liquidctl_devices())
    if not devices:
        raise ConfigError("No liquidctl devices found")
    if not address and not name:
        if len(devices) == 1:
            return devices[0]
        raise Exception("Found multiple liquidctl devices, please specify which one to use")
    matching_devices = [device for device in devices if
                        (not address or device.address == address)
                        and
                        (not name or name in device.description)]
    if not matching_devices:
        raise ConfigError("No matching liquidctl device found")
    if len(matching_devices) > 1:
        raise ConfigError("Found multiple matching liquidctl devices, please specify more narrowly")
    return matching_devices[0]


class LiquidCTL(FanInterface, SensorInterface):
    fans: dict[int, LiquidCTLFan]
    sensors: dict[int, LiquidCTLSensor]

    def __init__(self, address=None, name=None, dry_run=False):
        super().__init__(dry_run=dry_run)
        self.device = find_liquidctl_device(address, name)
        self.fans = defaultdict(lambda fan_id: LiquidCTLFan(self, fan_id))
        self.sensors = defaultdict(lambda sensor_id: LiquidCTLSensor(self, sensor_id))
        self._last_update = datetime.min

    async def setup(self) -> TearDown:
        # TODO: threadpool?

        self.device.connect()
        init = self.device.initialize()
        logger.info("Initialized liquidctl device %s: %s", self.device.description, init)

        async def teardown():
            self.device.disconnect()

        return teardown

    @throttle(seconds=0.5)
    async def update(self):
        self._last_update = datetime.now()
        status: list[(str, Union[int, float], str)] = self.device.get_status()
        for name, value, unit in status:
            if name.startswith("Temp sensor"):
                # ('Temp sensor 2', 33.92, '°C')
                match = _re_temp_value.match(name)
                if not match:
                    raise Exception(f"Unexpected temperature sensor name {name}")
                if unit != "°C":
                    raise Exception(f"Unexpected temperature unit {unit}")
                sensor_id = int(match.group(1))
                if sensor_id in self.sensors:
                    self.sensors[sensor_id].value = value
            elif name.startswith("Fan"):
                #  ('Fan 1 speed', 1307, 'rpm')
                match = _re_fan_value.match(name)
                if not match:
                    raise Exception(f"Unexpected fan name {name}")
                if unit != "rpm":
                    raise Exception(f"Unexpected fan unit {unit}")
                fan_id = int(match.group(1))
                if fan_id in self.fans:
                    fan = self.fans[fan_id]
                    fan.rpm = int(value)
                    fan._last_update = self._last_update

    def get_sensor(self, channel: int) -> TemperatureSensor:
        return self.sensors[channel]

    def get_fan_zone(self, channel: str) -> LiquidCTLFan:
        match = _re_fan_channel.match(channel)
        if not match:
            raise ConfigError(f"Invalid channel {channel}, expected fan[0-9]")
        chan_id = int(match.group(1))
        return self.fans[chan_id]


class LiquidCTLEntity:
    def __init__(self, interface: LiquidCTL, **kwargs):
        super().__init__(**kwargs)
        self.interface = interface

    async def update(self):
        # throttled, so just call for each entity
        await self.interface.update()

class LiquidCTLFan(LiquidCTLEntity, SingleFanZone):
    def __init__(self, interface: LiquidCTL, channel: int):
        super().__init__(interface=interface, name=f"Fan {channel}")
        self.interface = interface
        self.channel = channel
        self.fans = [self]
        self._last_duty = None

    async def get_duty(self) -> None:
        return None

    async def _do_set_duty(self, duty: int) -> None:
        self.interface.device.set_fixed_speed(f"fan{self.channel}", duty)

class LiquidCTLSensor(TemperatureSensor):
    value: float

    def __init__(self, interface: LiquidCTL, sensor_id: int):
        self.interface = interface
        self.sensor_id = sensor_id

    @property
    def temperature(self) -> Temperature:
        return Temperature(self.value, f"Sensor {self.sensor_id}")

    async def get_temperature(self) -> float:
        return self.temperature