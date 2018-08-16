from typing import AsyncIterator, Iterable
from . import CPUSource, MaxCPUTemperatureSource
from .. import Temperature
from ...util.ipmitool import IPMITool

class IPMIToolCPUSource(CPUSource):
    def __init__(self, *sensors: str) -> None:
        super().__init__()
        self.ipmitool = IPMITool()
        self.sensors = set(sensors)

    async def get_all_cpu_temperatures(self) -> AsyncIterator[float]:
        entries = self.ipmitool.sdr_type('Temperature')
        async for entry in entries:
            if entry.name in self.sensors:
                yield Temperature(entry.value, label=entry.name)

maxSystemTemperatureSource = MaxCPUTemperatureSource(IPMIToolCPUSource("CPU Temp", "PCH Temp"))
