import sys
import os
import time
import json
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from settrade_v2 import Investor

# Load main bot components
from bot import run_bot, send_daily_summary, is_market_open
from strategies.sma_cross import SMACrossover
from utils.notifier import Notifier


# Override market open check for testing
def mock_is_market_open():
    print("🕒 [TEST MODE] Simulating Market OPEN...")
    return True


if __name__ == "__main__":
    print("🔬 STARTING FULL CYCLE TEST (Simulation)...")

    # 1. Load Config
    load_dotenv()
    APP_ID = os.getenv("APP_ID")
    APP_SECRET = os.getenv("APP_SECRET")
    ACCOUNT_NO = os.getenv("ACCOUNT_NO")
    PIN = os.getenv("PIN")
    BROKER_ID = os.getenv("BROKER_ID", "SANDBOX")
    APP_CODE = os.getenv("APP_CODE", "SANDBOX")

    if not all([APP_ID, APP_SECRET, ACCOUNT_NO, PIN]):
        print("❌ Missing .env config")
        sys.exit(1)

    with open("config.json", "r") as f:
        app_config = json.load(f)
        portfolio_config = app_config.get("portfolio", [])
        strategies_config = app_config.get("strategies", {})

    notifier = Notifier()

    # 2. Init Strategies
    strategies_map = {}
    base_strat_name = app_config.get("active_strategy", "SMACrossover")
    for item in portfolio_config:
        symbol = item["symbol"]
        base_conf = strategies_config.get(base_strat_name, {}).copy()
        override_conf = item.get("strategy_override", {})
        final_conf = {**base_conf, **override_conf}
        strategies_map[symbol] = SMACrossover(final_conf)

    # 3. Connect API
    try:
        investor = Investor(
            app_id=APP_ID,
            app_secret=APP_SECRET,
            broker_id=BROKER_ID,
            app_code=APP_CODE,
            is_auto_queue=False,
        )
        print("✅ API Connected (Sandbox)")
    except Exception as e:
        print(f"❌ API Error: {e}")
        sys.exit(1)

    # --- PHASE 1: Simulate Market Run (Trading) ---
    print("\n📦 --- PHASE 1: TRADING CYCLE ---")
    # Force run_bot once
    try:
        run_bot(investor, ACCOUNT_NO, PIN, strategies_map, notifier, portfolio_config)
    except Exception as e:
        print(f"❌ Phase 1 Error: {e}")

    # --- PHASE 2: Simulate End of Day (Summary) ---
    print("\n📝 --- PHASE 2: DAILY SUMMARY ---")
    try:
        send_daily_summary(investor, ACCOUNT_NO, notifier)
    except Exception as e:
        print(f"❌ Phase 2 Error: {e}")

    print("\n✅ FULL CYCLE TEST COMPLETE.")
