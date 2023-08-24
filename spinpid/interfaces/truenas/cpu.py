from typing import Iterator

from spinpid.interfaces.sensor import TemperaturesSource, Temperature
from spinpid.interfaces.truenas.middleware import TrueNASClient


class TrueNASCPUTemperaturesSource(TemperaturesSource, TrueNASClient):
    async def get_all_temperatures(self) -> Iterator[Temperature]:
        temps: dict[str, float] = self.middleware.call('reporting.cpu_temperatures')
        return (
            Temperature(temp, f"CPU {idx}")
                for idx, temp in sorted(temps.items(), key=lambda x: int(x[0]))
        )
