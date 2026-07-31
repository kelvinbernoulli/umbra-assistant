from typing import Callable


class EventBus:
    def __init__(self):
        self.subscribers: list[Callable[[dict], None]] = []

    def subscribe(self, callback: Callable[[dict], None]) -> None:
        self.subscribers.append(callback)

    def publish(self, event: dict) -> None:
        for callback in self.subscribers:
            callback(event)
