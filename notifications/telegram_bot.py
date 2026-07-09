import os
import requests
from notifications.base import BaseNotifier

class TelegramNotifier(BaseNotifier):
    def __init__(self, token: str = None, chat_id: str = None):
        self.token = token or os.getenv("TELEGRAM_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")
        
    def send_message(self, message: str) -> bool:
        if not self.token or not self.chat_id:
            print("TelegramNotifier: No token or chat_id configured.")
            return False
            
        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error sending Telegram message: {e}")
            return False
