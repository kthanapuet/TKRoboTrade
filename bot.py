import sys
import os

# ---------------------------------------------------------
# บังคับเพิ่ม Path เพื่อป้องกัน Error: ModuleNotFoundError
# ---------------------------------------------------------
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import time
import json
import pandas as pd
from datetime import datetime, time as datetime_time
import pytz
from dotenv import load_dotenv

# Bangkok Timezone
BANGKOK_TZ = pytz.timezone("Asia/Bangkok")
from settrade_v2 import Investor

# โหลด Environment Variables
load_dotenv()

# Import Modules ของเรา
from strategies.sma_cross import SMACrossover
from strategies.ema_cross import EMACrossover
from strategies.supertrend import Supertrend
from strategies.bbands_rsi import BollingerRSI
from utils.notifier import Notifier


# ---------------------------------------------------------
# ฟังก์ชันเช็คเวลาตลาด (Market Hours)
# ---------------------------------------------------------
def is_market_open():
    now = datetime.now(BANGKOK_TZ)
    if now.weekday() > 4:  # เสาร์ (5) - อาทิตย์ (6)
        return False

    current_time = now.time()
    morning_session = datetime_time(10, 0) <= current_time <= datetime_time(12, 30)
    afternoon_session = datetime_time(14, 30) <= current_time <= datetime_time(16, 30)

    return morning_session or afternoon_session


