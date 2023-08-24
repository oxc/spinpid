from __future__ import annotations

from math import prod
from typing import Type, Optional, Union

Value = Union[int, float, Type['Expression']]


class Expression:
    referenced_sensors: Optional[frozenset[str]]
    referenced_fans: Optional[frozenset[str]]

    @staticmethod
    def wrap(value: Value) -> Expression:
        if isinstance(value, Expression):
            return value
        return Static(value)

    def value(self) -> int | float:
        raise NotImplementedError("Subclasses need to implement this")

    def __add__(self, other: Value) -> Expression:
        return Sum(self, Expression.wrap(other))

    def __mul__(self, other: Value) -> Expression:
        return Product(self, Expression.wrap(other))

    def __neg__(self) -> Expression:
        return Product(self, Static(-1))

    def __sub__(self, other: Value) -> Expression:
        return Sum(self, -Expression.wrap(other))


class Composite(Expression):
    operator: str

    def __init__(self, *operands: Expression) -> None:
        self.operands = operands
        self.referenced_sensors = frozenset(s for e in operands for s in e.referenced_sensors)
        self.referenced_fans = frozenset(f for e in operands for f in e.referenced_fans)

    def __str__(self):
        joiner = f" {self.operator} "
        return f"({joiner.join(str(operand) for operand in self.operands)})"

    def __repr__(self):
        return f"{self.__class__.__name__}({', '.join(repr(operand) for operand in self.operands)})"


class Sum(Composite):
    operator = '+'

    def value(self) -> int | float:
        return sum(operand.value() for operand in self.operands)

    def __add__(self, other: Value):
        return Sum(*self.operands, Expression.wrap(other))

    def __str__(self):
        return f"({' + '.join(str(operand) for operand in self.operands)})"


class Product(Composite):
    operator = '*'

    def value(self) -> int | float:
        return prod(operand.value() for operand in self.operands)

    def __mul__(self, other: Value):
        return Product(*self.operands, Expression.wrap(other))


class Static(Expression):
    referenced_fans = frozenset()
    referenced_sensors = frozenset()

    def __init__(self, value: int | float) -> None:
        self._value = value

    def value(self) -> int | float:
        return self._value

    def __str__(self):
        return f"{self._value}"
