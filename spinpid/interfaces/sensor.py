from abc import ABC, abstractmethod
from math import fsum
from typing import Iterator, Iterable, Tuple, Union, Type, TypeVar

InputTypes = Union[float, int, str]
T = TypeVar('T', bound='Temperature')


class Temperature(float):
    """Single temperature measurement that contains its label"""

    def __new__(cls: Type[T], value: InputTypes, label: str) -> T:
        return super().__new__(cls, value)  # type: ignore

    def __init__(self, value: float, label: str) -> None:
        super().__init__()
        self.label = label

    def __iter__(self) -> Iterator[Tuple[str, float]]:
        yield self.label, float(self)


class AggregatedTemperature(Temperature):
    """Temperature value that combines multiple single temperature values to
       form a new value (usually something like mean or median)."""

    def __new__(cls, value: InputTypes, aggregated_label: str,
                temperatures: Iterable[Temperature]) -> 'AggregatedTemperature':
        return super().__new__(cls, value, aggregated_label)

    def __init__(self, value: float, aggregated_label: str, temperatures: Iterable[Temperature]) -> None:
        super().__init__(value, aggregated_label)
        self.temperatures = temperatures

    def __iter__(self) -> Iterator[Tuple[str, float]]:
        yield from super().__iter__()
        for temp in self.temperatures:
            yield from temp


class SelectedTemperature(Temperature):
    """Temperature value that selects one of multiple single temperature
       values (usually the highest one)."""

    def __new__(cls, value: InputTypes, selected_label: str,
                temperatures: Iterable[Temperature]) -> 'SelectedTemperature':
        return super().__new__(cls, value, selected_label)

    def __init__(self, value: float, selected_label: str, temperatures: Iterable[Temperature]) -> None:
        super().__init__(value, selected_label)
        self.temperatures = temperatures

    def __iter__(self) -> Iterator[Tuple[str, float]]:
        # does not yield itself, since that's included in the following list anyway
        for temp in self.temperatures:
            yield from temp


class TemperaturesSource(ABC):
    @abstractmethod
    async def get_all_temperatures(self) -> Iterator[Temperature]:
        raise NotImplementedError("Must be implemented by subclasses")


class TemperatureSensor(ABC):
    @abstractmethod
    async def get_temperature(self) -> Temperature:
        raise NotImplementedError("Must be implemented by subclasses")


class MaxTemperatureSensor(TemperatureSensor):
    label: str

    def __init__(self, temps_source: TemperaturesSource, label: str, max_label: str = None) -> None:
        self.temps_source = temps_source
        self.label = label
        self.max_label = max_label or f"Max {label}"

    async def get_temperature(self) -> Temperature:
        temps = list(await self.temps_source.get_all_temperatures())
        max_temp = max(temps)
        single_temps = [temp for temp in temps if isinstance(temp, Temperature)]
        if not single_temps:
            return Temperature(max_temp, self.max_label)
        else:
            return SelectedTemperature(max_temp, self.max_label, single_temps)


class MeanTemperatureSensor(TemperatureSensor):
    def __init__(self, temps_source: TemperaturesSource, label: str = "⌀") -> None:
        self.temps_source = temps_source
        self.label = label

    async def get_temperature(self) -> Temperature:
        temps = list(await self.temps_source.get_all_temperatures())
        s = fsum(temps)
        count = len(temps)
        if count == 1:
            return temps[0]
        mean = s / count
        return AggregatedTemperature(mean, self.label, temps)
