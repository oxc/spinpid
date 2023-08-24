from typing import TypeVar, Iterable
from math import fsum


def avg(*values, default=None):
    if not (len(values) == 1 and isinstance(values[0], Iterable)):
        return avg([values], default=default)
    values = list(values[0])
    count = len(values)
    if count == 0:
        return default
    return fsum(values) / count


T = TypeVar('T', int, float)


def clamp(value: T, min_value: T, max_value: T) -> T:
    return min_value if value < min_value else max_value if value > max_value else value
