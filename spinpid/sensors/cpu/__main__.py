from .sysctl import maxCPUTemperatureSource

import asyncio
async def debug_main():
    #print("Debug: get_all_cpu_temperatures():")
    #async for temp in get_all_cpu_temperatures():
    #    print("temperature: ", temp)
    print("Debug: max cpu temperature:")
    print(await maxCPUTemperatureSource.get_temperature())
loop = asyncio.get_event_loop()
loop.run_until_complete(debug_main())
loop.close()

