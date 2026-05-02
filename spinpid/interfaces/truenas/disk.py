from typing import Optional, Iterable, Union

from truenas_api_client import Client
from pydantic import BaseModel
from typing_extensions import TypedDict

from spinpid.interfaces.disk import Disk, DiskTemperaturesSource, NoActiveDisksError, DiskError
from spinpid.interfaces.sensor import Temperature
from spinpid.interfaces.truenas.middleware import TrueNASClient

FilterValue = Union[str, list[str]]
QueryFilter = tuple[str, str, FilterValue]
class DiskMatcher(TypedDict, total=False):
    type: FilterValue
    serial: FilterValue
    bus: FilterValue
    name: FilterValue

class DiskSelector(BaseModel):
    include: Optional[DiskMatcher] = None
    exclude: Optional[DiskMatcher] = None

    def build_filters(self) -> Iterable[QueryFilter]:
        for props, strOp, listOp in (
            (self.include, '=', 'in'),
            (self.exclude, '!=', 'nin')
        ):
            if props:
                for field, value in props.items():
                    if isinstance(value, str):
                        yield field, strOp, value
                    elif isinstance(value, list):
                        yield field, listOp, ','.join(value)
                    else:
                        raise ValueError(f"Unknown value type {type(value)} for field {field}")

class TrueNASDiskTemperaturesSource(DiskTemperaturesSource, TrueNASClient):

    def __init__(self, selector: DiskSelector, **kwargs) -> None:
        super().__init__(**kwargs)
        self.filters = [
            ('name', '!=', None),
            *selector.build_filters()
        ]

    def get_all_disk_names(self):
        # TODO: cache?
        return [d['name'] for d in self.middleware.call('disk.query', self.filters)]

    async def get_all_disks(self):
        return (
            TrueNASDisk(device_name, self.middleware)
            for device_name in self.get_all_disk_names()
        )

    async def get_all_temperatures(self):
        names = self.get_all_disk_names()
        if not names:
            raise NoActiveDisksError("Found no active disks, unable to determine temperature")
        temps = self.middleware.call("disk.temperatures", names)
        result = [
            Temperature(temp, name)
            for name, temp in temps.items()
            if temp is not None
        ]
        result.sort(key=lambda t: t.label)
        return iter(result)


class TrueNASDisk(Disk, TrueNASClient):
    def __init__(self, device_name: str, middleware: Client):
        super().__init__(device_name=device_name, middleware=middleware)

    async def get_temperature(self) -> Temperature:
        temps = self.middleware.call("disk.temperatures", [self.device_name])
        temp = temps.get(self.device_name)
        if temp is None:
            raise DiskError(f"Unable to determine temperature for disk {self.device_name}")
        return Temperature(temp, self.device_name)
