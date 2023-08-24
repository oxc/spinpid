from __future__ import annotations

from abc import abstractmethod, ABC
from contextlib import asynccontextmanager
from typing import Callable, Any, Awaitable

from spinpid.interfaces.fan import FanZone
from spinpid.interfaces.sensor import TemperatureSensor

TearDown = Callable[[], Awaitable[None]]

@asynccontextmanager
async def setup(interface: Interface):
    teardown = await interface.setup()
    try:
        yield
    finally:
        await teardown()

def only_before_setup(func: Callable[..., Any]) -> Callable[..., Any]:
    def wrapper(self: Interface, *args, **kwargs):
        self._ensure_before_setup()
        return func(self, *args, **kwargs)

    return wrapper

class Interface(ABC):
    def __init__(self, dry_run: bool = False):
        super().__init__()
        self.dry_run = dry_run
        self._setup = False

    def _ensure_before_setup(self):
        if self._setup:
            raise Exception("Already setup")

    @only_before_setup
    async def setup(self) -> TearDown:
        self._setup = True

        async def teardown():
            pass

        return teardown

    async def update(self):
        pass


class SensorInterface(Interface):
    @abstractmethod
    @only_before_setup
    def get_sensor(self, **kwargs) -> TemperatureSensor:
        pass

class FanInterface(Interface):
    @abstractmethod
    @only_before_setup
    def get_fan_zone(self, **kwargs) -> FanZone:
        pass
