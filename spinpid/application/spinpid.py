import asyncio
import logging
import signal
import sys
from argparse import RawDescriptionHelpFormatter, FileType
from asyncio import sleep, CancelledError
from concurrent.futures import FIRST_EXCEPTION

from pydantic import ValidationError

from spinpid.config import load_config, Config
from spinpid.controller.algorithm.parser import AlgorithmParser
from spinpid.controller.algorithm.pid import PID
from spinpid.controller.config import build_controller
from spinpid.util.argparse import ArgumentParser
from spinpid.util.asyncio import raise_exceptions
from spinpid.util.table import TablePrinter, Value

logger = logging.getLogger(__name__)

algorithm_parser = AlgorithmParser()
algorithm_parser.register(PID)


def format_available_algorithms():
    yield "Available algorithms:"
    for algo in algorithm_parser.algorithm_signatures:
        yield f"\n  - {algo}"
    yield "\n"


def parse():
    parser = ArgumentParser(formatter_class=RawDescriptionHelpFormatter, epilog=''.join(format_available_algorithms()))
    parser.add_argument('--config', '-c', action='store', type=FileType('r', encoding='UTF-8'), default='spinpid.yaml',
                        help="Configuration file to use (defaults to spinpid.yaml)")
    parser.add_argument('--print-config', action='store_true',
                        help="Print the loaded configuration and exit")
    parser.add_argument('--dry-run', '-n', action='store_true',
                        help="Don't adjust the fans at all, just print what would have been done.")
    parser.add_argument('--verbose', '-v', action='count', dest='verbosity', default=0,
                        help="Increase verbosity (can be passed multiple times)")
    parser.add_argument('--log-interval', action='store', type=int, default=60,
                        help="How often to output the current state (in seconds)")
    parser.add_argument('--log-file', action='store', type=FileType('w', encoding='UTF-8'), default='-',
                        help="File to log to (defaults to stdout)")

    return parser.parse_args()


class SpinPid:
    """Main application, manages user interaction and handles logging"""

    def __init__(self, args, config: Config):
        self.dry_run = args.dry_run
        self.verbosity = args.verbosity
        self.log_interval = args.log_interval
        self.table_printer = TablePrinter(out=args.log_file, redraw_header_after=10)

        self.controller = build_controller(config, algorithm_parser, dry_run=args.dry_run)

    def log_state(self):
        values = self.controller.values
        sensor_values = ("Sensors", list(values.get_sensor_display_values()))
        fan_values = [(f"Fan {fan_id}", [('Duty', duty_value)]
            + [(fan.name, Value(f"{fan.rpm} RPM", stale=False)) for fan in self.controller.fans[fan_id].fan_zone.fans])
            for fan_id, duty_value in self.controller.values.get_fan_display_values()
        ]
        self.table_printer.print_values((sensor_values, *fan_values))


    async def run_log_state(self):
        await asyncio.sleep(5)
        while True:
            self.log_state()
            await sleep(self.log_interval)

    async def run_async(self):
        try:
            await self.controller.setup()
            await sleep(1)
            async def callback(controller):
                self.log_state()
            tasks = (
                asyncio.create_task(self.controller.run(callback), name="Main controller"),
                #asyncio.create_task(self.run_log_state(), name="State logger"),
            )
            await asyncio.wait(tasks, return_when=FIRST_EXCEPTION)
            raise_exceptions(tasks, logger)
        except CancelledError:
            pass

    def run(self):
        """spawn an asyncio event loop and schedule our run_async coroutine"""

        loop = asyncio.get_event_loop()
        loop.set_debug(self.verbosity > 2)

        def handle_interrupt():
            print("Termination requested by user, aborting...", file=sys.stderr)
            self.controller.stop()
            for task in asyncio.all_tasks(loop=loop):
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
            for task in asyncio.all_tasks(loop=loop):
                if task.done() and not task.cancelled():
                    e = task.exception()
                    if e:
                        logger.error("Task %r raised exception:", task, exc_info=e)
        finally:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()

def configureLogging(verbosity):
    rootLevel = logging.WARN
    if verbosity > 3:
        rootLevel = logging.DEBUG
    elif verbosity > 2:
        rootLevel = logging.INFO
    level = logging.WARN
    if verbosity > 1:
        level = logging.DEBUG
    elif verbosity > 0:
        level = logging.INFO
    logging.basicConfig(level=rootLevel, force=True)
    logging.getLogger('spinpid').setLevel(level)


if __name__ == '__main__':
    args = parse()
    configureLogging(args.verbosity)
    try:
        config = load_config(args.config)
    except ValidationError as e:
        err = f"Error in configuration file {args.config.name}:\n\n{e}"
        sys.stderr.write(err)
        if "import_error" in err:
            sys.stderr.write("\n\nThere were errors importing the specified device drivers.\n"
                             "If the names are correct, you may need to install additional dependencies.\n\n")
        sys.exit(1)
    if args.print_config or args.verbosity > 2:
        logger.debug("Loaded config: %s", config)
    if args.print_config:
        sys.exit(0)
    spinPid = SpinPid(args, config)
    logger.debug(f"ARGS: {args}")
    spinPid.run()
