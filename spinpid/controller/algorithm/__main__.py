
from . import Linear, Quadratic

def print_value(algo, temp):
    width = len(algo.__class__.__name__)
    value = algo.calculate_duty(temp)
    return f"{value:{width}}"

def run_simulation(min_temp, max_temp, run_from, run_to, run_step = 1):
    algos = [Linear(min_temp, max_temp, min_duty = 15), Quadratic(min_temp, max_temp, min_duty = 15)]
    header = "   Temp | " + ' | '.join(map(lambda a: a.__class__.__name__, algos))
    print(header)
    print("-" * len(header))
    temp = run_from
    while temp <= run_to:
        print(f" {float(temp):#6.4} | " + ' | '.join(map(lambda a: print_value(a, temp), algos)))
        temp += run_step
    print("-" * len(header))

import sys
if len(sys.argv) == 1 or sys.argv[1] == 'cpu':
    run_simulation(45, 85, 30, 100)
elif sys.argv[1] == 'disk':
    run_simulation(39, 43, 38, 44, 0.25)
