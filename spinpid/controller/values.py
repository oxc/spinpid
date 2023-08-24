from __future__ import annotations

from typing import Iterable

__all__ = ["LastKnownValues"]

from spinpid.interfaces.sensor import Temperature
from spinpid.util.table import Value as TableValue


class TemperatureValue:
    def __init__(self, value: Temperature) -> None:
        self.value = value
        self.was_displayed = False

class FanDutyValue:
    def __init__(self, value: int) -> None:
        self.value = value
        self.was_displayed = False

class LastKnownValues:
    sensor_temperature_values: dict[str, TemperatureValue]
    fan_duty_values: dict[str, FanDutyValue]

    def __init__(self, sensor_names: Iterable[str], fan_names: Iterable[str]) -> None:
        self.sensor_temperature_values = {name: None for name in sensor_names}
        self.fan_duty_values = {name: None for name in fan_names}

    def set_fan_duty(self, fan_id: str, duty: int | float) -> None:
        if fan_id not in self.fan_duty_values:
            raise ValueError(f"Unknown fan id {fan_id}")
        self.fan_duty_values[fan_id] = FanDutyValue(duty)

    def set_sensor_temperature(self, sensor_id: str, temperature: Temperature) -> None:
        if sensor_id not in self.sensor_temperature_values:
            raise ValueError(f"Unknown sensor id {sensor_id}")
        self.sensor_temperature_values[sensor_id] = TemperatureValue(temperature)

    def get_sensor_display_values(self) -> Iterable[tuple[str, TableValue]]:
        for sensor_id, value in self.sensor_temperature_values.items():
            if value is not None:
                stale = value.was_displayed
                value.was_displayed = True
                yield sensor_id, TableValue(value.value, stale=stale)

    def get_fan_display_values(self) -> Iterable[tuple[str, TableValue]]:
        for fan_id, value in self.fan_duty_values.items():
            if value is not None:
                stale = value.was_displayed
                value.was_displayed = True
                yield fan_id, TableValue(f"{value.value}%", stale=stale)