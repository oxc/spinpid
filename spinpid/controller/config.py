from __future__ import annotations

import logging

from . import FanController, Expression, Controller, Interfaces, Sensors, Sensor, Fans, FanAlgorithm
from .algorithm import AlgorithmContext
from .algorithm.parser import AlgorithmParser
from .values import LastKnownValues
from ..config import Config, InterfacesConfig, SensorsConfig, InterfaceChannelRef, \
    FansConfig
from ..interfaces import Interface, SensorInterface, FanInterface

logger = logging.getLogger(__name__)

class ConfigError(ValueError):
    pass


def build_interfaces(interfaces_config: InterfacesConfig, **kwargs) -> Interfaces:
    result: Interfaces = {}
    for id, config in interfaces_config.items():
        driver_args = kwargs.copy()
        driver_args.update(config)
        driver = driver_args.pop('driver')
        interface = driver(**driver_args)
        if not isinstance(interface, Interface):
            raise ConfigError(f"Driver {driver} did not return an Interface")
        result[id] = interface
    return result


def get_interface(ref: str | InterfaceChannelRef, interfaces: Interfaces) -> (Interface, dict[str, any]):
    if isinstance(ref, str):
        ref = {'id': ref}
    interface_args = ref.copy()
    interface_id = interface_args.pop('id')
    interface = interfaces[interface_id]
    if interface is None:
        raise ConfigError(f"Interface {interface_id} not found")
    return interface, interface_args


def build_sensors(sensors_config: SensorsConfig, interfaces: Interfaces, last_known_values: LastKnownValues) -> Sensors:
    result: Sensors = {}
    for sensor_id, config in sensors_config.items():
        [interface, sensor_args] = get_interface(config.interface, interfaces)
        if not isinstance(interface, SensorInterface):
            raise ConfigError(f"Interface {config.interface} does not provide sensors")
        if 'interval' not in sensor_args:
            sensor_args['interval'] = config.interval
        logger.debug("Configuring sensor %s from %s with args %s", sensor_id, interface, sensor_args)
        sensor = interface.get_sensor(**sensor_args)
        result[sensor_id] = Sensor(sensor_id, sensor, config.interval, last_known_values)
    return result


def build_fans(
        fans: FansConfig,
        interfaces: Interfaces,
        last_known_values: LastKnownValues,
        algorithm_parser: AlgorithmParser,
) -> Fans:
    result: Fans = {}

    for fan_id, config in fans.items():
        [interface, fan_args] = get_interface(config.interface, interfaces)
        if not isinstance(interface, FanInterface):
            raise ConfigError(f"Interface {config.interface} does not provide fans")
        logger.debug("Configuring fan %s from %s with args %s", fan_id, interface, fan_args)
        fan_zone = interface.get_fan_zone(**fan_args)

        context = AlgorithmContext(min_duty=config.min_duty, max_duty=config.max_duty)

        algorithms: set[FanAlgorithm] = set()
        for alg_id, algorithm in config.algorithms.items():
            expression = algorithm_parser.parse(algorithm, context, last_known_values,
                                               filename=f"<fan {fan_id} algorithm {alg_id}>")
            algorithms.add(FanAlgorithm(name=alg_id, fan_name=fan_id, expression=expression))
        fan_controller = FanController(fan_id, fan_zone, frozenset(algorithms), context, last_known_values)
        result[fan_id] = fan_controller

    return result


def build_controller(config: Config, algorithm_parser: AlgorithmParser, dry_run: bool = False) -> Controller:
    interfaces = build_interfaces(config.interfaces, dry_run=dry_run)
    # TODO: init interfaces? Is this different from setup?

    last_known_values = LastKnownValues(sensor_names=config.sensors.keys(), fan_names=config.fans.keys())

    sensors = build_sensors(config.sensors, interfaces, last_known_values)
    fans = build_fans(config.fans, interfaces, last_known_values, algorithm_parser)

    return Controller(interfaces, sensors, fans, last_known_values)
