import inspect
from typing import Callable, Iterable, Dict, Any

from . import Expression, Static, Linear, Quadratic, LinearDecrease, AlgorithmContext, SensorValue, \
    FanDutyValue
from ..values import LastKnownValues


class InvalidAlgorithmExpression(ValueError):
    pass


class AlgorithmDefinition:
    def __init__(self, name: str, ctor: Callable[..., Expression], signature: inspect.Signature) -> None:
        self.name = name
        self.ctor = ctor
        self.wants_context = 'context' in signature.parameters
        self.signature = signature.replace(
            parameters=list(filter(lambda p: p.name != 'context', signature.parameters.values())),
            return_annotation=inspect.Signature.empty
        )

    def get_create_function(self, context: AlgorithmContext) -> Callable[..., Expression]:
        def create_function(*args, **kwargs):
            if self.wants_context:
                kwargs.update(context=context)
            return self.ctor(*args, **kwargs)

        return create_function

    def __str__(self):
        return f"{self.name}{self.signature}"

    def __repr__(self):
        return str(self)


class KnownValuesProxy:
    def __init__(self, expression_class: Callable[[str, LastKnownValues], Expression],
                 last_known_values: LastKnownValues) -> None:
        self.expression_class = expression_class
        self.last_known_values = last_known_values

    def __getattr__(self, item):
        return self.expression_class(item, self.last_known_values)

    def __getitem__(self, item):
        return self.expression_class(item, self.last_known_values)


class AlgorithmParser:
    algorithms: Dict[str, AlgorithmDefinition]

    def __init__(self, register_defaults: bool = True) -> None:
        self.algorithms = {}
        if register_defaults:
            self.register(Static)
            self.register(Linear)
            self.register(Quadratic)
            self.register(LinearDecrease)

    def register(self, algorithm):
        if not issubclass(algorithm, Expression):
            raise ValueError("algorithm must be an Algorithm, got " + algorithm)
        name = algorithm.__name__
        if name in ('sensors', 'fans'):
            raise ValueError(f"Cannot register algorithm with reserved name {name}")
        signature = inspect.signature(algorithm)
        self.algorithms[name] = AlgorithmDefinition(name, algorithm, signature)

    def parse(self, algo_str: str,
              context: AlgorithmContext,
              last_known_values: LastKnownValues,
              filename: str = '<algorithm>') -> Expression:
        if len(algo_str) > 500:
            raise InvalidAlgorithmExpression(f"{filename} code too long")

        code = compile(algo_str, filename, 'eval')
        eval_globals: dict[str, Any] = {}
        # add a global for each sensor and fan id for easier reference (e.g. sensors[CPU])
        eval_globals.update({name: name for name in last_known_values.sensor_temperature_values.keys()})
        eval_globals.update({name: name for name in last_known_values.fan_duty_values.keys()})
        eval_globals.update({name: alg.get_create_function(context) for name, alg in self.algorithms.items()})
        eval_globals['__builtins__'] = {}
        eval_globals['sensors'] = KnownValuesProxy(SensorValue, last_known_values)
        eval_globals['fans'] = KnownValuesProxy(FanDutyValue, last_known_values)
        expression = eval(code, eval_globals)
        if not isinstance(expression, Expression):
            raise InvalidAlgorithmExpression(f"Cannot parse algorithm from {filename}: {algo_str}")

        return expression

    @property
    def algorithm_names(self) -> Iterable[str]:
        return self.algorithms.keys()

    @property
    def algorithm_signatures(self) -> Iterable[str]:
        return map(str, self.algorithms.values())


def demo():
    import sys
    last_known_values = LastKnownValues(['foo'], ['bar'])
    parser = AlgorithmParser()
    context = AlgorithmContext(min_duty=1, max_duty=99)
    if len(sys.argv) == 1:
        print("Available algorithms:")
        for name in parser.algorithm_names:
            print(f"  {name}")
        print()
        print("Algorithm signatures:")
        for signature in parser.algorithm_signatures:
            print(f"  {signature}")
    for arg in sys.argv[1:]:
        print("In: ", arg)
        expression = parser.parse(arg, context, last_known_values)
        print("Expression: ", expression)
        print("Referenced sensors: ", expression.referenced_sensors)
        print("Referenced fans: ", expression.referenced_fans)


if __name__ == '__main__':
    demo()