# ---------------------------------------------------------
# Main Bot Logic
# ---------------------------------------------------------
# ---------------------------------------------------------
# Main Bot Logic
# ---------------------------------------------------------
def run_bot(
    investor, account_no, pin, strategies_map, notifier, portfolio_config, trade_tracker
):
    try:
        print(
            f"\n[{datetime.now(BANGKOK_TZ).strftime('%H:%M:%S')}] เริ่มตรวจสอบ Portfolio..."
        )
        market = investor.MarketData()
        equity = investor.Equity(account_no=account_no)
        portfolio_info = equity.get_portfolios()

        # Loop check each stock in config
        for item in portfolio_config:
            symbol = item["symbol"]
            # ต้องตัด .BK ออกถ้าส่งคำสั่งผ่าน SETTRADE API ? (ปกติ Sandbox ใช้ชื่อเต็มได้ หรือชื่อย่อ)
            # แต่เพื่อความชัวร์ ใช้ symbol ตาม config ไปก่อน ถ้าระบบจริงต้อง check format
            # เช็คว่า symbol ใน config มี .BK ไหม ถ้ามีต้องเอาออกตอนส่งคำสั่งไหม?
            # ปกติ Settrade ใช้ "PTT" ไม่ใช่ "PTT.BK"
            trade_symbol = symbol.replace(".BK", "")

            print(f"🔎 กำลังวิเคราะห์: {trade_symbol}")

            # --- 1. เช็ค Portfolio ต้นทุน ---
            my_position = next(
                (
                    p
                    for p in portfolio_info.get("portfolio_list", [])
                    if p["symbol"] == trade_symbol
                ),
                None,
            )

            current_cost = my_position["average_price"] if my_position else 0.0
            current_vol = my_position["actual_volume"] if my_position else 0

            print(f"   📊 สถานะ: ถือ {current_vol} หุ้น | ทุน {current_cost:.2f}")

            # --- 2. ดึงกราฟ ---
            # ใช้ trade_symbol (เช่น PTT)
            try:
                historical_data = market.get_candlestick(trade_symbol, "1d", 200)
                df = pd.DataFrame(historical_data)
                df["time"] = pd.to_datetime(df["time"], unit="s")
                df.set_index("time", inplace=True)
            except Exception as e:
                print(f"   ❌ ดึงกราฟไม่สำเร็จ: {e}")
                continue

            # --- 3. เรียก Strategy ที่เตรียมไว้ ---
            strategy = strategies_map.get(symbol)
            if not strategy:
                print(f"   ❌ ไม่พบ Strategy สำหรับ {symbol}")
                continue

            df = strategy.generate_signals(df, current_cost=current_cost)
            latest_data = df.iloc[-1]
            strat_name = strategy.__class__.__name__

            print(
                f"   [{strat_name}] Close: {latest_data['close']} | {latest_data.get('Status_Text', '')}"
            )

            # --- 4. Execution Logic & Cash Management ---
            # 4.1 Get Real-time Account Info
            try:
                acct_info = equity.get_account_info()

                # Support both snake_case and camelCase (Sandbox vs Real?)
                line_available = float(
                    acct_info.get("line_available") or acct_info.get("lineAvailable", 0)
                )
                cash_balance = float(
                    acct_info.get("cash_balance") or acct_info.get("cashBalance", 0)
                )

                total_market_value = float(
                    portfolio_info.get("total_portfolio_market_value", 0)
                )

                # Total Equity = Line Available + Market Value (Approx)
                # Note: Line Available is buying power.
                total_equity = cash_balance + total_market_value
            except Exception as e:
                print(f"   ⚠️ Cannot get account info: {e}. Using default budget.")
                line_available = 0
                total_equity = 0

            # 4.2 Calculate Dynamic Budget based on Config Allocation
            # Config: allocation_check = 0.1 (10% of total port)
            allocation_ratio = item.get("allocation_check", 0.1)

            # Target Investment Value for this stock
            # If total_equity is 0 (error), use fallback fixed amount or 0
            if total_equity > 0:
                target_value = total_equity * allocation_ratio
                print(
                    f"   💰 Port Equity: {total_equity:,.2f} | Target Alloc: {target_value:,.2f} | Available: {line_available:,.2f}"
                )

                # Use MIN(Target, Available) but ensure we don't spend more than Available
                trade_budget = min(target_value, line_available)
            else:
                trade_budget = min(5000, line_available)  # Fallback

            latest_price = latest_data["close"]

            # Calculate Shares
            if latest_price > 0:
                trade_volume = int(trade_budget / latest_price)
            else:
                trade_volume = 0

            trade_volume = (trade_volume // 100) * 100  # Round down to board lot

            if trade_volume == 0:
                print("   ⚠️ Insufficient funds or price error for min 100 shares.")
                continue

            action = None

            # 4.1 Check Signal
            if latest_data["Position"] == 2:  # Buy Signal
                # เช็คทั้ง portfolio และ trade_tracker เพื่อป้องกันการซื้อซ้ำ
                if current_vol == 0 and trade_symbol not in trade_tracker:
                    # เช็คเพิ่ม: ดู order history ว่ามี order ล่าสุดไหม (กรณี bot restart)
                    try:
                        today_orders = equity.get_orders()
                        recent_buy = any(
                            o["symbol"] == trade_symbol
                            and o["side"] == "Buy"
                            and o["order_status"]
                            in ["Submitted", "Matched", "Partial_Filled"]
                            for o in today_orders.get("order_list", [])
                        )
                        if recent_buy:
                            print(
                                "   ⚠️ (Buy Signal) แต่มี Order ล่าสุดอยู่แล้ว -> Skip Duplicate"
                            )
                        else:
                            action = "BUY"
                    except Exception:
                        # ถ้าเช็ค order history ไม่ได้ ให้ BUY ไปก่อน (ไว้ใจ trade_tracker)
                        action = "BUY"
                elif current_vol > 0:
                    print("   ⚠️ (Buy Signal) แต่มีของอยู่แล้ว -> Hold")
                elif trade_symbol in trade_tracker:
                    print("   ⚠️ (Buy Signal) แต่มี Order รออยู่แล้ว -> Skip Duplicate")

            elif latest_data["Position"] == -2:  # Sell Signal
                if current_vol > 0:
                    action = "SELL"
                else:
                    print("   ⚠️ (Sell Signal) แต่ไม่มีของ -> Skip")

            # 4.2 Send Order
            if action == "BUY":
                # Get Entry Reason from Status_Text
                entry_reason = latest_data.get("Status_Text", "SMA Crossover")

                # Calculate total investment
                total_investment = trade_volume * latest_price

                msg = f"� BUY ORDER\n"
                msg += f"━━━━━━━━━━━━━━━━\n"
                msg += f"📊 Symbol: {trade_symbol}\n"
                msg += f"🎯 Entry Reason: {entry_reason}\n"
                msg += f"📈 Strategy: {strat_name}\n\n"
                msg += f"💰 Investment: {total_investment:,.2f} THB\n"
                msg += f"📈 Entry Price: {latest_price:.2f}\n"
                msg += f"📦 Volume: {trade_volume:,} shares\n"
                msg += f"📅 Date: {datetime.now(BANGKOK_TZ).strftime('%d/%m/%y %H:%M')}"

                print(f"   🚀 {msg}")
                notifier.send(msg)
                try:
                    order = equity.place_order(
                        pin=pin,
                        symbol=trade_symbol,
                        side="Buy",
                        volume=trade_volume,
                        price=latest_price,
                        price_type="Limit",
                    )
                    notifier.send(f"✅ Order Sent: {order.get('order_no', 'N/A')}")

                    # Track Entry Info
                    trade_tracker[trade_symbol] = {
                        "entry_date": datetime.now(),
                        "entry_price": latest_price,
                        "entry_vol": trade_volume,
                    }
                except Exception as ex:
                    notifier.send(f"❌ Order Failed: {ex}")

            elif action == "SELL":
                # Get Exit Reason from Status_Text
                exit_reason = latest_data.get("Status_Text", "Signal")

                # Calculate P&L if we have entry info
                entry_info = trade_tracker.get(trade_symbol, {})

                if entry_info:
                    entry_price = entry_info.get("entry_price", current_cost)
                    entry_date = entry_info.get("entry_date")
                    entry_vol = entry_info.get("entry_vol", current_vol)

                    # Calculate P&L
                    pnl_per_share = latest_price - entry_price
                    pnl_total = pnl_per_share * current_vol
                    pnl_pct = (pnl_per_share / entry_price) * 100

                    # Calculate Duration
                    if entry_date:
                        duration = (datetime.now() - entry_date).days
                        duration_str = f"{duration} วัน"
                    else:
                        duration_str = "N/A"

                    # Emoji based on P&L
                    emoji = "💚" if pnl_total >= 0 else "🔴"

                    msg = f"{emoji} SELL ORDER\n"
                    msg += f"━━━━━━━━━━━━━━━━\n"
                    msg += f"📊 Symbol: {trade_symbol}\n"
                    msg += f"🚪 Exit Reason: {exit_reason}\n\n"
                    msg += f"💰 P&L: {pnl_total:,.2f} THB ({pnl_pct:+.2f}%)\n"
                    msg += f"📈 Entry: {entry_price:.2f} | Exit: {latest_price:.2f}\n"
                    msg += f"📦 Volume: {current_vol:,} shares\n"
                    msg += f"⏱️ Duration: {duration_str}\n"
                    msg += f"📅 {entry_date.strftime('%d/%m/%y') if entry_date else 'N/A'} → {datetime.now(BANGKOK_TZ).strftime('%d/%m/%y')}"
                else:
                    # Fallback if no entry info
                    msg = f"📉 Sell Signal: {trade_symbol} @ {latest_price}\nReason: {exit_reason}"

                print(f"   🚀 {msg}")
                notifier.send(msg)

                try:
                    # ขายหมดพอร์ต (Clear Position)
                    order = equity.place_order(
                        pin=pin,
                        symbol=trade_symbol,
                        side="Sell",
                        volume=current_vol,  # ขายเท่าที่มี
                        price=latest_price,
                        price_type="Limit",
                    )
                    notifier.send(f"✅ Order Sent: {order.get('order_no', 'N/A')}")

                    # Clear tracking
                    if trade_symbol in trade_tracker:
                        del trade_tracker[trade_symbol]

                except Exception as ex:
                    notifier.send(f"❌ Order Failed: {ex}")
            else:
                print("   💤 Wait...")

        print(
            f"[{datetime.now(BANGKOK_TZ).strftime('%H:%M:%S')}] จบรอบการทำงาน. รอรอบถัดไป..."
        )

    except Exception as e:
        error_msg = f"❌ เกิดข้อผิดพลาดใน Main Loop: {e}"
        print(error_msg)
        notifier.send(error_msg)


# ---------------------------------------------------------
# Report Logic
# ---------------------------------------------------------
def send_daily_summary(investor, account_no, notifier):
    try:
        equity = investor.Equity(account_no=account_no)

        # 1. Portfolio Summary
        port_list = equity.get_portfolios()
        # Note: Sandbox may return raw list or dict with wrapper depending on version
        # If returns dict {'portfolio_list': [...], 'total_portfolio_market_value': ...}

        try:
            total_value = float(port_list.get("total_portfolio_market_value", 0))
        except:
            # Fallback if structure is different
            total_value = 0

        acct = equity.get_account_info()
        cash = float(acct.get("cash_balance") or acct.get("cashBalance", 0))
        total_equity = float(total_value) + float(cash)

        msg = f"📊 Daily Summary ({datetime.now(BANGKOK_TZ).strftime('%Y-%m-%d')})\n"
        msg += f"💰 Total Equity: {total_equity:,.2f} THB\n"
        msg += f"💵 Cash Balance: {float(cash):,.2f} THB\n"
        msg += f"📦 Stock Value: {float(total_value):,.2f} THB\n"
        msg += "-" * 20 + "\n"

        # 2. Orders Summary (Today)
        orders = equity.get_orders()  # Default returns orders of the day
        if not orders:
            msg += "📝 No orders today."
        else:
            # Debug Orders
            # print(f"DEBUG Orders: {orders[0]}")

            # Helper to get status safely
            def get_status(o):
                return (
                    o.get("show_order_status") or o.get("showOrderStatus") or "Unknown"
                )

            matched = [o for o in orders if get_status(o) == "Matched"]
            cancelled = [
                o
                for o in orders
                if get_status(o) in ["Cancelled", "Rejected", "Expired"]
            ]
            open_orders = [o for o in orders if get_status(o) in ["Open", "Queuing"]]

            msg += f"✅ Matched: {len(matched)}\n"
            for o in matched:
                msg += f"   - {o['side']} {o['symbol']} {o['vol']} @ {o['price']}\n"

            if open_orders:
                msg += f"⏳ Open/Pending: {len(open_orders)}\n"
                for o in open_orders:
                    msg += f"   - {o['side']} {o['symbol']} {o['vol']} @ {o['price']}\n"

            if cancelled:
                msg += f"❌ Cancelled/Rejected: {len(cancelled)}\n"

        notifier.send(msg)
        print("✅ Daily summary sent.")

    except Exception as e:
        print(f"❌ Failed to send summary: {e}")


# ---------------------------------------------------------
# Entry Point
# ---------------------------------------------------------
if __name__ == "__main__":
    print("🚀 Starting TK Robo Trade Daemon...")

    # 1. ดึง Config Environment
    APP_ID = os.getenv("APP_ID")
    APP_SECRET = os.getenv("APP_SECRET")
    ACCOUNT_NO = os.getenv("ACCOUNT_NO")
    PIN = os.getenv("PIN")
    BROKER_ID = os.getenv("BROKER_ID", "SANDBOX")
    APP_CODE = os.getenv("APP_CODE", "SANDBOX")

    if not all([APP_ID, APP_SECRET, ACCOUNT_NO, PIN]):
        print("❌ ไม่พบข้อมูล Config ในไฟล์ .env")
        exit()

    # 2. ดึง Config JSON
    try:
        with open("config.json", "r") as f:
            app_config = json.load(f)
            portfolio_config = app_config.get("portfolio", [])
            strategies_config = app_config.get("strategies", {})
    except FileNotFoundError:
        print("❌ ไม่พบไฟล์ config.json")
        exit()

    if not portfolio_config:
        print("❌ ไม่พบ Portfolio Config ในไฟล์ JSON")
        exit()

    # 3. เตรียม Tools & Build Strategies Map
    notifier = Notifier()

    # Map: 'PTT.BK' -> StrategyInstance
    strategies_map = {}

    base_strat_name = app_config.get("active_strategy", "EMACrossover")

    for item in portfolio_config:
        symbol = item["symbol"]
        # ผสม Config: Base + Override
        base_conf = strategies_config.get(base_strat_name, {}).copy()

        # Remove comment fields from config
        base_conf = {k: v for k, v in base_conf.items() if not k.startswith("_")}

        override_conf = item.get("strategy_override", {})
        final_conf = {**base_conf, **override_conf}

        # Init Strategy
        if base_strat_name == "SMACrossover":
            strategies_map[symbol] = SMACrossover(final_conf)
        elif base_strat_name == "EMACrossover":
            strategies_map[symbol] = EMACrossover(final_conf)
        elif base_strat_name == "Supertrend":
            strategies_map[symbol] = Supertrend(final_conf)
        elif base_strat_name == "BollingerRSI":
            strategies_map[symbol] = BollingerRSI(final_conf)
        else:
            print(f"❌ Strategy {base_strat_name} not implemented yet.")
            print(f"   Available: SMACrossover, EMACrossover, Supertrend, BollingerRSI")
            exit()

    print(f"✅ Active Strategy: {base_strat_name}")
    print(f"✅ เตรียมกลยุทธ์สำหรับ {len(strategies_map)} หุ้นสำเร็จ")

    # 4. เชื่อมต่อ API
    try:
        investor = Investor(
            app_id=APP_ID,
            app_secret=APP_SECRET,
            broker_id=BROKER_ID,
            app_code=APP_CODE,
            is_auto_queue=False,
        )
        print("✅ เชื่อมต่อ SETTRADE API สำเร็จ พร้อมทำงาน!")
        notifier.send(
            f"🤖 TK Robo Trade Started! Monitoring {len(portfolio_config)} symbols."
        )
    except Exception as e:
        print(f"❌ เชื่อมต่อ API ล้มเหลว: {e}")
        exit()

    # 5. Trade Tracking (เก็บข้อมูล Entry)
    # Format: {'SYMBOL': {'entry_date': datetime, 'entry_price': float, 'entry_vol': int}}
    trade_tracker = {}

    # 5. Main Loop
    # State flags
    summary_sent = False
    last_heartbeat_hour = -1

    while True:
        now = datetime.now(BANGKOK_TZ)

        # Reset summary flag at midnight
        if now.hour == 0 and now.minute < 5:
            summary_sent = False

        if is_market_open():
            # 1. Run Strategy (Pass trade_tracker)
            run_bot(
                investor,
                ACCOUNT_NO,
                PIN,
                strategies_map,
                notifier,
                portfolio_config,
                trade_tracker,
            )

            # 2. Heartbeat Check (Every hour at minute 0-5)
            if now.minute < 5 and now.hour != last_heartbeat_hour:
                try:
                    # Simple API Ping
                    equity = investor.Equity(account_no=ACCOUNT_NO)
                    equity.get_account_info()
                    notifier.send(
                        f"💓 Heartbeat [{now.strftime('%H:%M')}]\n✅ Status: Online\n📶 API: Connected"
                    )
                    last_heartbeat_hour = now.hour
                except Exception as e:
                    notifier.send(f"⚠️ Heartbeat Failed: API Error {e}")

            time.sleep(300)  # Check every 5 mins
        else:
            # Market Closed Logic
            # Trigger Summary at 17:30 (Market officially closes trading at ~17:00, 17:30 is safe)
            if (
                now.hour == 17
                and now.minute >= 30
                and not summary_sent
                and now.weekday() <= 4
            ):
                print("📝 Sending Daily Summary...")
                send_daily_summary(investor, ACCOUNT_NO, notifier)
                summary_sent = True

            print(f"[{now.strftime('%H:%M:%S')}] นอกเวลาทำการ ตลาดปิด... 😴")
            time.sleep(60)  # Fast check to catch 17:30 time window
