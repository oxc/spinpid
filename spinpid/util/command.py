import asyncio
import signal
import subprocess

# copied from https://github.com/truenas/middleware/blob/TS-22.12.3.3/src/middlewared/middlewared/utils/__init__.py#L48
async def run(*args, **kwargs):
    if isinstance(args[0], list):
        args = tuple(args[0])
    kwargs.setdefault('stdout', subprocess.PIPE)
    kwargs.setdefault('stderr', subprocess.PIPE)
    check = kwargs.pop('check', True)
    encoding = kwargs.pop('encoding', None)
    errors = kwargs.pop('errors', None) or 'strict'
    input = kwargs.pop('input', None)
    if input is not None:
        kwargs['stdin'] = subprocess.PIPE
    abort_signal = kwargs.pop('abort_signal', signal.SIGKILL)
    proc = await asyncio.create_subprocess_exec(*args, **kwargs)
    try:
        stdout, stderr = await proc.communicate(input)
    except asyncio.CancelledError:
        if abort_signal is not None:
            proc.send_signal(abort_signal)
        raise
    if encoding:
        if stdout is not None:
            stdout = stdout.decode(encoding, errors)
        if stderr is not None:
            stderr = stderr.decode(encoding, errors)
    cp = subprocess.CompletedProcess(args, proc.returncode, stdout=stdout, stderr=stderr)
    if check:
        cp.check_returncode()
    return cp

class Command:
    def __init__(self, command):
        self.command = command

    async def run(self, *args: str) -> None:
        await run(self.command, *args)

    async def run_and_read(self, *args: str) -> str:
        result = await run(self.command, *args, encoding='utf-8')
        return result.stdout
