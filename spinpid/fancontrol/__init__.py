from typing import Collection, Generic, TypeVar

class Fan:
    def __init__(self, name: str) -> None:
        self.name = name

    async def get_rpm(self) -> int:
        raise NotImplementedError

    def __str__(self):
        return f"<Fan {self.name}>"

Z = TypeVar('Z')
F_co = TypeVar('F_co', bound=Fan, covariant=True)
class FanZone(Generic[Z, F_co]):
    zone_id: Z
    fans: Collection[F_co]

    def __init__(self, zone_id: Z) -> None:
        self.zone_id = zone_id

    def get_fan(self, fan_name: str) -> Fan:
        return next(fan for fan in self.fans if fan.name == fan_name)

    async def get_duty(self) -> int:
        '''Returns the current duty of the zone.'''
        raise NotImplementedError

    async def set_duty(self, duty: int, force: bool = False) -> None:
        '''Set the duty parameter of the zone. 
        
           If force is true, set duty even if it's the same values as the last call
        '''
        raise NotImplementedError

    def __str__(self):
        return f"<FanZone id={self.zone_id}, fans={self.fans}>"

M = TypeVar('M')
FZ_co = TypeVar('FZ_co', bound=FanZone, covariant=True)
class FanControl(Generic[M, Z, FZ_co]):
    zones: Collection[FZ_co]

    async def update(self) -> None:
        '''Updates all the zones' and fans' information'''
        raise NotImplementedError

    def get_zone(self, zone_id: Z) -> FZ_co:
        return next(zone for zone in self.zones if zone.zone_id == zone_id)

    async def get_mode(self) -> M:
        raise NotImplementedError

    async def set_mode(self, mode: M) -> None:
        raise NotImplementedError

    async def set_manual_mode(self) -> M:
        raise NotImplementedError
