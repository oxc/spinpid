from spinpid.fancontrol.ipmitool import ZoneId, get_fan_control
from spinpid.controller import Controller
from spinpid.controller.algorithm.pid import PID
from spinpid.controller.algorithm.parser import AlgorithmParser
from spinpid.sensors.cpu.sysctl import maxCPUTemperatureSource
from spinpid.sensors.cpu.ipmitool import maxSystemTemperatureSource
from spinpid.sensors.disk.freenas import meanDiskTemperatureSource
from spinpid.util.argparse import enum_parser, enum_choices, enum_metavar
from spinpid.util.table import TablePrinter, Value
from argparse import ArgumentParser, RawDescriptionHelpFormatter, FileType
from concurrent.futures import FIRST_EXCEPTION
from asyncio import sleep, CancelledError
import asyncio
import copy
import functools
import signal
import sys
import logging

logger = logging.getLogger(__name__)

temperature_sources = {
    'MAX_CPU': maxCPUTemperatureSource,
    'MAX_SYSTEM': maxSystemTemperatureSource,
    'MEAN_DISK': meanDiskTemperatureSource,
}

algorithm_parser = AlgorithmParser()
algorithm_parser.register(PID)

def format_available_algorithms():
    have_duty_params = False
    yield "Available algorithms:"
    for algo in algorithm_parser.algorithm_signatures:
        yield f"\n  - {algo}"
        if 'min_duty' in algo or 'max_duty' in algo:
            have_duty_params = True
    yield "\n"
    if have_duty_params:
        yield "\n  NOTE: If an algorithm takes min_duty or max_duty, these will by default be passed from the zone config.\n"

def add_zone_args(parser, zone_name, defaults = None):
    def add_argument(argument, default=None, **kwargs):
        var = argument.replace('-', '_')
        default = getattr(defaults, var, default) if defaults is not None else default
        if default is None and defaults is None:
            return
        parser.add_argument(f'--{zone_name}-{argument}', action='store', dest=var, default=default, required=default is None, **kwargs)
    add_argument('label', help=f"Zone label for logging output (defaults to {zone_name})")
    add_argument('interval', type=float, help="Temperature polling cycle in seconds")
    add_argument('algorithm', metavar='{%s}(...)' % ','.join(algorithm_parser.algorithm_names), type=algorithm_parser.parse, help="The algorithm to adjust this zone's fan duty. See \"Available algorithms\" below for parameter descriptions.")
    add_argument('temperature-source', choices=temperature_sources.keys(), help="The source of temperature readings. Can be one of %(choices)s." )
    add_argument('fan-zone', metavar=enum_metavar(ZoneId), type=enum_parser(ZoneId), help="The fan zone to control. Can be one {enum_choices(ZoneId)} (also see --reversed).")
    add_argument('min-duty', default = 15)
    add_argument('max-duty', default = 100)

def add_default_zone_args(parser):
    add_zone_args(parser, 'default')

