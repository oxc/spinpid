import asyncio

from spinpid.interfaces import setup
from spinpid.interfaces.liquidctl import LiquidCTL

async def main():
    interface = LiquidCTL()
    fans = [interface.get_fan_zone(f"fan{i}") for i in range(1, 5)]
    async with setup(interface):
        await interface.update()
        for fan in fans:
            print(fan)

asyncio.run(main())