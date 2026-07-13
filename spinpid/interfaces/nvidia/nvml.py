from datetime import timedelta

import pynvml

from spinpid.interfaces import SensorInterface, TearDown, only_before_setup
from spinpid.interfaces.sensor import Temperature, TemperatureSensor
from spinpid.util.collections import defaultdict


class NvidiaNVML(SensorInterface):
    """GPU temperature source backed by a persistent NVML handle.

    Unlike :class:`~spinpid.interfaces.nvidia.NvidiaSMI`, this does not spawn a
    subprocess per reading. NVML is initialised once in :meth:`setup` and each
    reading is a direct (microsecond) library call, so it can be polled at a
    short interval without noticeable CPU cost.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        def create_sensor(channel: int) -> 'NvidiaNVMLSensor':
            return NvidiaNVMLSensor(self, channel)

        self.sensors = defaultdict(create_sensor)
        self._handles: dict[int, object] = {}

    @only_before_setup
    def get_sensor(self, channel: int, interval: timedelta = None, **kwargs) -> TemperatureSensor:
        return self.sensors[channel]

    async def setup(self) -> TearDown:
        teardown = await super().setup()
        pynvml.nvmlInit()

        async def _teardown() -> None:
            pynvml.nvmlShutdown()
            await teardown()

        return _teardown

    def _handle(self, device_id: int):
        handle = self._handles.get(device_id)
        if handle is None:
            handle = pynvml.nvmlDeviceGetHandleByIndex(device_id)
            self._handles[device_id] = handle
        return handle

    def get_temperature(self, device_id: int) -> int:
        return pynvml.nvmlDeviceGetTemperature(self._handle(device_id), pynvml.NVML_TEMPERATURE_GPU)


class NvidiaNVMLSensor(TemperatureSensor):
    def __init__(self, interface: NvidiaNVML, device_id: int) -> None:
        self.interface = interface
        self.device_id = device_id

    async def get_temperature(self) -> Temperature:
        temp = self.interface.get_temperature(self.device_id)
        return Temperature(int(temp), f"GPU {self.device_id}")


if __name__ == '__main__':
    import asyncio

    from spinpid.interfaces import setup

    async def main():
        nvidia = NvidiaNVML()
        device = nvidia.get_sensor(0)
        async with setup(nvidia):
            print(await device.get_temperature())

    asyncio.run(main())
