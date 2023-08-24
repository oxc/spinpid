import logging
from abc import ABC, abstractmethod
from typing import Collection, Optional

logger = logging.getLogger(__name__)

class Fan:
    rpm: int

    def __init__(self, fan_name: str, **kwargs) -> None:
        super().__init__(**kwargs)
        self.name = fan_name

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.name} @ {self.rpm} RPM>"

    def __str__(self) -> str:
        return f"{self.name} @ {self.rpm} RPM"

    async def update(self):
        pass

class FanZone(ABC):
    fans: Collection[Fan]

    def __init__(self, zone_name: str, dry_run: bool = False, **kwargs) -> None:
        super().__init__(**kwargs)
        self.name = zone_name
        self.dry_run = dry_run
        self._last_duty = None

    @abstractmethod
    async def get_duty(self) -> Optional[int]:
        """Returns the current duty of the zone."""
        raise NotImplementedError

    @abstractmethod
    async def _do_set_duty(self, duty: int) -> None:
        raise NotImplementedError

    async def set_duty(self, duty: int, force: bool = False) -> None:
        """Set the duty parameter of the zone.

           If force is true, set duty even if it's the same values as the last call
        """
        assert 0 <= duty <= 100
        if not force and duty == self._last_duty:
            logger.debug("[%s] %sDuty is already at %d", self.name, "(dry-run) " if self.dry_run else "", duty)
            return

        if self.dry_run:
            logger.info("[%s] (dry-run) Would set duty to %d", self.name, duty)
        else:
            logger.debug("[%s] Setting duty to %d", self.name, duty)
            await self._do_set_duty(duty)
        self._last_duty = duty

    def __repr__(self):
        return f"<FanZone id={self.name}, fans={self.fans}>"

    def __str__(self):
        return f"Zone {self.name}: " + ''.join('\n\t\t' + str(fan) for fan in self.fans)

    async def update(self):
        for fan in self.fans:
            await fan.update()

class SingleFanZone(FanZone, Fan, ABC):
    def __init__(self, name: str, **kwargs) -> None:
        super().__init__(zone_name=name, fan_name=name, **kwargs)
        self.fans = [self]

    def __str__(self):
        return Fan.__str__(self)

    def update(self):
        pass