import os
import time
import requests
import pandas as pd
from datetime import datetime, time as datetime_time
from settrade_v2 import Investor
from dotenv import load_dotenv  # นำเข้าไลบรารีอ่านไฟล์ .env

# โหลดค่าจากไฟล์ .env ขึ้นมาไว้ในระบบ
load_dotenv()


# ==========================================
# เพิ่มฟังก์ชันส่งข้อความเข้า LINE
# ==========================================
def send_line_message(msg):
    access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
    user_id = os.getenv("LINE_USER_ID")

    if not access_token or not user_id:
        print("⚠️ ไม่พบ Config ของ LINE Messaging API จะข้ามการส่งข้อความ")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

    # รูปแบบ Payload สำหรับ Messaging API
    payload = {"to": user_id, "messages": [{"type": "text", "text": msg}]}

    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            print("✅ ส่งแจ้งเตือนเข้า LINE สำเร็จ")
        else:
            print(f"❌ ส่ง LINE ไม่สำเร็จ: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error ส่ง LINE: {e}")


def is_market_open():
    """ฟังก์ชันเช็คว่าตอนนี้ตลาดหุ้นไทยเปิดอยู่หรือไม่"""
    now = datetime.now()

    # เช็คว่าเป็นวันจันทร์ (0) ถึง ศุกร์ (4) หรือไม่
    if now.weekday() > 4:
        return False

    current_time = now.time()

    # ช่วงเช้า 10:00 - 12:30
    morning_session = current_time >= datetime_time(
        10, 0
    ) and current_time <= datetime_time(12, 30)
    # ช่วงบ่าย 14:30 - 16:30
    afternoon_session = current_time >= datetime_time(
        14, 30
    ) and current_time <= datetime_time(16, 30)

    return morning_session or afternoon_session


def run_bot(investor, account_no, pin):
    try:
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] ดึงข้อมูลและประมวลผล...")
        market = investor.MarketData()
        equity = investor.Equity(account_no=account_no)

        historical_data = market.get_candlestick("PTT", "1d", 200)
        df = pd.DataFrame(historical_data)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df.set_index("time", inplace=True)

        df["SMA_15"] = df["close"].rolling(window=15).mean()
        df["SMA_50"] = df["close"].rolling(window=50).mean()

        df["Signal"] = 0
        df.loc[df["SMA_15"] > df["SMA_50"], "Signal"] = 1
        df.loc[df["SMA_15"] < df["SMA_50"], "Signal"] = -1
        df["Position"] = df["Signal"].diff()

        latest_data = df.iloc[-1]
        trade_volume = 100

        # ----------------------------------------------------
        # เพิ่มการเรียกใช้ send_line_message ในจังหวะที่เทรด
        # ----------------------------------------------------
        if latest_data["Position"] == 2:
            msg = f"\n📈 สัญญาณซื้อ (Golden Cross)!\nหุ้น: PTT\nราคา: {latest_data['close']}\nกำลังส่งคำสั่งเข้าระบบ..."
            print(msg)
            send_line_message(msg)

            order = equity.place_order(
                pin=pin,
                symbol="PTT",
                side="Buy",
                volume=trade_volume,
                price=latest_data["close"],
                price_type="Limit",
            )
            send_line_message(
                f"✅ ยิงคำสั่งซื้อสำเร็จ\nOrder No: {order.get('order_no', 'N/A')}"
            )

        elif latest_data["Position"] == -2:
            msg = f"\n📉 สัญญาณขาย (Death Cross)!\nหุ้น: PTT\nราคา: {latest_data['close']}\nกำลังส่งคำสั่งเข้าระบบ..."
            print(msg)
            send_line_message(msg)

            order = equity.place_order(
                pin=pin,
                symbol="PTT",
                side="Sell",
                volume=trade_volume,
                price=latest_data["close"],
                price_type="Limit",
            )
            send_line_message(
                f"✅ ยิงคำสั่งขายสำเร็จ\nOrder No: {order.get('order_no', 'N/A')}"
            )

        else:
            print("💤 ยังไม่มีจุดตัดใหม่ (Hold and Wait)")

    except Exception as e:
        error_msg = f"❌ เกิดข้อผิดพลาดในบอท: {e}"
        print(error_msg)
        send_line_message(error_msg)  # แจ้งเตือนเวลาบอทพังด้วย


# ==========================================
# Main Loop
# ==========================================
if __name__ == "__main__":
    print("🚀 Starting Bualuang Algo Trading Daemon...")

    # ---------------------------------------------
    # ดึงค่า Config มาจากไฟล์ .env แทนการฝังในโค้ด
    # ---------------------------------------------
    APP_ID = os.getenv("APP_ID")
    APP_CODE = os.getenv("APP_CODE")
    APP_SECRET = os.getenv("APP_SECRET")
    ACCOUNT_NO = os.getenv("ACCOUNT_NO")
    BROKER_ID = os.getenv("BROKER_ID")
    PIN = os.getenv("PIN")

    # เช็คว่ามีค่าครบหรือไม่ (ป้องกันการลืมใส่ Config)
    if not all([APP_ID, APP_SECRET, ACCOUNT_NO, PIN]):
        print("❌ เกิดข้อผิดพลาด: ไม่พบข้อมูล Config กรุณาตรวจสอบไฟล์ .env")
        exit()

    try:
        investor = Investor(
            app_id=APP_ID,
            app_secret=APP_SECRET,
            broker_id=BROKER_ID,
            app_code=APP_CODE,
            is_auto_queue=False,
        )
        print("✅ เชื่อมต่อ SETTRADE Sandbox สำเร็จ พร้อมทำงาน!")
        # เพิ่มบรรทัดนี้เพื่อทดสอบ LINE
        send_line_message(
            "🤖 บอท Bualuang Algo เวอร์ชัน Messaging API เริ่มทำงานแล้วครับเจ้านาย!"
        )
    except Exception as e:
        print(f"❌ เชื่อมต่อ API ล้มเหลว: {e}")
        exit()

    while True:
        if is_market_open():
            run_bot(investor, ACCOUNT_NO, PIN)
            time.sleep(300)
        else:
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}] นอกเวลาทำการ ตลาดปิด... บอทพักการทำงาน 😴"
            )
            time.sleep(3600)
