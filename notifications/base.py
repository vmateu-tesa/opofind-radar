from abc import ABC, abstractmethod

class BaseNotifier(ABC):
    @abstractmethod
    def send_message(self, message: str) -> bool:
        pass
