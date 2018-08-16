from .. import Temperature
from . import Disk, DiskSource, DiskError, MeanDiskTemperatureSource 
from .smart import parse_smart_temperature
from middlewared.client.client import Client
from middlewared.utils import Popen, run
import subprocess

c = Client()

try:
    from middlewared.common.smart.smartctl import get_smartctl_args
except ImportError:
    async def get_smartctl_args(devname):
        return c.call('disk._DiskService__get_smartctl_args', devname)

class FreenasDiskSource(DiskSource):
    def get_all_disk_names(self):
        # return all disks with smart enabled
        return (d['name'] for d in c.call('disk.query', [('togglesmart', '=', True)]))

    async def get_all_disks(self):
        return (FreenasDisk(d) for d in self.get_all_disk_names())

class FreenasDisk(Disk):
    async def get_temperature(self) -> Temperature:
        args = await get_smartctl_args(self.device)
        if not args:
            raise DiskError(f"Unable to determine smartctl args for disk {self.device}")
        p1 = await Popen(['smartctl', '--attributes', '--nocheck=standby'] + args, stdout=subprocess.PIPE)
        output = (await p1.communicate())[0].decode()
        temp = parse_smart_temperature(output)
        if not temp:
            raise DiskError(f"Unable to determine temperature for disk {self.device}")
        return Temperature(temp, self.device)

meanDiskTemperatureSource = MeanDiskTemperatureSource(FreenasDiskSource())
