from spinpid.interfaces import SensorInterface, TemperatureSensor

from spinpid.interfaces.sensor import MeanTemperatureSensor, MaxTemperatureSensor

from middlewared.client import Client

class TrueNAS(SensorInterface):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self.middleware = Client()

    async def setup(self):
        async def teardown():
            self.middleware.close()
        return teardown

    def get_sensor(self, channel: str, **kwargs) -> TemperatureSensor:
        if channel in ('disk', 'disks'):
            from spinpid.interfaces.truenas.disk import TrueNASDiskTemperaturesSource
            return MeanTemperatureSensor(TrueNASDiskTemperaturesSource(self.middleware))
        if channel == 'cpu':
            from spinpid.interfaces.truenas.cpu import TrueNASCPUTemperaturesSource
            return MaxTemperatureSensor(TrueNASCPUTemperaturesSource(self.middleware), label = 'CPU')
        raise ValueError(f"Unknown channel '{channel}', must be one of 'disk', 'cpu'")

