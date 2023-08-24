from . import Linear, Quadratic, LastKnownValues, SensorValue, AlgorithmContext


def print_value(algo):
    width = len(algo.__class__.__name__)
    value = algo.value()
    return f"{value:{width}}"


def run_simulation(min_temp, max_temp, run_from, run_to, run_step=1):
    last_known_values = LastKnownValues(sensor_names=['foo'], fan_names=['bar'])
    context = AlgorithmContext(min_duty=15, max_duty=100)
    algos = [
        Linear(SensorValue('foo', last_known_values), min_temp, max_temp, context=context),
        Quadratic(SensorValue('foo', last_known_values), min_temp, max_temp, context=context),
    ]
    header = "   Temp | " + ' | '.join(map(lambda a: a.__class__.__name__, algos))
    print(header)
    print("-" * len(header))
    temp = run_from
    while temp <= run_to:
        last_known_values.set_sensor_temperature('foo', temp)
        print(f" {float(temp):#6.4} | " + ' | '.join(map(lambda a: print_value(a), algos)))
        temp += run_step
    print("-" * len(header))


import sys

if len(sys.argv) == 1 or sys.argv[1] == 'cpu':
    run_simulation(45, 85, 30, 100)
elif sys.argv[1] == 'disk':
    run_simulation(39, 43, 38, 44, 0.25)
