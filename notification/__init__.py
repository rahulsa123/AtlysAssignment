from abc import ABC, abstractmethod


class BaseNotification(ABC):
    @abstractmethod
    def notify(self, message):
        pass
