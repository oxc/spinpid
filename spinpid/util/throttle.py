import inspect
from datetime import timedelta, datetime
from functools import wraps


def throttle(seconds=0, microseconds=0, milliseconds=0, minutes=0):
    """
    Decorator that prevents a function from being called more than once every
    time period.

    To create a function that cannot be called more than once a minute:

        @throttle(minutes=1)
        def my_fun():
            pass
    """
    throttle_delta = timedelta(seconds=seconds, microseconds=microseconds, milliseconds=milliseconds, minutes=minutes)
    time_of_last_call = datetime.min

    def decorator(f: callable):
        fallback_value_generator = None
        if inspect.iscoroutinefunction(f):
            async def fallback_value_generator():
                return

        @wraps(f)
        def wrapper(*args, **kwargs):
            nonlocal time_of_last_call, throttle_delta

            now = datetime.now()
            time_since_last_call = now - time_of_last_call

            if time_since_last_call > throttle_delta:
                time_of_last_call = now
                return f(*args, **kwargs)

            if fallback_value_generator is not None:
                return fallback_value_generator()

        return wrapper
    return decorator