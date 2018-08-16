from typing import Iterator, Iterable, Tuple, Union, Type, TypeVar

InputTypes = Union[float, int, str]
T = TypeVar('T', bound='Temperature')

class Temperature(float):
    '''Single temperature measurement that contains its label'''

    def __new__(cls: Type[T], value: InputTypes, label: str) -> T:
        return super().__new__(cls, value) # type: ignore

    def __init__(self, value: float, label: str) -> None:
        super().__init__()
        self.label = label

    def __iter__(self) -> Iterator[Tuple[str, float]]:
        yield self.label, float(self)

class AggregatedTemperature(Temperature):
    '''Temperature value that combines multiple single temperature values to 
       form a new value (usually something like mean or median).'''

    def __new__(cls, value: InputTypes, aggregated_label: str, temperatures: Iterable[Temperature]) -> 'AggregatedTemperature':
        return super().__new__(cls, value, aggregated_label)

    def __init__(self, value: float, aggregated_label: str, temperatures: Iterable[Temperature]) -> None:
        super().__init__(value, aggregated_label)
        self.temperatures = temperatures

    def __iter__(self) -> Iterator[Tuple[str, float]]:
        yield from super().__iter__()
        for temp in self.temperatures:
            yield from temp

class SelectedTemperature(Temperature):
    '''Temperature value that selects one of multiple single temperature 
       values (usually the highest one).'''

    def __new__(cls, value: InputTypes, selected_label: str, temperatures: Iterable[Temperature]) -> 'SelectedTemperature':
        return super().__new__(cls, value, selected_label)

    def __init__(self, value: float, selected_label: str, temperatures: Iterable[Temperature]) -> None:
        super().__init__(value, selected_label)
        self.temperatures = temperatures

    def __iter__(self) -> Iterator[Tuple[str, float]]:
        # does not yield itself, since that's included in the following list anyway
        for temp in self.temperatures:
            yield from temp


class TemperatureSource:
    async def get_temperature(self) -> Temperature:
        raise NotImplementedError("Must be implemented by subclasses")
