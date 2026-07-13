import logging
import os
import subprocess
import tempfile
from io import StringIO
from typing import Iterable, Optional

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

    def __init__(self) -> None:
        self._sdr_cache: Optional[str] = None

    async def load_sdr_cache(self) -> None:
        """Dump the SDR repository to a local cache file once.

        Reading the SDR repository over the in-band KCS interface is slow
        (byte-at-a-time, hundreds of transactions). Without a cache every
        `ipmitool sdr` invocation re-reads the whole repository. Dumping it
        once and passing `-S <file>` on subsequent calls skips that reload;
        live sensor *readings* are still fetched from the BMC each time, so
        temperatures and fan RPMs stay current."""
        fd, path = tempfile.mkstemp(prefix='spinpid-ipmi-sdr-', suffix='.cache')
        os.close(fd)
        try:
            await self.ipmitool.run('sdr', 'dump', path)
        except BaseException:
            os.unlink(path)
            raise
        self._sdr_cache = path
        logger.debug("Loaded IPMI SDR cache to %s", path)

    def clear_sdr_cache(self) -> None:
        if self._sdr_cache is not None:
            try:
                os.unlink(self._sdr_cache)
            except FileNotFoundError:
                pass
            self._sdr_cache = None

    @property
    def _global_args(self) -> tuple[str, ...]:
        if self._sdr_cache is not None:
            return ('-S', self._sdr_cache)
        return ()

    async def raw(self, *args: str) -> None:
        return await self.ipmitool.run(*self._global_args, 'raw', *args)

    async def raw_read(self, *args: str) -> str:
        return await self.ipmitool.run_and_read(*self._global_args, 'raw', *args)

    async def _sdr(self, *args: str) -> Iterable[SDREntry]:
        out = await self.ipmitool.run_and_read(*self._global_args, 'sdr', *args)
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
