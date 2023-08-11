from typing import AsyncIterator
from . import CPUSource, MaxCPUTemperatureSource

class FreenasCPUSource(CPUSource):
    async def get_all_cpu_temperatures(self) -> AsyncIterator[float]:
        temps = middleware.call('reporting.cpu_temperatures')
        for temp in values(temp):
            yield temp

maxCPUTemperatureSource = MaxCPUTemperatureSource(FreenasCPUSource())
