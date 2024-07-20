from cache import BaseCache


class DictCache(BaseCache):
    """
    Using python dict as cache to handle testing load.
    """
    def __init__(self):
        self.cache = {}

    def get(self, key):
        return self.cache.get(key)

    def set(self, key, value):
        self.cache[key] = value
