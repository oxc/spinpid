import asyncio
import logging
from asyncio import ensure_future, create_task
from typing import Iterator, AsyncIterator

from .sensor import TemperaturesSource, Temperature
from ..util.asyncio import raise_exceptions

logger = logging.getLogger(__name__)

class NoActiveDisksError(Exception):
    pass


class DiskError(Exception):
    pass


class Disk:
    def __init__(self, device_name: str, **kwargs):
        super().__init__(**kwargs)
        self.device_name = device_name

    async def get_temperature(self) -> Temperature:
        raise NotImplementedError("Must be implemented by subclasses")

    def __str__(self):
        return "<Disk " + self.device_name + ">"


class DiskTemperaturesSource(TemperaturesSource):
    async def get_all_disks(self) -> Iterator[Disk]:
        raise NotImplementedError("Must be implemented by subclasses")

    async def get_all_temperatures(self) -> Iterator[Temperature]:
        disks = list(await self.get_all_disks())
        if not disks:
            raise NoActiveDisksError("Found no active disks, unable to determine temperature")
        tasks = [create_task(disk.get_temperature()) for disk in disks]
        await asyncio.wait(tasks)
        raise_exceptions(tasks, logger)

        temps = [f.result() for f in tasks]
        temps.sort(key=lambda t: t.label)
        return iter(temps)
