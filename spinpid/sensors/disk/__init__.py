from typing import AsyncIterator, Iterator
from math import fsum
from asyncio import as_completed, ensure_future
from .. import TemperatureSource, Temperature, AggregatedTemperature

class NoActiveDisksError(Exception):
    pass

class DiskError(Exception):
    pass

class Disk:
    def __init__(self, device):
        self.device = device

    async def get_temperature(self) -> Temperature:
        raise NotImplementedError("Must be implemented by subclasses")

    def __str__(self):
        return "<Disk " + self.device + ">"

class DiskSource:
    async def get_all_disks(self) -> Iterator[Disk]:
        raise NotImplementedError("Must be implemented by subclasses")

    async def get_all_disk_temperatures(self) -> AsyncIterator[Temperature]:
        disks = list(await self.get_all_disks())
        if len(disks) == 0:
            raise NoActiveDisksError("Found no active disks, unable to determine temperature")
        fs = []
        for disk in disks:
            fs.append(ensure_future(disk.get_temperature()))
        for temp in fs:
            yield await temp

class MeanDiskTemperatureSource(TemperatureSource):
    def __init__(self, disk_source: DiskSource) -> None:
        self.disk_source = disk_source

    async def get_temperature(self) -> AggregatedTemperature:
        temps = [t async for t in self.disk_source.get_all_disk_temperatures()]
        s = fsum(temps)
        mean = s / len(temps)
        return AggregatedTemperature(mean, "⌀", temps)
