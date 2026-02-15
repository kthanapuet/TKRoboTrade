import os
import requests


class LineNotifier:
    def __init__(self):
        # ดึงค่าจากตัวแปรระบบ (ซึ่งถูกโหลดมาจาก .env ใน bot.py แล้ว)
        self.access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        self.user_id = os.getenv("LINE_USER_ID")

    def send(self, msg: str):
        if not self.access_token or not self.user_id:
            print("⚠️ ไม่พบ Config ของ LINE Messaging API จะข้ามการส่งข้อความ")
            return

        url = "https://api.line.me/v2/bot/message/push"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}",
        }

        payload = {"to": self.user_id, "messages": [{"type": "text", "text": msg}]}

        try:
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                print("✅ ส่งแจ้งเตือนเข้า LINE สำเร็จ")
            else:
                print(f"❌ ส่ง LINE ไม่สำเร็จ: {response.status_code} - {response.text}")
        except Exception as e:
            print(f"❌ Error ส่ง LINE: {e}")
