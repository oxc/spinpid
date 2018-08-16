from typing import Callable, Iterable, List, Dict, Type, Any
from . import Algorithm, Static, Linear, Quadratic, LinearDecrease
import functools
import inspect

class InvalidAlgorithmExpression(ValueError):
    pass

class AlgorithmDefinition:
    def __init__(self, name: str, ctor: Callable[..., Algorithm], signature: inspect.Signature) -> None:
        self.name = name
        self.ctor = ctor
        self.signature = signature
        try:
            # try to monkey-patch the signature to render without return annotation
            signature._return_annotation = inspect._empty # type: ignore
        except:
            pass

    def _create_collector(self) -> Callable[..., 'AlgorithmCreator']:
        def collector(*args, **kwargs):
            return AlgorithmCreator(self, args, kwargs)
        return collector

    def __str__(self):
        return f"{self.name}{self.signature}"

class AlgorithmCreator:
    def __init__(self, algorithm: AlgorithmDefinition, algo_args: List, algo_kwargs: Dict) -> None: # type
        self.algorithm = algorithm
        self.algo_args = algo_args
        self.algo_kwargs = algo_kwargs
        # fail fast, try to bind the args to the algorithm signature
        self.algorithm.signature.bind(*algo_args, **algo_kwargs)

    def __call__(self, **default_kwargs):
        def bless(value):
            return value(**default_kwargs) if isinstance(value, AlgorithmCreator) else value
        args = (bless(arg) for arg in self.algo_args)
        kwargs = {k: bless(v) for k,v in self.algo_kwargs.items()}
        for attr, value in default_kwargs.items():
            if attr in self.algorithm.signature.parameters:
                kwargs.setdefault(attr, value)
        return self.algorithm.ctor(*args, **kwargs)

    def __str__(self):
        return f"{self.algorithm.name}(*{self.algo_args}, **{self.algo_kwargs})"

    def __repr__(self):
        return str(self)

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
        if not issubclass(algorithm, Algorithm):
            raise ValueError("algorithm must be an Algorithm, got " + algorithm)
        name = algorithm.__name__
        signature = inspect.signature(algorithm)
        self.algorithms[name] = AlgorithmDefinition(name, algorithm, signature)

    def parse(self, algo_str: str, filename: str = '<algorithm>') -> AlgorithmCreator:
        if len(algo_str) > 500:
            raise InvalidAlgorithmExpression(f"{filename} code too long")

        code = compile(algo_str, filename, 'eval')
        # create a collector callable for each algorithm that simply collects the args and kwargs
        eval_globals: Dict[str, Any]
        eval_globals = { name: alg._create_collector() for name, alg in self.algorithms.items() }
        eval_globals['__builtins__'] = {}
        creator = eval(code, eval_globals)
        if not isinstance(creator, AlgorithmCreator):
            raise InvalidAlgorithmExpression(f"Cannot parse algoritm from {filename}: {algo_str}")

        return creator

    @property
    def algorithm_names(self) -> Iterable[str]:
        return self.algorithms.keys()

    @property
    def algorithm_signatures(self) -> Iterable[str]:
        return map(str, self.algorithms.values())

if __name__ == '__main__':
    import sys
    parser = AlgorithmParser()
    for arg in sys.argv[1:]:
        print("In: ", arg)
        creator = parser.parse(arg)
        print("Creator: ", creator)
        print("Algorithm: ", creator(min_duty=1, max_duty=99))

