from typing import Dict, List, Collection, AsyncIterable
from middlewared.utils import Popen, run
from io import StringIO
import functools
import logging
import subprocess

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
            return (None, None)
        chunks = raw_value.split(None, 1)
        if len(chunks) == 1:
            return (raw_value, None)
        return chunks


class IPMIError(Exception):
    pass

class IPMITool:
    async def _run(self, *args: str) -> subprocess.CompletedProcess:
        return await run('ipmitool', *args)

    async def _popen(self, *args: str) -> str:
        p1 = await Popen(['ipmitool'] + list(args), stdout=subprocess.PIPE)
        return (await p1.communicate())[0].decode()

    async def raw(self, *args: str) -> subprocess.CompletedProcess:
        return await self._run('raw', *args)

    async def raw_read(self, *args: str) -> str:
        return await self._popen('raw', *args)

    async def _sdr(self, *args: str) -> AsyncIterable[SDREntry]:
        out = await self._popen('sdr', *args)
        with StringIO(out) as lines:
            for line in lines:
                fields = [f.strip() for f in line.split('|')]
                if len(fields) != 5:
                    raise IPMIError(f"Unexpected line from `ipmitool sdr`: {line}")
                yield SDREntry(*fields)

    def sdr_type(self, type: str) -> AsyncIterable[SDREntry]:
        return self._sdr('type', type) 


