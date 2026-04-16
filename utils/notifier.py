import os
import requests


class Notifier:
    def __init__(self):
        # โหลดค่าจาก .env รองรับหลายช่องทาง
        self.line_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        self.line_user = os.getenv("LINE_USER_ID")
        
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
        
        self.telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.telegram_chat = os.getenv("TELEGRAM_CHAT_ID")

    def send(self, msg: str):
        # 1. ส่งผ่าน Discord (ฟรี 100% ลิมิตเยอะมาก)
        if self.discord_webhook:
            self._send_discord(msg)
            
        # 2. ส่งผ่าน Telegram (ฟรี 100% ไร้ลิมิต)
        elif self.telegram_token and self.telegram_chat:
            self._send_telegram(msg)
            
        # 3. ส่งผ่าน LINE (ยังเก็บไว้เป็น Backup)
        elif self.line_token and self.line_user:
            self._send_line(msg)
            
        else:
            print("⚠️ ไม่พบ Config ของระบบแจ้งเตือนใดๆ จะข้ามการส่งข้อความ")

    def _send_line(self, msg: str):
        url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.line_token}",
        }
        payload = {"to": self.line_user, "messages": [{"type": "text", "text": msg}]}
        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                print("✅ ส่งเข้า LINE สำเร็จ")
            else:
                print(f"❌ ส่ง LINE ไม่สำเร็จ: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Error ส่ง LINE: {e}")

    def _send_discord(self, msg: str):
        url = self.discord_webhook
        payload = {"content": msg}
        try:
            response = requests.post(url, json=payload)
            if response.status_code in (200, 204):
                print("✅ ส่งเข้า Discord สำเร็จ")
            else:
                print(f"❌ ส่ง Discord ไม่สำเร็จ: {response.status_code}")
        except Exception as e:
            print(f"❌ Error ส่ง Discord: {e}")

    def _send_telegram(self, msg: str):
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        payload = {"chat_id": self.telegram_chat, "text": msg}
        try:
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                print("✅ ส่งเข้า Telegram สำเร็จ")
            else:
                print(f"❌ ส่ง Telegram ไม่สำเร็จ: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Error ส่ง Telegram: {e}")