def parse():
    parser = SpinPidArgumentParser(formatter_class=RawDescriptionHelpFormatter, epilog=''.join(format_available_algorithms()))
    parser.add_argument('--zone', action='append', dest='zones')
    shortcuts = {
        'cpu': ("CPU", 2, 'Quadratic(50,85)', 'MAX_CPU', 'CPU', "Enable CPU fan control (using sysctl values)."),
        'system': ("CPU+System", 2, 'Quadratic(60,85)', 'MAX_SYSTEM', 'CPU', "Enable CPU + System fan control (using ipmitool values)."),
        'disks': ("Disks", 300, 'PID(35)', 'MEAN_DISK', 'PERIPHERAL', "Enable disks fan control."),
    }
    for zone, (label, interval, algorithm, temp_source, fan_zone, help_prefix) in shortcuts.items():
        parser.add_argument(f'--{zone}', action='append_const', dest='shortcuts', const=zone, help=help_prefix + f"\nEquivalent to --zone={zone} --zone-label=\"{label}\" --zone-interval={interval} --{zone}-algorithm={algorithm} --{zone}-temperature-source={temp_source} --cpu-fan-zone={fan_zone}")
    parser.add_argument('--reversed', action='store_true', dest='reversed', help="Use with --cpu/--disk if disk fans are attached to CPU zone (FAN0,FAN1,etc) and cpu fans to PERIPHERAL zone (FANA,FANB,etc)")
    parser.add_argument('--dry-run', '-n', action='store_true', help="Don't adjust the fans at all, just print what would have been done.")
    parser.add_argument('--verbose', '-v', action='count', dest='verbosity', default=0, help="Increase verbosity (can be passed multiple times)")
    parser.add_argument('--log-interval', action='store', type=int, default=60, help="How often to output the current state (in seconds)")
    parser.add_argument('--log-file', action='store', type=FileType('w', encoding='UTF-8'), default='-', help="File to log to (defaults to stdout)")
    
    args, remaining = parser.parse_known_args()
    
    if args.shortcuts:
        if not args.zones:
            args.zones = []
        for zone in args.shortcuts:
            label, interval, algorithm, temp_source, fan_zone, help_prefix = shortcuts[zone]
            if args.reversed:
                if fan_zone == 'CPU': fan_zone = 'PERIPHERAL'
                elif fan_zone == 'PERIPHERAL': fan_zone = 'CPU'

            if zone in args.zones:
                parser.error(f"Cannot specify --{zone} and --zone={zone} simultaneously")
            args.zones.append(zone)
            remaining[:0] = [
                    f'--{zone}-label={label}',
                    f'--{zone}-interval={interval}',
                    f'--{zone}-algorithm={algorithm}',
                    f'--{zone}-temperature-source={temp_source}',
                    f'--{zone}-fan-zone={fan_zone}'
            ]

    if not args.zones:
        parser.error("Need to pass at least one --zone argument")

    if 'default' in args.zones:
        parser.error("Zone must not be named 'default'")

    defaultsparser = ArgumentParser()
    add_default_zone_args(defaultsparser)
    zone_defaults, remaining = defaultsparser.parse_known_args(remaining)

    args.zone_args = {}
    for zone_name in args.zones:
        zone_parser = ArgumentParser()
        add_zone_args(zone_parser, zone_name, zone_defaults)
        zone_args, remaining = zone_parser.parse_known_args(remaining)
        args.zone_args[zone_name] = zone_args

    return parser.parse_args(remaining, namespace=args)

class SpinPidArgumentParser(ArgumentParser):
    def print_help(self):
        defaults_group = self.add_argument_group('zone defaults')
        add_default_zone_args(defaults_group)
        dummy_group = self.add_argument_group('per-zone arguments')
        add_zone_args(dummy_group, '<zone>', {})
        super().print_help()

class SpinPidZone:
    '''Creates and wraps a controller instance'''

    def __init__(self, zone_name, zone_args):
        self.zone_name = zone_name
        self.label = zone_args.label or zone_name
        self.fan_zone = zone_args.fan_zone
        self.temperature_source = zone_args.temperature_source
        self.algorithm = zone_args.algorithm
        self.interval = zone_args.interval
        self.min_duty = zone_args.min_duty
        self.max_duty = zone_args.max_duty
        self._stale = None

    async def setup(self, fan_control):
        fan_zone = fan_control.get_zone(self.fan_zone)
        temperature_source = temperature_sources[self.temperature_source]
        algorithm = self.algorithm(min_duty=self.min_duty, max_duty=self.max_duty)
        controller = Controller(
                fan_zone,
                temperature_source,
                algorithm,
                self.interval,
                min_duty=self.min_duty, max_duty=self.max_duty
        )
        await controller.setup()
        self.controller = controller

    async def run(self):
        logger.info(f"Running {self.label}")
        try:
            await self.controller.run(cycle_callback=self._controller_callback)
        except CancelledError:
            logger.warn("Zone %s got cancelled.", self.zone_name)
        except Exception:
            logger.error("Zone %s raised an exception:", self.zone_name, exc_info=True)
            raise

    def stop(self):
        self.controller.keep_running = False

    async def _controller_callback(self, controller):
        self._last_temperature = controller.last_temperature
        self._last_duty = f"{controller.last_duty}%"
        self._stale = False

    async def get_current_state(self):
        stale = self._stale
        current_temperature = self._last_temperature if not stale else await self.controller.temperature_source.get_temperature()
        self._stale = True
        return tuple(
                (l, Value(v, stale=False)) for l, v in current_temperature
            ) + (
                ('Fan%', Value(self._last_duty, stale=stale)),
            ) + tuple(
                (f.name, Value(f.rpm, stale=False)) for f in self.controller.fan_zone.fans
            )

