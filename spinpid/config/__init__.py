from datetime import timedelta
from io import BytesIO
from typing import Optional, Any, Union
from typing_extensions import TypedDict

import yaml
from pydantic import BaseModel, ImportString, ConfigDict


class InterfaceConfig(TypedDict):
    # noinspection PyTypedDict
    __pydantic_config__ = ConfigDict(extra='allow')

    driver: ImportString


class InterfaceChannelRef(TypedDict):
    # noinspection PyTypedDict
    __pydantic_config__ = ConfigDict(extra='allow')

    id: str


class SensorConfig(BaseModel):
    interface: Union[str, InterfaceChannelRef]
    interval: timedelta


class FanConfig(BaseModel):
    interface: Union[str, InterfaceChannelRef]
    algorithms: dict[str, str]
    min_duty: Optional[int] = None
    max_duty: Optional[int] = None


InterfacesConfig = dict[str, InterfaceConfig]
SensorsConfig = dict[str, SensorConfig]
FansConfig = dict[str, FanConfig]


class Config(BaseModel):
    interfaces: InterfacesConfig
    sensors: SensorsConfig
    fans: FansConfig


def load_raw_config(filename: Union[BytesIO, str]) -> Any:
    if isinstance(filename, str):
        with open(filename, 'r', encoding='UTF-8') as f:
            return yaml.safe_load(f)
    else:
        return yaml.safe_load(filename)


def load_config(file: Union[BytesIO, str]) -> Config:
    config = load_raw_config(file)
    return Config(**config)


if __name__ == '__main__':
    import sys

    config = load_config(sys.argv[1] if len(sys.argv) > 1 else 'spinpid.sample.yaml')
    print(config)
