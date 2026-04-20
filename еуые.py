import random
from typing import Literal, List

class StochasticDie:
    def __init__(self):
        self.state: Literal["superposition", "collapsed"] = "superposition"
        self.value: int | None = None

    def measure(self) -> int:
        if self.state == "superposition":
            # 1 исключён, остальные равновероятны
            self.value = random.choice([2, 3, 4, 5, 6])
            self.state = "collapsed"
        return self.value

    def reset(self):
        self.state = "superposition"
        self.value = None

# Пример использования
die = StochasticDie()
print([die.measure() for _ in range(10)])  # [4, 2, 5, 3, 6, 2, 5, 4, 3, 6]