from spinpid.interfaces import SensorInterface, TemperatureSensor
from spinpid.interfaces.ipmi.fan import IPMIFanInterface
from spinpid.interfaces.sensor import MaxTemperatureSensor


class IPMI(IPMIFanInterface, SensorInterface):
    def get_sensor(self, channel: str, **kwargs) -> TemperatureSensor:
        if channel == 'system':
            from spinpid.interfaces.ipmi.cpu import IPMIToolCPUSource
            return MaxTemperatureSensor(IPMIToolCPUSource(self.ipmitool, "CPU Temp", "PCH Temp"), "Sys")