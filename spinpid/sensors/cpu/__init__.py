from typing import AsyncIterator
from .. import TemperatureSource, Temperature, SelectedTemperature

class CPUSource:
    async def get_all_cpu_temperatures(self) -> AsyncIterator[float]:
        raise NotImplementedError("Must be implemented by subclasses")
        yield 0.0 # to make this an iterator

class MaxCPUTemperatureSource(TemperatureSource):
    def __init__(self, cpu_source: CPUSource) -> None:
        self.cpu_source = cpu_source

    async def get_temperature(self) -> Temperature:
        temps = [temp async for temp in self.cpu_source.get_all_cpu_temperatures()]
        max_temp = max(temps)
        single_temps = [temp for temp in temps if isinstance(temp, Temperature)]
        if not single_temps:
            return Temperature(max_temp, "Max CPU")
        else:
            return SelectedTemperature(max_temp, "Max System", single_temps)


    def get_label(self) -> str:
        return "CPU"
