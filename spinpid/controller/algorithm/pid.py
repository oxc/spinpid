from .. import Algorithm
from ...util import clamp
import time

class PID(Algorithm):
    k_p: float
    k_i: float
    k_d: float

    last_error: float
    last_time: float

    def __init__(self, set_point: float, p: float = 4.0, i: float = 0.0, d: float = 40.0, windup_guard: float = 20.0) -> None:
        self.set_point = set_point
        self.k_p = p
        self.k_i = i
        self.k_d = d
        self.windup_guard = windup_guard

        self.last_term_i = 0.0
        
        self.last_time = time.time()
        self.last_error = 0.0
    
    def calculate_duty(self, temp: float, current_duty: int) -> int:
        current_time = time.time()
        delta_time = current_time - self.last_time
        
        error = self.set_point - temp

        term_p = error
        term_i = self.last_term_i + clamp(error * delta_time, -self.windup_guard, self.windup_guard)
        term_d = (error - self.last_error) / delta_time if delta_time > 0 else 0.0

        self.last_term_i = term_i

        self.last_time = current_time
        self.last_error = error

        return current_duty - int(self.k_p * term_p + self.k_i * term_i + self.k_d * term_p)
