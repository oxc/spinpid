import asyncio
import errno
import logging
from typing import Any, Optional

from truenas_api_client import Client
from truenas_api_client.exc import ClientException

logger = logging.getLogger(__name__)


class Middleware:
    """A retrying wrapper around the TrueNAS middleware client.

    Two kinds of transient failure would otherwise kill the sensor task, since
    a failed `call()` propagates all the way out of `Sensor.update()`:

    * middlewared fails to produce a result, e.g. `reporting.cpu_temperatures`
      raising `Response payload is not completed: <TransferEncodingError ...>`
      because its own HTTP fetch of the data got truncated. The websocket is
      fine here, so the call is simply retried.
    * the websocket to middlewared dies (middlewared restart, socket torn
      down), reported as `WebSocket connection closed with code=...`. The
      client never reconnects on its own, so we drop it and reconnect.

    Genuine API errors are raised unchanged."""

    _MAX_ATTEMPTS = 3
    _RETRY_DELAY = 0.2  # seconds, multiplied by the attempt number

    # Errors from middlewared that mean "this call didn't work out, ask again".
    _RETRY_MARKERS = (
        'payload is not completed',
        'transfer length',
        'timed out',
        'timeout',
    )
    # Errors that mean the connection itself is gone and must be re-established
    # before retrying.
    _RECONNECT_MARKERS = (
        'connection closed',
        'connection reset',
        'connection aborted',
        'server disconnected',
        'broken pipe',
        'not connected',
        'closing transport',
    )

    def __init__(self) -> None:
        self._client: Optional[Client] = None
        self._lock = asyncio.Lock()

    def _connect(self) -> Client:
        if self._client is None:
            logger.debug("Connecting to middlewared")
            self._client = Client()
        return self._client

    async def close(self) -> None:
        client, self._client = self._client, None
        if client is not None:
            try:
                # `close` waits up to a second for the reader thread to finish
                await asyncio.to_thread(client.close)
            except Exception as e:
                logger.debug("Ignoring error while closing middleware client: %s", e)

    @classmethod
    def _classify(cls, error: Exception) -> Optional[bool]:
        """Return whether `error` is retryable, and if so whether it needs a
        reconnect first: None = not retryable, False = retry as is,
        True = reconnect and retry."""
        # a dropped websocket is reported as ECONNABORTED, CallTimeout as ETIMEDOUT
        code = getattr(error, 'errno', None)
        if isinstance(error, OSError) or code == errno.ECONNABORTED:
            return True
        if code == errno.ETIMEDOUT:
            return False
        message = str(error).lower()
        if any(marker in message for marker in cls._RECONNECT_MARKERS):
            return True
        if any(marker in message for marker in cls._RETRY_MARKERS):
            return False
        return None

    def _call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """Blocking call, run in a worker thread by `call`."""
        return self._connect().call(method, *args, **kwargs)

    async def call(self, method: str, *args: Any, **kwargs: Any) -> Any:
        """Call an API method, retrying transient failures.

        The client is synchronous (websocket-client plus a reader thread, it
        blocks on an Event), so the call is handed to a worker thread to keep
        the event loop free. `_lock` keeps one call in flight at a time, since
        a single client is shared by all sensors and it does not guard its
        websocket against concurrent senders."""
        last_error: Optional[Exception] = None
        async with self._lock:
            for attempt in range(1, self._MAX_ATTEMPTS + 1):
                try:
                    return await asyncio.to_thread(self._call, method, *args, **kwargs)
                except (ClientException, OSError) as e:
                    reconnect = self._classify(e)
                    if reconnect is None:
                        raise
                    last_error = e
                    if reconnect:
                        await self.close()  # the next attempt reconnects
                    logger.warning("Middleware call %r attempt %d/%d failed: %s",
                                   method, attempt, self._MAX_ATTEMPTS, e)
                    if attempt < self._MAX_ATTEMPTS:
                        await asyncio.sleep(self._RETRY_DELAY * attempt)
        raise ClientException(
            f"Middleware call {method!r} failed after {self._MAX_ATTEMPTS} attempts: {last_error}"
        )


class TrueNASClient:
    middleware: Middleware

    def __init__(self, middleware: Middleware, **kwargs) -> None:
        super().__init__(**kwargs)
        self.middleware = middleware
