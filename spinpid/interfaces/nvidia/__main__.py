import asyncio

from spinpid.interfaces import setup
from spinpid.interfaces.nvidia import NvidiaSMI


async def main():
    nvidia = NvidiaSMI()
    device = nvidia.get_sensor(0)
    async with setup(nvidia):
        print(await device.get_temperature())

asyncio.run(main())