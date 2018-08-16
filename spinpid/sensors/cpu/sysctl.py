from typing import AsyncIterator
from . import CPUSource, MaxCPUTemperatureSource
import sysctl

class SysctlCPUSource(CPUSource):
    async def get_all_cpu_temperatures(self) -> AsyncIterator[float]:
        ncpus = sysctl.filter("hw.ncpu")[0].value
        for cpu in range(ncpus):
            kelvin10 = sysctl.filter(f"dev.cpu.{cpu}.temperature")[0].value
            celsius = (kelvin10-2731.5) // 10
            yield celsius

maxCPUTemperatureSource = MaxCPUTemperatureSource(SysctlCPUSource())
