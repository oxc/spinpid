from .. import Temperature
from . import Disk, DiskSource, DiskError, MeanDiskTemperatureSource 
from .smart import parse_smart_temperature
from middlewared.client.client import Client
from middlewared.common.camcontrol import camcontrol_list
from middlewared.common.smart.smartctl import get_smartctl_args
from middlewared.utils import Popen, run
import subprocess

c = Client()


class FreenasDiskSource(DiskSource):
    def get_all_disk_names(self):
        # return all disks with smart enabled
        return (d['name'] for d in c.call('disk.query', [('togglesmart', '=', True)]))

    async def get_all_disks(self):
        devices = await camcontrol_list()
        return (FreenasDisk(devname, devices) for devname in self.get_all_disk_names() if devname in devices)

class FreenasDisk(Disk):
    def __init__(self, devname, devices):
        super().__init__(devname)
        self.devices = devices

    async def get_temperature(self) -> Temperature:
        args = await get_smartctl_args(c, self.devices, self.device)
        if not args:
            raise DiskError(f"Unable to determine smartctl args for disk {self.device}")
        p1 = await Popen(['smartctl', '--attributes', '--nocheck=standby'] + args, stdout=subprocess.PIPE)
        output = (await p1.communicate())[0].decode()
        temp = parse_smart_temperature(output)
        if not temp:
            raise DiskError(f"Unable to determine temperature for disk {self.device}")
        return Temperature(temp, self.device)

meanDiskTemperatureSource = MeanDiskTemperatureSource(FreenasDiskSource())
