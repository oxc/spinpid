from __future__ import annotations

import asyncio
import logging
from asyncio import sleep, CancelledError, ensure_future, create_task
from datetime import datetime, timedelta
from itertools import chain
from typing import Callable, Awaitable, Optional

from .algorithm import Expression, AlgorithmContext
from .values import LastKnownValues
from ..interfaces import Interface, TearDown
from ..interfaces.fan import FanZone
from ..interfaces.sensor import Temperature, TemperatureSensor
from ..util import clamp
from ..util.asyncio import raise_exceptions

logger = logging.getLogger(__name__)

class Sensor:
    name: str

    temperature_sensor: TemperatureSensor

    interval: timedelta

    last_update: datetime

    last_temperature: Optional[Temperature] = None

    def __init__(self, name, temperature_sensor: TemperatureSensor, interval: timedelta,
                 last_known_values: LastKnownValues) -> None:
        self.name = name
        self.temperature_sensor = temperature_sensor
        self.interval = interval
        self.last_update = datetime.min
        self.last_known_values = last_known_values

    async def setup(self) -> TearDown:
        pass

    async def update(self) -> None:
        temperature = await self.temperature_sensor.get_temperature()
        self.last_temperature = temperature
        self.last_update = datetime.now()
        self.last_known_values.set_sensor_temperature(self.name, temperature)
        logger.debug(f"[{self.name}] Updated temperature to {temperature}°C")

    @property
    def needs_update(self) -> bool:
        return self.last_update + self.interval < datetime.now()

class FanController:

    def __init__(self, name: str,
                 fan_zone: FanZone,
                 algorithms: dict[str, Expression],
                 context: AlgorithmContext,
                 last_known_values: LastKnownValues) -> None:
        self.name = name
        self.fan_zone = fan_zone
        self.algorithms = algorithms
        self.context = context
        self.min_duty = context.min_duty
        self.max_duty = context.max_duty
        self.last_known_values = last_known_values

        self.keep_running = True

    def calculate_duty(self) -> int:
        raw_duties: dict[str, int] = {}
        highest_alg, highest_duty = None, -1
        for [alg_id, alg] in self.algorithms.items():
            raw_duty = alg.value()
            raw_duties[alg_id] = raw_duty
            if raw_duty > highest_duty:
                highest_alg, highest_duty = alg_id, raw_duty

        duty = clamp(highest_duty, self.min_duty, self.max_duty)
        logger.debug(f"[{self.name}] Algorithm {highest_alg} returned {highest_duty} -> {duty}")
        return duty

    async def setup(self) -> None:
        self.context.last_duty = await self.fan_zone.get_duty()

    async def update(self) -> None:
        duty = self.calculate_duty()
        self.context.last_duty = duty
        self.last_known_values.set_fan_duty(self.name, duty)
        await self.fan_zone.set_duty(duty)
        await self.fan_zone.update()


Interfaces = dict[str, Interface]
Sensors = dict[str, Sensor]
Fans = dict[str, FanController]


class Controller:
    interface_teardowns: dict[str, TearDown]

    def __init__(self, interfaces: Interfaces, sensors: Sensors, fans: Fans, values: LastKnownValues):
        self.interfaces = interfaces
        self.sensors = sensors
        self.fans = fans
        self.values = values

        self.keep_running = True

    def stop(self) -> None:
        self.keep_running = False

    async def setup(self) -> None:
        self.interface_teardowns = {
            iid: await setup for iid, setup in (
                (iid, ensure_future(interface.setup())) for iid, interface in self.interfaces.items()
            )
        }
        tasks = [asyncio.create_task(coro) for coro in chain(
            (fan.setup() for fan in self.fans.values()),
            (sensor.setup() for sensor in self.sensors.values()),
        )]
        await asyncio.wait(tasks)
        raise_exceptions(tasks, logger)

    async def update_sensors(self) -> None:
        tasks = [
            create_task(sensor.update(), name=f"Update sensor {sensor.name}")
            for sensor in self.sensors.values()
            if sensor.needs_update
        ]
        await asyncio.wait(tasks)
        raise_exceptions(tasks, logger)

    async def update_fans(self) -> None:
        tasks = [
            create_task(fan.update(), name=f"Update fan {fan.name}")
            for fan in self.fans.values()
        ]
        await asyncio.wait(tasks)
        raise_exceptions(tasks, logger)

    async def run(self, cycle_callback: Callable[['Controller'], Awaitable] = None) -> None:
        try:
            sleep_seconds = min(sensor.interval for sensor in self.sensors.values()).total_seconds()
            while self.keep_running:
                await self.update_sensors()
                # TODO: get changed sensors

                await self.update_fans()

                if cycle_callback is not None:
                    try:
                        await cycle_callback(self)
                    except CancelledError:
                        raise
                    except Exception as e:
                        logger.warning("Exception in controller cycle callback: %s", e, exc_info=True)
                        pass
                await sleep(sleep_seconds)
        finally:
            for iid, teardown in self.interface_teardowns.items():
                try:
                    await teardown()
                except Exception as e:
                    logger.warning("Exception in interface %s teardown: %s", iid, e, exc_info=True)
