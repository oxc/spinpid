from middlewared.client import Client


class TrueNASClient:
    middleware: Client

    def __init__(self, middleware: Client, **kwargs) -> None:
        super().__init__(**kwargs)
        self.middleware = middleware
