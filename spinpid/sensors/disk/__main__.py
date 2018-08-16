from .freenas import meanDiskTemperatureSource

import asyncio
async def debug_main():
    #print("Debug: get_all_disks():")
    #disks = await get_all_disks()
    #for disk in (Disk(d) for d in disks):
    #    print(disk, "temperature: ", await disk.get_temperature())
    temp = await meanDiskTemperatureSource.get_temperature()
    cols = [(label, t) for label, t in temp]
    collen = [max(len(str(k)),len(str(v))) for k,v in cols]
    for (header,_), w in zip(cols, collen):
        print(f"| {header:^{w}} ", end="")
    print("|")
    for (_, value), w in zip(cols, collen):
        print(f"| {value:^{w}} ", end="")
    print("|")



loop = asyncio.get_event_loop()
loop.run_until_complete(debug_main())
loop.close()

