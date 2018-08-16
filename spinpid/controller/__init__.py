from typing import Callable, Awaitable
from ..fancontrol import FanZone
from ..sensors import TemperatureSource, Temperature
from ..util import clamp
from .algorithm import Algorithm
from asyncio import sleep, CancelledError
import logging

logger = logging.getLogger(__name__)

class Controller:
    temperature_source: TemperatureSource
    algorithm: Algorithm
    interval: float # seconds
    min_duty: int
    max_duty: int

    last_temperature: Temperature
    last_duty: int

    def __init__(self, fan_zone: FanZone, 
            temperature_source: TemperatureSource,
            algorithm: Algorithm,
            interval: float,
            min_duty: int = 15, max_duty: int = 100) -> None:
        self.fan_zone = fan_zone
        self.temperature_source = temperature_source
        self.algorithm = algorithm
        self.interval = interval
        self.min_duty = min_duty
        self.max_duty = max_duty

        self.keep_running = True

    def calculate_duty(self, temp: float, current_duty: int) -> int:
        raw_duty = self.algorithm.calculate_duty(temp, current_duty)
        duty = clamp(raw_duty, self.min_duty, self.max_duty)
        logger.debug(f"[{self.fan_zone.zone_id}] Algorithm returned {raw_duty} -> {duty}")
        return duty

    async def setup(self) -> None:
        self.last_duty = await self.fan_zone.get_duty()

    async def run(self, cycle_callback: Callable[['Controller'], Awaitable] = None) -> None:
        try:
            duty = self.last_duty # from setup()
            while self.keep_running:
                # TODO: always get duty from fan zone?
                temp = await self.temperature_source.get_temperature()
                duty = self.calculate_duty(temp, duty)
                await self.fan_zone.set_duty(duty)
                
                self.last_temperature = temp
                self.last_duty = duty
                if cycle_callback is not None:
                    try:
                        await cycle_callback(self)
                    except CancelledError:
                        raise
                    except Exception as e:
                        logger.warn("Exception in controller cycle callback: %s", e, exc_info=True)
                        pass
                await sleep(self.interval)
        finally:
            await self.fan_zone.set_duty(self.max_duty)
