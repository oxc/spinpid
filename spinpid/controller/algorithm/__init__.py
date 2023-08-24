from __future__ import annotations

from typing import Union, Optional

from .expression import Static, Expression
from ..values import LastKnownValues
from ...util import clamp

Value = Union[int, float, Expression]

class SensorValue(Expression):
    referenced_fans = frozenset()

    def __init__(self, sensor_id: str, last_known_values: LastKnownValues) -> None:
        if sensor_id not in last_known_values.sensor_temperature_values:
            raise ValueError(f"Unknown sensor {sensor_id}")
        self.sensor_id = sensor_id
        self.last_known_values = last_known_values

        self.referenced_sensors = frozenset((sensor_id,))

    def value(self) -> int | float:
        value = self.last_known_values.sensor_temperature_values[self.sensor_id]
        if value is None:
            raise ValueError(f"No last known temperature value for sensor {self.sensor_id}")
        return value.value

    def __str__(self):
        return f"sensors.{self.sensor_id}"


class FanDutyValue(Expression):
    referenced_sensors = frozenset()

    def __init__(self, fan_id: str, last_known_values: LastKnownValues) -> None:
        if fan_id not in last_known_values.fan_duty_values:
            raise ValueError(f"Unknown fan {fan_id}")
        self.fan_id = fan_id
        self.last_known_values = last_known_values

        self.referenced_fans = frozenset((fan_id,))

    def value(self) -> int | float:
        value = self.last_known_values.fan_duty_values[self.fan_id]
        if value is None:
            raise ValueError(f"No last known duty value for fan {self.fan_id}")
        return value.value

    def __str__(self):
        return f"fans.{self.fan_id}"


class AlgorithmContext:
    PLACEHOLDER: 'AlgorithmContext' = None

    last_duty: Optional[int] = None

    def __init__(self, min_duty: int = None, max_duty: int = None) -> None:
        self.min_duty = min_duty or 15
        self.max_duty = max_duty or 100

    def __repr__(self):
        return f"AlgorithmContext(min_duty={self.min_duty}, max_duty={self.max_duty})"

    def __str__(self):
        return repr(self)

class Algorithm(Expression):
    def __init__(self, expression: Expression, context: AlgorithmContext) -> None:
        if expression is None:
            raise ValueError(f"{self.__class__.__name__} must be created with expression")
        if context is None:
            raise ValueError(f"{self.__class__.__name__} must be created with context")

        self.expression = expression
        self.context = context

        self.referenced_fans = expression.referenced_fans
        self.referenced_sensors = expression.referenced_sensors

        self.min_duty = context.min_duty
        self.max_duty = context.max_duty


class Polynomial(Algorithm):
    poly_degree: int

    def __init__(self, expression: Expression, start_temperature: float, full_duty_temperature: float,
                 context: AlgorithmContext = AlgorithmContext.PLACEHOLDER) -> None:
        super().__init__(expression=expression, context=context)
        self.start_temperature = start_temperature
        self.factor = (context.max_duty - context.min_duty) / pow(full_duty_temperature - start_temperature,
                                                                  self.poly_degree)

    def value(self) -> int:
        value = self.expression.value()
        if value < self.start_temperature:
            return self.min_duty
        raw = int(pow(value - self.start_temperature, self.poly_degree) * self.factor) + self.min_duty
        return clamp(raw, self.min_duty, self.max_duty)

    def __str__(self):
        return f"""{self.__class__.__name__}({self.expression
        }, start_temperature={self.start_temperature
        }, factor={self.factor
        }, min_duty={self.min_duty
        }, max_duty={self.max_duty})"""


class Linear(Polynomial):
    poly_degree = 1


class Quadratic(Polynomial):
    poly_degree = 2


class LinearDecrease(Algorithm):
    def __init__(self, expression: Expression, max_decrease: int = 1,
                 context: AlgorithmContext = AlgorithmContext.PLACEHOLDER) -> None:
        super().__init__(expression=expression, context=context)
        self.max_decrease = max_decrease
        self._min_duty = 0

    def value(self) -> int:
        duty = self.expression.value()
        if duty < self._min_duty:
            self._min_duty -= self.max_decrease
            return self._min_duty
        else:
            self._min_duty = duty
            return duty

    def __str__(self):
        return f"LinearDecrease({self.expression}, max_decrease={self.max_decrease})"
