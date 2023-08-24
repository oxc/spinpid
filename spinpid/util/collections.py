
class defaultdict(dict):
    """dict subclass that provides a default *based on the missing key*"""

    def __init__(self, default_factory):
        self.default_factory = default_factory

    def __missing__(self, key):
        return self.setdefault(key, self.default_factory(key))
