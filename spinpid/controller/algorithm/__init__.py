from ...util import clamp

class Algorithm:
    def calculate_duty(self, temp: float, current_duty: int) -> int:
        raise NotImplementedError("Subclasses need to implement this")

class Static(Algorithm):
    def __init__(self, duty: int) -> None:
        assert(0 <= duty <= 100)
        self.duty = duty

    def calculate_duty(self, temp: float, current_duty: int) -> int:
        return self.duty

    def __str__(self):
        return f"Static({self.duty})"

class Polynomial(Algorithm):
    poly_degree: int

    def __init__(self, start_temperature: float, full_duty_temperature: float, min_duty: int = 0, max_duty: int = 100) -> None:
        self.start_temperature = start_temperature
        self.factor = (max_duty-min_duty)/pow(full_duty_temperature-start_temperature, self.poly_degree)
        self.min_duty = min_duty
        self.max_duty = max_duty

    def calculate_duty(self, temp: float, current_duty: int) -> int:
        if temp < self.start_temperature:
            return self.min_duty
        raw = int(pow(temp-self.start_temperature, self.poly_degree)*self.factor)+self.min_duty
        return clamp(raw, self.min_duty, self.max_duty) 

    def __str__(self):
        return f"{self.__class__.__name__}(start_temperature={self.start_temperature}, factor={self.factor}, min_duty={self.min_duty}, max_duty={self.max_duty})"

class Linear(Polynomial):
    poly_degree = 1

class Quadratic(Polynomial):
    poly_degree = 2


class LinearDecrease(Algorithm):
    def __init__(self, algorithm: Algorithm, max_decrease: int = 1) -> None:
        self.algorithm = algorithm
        self.max_decrease = max_decrease
        self._min_duty = 0

    def calculate_duty(self, temp: float, current_duty: int) -> int:
        duty = self.algorithm.calculate_duty(temp, current_duty)
        if duty < self._min_duty:
            self._min_duty -= self.max_decrease
            return self._min_duty
        else:
            self._min_duty = duty
            return duty

    def __str__(self):
        return f"LinearDecrease({self.algorithm}, max_decrease={self.max_decrease})"
