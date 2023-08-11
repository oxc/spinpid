from .. import Temperature
from . import Disk, DiskSource, DiskError, MeanDiskTemperatureSource 
from .smart import parse_smart_temperature
from middlewared.client import Client
import asyncio

middleware = Client()

class FreenasDiskSource(DiskSource):
    def get_all_disk_names(self):
        # return all disks with smart enabled
        return (d['name'] for d in middleware.call('disk.query', [
                ('name', '!=', None),
                ('togglesmart', '=', True)
        ]))

    async def get_all_disks(self):
        devices = middleware.call("device.get_disks")
        return (FreenasDisk(devname) for devname in self.get_all_disk_names() if devname in devices)

class FreenasDisk(Disk):
    def __init__(self, devname):
        super().__init__(devname)

    async def get_temperature(self) -> Temperature:
        temp = middleware.call("disk.temperature", self.device, { 'powermode': 'STANDBY' })
        if not temp:
            raise DiskError(f"Unable to determine temperature for disk {self.device}")
        return Temperature(temp, self.device)

meanDiskTemperatureSource = MeanDiskTemperatureSource(FreenasDiskSource())
