import asyncio
import logging
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
    """Talks to the BMC through a single, long-lived ``ipmitool shell`` process.

    Every fresh ``ipmitool`` invocation pays a fixed per-process BMC/KCS init
    handshake (~60 ms of busy-polled CPU on the in-band interface), which
    dominates the cost; the actual sensor reads are cheap once initialised.
    So instead of forking ipmitool per command we spawn ``ipmitool shell``
    once and feed it commands over stdin, reading each response up to the
    ``ipmitool> `` prompt. Commands are serialised through a lock (the shell is
    a single serial channel) and the process is respawned on demand if it dies.

    The shell also parses the SDR repository once, on the first ``sdr`` command,
    and keeps it in memory for the rest of its life, so there is no need to
    maintain an external ``-S`` SDR cache; live sensor *readings* are still
    fetched from the BMC on every command.
    """

    ipmitool = Command('ipmitool')

    _PROMPT = b'ipmitool> '
    _COMMAND_TIMEOUT = 15  # seconds to wait for a single command's response

    def __init__(self) -> None:
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._lock = asyncio.Lock()

    async def _start(self) -> None:
        logger.debug("Starting persistent ipmitool shell")
        self._proc = await asyncio.create_subprocess_exec(
            self.ipmitool.command, 'shell',
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        # consume the shell banner / initial prompt
        await asyncio.wait_for(self._read_to_prompt(), self._COMMAND_TIMEOUT)

    async def stop(self) -> None:
        """Cleanly shut down the persistent shell (best effort)."""
        proc, self._proc = self._proc, None
        if proc is None or proc.returncode is not None:
            return
        try:
            proc.stdin.write(b'exit\n')
            await proc.stdin.drain()
            await asyncio.wait_for(proc.wait(), timeout=5)
        except (asyncio.TimeoutError, OSError):
            await self._terminate(proc)

    @staticmethod
    async def _terminate(proc: asyncio.subprocess.Process) -> None:
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            try:
                await proc.wait()
            except Exception:
                pass

    async def _read_to_prompt(self) -> str:
        assert self._proc is not None and self._proc.stdout is not None
        buf = bytearray()
        while not buf.endswith(self._PROMPT):
            chunk = await self._proc.stdout.read(4096)
            if not chunk:
                raise IPMIError("ipmitool shell exited unexpectedly")
            buf += chunk
        return buf[:buf.rfind(self._PROMPT)].decode('utf-8', 'replace')

    async def _run(self, command: str) -> str:
        """Send one command to the persistent shell and return its output.

        Serialised through ``self._lock`` since the shell is a single channel.
        A dead shell is respawned on the next call; a hung/failed command kills
        the shell so it gets respawned rather than left in a bad state."""
        async with self._lock:
            if self._proc is None or self._proc.returncode is not None:
                await self._start()
            try:
                self._proc.stdin.write((command + '\n').encode())
                await self._proc.stdin.drain()
                out = await asyncio.wait_for(self._read_to_prompt(), self._COMMAND_TIMEOUT)
            except (asyncio.TimeoutError, IPMIError, OSError):
                proc, self._proc = self._proc, None
                if proc is not None:
                    await self._terminate(proc)
                raise
        # the shell echoes the command back as the first output line; drop it
        echo = command + '\n'
        if out.startswith(echo):
            out = out[len(echo):]
        return out

    async def raw(self, *args: str) -> None:
        await self._run('raw ' + ' '.join(args))

    async def raw_read(self, *args: str) -> str:
        return await self._run('raw ' + ' '.join(args))

    async def _sdr(self, *args: str) -> Iterable[SDREntry]:
        out = await self._run('sdr ' + ' '.join(args))
        def parse_entries():
            with StringIO(out) as lines:
                for line in lines:
                    if not line.strip():
                        continue
                    fields = [f.strip() for f in line.split('|')]
                    if len(fields) != 5:
                        raise IPMIError(f"Unexpected line from `ipmitool sdr`: {line}")
                    yield SDREntry(*fields)

        return parse_entries()

    async def sdr_type(self, typ: str) -> Iterable[SDREntry]:
        return await self._sdr('type', typ)
