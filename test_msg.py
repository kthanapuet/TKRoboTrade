from dotenv import load_dotenv
import os
import sys

# Load environment variables FIRST before initializing Notifier
load_dotenv()

# Append path to allow importing from utils
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.notifier import Notifier

def main():
    print("🚀 เริ่มทำการทดสอบระบบแจ้งเตือน (Notifier Test)")
    print(f"Telegram Token: {'✅ Configured' if os.getenv('TELEGRAM_BOT_TOKEN') else '❌ Missing'}")
    print(f"Telegram Chat ID: {'✅ Configured' if os.getenv('TELEGRAM_CHAT_ID') else '❌ Missing'}")
    print("-" * 40)
    
    notifier = Notifier()
    test_message = "🔔 เทสระบบแจ้งเตือนจากบอท TKRoboTrade! หากได้รับข้อความนี้แสดงว่าเชื่อมต่อสำเร็จเรียบร้อยครับ"
    print("กำลังส่งข้อความ: ", test_message)
    
    # สั่งให้ส่งข้อความ
    notifier.send(test_message)

if __name__ == "__main__":
    main()