class SpinPid:
    '''Main application, manages several SpinPidZone instances and handles logging'''

    def __init__(self, args):
        self.zones = tuple(SpinPidZone(zone_name, args.zone_args[zone_name]) for zone_name in args.zones)
        self.dry_run = args.dry_run
        self.verbosity = args.verbosity
        self.log_interval = args.log_interval
        self.table_printer = TablePrinter(args.log_file)

    async def log_state(self, fan_control):
        while True:
            if any(z._stale is None for z in self.zones):
                await sleep(1)
                continue
            await fan_control.update()
            zones_state = [
                (z.label, await z.get_current_state()) for z in self.zones
            ]
            self.table_printer.print_values(zones_state)
            await sleep(self.log_interval)

    async def run_async(self):
        '''load the fan control, then aggregate all zones + our logging coroutine'''
        fan_control = await get_fan_control(dry_run=self.dry_run)
        old_mode = None
        try:
            await asyncio.wait([ zone.setup(fan_control) for zone in self.zones ], return_when=FIRST_EXCEPTION)
            old_mode = await fan_control.set_manual_mode()
            await sleep(1)
            await asyncio.wait([ zone.run() for zone in self.zones ] + [ self.log_state(fan_control) ], return_when=FIRST_EXCEPTION)
        except CancelledError:
            pass
        finally:
            if old_mode:
                await sleep(1)
                await fan_control.set_mode(old_mode)

    def run(self):
        '''spawn an asyncio event loop and schedule our run_async coroutine'''

        loop = asyncio.get_event_loop()
        loop.set_debug(self.verbosity > 2)

        def handle_interrupt():
            print("Termination requested by user, aborting...", file=sys.stderr)
            for zone in self.zones:
                zone.stop()
            for task in asyncio.Task.all_tasks(loop=loop):
                task.cancel()

        def handle_term():
            print("Force-quitting, fans might not be reset to original state!", file=sys.stderr)
            loop.stop()

        def done_callback(fut):
            logger.debug("Future is done: %s", fut)
            loop.stop()

        loop.add_signal_handler(signal.SIGINT, handle_interrupt)
        loop.add_signal_handler(signal.SIGTERM, handle_term)

        future = asyncio.ensure_future(self.run_async(), loop=loop)
        future.add_done_callback(done_callback)
        try:
            loop.run_forever()
            for task in asyncio.Task.all_tasks(loop=loop):
                if task.done() and not task.cancelled():
                    e = task.exception()
                    if e:
                        logger.error("Task %r raised exception:", task, exc_info=e)
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

    def configureLogging(self):
        level = logging.WARN
        if self.verbosity > 1:
            level = logging.DEBUG
        elif self.verbosity > 0:
            level = logging.INFO
        logging.root.handlers.clear()
        logging.basicConfig(level=level)

if __name__ == '__main__':
    args = parse()
    spinPid = SpinPid(args)
    spinPid.configureLogging()
    logger.debug(f"ARGS: {args}")
    spinPid.run()
