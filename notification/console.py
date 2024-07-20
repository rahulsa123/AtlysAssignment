from notification import BaseNotification


class ConsoleNotification(BaseNotification):
    def notify(self, message):
        print(message)
