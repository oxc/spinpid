from typing import Iterator

from spinpid.interfaces.ipmi.ipmitool import IPMITool
from spinpid.interfaces.sensor import TemperaturesSource, Temperature, MaxTemperatureSensor


class IPMIToolCPUSource(TemperaturesSource):
    def __init__(self, ipmitool: IPMITool, *sensors: str) -> None:
        super().__init__()
        self.ipmitool = ipmitool
        self.sensors = set(sensors)

    async def get_all_temperatures(self) -> Iterator[Temperature]:
        entries = await self.ipmitool.sdr_type('Temperature')
        return (
            Temperature(entry.value, label=entry.name)
            for entry in entries
            if entry.name in self.sensors
        )
