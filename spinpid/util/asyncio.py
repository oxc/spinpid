import asyncio
from typing import Iterable


def raise_exceptions(tasks: Iterable[asyncio.Task], logger) -> None:
    exception_raised = False
    for task in tasks:
        if not task.cancelled() and task.done():
            exception = task.exception()
            if exception:
                logger.error("Exception in task %s:", task.get_name(), exc_info=exception)
                exception_raised = True
    if exception_raised:
        raise Exception("Error while running tasks")
