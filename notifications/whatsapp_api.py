import os
import requests
from notifications.base import BaseNotifier

class WhatsappNotifier(BaseNotifier):
    def __init__(self, token: str = None, phone_number_id: str = None, to_number: str = None):
        self.token = token or os.getenv("WHATSAPP_TOKEN")
        self.phone_number_id = phone_number_id or os.getenv("WHATSAPP_PHONE_ID")
        self.to_number = to_number or os.getenv("WHATSAPP_TO_NUMBER")
        
    def send_message(self, message: str) -> bool:
        if not self.token or not self.phone_number_id or not self.to_number:
            print("WhatsappNotifier: Credentials not fully configured.")
            return False
            
        url = f"https://graph.facebook.com/v17.0/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        # Primero intentamos enviar mensaje de texto libre
        payload_text = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": self.to_number,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": message
            }
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload_text)
            response.raise_for_status()
            return True
        except requests.exceptions.HTTPError as e:
            # Si da error por ventana de 24h, deberíamos enviar plantilla 'opo_alerta'
            print(f"Error enviando mensaje libre WhatsApp: {e.response.text}")
            print("Fallback a plantilla opo_alerta...")
            return self._send_template()
        except Exception as e:
            print(f"Error general enviando WhatsApp: {e}")
            return False
            
    def _send_template(self) -> bool:
        url = f"https://graph.facebook.com/v17.0/{self.phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        payload_template = {
            "messaging_product": "whatsapp",
            "to": self.to_number,
            "type": "template",
            "template": {
                "name": "opo_alerta",
                "language": {
                    "code": "es"
                }
            }
        }
        try:
            response = requests.post(url, headers=headers, json=payload_template)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error enviando plantilla WhatsApp: {e}")
            return False
