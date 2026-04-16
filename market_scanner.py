import yfinance as yf
import pandas as pd
import sys
import os
from dotenv import load_dotenv

# Load ENV and Notifier
load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.notifier import Notifier

# กลุ่มหุ้นที่ต้องการสแกน (DR และ หุ้นใหญ่ๆ ในตลาด)
SCAN_UNIVERSE = [
    # Top Tech DRs
    "NVDA80.BK", "AAPL80.BK", "MSFT80.BK", "TSLA80.BK", "GOOG80.BK", "AMZN80.BK", "META80.BK",
    # Global ETF DRs
    "NDX01.BK", "SPX01.BK", "E1VFVN3001.BK", "FUEVFVND01.BK", "JAPAN13.BK", "CHINA01.BK", "HKCE11.BK",
    # Asian DRs
    "TENCENT80.BK", "BABA80.BK", "PINGAN80.BK",
    # SET50 Some active stocks for comparison
    "PTT.BK", "AOT.BK", "ADVANC.BK", "GULF.BK", "DELTA.BK", "CPALL.BK", "KBANK.BK", "KTB.BK"
]

def scan_liquidity():
    print("🔍 กำลังสแกนหาสภาพคล่อง (Top Demand) ประจำวัน...")
    results = []

    for symbol in SCAN_UNIVERSE:
        try:
            ticker = yf.Ticker(symbol)
            # ดึงข้อมูลย้อนหลัง 5 วันเพื่อเทียบค่าเฉลี่ย
            hist = ticker.history(period="5d")
            if len(hist) < 2:
                continue

            today = hist.iloc[-1]
            avg_vol_5d = hist["Volume"].mean()
            
            # คำนวณมูลค่าการซื้อขายวันนี้ (Trading Value = Price * Volume)
            today_value = today["Close"] * today["Volume"]
            
            # คำนวณความผิดปกติของ Volume (Spike)
            # ยกเว้นกรณีหารด้วย 0
            vol_spike = (today["Volume"] / avg_vol_5d) if avg_vol_5d > 0 else 0

            results.append({
                "Symbol": symbol,
                "Price": today["Close"],
                "Volume": today["Volume"],
                "Value": today_value,
                "VolSpike": vol_spike
            })
        except Exception as e:
            print(f"⚠️ ดึงข้อมูล {symbol} ไม่สำเร็จ: {e}")

    if not results:
        return

    # สร้าง DataFrame เพื่อคำนวณและเรียงลำดับ
    df = pd.DataFrame(results)

    # กรองเอาเฉพาะตัวที่มีการซื้อขายจริงๆ (Value > 0)
    df = df[df["Value"] > 0]
    
    # เรียงลำดับ 10 อันดับแรก โดยใช้เกณฑ์ "มูลค่าการซื้อขายสูงสุด" หรือ "Volume พุ่งสูงสุด"
    # ในที่นี้ขอดึงจาก "มูลค่าการซื้อขายรวมสูงสุด (Top Turnover / Liquidity)"
    top10_value = df.sort_values(by="Value", ascending=False).head(10)

    # สร้างข้อความแจ้งเตือน
    msg = "🔥 10 อันดับ หุ้น/DR สภาพคล่องสูงประจำวัน (Volume + Value)\n"
    msg += "เพื่อเป็นไอเดียคัดเลือกหุ้นเข้าพอร์ต\n"
    msg += "-" * 30 + "\n"

    for i, row in enumerate(top10_value.itertuples(), start=1):
        symbol_name = row.Symbol.replace(".BK", "")
        # แปลง Value เป็นล้านบาท
        value_mb = row.Value / 1_000_000
        
        # เพิ่มสัญลักษณ์ไฟถ้า Volพุ่ง มากกว่าค่าเฉลี่ย 1.5 เท่า
        fire = "🚨(Volume พุ่ง!) " if row.VolSpike > 1.5 else ""
        
        msg += f"{i}. {symbol_name}\n"
        msg += f"   ➤ มูลค่าเทรด: {value_mb:,.1f} ลบ.\n"
        msg += f"   ➤ ราคา: {row.Price:,.2f} {fire}\n"

    msg += "-" * 30

    print(msg)
    
    # ส่งแจ้งเตือนผ่าน Notifier
    notifier = Notifier()
    notifier.send(msg)
    print("✅ ส่งแจ้งเตือน Top Demand เรียบร้อยแล้ว")

if __name__ == "__main__":
    scan_liquidity()
