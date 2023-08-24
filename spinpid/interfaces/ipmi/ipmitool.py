import logging
import subprocess
from io import StringIO
from typing import Iterable

from spinpid.util.command import Command

logger = logging.getLogger(__name__)


class SDREntry:
    def __init__(self, name, hex_id, status, entity, raw_value):
        self.name = name
        self.hex_id = hex_id
        self.status = status
        self.entity = entity
        self.raw_value = raw_value
        self.value, self.unit = SDREntry.split_value(raw_value)

    @staticmethod
    def split_value(raw_value):
        if raw_value.lower() == "no reading":
            return None, None
        chunks = raw_value.split(None, 1)
        if len(chunks) == 1:
            return raw_value, None
        return chunks


class IPMIError(Exception):
    pass


class IPMITool:
    ipmitool = Command('ipmitool')

    async def raw(self, *args: str) -> None:
        return await self.ipmitool.run('raw', *args)

    async def raw_read(self, *args: str) -> str:
        return await self.ipmitool.run_and_read('raw', *args)

    async def _sdr(self, *args: str) -> Iterable[SDREntry]:
        out = await self.ipmitool.run_and_read('sdr', *args)
        def parse_entries():
            with StringIO(out) as lines:
                for line in lines:
                    fields = [f.strip() for f in line.split('|')]
                    if len(fields) != 5:
                        raise IPMIError(f"Unexpected line from `ipmitool sdr`: {line}")
                    yield SDREntry(*fields)

        return parse_entries()

    async def sdr_type(self, typ: str) -> Iterable[SDREntry]:
        return await self._sdr('type', typ)
