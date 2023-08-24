from middlewared.client import Client

from spinpid.interfaces.sensor import Temperature
from spinpid.interfaces.truenas.middleware import TrueNASClient
from spinpid.interfaces.disk import Disk, DiskTemperaturesSource, DiskError


class TrueNASDiskTemperaturesSource(DiskTemperaturesSource, TrueNASClient):

    def get_all_disk_names(self):
        # return all disks with smart enabled
        return (
            d['name'] for d in self.middleware.call('disk.query', [
            ('name', '!=', None),
            ('togglesmart', '=', True)
        ])
        )

    async def get_all_disks(self):
        devices = self.middleware.call("device.get_disks")
        return (
            TrueNASDisk(device_name, self.middleware)
            for device_name in self.get_all_disk_names()
            if device_name in devices
        )


class TrueNASDisk(Disk, TrueNASClient):
    def __init__(self, device_name: str, middleware: Client):
        super().__init__(device_name=device_name, middleware=middleware)

    async def get_temperature(self) -> Temperature:
        temp = self.middleware.call("disk.temperature", self.device_name, {'powermode': 'STANDBY'})
        if not temp:
            raise DiskError(f"Unable to determine temperature for disk {self.device_name}")
        return Temperature(temp, self.device_name)
