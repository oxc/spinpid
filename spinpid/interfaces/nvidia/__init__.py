from datetime import timedelta

from spinpid.interfaces import SensorInterface, TemperatureSensor, only_before_setup, TearDown
from spinpid.interfaces.sensor import Temperature
from spinpid.util.collections import defaultdict
from spinpid.util.command import Command

nvidia_smi = Command("nvidia-smi")

class NvidiaSMI(SensorInterface):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        def create_sensor(channel: int) -> NvidiaSMISensor:
            return NvidiaSMISensor(channel)
        self.sensors = defaultdict(create_sensor)

    @only_before_setup
    def get_sensor(self, channel: int, interval: timedelta = None, **kwargs) -> TemperatureSensor:
        sensor = self.sensors[channel]
        return sensor

class NvidiaSMISensor(TemperatureSensor):
    def __init__(self, device_id: int):
        self.device_id = device_id

    async def get_temperature(self) -> Temperature:
        temp = await nvidia_smi.run_and_read(
            "--query-gpu=temperature.gpu",
            "--format=csv,noheader,nounits",
            "--id=" + str(self.device_id)
        )
        return Temperature(int(temp), f"GPU {self.device_id}")
