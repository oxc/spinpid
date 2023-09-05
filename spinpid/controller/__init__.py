from __future__ import annotations

import asyncio
import logging
from asyncio import sleep, CancelledError, ensure_future, create_task
from datetime import timedelta
from graphlib import TopologicalSorter
from itertools import chain
from typing import Callable, Awaitable, Optional, Iterable, Generator

from .algorithm import Expression, AlgorithmContext
from .values import LastKnownValues
from ..interfaces import Interface, TearDown
from ..interfaces.fan import FanZone
from ..interfaces.sensor import Temperature, TemperatureSensor
from ..util import clamp
from ..util.asyncio import raise_exceptions
from ..util.table import LabelledValue, LabelledValueGroup, Value as TableValue

logger = logging.getLogger(__name__)

class PubSubValue:
    def __init__(self, name: str, **kwargs):
        super().__init__(**kwargs)
        self.name = name
        self.needs_update = True
        self.subscribers: set[PubSubValue] = set()

    def subscribe(self, subscriber: PubSubValue):
        self.subscribers.add(subscriber)

    def publish_value_update(self, needs_update: bool = False):
        self.needs_update = needs_update
        for subscriber in self.subscribers:
            logger.debug(f"[{self.name}] Publishing update to {subscriber.name}")
            subscriber.publish_value_update(needs_update=True)


class Sensor(PubSubValue):
    temperature_sensor: TemperatureSensor

    interval: timedelta

    last_temperature: Optional[Temperature] = None

    def __init__(self, name, temperature_sensor: TemperatureSensor,
                 last_known_values: LastKnownValues,
                 interval: timedelta, show_single_values: bool) -> None:
        super().__init__(name=name)
        self.temperature_sensor = temperature_sensor
        self.last_known_values = last_known_values
        self.interval = interval
        self.show_single_values = show_single_values

    async def setup(self) -> TearDown:
        # As a quick fix update in setup to ensure that sensors have a last value. We can do better than that.
        await self.update()

        async def teardown():
            pass
        return teardown

    async def update(self) -> None:
        temperature = await self.temperature_sensor.get_temperature()
        self.last_temperature = temperature
        self.last_known_values.set_sensor_temperature(self.name, temperature)
        logger.debug(f"[Sensor {self.name}] Updated temperature to {temperature}°C")
        self.publish_value_update()

    async def run(self):
        while True:
            await self.update()
            await sleep(self.interval.total_seconds())

    def create_task(self):
        return create_task(self.run(), name=f"Update sensor {self.name}")

    def get_log_state(self) -> Iterable[LabelledValue]:
        value = self.last_known_values.sensor_temperature_values[self.name]
        if value is not None:
            stale = value.was_displayed
            value.was_displayed = True
            temp = value.value
            if self.show_single_values:
                for label, temp in temp:
                    yield label, TableValue(f"{temp}", stale=stale)
            else:
                yield temp.label, TableValue(f"{temp}", stale=stale)

class FanAlgorithm(PubSubValue):
    def __init__(self, name: str, fan_name: str, expression: Expression) -> None:
        super().__init__(name=name)
        self.fan_name = fan_name
        self.expression = expression

        self.referenced_sensors = frozenset(expression.referenced_sensors or ())
        self.referenced_fans = frozenset(expression.referenced_fans or ())

        self._value = None

    def value(self):
        if self.needs_update:
            self._value = self.expression.value()
            logger.debug(f"[Algorithm {self.fan_name}/{self.name}] Update value {self._value}")
            self.publish_value_update()
        else:
            logger.debug(f"[Algorithm {self.fan_name}/{self.name}] Returning cached value {self._value}")
        return self._value


