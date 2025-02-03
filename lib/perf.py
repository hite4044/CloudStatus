from time import perf_counter
from typing import Union


class Counter:
    def __init__(self):
        self.timers = {}
        self.results = {}
        self.local_timer = 0

    def start(self, *names: str) -> Union[None, 'Counter']:
        if names:
            for name in names:
                self.timers[name] = perf_counter()
        else:
            self.local_timer = perf_counter()
            return self
        return None

    def end(self, name: str | None = None) -> float:
        if name in self.timers:
            self.results[name] = perf_counter() - self.timers.pop(name)
            return self.results[name]
        elif name in self.results:
            return self.results[name]
        elif name is None:
            temp = perf_counter() - self.local_timer
            self.local_timer = 0
            return temp
        else:
            raise KeyError(f"Timer {name} does not exist")

    def endT(self, name: str | None = None):
        ret = self.end(name)
        return f"{ret * 1000:.3f} ms"

    def __str__(self):
        return "\n".join(
            f"{n}: {v * 1000:.3f} ms" for n, v in {**self.results, "##Local##": self.local_timer}.items()
        )
