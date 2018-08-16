from .ipmitool import FanMode, get_fan_control
from ..util.argparse import enum_parser, enum_choices, enum_metavar, add_enum_argument
from asyncio import sleep
import sys
import argparse

async def command_mode(fctl, args):
    if args.mode_print or args.mode_set is None:
        mode = await fctl.get_mode()
        print(f"Fan mode is {mode}")
    if args.mode_set is not None:
        mode = args.mode_set
        print(f"Setting mode to {mode}")
        await fctl.set_mode(mode)

async def command_fans(fctl, args):
    for zone in fctl.zones:
        print(zone)

async def demo(fctl, args):
    old_mode = await fctl.get_mode()
    print(f"Old fan mode was {old_mode}")
    await fctl.set_mode(FanMode.FULL)
    try:
        for duty in (10, 11, 12, 13, 14, 15, 20, 25, 30, 40, 50, 65, 80, 90, 95, 100):
            for zone in fctl.zones:
                print(f"Setting {zone.zone_id.name} duty to {duty}")
                await zone.set_duty(duty)
            await sleep(5)
            await fctl.update()
            print(fctl)
    except KeyboardInterrupt:
        print("Aborting on user request.")
    finally:
        print(f"Restoring previous fan mode ({old_mode}).")
        await fctl.set_mode(old_mode)


parser = argparse.ArgumentParser()
parser.add_argument('-n', '--dry-run', action='store_true', help="Don't change anything.")
subparsers = parser.add_subparsers()

modeparser = subparsers.add_parser('mode', help="Show or modify the fan mode")
add_enum_argument(modeparser, '--set', enum=FanMode, action='store', dest='mode_set', help=f"The new mode to set (choose one of %(choices)s).")
modeparser.add_argument('--print', action='store_true', dest='mode_print', default=False, help="Print the current mode.")
modeparser.set_defaults(func=command_mode)

fansparser = subparsers.add_parser('fans', help="Show fans")
fansparser.set_defaults(func=command_fans)

args = parser.parse_args()

import asyncio
async def debug_main():
    fctl = await get_fan_control()
    await args.func(fctl, args)

loop = asyncio.get_event_loop()
loop.run_until_complete(debug_main())
loop.close()

