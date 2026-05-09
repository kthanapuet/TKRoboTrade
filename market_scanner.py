import yfinance as yf
import pandas as pd
import sys
import os
from dotenv import load_dotenv
import time
import random

# Load ENV and Notifier
load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from utils.notifier import Notifier
import concurrent.futures
from utils.dynamic_universe import get_set50_symbols, get_sp500_symbols

# กลุ่มหุ้นที่ต้องการสแกนแบบคงที่ (เฉพาะ DR)

UNIVERSE_DR = [
    "NVDA80.BK", "AAPL80.BK", "MSFT80.BK", "TSLA80.BK", "GOOG80.BK", "AMZN80.BK", "META80.BK",
    "NDX01.BK", "SPX01.BK", "E1VFVN3001.BK", "FUEVFVND01.BK", "JAPAN13.BK", "CHINA01.BK", "HKCE11.BK",
    "TENCENT80.BK", "BABA80.BK", "PINGAN80.BK", "STAR5001.BK", "ASML01.BK"
]

def check_fundamentals(info):
    """
    เช็คพื้นฐาน:
    P/E 0 - 25
    ROE > 15% (0.15)
    D/E < 2 (หรือ 200 ถ้าระบุเป็นเปอร์เซ็นต์ใน yf)
    """
    try:
        pe = info.get('trailingPE', 0)
        roe = info.get('returnOnEquity', 0)
        de = info.get('debtToEquity', 0)

        if pe is None: pe = 0
        if roe is None: roe = 0
        if de is None: de = 0

        # yfinance D/E is often multiplied by 100
        de_ratio = de / 100 if de > 10 else de

        good_pe = 0 < pe <= 25
        good_roe = roe >= 0.15
        good_de = de_ratio <= 2.0

        return good_pe and good_roe and good_de
    except:
        return False

def check_technical(hist):
    """
    เช็คเทคนิค (Uptrend):
    Price > EMA200
    EMA50 > EMA200
    """
    try:
        if len(hist) < 200:
            return False

        hist['EMA50'] = hist['Close'].ewm(span=50, adjust=False).mean()
        hist['EMA200'] = hist['Close'].ewm(span=200, adjust=False).mean()

        last_price = hist['Close'].iloc[-1]
        ema50 = hist['EMA50'].iloc[-1]
        ema200 = hist['EMA200'].iloc[-1]

        return bool((last_price > ema200) and (ema50 > ema200))
    except:
        return False

def run_scan(market="TH"):
    if market == "TH":
        universe = get_set50_symbols()
        # Fallback in case of fetching error
        if not universe:
            universe = ["PTT.BK", "AOT.BK", "ADVANC.BK", "GULF.BK", "DELTA.BK", "CPALL.BK", "KBANK.BK"]
    elif market == "US":
        universe = get_sp500_symbols()
        if not universe:
            universe = ["AAPL", "MSFT", "NVDA", "GOOG", "AMZN", "META", "TSLA"]
    elif market == "DR":
        universe = UNIVERSE_DR
    else:
        universe = []
    all_results = scan_symbols(universe, market)
    return [r for r in all_results if r["fund_pass"] or r["tech_pass"]]

def process_symbol(symbol, market):
    try:
        # หน่วงเวลาเล็กน้อยเพื่อป้องกัน Rate Limit (เฉพาะตลาด US ที่มีหุ้นเยอะ)
        if market == "US":
            time.sleep(random.uniform(0.2, 0.5))
        
        ticker = yf.Ticker(symbol)
        # ดึง info พื้นฐาน
        info = ticker.info
        # ดึงประวัติกราฟ
        hist = ticker.history(period="1y")

        if hist.empty:
            return {
                "symbol": symbol,
                "market": market,
                "price": 0,
                "tags": ["❌ ไม่มีข้อมูลเทรดล่าสุด"],
                "fund_pass": False,
                "tech_pass": False
            }

        last_price = hist['Close'].iloc[-1]
        full_name = info.get('longName') or info.get('shortName') or symbol
        
        is_fund_good = bool(check_fundamentals(info))
        is_tech_good = bool(check_technical(hist))

        tags = []
        if is_fund_good and is_tech_good:
            tags.append("🌟 All-Star")
        elif is_fund_good:
            tags.append("📊 พื้นฐานดี")
        elif is_tech_good:
            tags.append("📈 ขาขึ้น")
        else:
            tags.append("⚠️ ไม่เข้าเงื่อนไข")

        return {
            "symbol": symbol,
            "name": full_name,
            "market": market,
            "price": round(last_price, 2),
            "tags": tags,
            "fund_pass": is_fund_good,
            "tech_pass": is_tech_good
        }
    except Exception as e:
        print(f"⚠️ สแกน {symbol} ไม่สำเร็จ: {e}")
        return {
            "symbol": symbol,
            "name": symbol,
            "market": market,
            "price": 0,
            "tags": ["❌ ข้อมูลผิดพลาด"],
            "fund_pass": False,
            "tech_pass": False
        }

def scan_symbols(symbols, market="MIXED"):
    results = []
    # ลด max_workers ลงเพื่อป้องกันโดน Yahoo บล็อค (เดิม 10)
    workers = 5 if market == "US" else 10
    print(f"Scanning market {market} ({len(symbols)} symbols) using multithreading ({workers} workers)...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(process_symbol, sym, market) for sym in symbols]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                results.append(res)

    # เรียงลำดับ All-Star ขึ้นก่อน
    results.sort(key=lambda x: (x["fund_pass"] and x["tech_pass"], x["tech_pass"], x["fund_pass"]), reverse=True)
    return results

def scan_liquidity():
    # Legacy wrapper if called directly
    res = run_scan("TH")
    print(res)

if __name__ == "__main__":
    scan_liquidity()