class FanController(PubSubValue):

    def __init__(self, name: str,
                 fan_zone: FanZone,
                 algorithms: frozenset[FanAlgorithm],
                 context: AlgorithmContext,
                 last_known_values: LastKnownValues) -> None:
        super().__init__(name=name)
        self.fan_zone = fan_zone
        self.algorithms = algorithms
        self.context = context
        self.min_duty = context.min_duty
        self.max_duty = context.max_duty
        self.last_known_values = last_known_values

        self.keep_running = True

    def calculate_duty(self) -> int:
        highest_alg, highest_duty = None, -1
        for alg in self.algorithms:
            raw_duty = alg.expression.value()
            if raw_duty > highest_duty:
                highest_alg, highest_duty = alg, raw_duty

        duty = clamp(highest_duty, self.min_duty, self.max_duty)
        logger.debug(f"[Fan {self.name}] Algorithm {highest_alg.name} returned {highest_duty} -> {duty}")
        return duty

    async def setup(self) -> None:
        self.context.last_duty = await self.fan_zone.get_duty()

    async def update(self) -> None:
        duty = self.calculate_duty()
        self.context.last_duty = duty
        self.last_known_values.set_fan_duty(self.name, duty)
        await self.fan_zone.set_duty(duty)
        await self.fan_zone.update()
        self.publish_value_update()

    def get_log_state(self) -> Iterable[LabelledValue]:
        value = self.last_known_values.fan_duty_values[self.name]
        if value is not None:
            stale = value.was_displayed
            value.was_displayed = True
            yield 'Duty', TableValue(f"{value.value}%", stale=stale)
            for fan in self.fan_zone.fans:
                yield fan.name, TableValue(f"{fan.rpm}", stale=False)

Interfaces = dict[str, Interface]
Sensors = dict[str, Sensor]
Fans = dict[str, FanController]

def sorted_fan_groups(fans: Fans) -> Generator[frozenset[FanController]]:
    ts = TopologicalSorter({
        fan_id: { fan for alg in fan.algorithms for fan in alg.referenced_fans } for fan_id, fan in fans.items()
    })
    ts.prepare()
    while ts.is_active():
        fan_ids = ts.get_ready()
        fan_group = [fans[fan_id] for fan_id in fan_ids]
        yield frozenset(fan_group)
        ts.done(*fan_ids)


class Controller:
    interface_teardowns: dict[str, TearDown]

    def __init__(self, interfaces: Interfaces, sensors: Sensors, fans: Fans, last_known_values: LastKnownValues):
        self.interfaces = interfaces
        self.sensors = sensors
        self.fans = fans
        self.last_known_values = last_known_values

        self.fans_ordered = tuple(sorted_fan_groups(fans))
        logger.info("Will update fans in this order: %r", self.fans_ordered)

        self.keep_running = True

        for fan in fans.values():
            for alg in fan.algorithms:
                for sensor_id in alg.referenced_sensors:
                    sensors[sensor_id].subscribe(alg)
                for fan_id in alg.referenced_fans:
                    fans[fan_id].subscribe(alg)
                alg.subscribe(fan)

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

    async def update_fans(self) -> None:
        for group_id, fan_group in enumerate(self.fans_ordered):
            pending_fans = [fan for fan in fan_group if fan.needs_update]
            if not pending_fans:
                logger.debug('No fans need updating in Fan Group %d', group_id)
                continue

            tasks = [
                create_task(fan.update(), name=f"Update fan {fan.name}")
                for fan in pending_fans
            ]
            await asyncio.wait(tasks)
            raise_exceptions(tasks, logger)

    async def run(self, cycle_callback: Callable[['Controller'], Awaitable] = None) -> None:
        try:
            sensor_update_tasks = [sensor.create_task() for sensor in self.sensors.values()]
            sleep_seconds = min(sensor.interval for sensor in self.sensors.values()).total_seconds()
            while self.keep_running:
                raise_exceptions(sensor_update_tasks, logger)

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

    def get_log_state(self) -> Iterable[LabelledValueGroup]:
        for sensor in self.sensors.values():
            yield sensor.name, sensor.get_log_state()
        for fan in self.fans.values():
            yield f"Fan {fan.name}", fan.get_log_state()