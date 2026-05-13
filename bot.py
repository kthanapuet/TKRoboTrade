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
    weekday = now.weekday()
    current_time = now.time()

    # 1. ช่วงเวลาตลาดปกติ (จันทร์ - ศุกร์)
    if weekday <= 4:
        # ช่วงเช้า (SET)
        if datetime_time(9, 30) <= current_time <= datetime_time(12, 35):
            return True
        # ช่วงบ่าย (SET)
        if datetime_time(13, 55) <= current_time < datetime_time(17, 0):
            return True
        # ช่วงดึก (DRx / US Market Night Session)
        if datetime_time(20, 0) <= current_time <= datetime_time(23, 59, 59):
            return True

    # 2. ช่วงเช้ามืด (อังคาร - เสาร์) สำหรับ Night Session ที่ลากยาวจากคืนก่อนหน้า
    if 1 <= weekday <= 5:
        # รองรับถึง 04:05 น. (เผื่อเวลาปิดตลาด US)
        if datetime_time(0, 0) <= current_time <= datetime_time(4, 5):
            return True

    return False


# ---------------------------------------------------------
# Main Bot Logic
# ---------------------------------------------------------
def run_bot(
    investor, account_no, pin, strategies_map, notifier, portfolio_config, trade_tracker
):
    try:
        config_changed = False
        print(
            f"\n[{datetime.now(BANGKOK_TZ).strftime('%H:%M:%S')}] Checking Portfolio..."
        )
        market = investor.MarketData()
        equity = investor.Equity(account_no=account_no)
        portfolio_info = equity.get_portfolios()

        # Loop check each stock in config
        for item in portfolio_config:
            symbol = item["symbol"]
            # ต้องตัด .BK ออกถ้าส่งคำสั่งผ่าน SETTRADE API
            trade_symbol = symbol.replace(".BK", "")

            print(f"Analyzing: {trade_symbol}")

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

            print(f"   Status: Holding {current_vol} shares | Cost {current_cost:.2f}")

            # --- 2. ดึงกราฟ ---
            try:
                historical_data = market.get_candlestick(trade_symbol, "1d", 250)
                df = pd.DataFrame(historical_data)
                
                if df.empty:
                    print(f"   [!] [{trade_symbol}] No data from API. Skipping...")
                    continue

                df["time"] = pd.to_datetime(df["time"], unit="s")
                df.set_index("time", inplace=True)
                df.sort_index(inplace=True) # Ensure chronological order

                # Trend Calculation
                if len(df) >= 50:
                    ema50_val = df["close"].ewm(span=50, adjust=False).mean().iloc[-1]
                    ema200_val = df["close"].ewm(span=200, adjust=False).mean().iloc[-1]
                    price_val = df["close"].iloc[-1]

                    if price_val > ema200_val and ema50_val > ema200_val:
                        trend_status = "Uptrend"
                    elif price_val < ema200_val and ema50_val < ema200_val:
                        trend_status = "Downtrend"
                    else:
                        trend_status = "Sideways"
                else:
                    trend_status = "Insufficient data"
            except Exception as e:
                print(f"   [-] [{trade_symbol}] Data fetch failed: {e}")
                continue

            # --- 3. เรียก Strategy ที่เตรียมไว้ ---
            strategy = strategies_map.get(symbol)
            if not strategy:
                print(f"   [-] Strategy not found for {symbol}")
                continue

            df = strategy.generate_signals(df, current_cost=current_cost)
            
            if df.empty:
                print(f"   [!] [{trade_symbol}] Strategy returned empty DF. Skipping...")
                continue
                
            latest_data = df.iloc[-1]
            strat_name = strategy.__class__.__name__

            print(
                f"   [{strat_name}] Close: {latest_data['close']} | {latest_data.get('Status_Text', '')}"
            )

            # --- อัปเดต Signal & Trend ลงใน Memory Config ---
            status_text = latest_data.get("Status_Text", "")
            current_signal = int(latest_data.get("Position", 0))
            last_signal = item.get("last_signal", 0)

            if (
                item.get("signal_text") != status_text
                or item.get("long_term_trend") != trend_status
                or last_signal != current_signal
            ):
                item["signal_text"] = status_text
                item["long_term_trend"] = trend_status
                item["last_signal"] = current_signal
                config_changed = True

            # --- 4. Execution Logic & Cash Management ---
            # 4.1 Get Real-time Account Info
            try:
                acct_info = equity.get_account_info()

                # Support both snake_case and camelCase
                line_available = float(
                    acct_info.get("line_available") or acct_info.get("lineAvailable", 0)
                )
                cash_balance = float(
                    acct_info.get("cash_balance") or acct_info.get("cashBalance", 0)
                )

                total_market_value = float(
                    portfolio_info.get("total_portfolio_market_value", 0)
                )

                # Total Equity = Cash + Market Value (Approx)
                total_equity = cash_balance + total_market_value
            except Exception as e:
                print(f"   ⚠️ Cannot get account info: {e}. Using default budget.")
                line_available = 0
                total_equity = 0

            # Fetch latest price for notifications/orders
            try:
                quote = market.get_quote_symbol(trade_symbol)
                latest_price = float(quote.get("last", latest_data["close"]))
            except Exception:
                latest_price = latest_data["close"]

            action = None

            # 4.1 Check Signal (Notify only on Reversal/Change)
            is_new_signal = (current_signal != 0 and current_signal != last_signal)

            if current_signal == 2:  # Buy Signal
                if is_new_signal:
                    # เช็คทั้ง portfolio และ trade_tracker เพื่อป้องกันการซื้อซ้ำ
                    if current_vol == 0 and trade_symbol not in trade_tracker:
                        # เช็คเพิ่ม: ดู order history ว่ามี order ล่าสุดไหม
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
                                    "   [!] (Buy Signal) Order already exists -> Skip Duplicate"
                                )
                            else:
                                action = "BUY"
                        except Exception:
                            # ถ้าเช็ค order history ไม่ได้ ให้ BUY ไปก่อน
                            action = "BUY"
                    elif current_vol > 0:
                        print("   [!] (Buy Signal) Already holding -> Hold")
                    elif trade_symbol in trade_tracker:
                        print("   [!] (Buy Signal) Order already tracked -> Skip Duplicate")
                else:
                    # Same signal as before, skip notification
                    pass

            elif current_signal == -2:  # Sell Signal
                if is_new_signal:
                    action = "SELL"
                    if current_vol == 0:
                        print("   [!] (Sell Signal) No position, but notification will be sent")
                else:
                    # Same signal as before, skip notification
                    pass

            # 4.2 Send Order
            if action == "BUY":
                # --- Calculate Budget & Volume specifically for BUY ---
                allocation_ratio = item.get("allocation_check", 0.1)
                if total_equity > 0:
                    target_value = total_equity * allocation_ratio
                    trade_budget = min(target_value, line_available)
                else:
                    trade_budget = min(5000, line_available)
                
                if latest_price > 0:
                    trade_volume = int(trade_budget / latest_price)
                else:
                    trade_volume = 0
                
                trade_volume = (trade_volume // 100) * 100
                
                if trade_volume == 0:
                    print("   [!] Insufficient funds for board lot (100 shares).")
                    continue # Skip this buy
                    
                # Get Entry Reason from Status_Text
                entry_reason = latest_data.get("Status_Text", "SMA Crossover")

                # Calculate total investment
                total_investment = trade_volume * latest_price

                msg = f"🛒 BUY ORDER\n"
                msg += f"━━━━━━━━━━━━━━━━\n"
                msg += f"📊 Symbol: {trade_symbol}\n"
                msg += f"🌊 Trend: {trend_status}\n"
                msg += f"🎯 Entry Reason: {entry_reason}\n"
                msg += f"📈 Strategy: {strat_name}\n\n"
                msg += f"💰 Investment: {total_investment:,.2f} THB\n"
                msg += f"📈 Entry Price: {latest_price:.2f}\n"
                msg += f"📦 Volume: {trade_volume:,} shares\n"
                msg += f"📅 Date: {datetime.now(BANGKOK_TZ).strftime('%d/%m/%y %H:%M')}"

                print(f"   [ORDER] {trade_symbol} @ {latest_price}")
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

                    # Calculate P&L
                    pnl_per_share = latest_price - entry_price
                    pnl_total = pnl_per_share * current_vol
                    pnl_pct = (pnl_per_share / entry_price) * 100

                    # Calculate Duration
                    if entry_date:
                        duration = (datetime.now() - entry_date).days
                        duration_str = f"{duration} days"
                    else:
                        duration_str = "N/A"

                    # Emoji based on P&L
                    emoji = "💚" if pnl_total >= 0 else "🔴"

                    msg = f"{emoji} SELL ORDER\n"
                    msg += f"━━━━━━━━━━━━━━━━\n"
                    msg += f"📊 Symbol: {trade_symbol}\n"
                    msg += f"🌊 Trend: {trend_status}\n"
                    msg += f"🚪 Exit Reason: {exit_reason}\n\n"
                    msg += f"💰 P&L: {pnl_total:,.2f} THB ({pnl_pct:+.2f}%)\n"
                    msg += f"📈 Entry: {entry_price:.2f} | Exit: {latest_price:.2f}\n"
                    msg += f"📦 Volume: {current_vol:,} shares\n"
                    msg += f"⏱️ Duration: {duration_str}\n"
                    msg += f"📅 {entry_date.strftime('%d/%m/%y') if entry_date else 'N/A'} → {datetime.now(BANGKOK_TZ).strftime('%d/%m/%y')}"
                else:
                    # Fallback if no entry info
                    msg = f"📉 Sell Signal: {trade_symbol} @ {latest_price}\nReason: {exit_reason}\nTrend: {trend_status}"

                print(f"   [ORDER] {trade_symbol} @ {latest_price}")
                notifier.send(msg)

                try:
                    if current_vol > 0:
                        # ขายหมดพอร์ต (Clear Position)
                        order = equity.place_order(
                            pin=pin,
                            symbol=trade_symbol,
                            side="Sell",
                            volume=current_vol,
                            price=latest_price,
                            price_type="Limit",
                        )
                        notifier.send(f"✅ Order Sent: {order.get('order_no', 'N/A')}")
                    else:
                        print("   [!] Skipping sell order to broker as volume is 0")

                    # Clear tracking
                    if trade_symbol in trade_tracker:
                        del trade_tracker[trade_symbol]

                except Exception as ex:
                    notifier.send(f"❌ Order Failed: {ex}")
            else:
                print("   Wait...")

        # อัปเดตลงไฟล์ portfolio.json ถ้ามีการเปลี่ยนแปลง
        if config_changed:
            try:
                with open("portfolio.json", "r", encoding="utf-8") as f:
                    app_portfolio = json.load(f)

                for app_item in app_portfolio:
                    for mem_item in portfolio_config:
                        if app_item["symbol"] == mem_item["symbol"]:
                            app_item["signal_text"] = mem_item.get("signal_text", "")
                            app_item["long_term_trend"] = mem_item.get("long_term_trend", "")
                            app_item["last_signal"] = mem_item.get("last_signal", 0)

                with open("portfolio.json", "w", encoding="utf-8") as f:
                    json.dump(app_portfolio, f, indent=4, ensure_ascii=False)
            except Exception as e:
                print(f"❌ Failed to persist portfolio: {e}")

        msg_finish = f"[*] [{datetime.now(BANGKOK_TZ).strftime('%H:%M:%S')}] Loop cycle finished."
        print(msg_finish)

    except Exception as e:
        error_msg = f"[-] Error in Main Loop: {e}"
        print(error_msg)
        notifier.send(error_msg)


# ---------------------------------------------------------
# Report Logic
# ---------------------------------------------------------
def send_weekly_trend_report(investor, portfolio_config, notifier):
    try:
        print("📊 Checking Weekly Trend...")
        market = investor.MarketData()

        msg = "📈 Weekly Trend Update (Long-Term)\n━━━━━━━━━━━━━━━━\n"
        uptrend_count = 0

        for item in portfolio_config:
            symbol = item["symbol"]
            trade_symbol = symbol.replace(".BK", "")

            try:
                historical_data = market.get_candlestick(trade_symbol, "1d", 250)
                if not historical_data:
                    continue

                df = pd.DataFrame(historical_data)

                if len(df) < 50:
                    msg += f"⚪ {trade_symbol}: Insufficient data\n"
                    continue

                df["time"] = pd.to_datetime(df["time"], unit="s")
                df.set_index("time", inplace=True)

                df["EMA_50"] = df["close"].ewm(span=50, adjust=False).mean()
                df["EMA_200"] = df["close"].ewm(span=200, adjust=False).mean()

                price = df["close"].iloc[-1]
                ema50 = df["EMA_50"].iloc[-1]
                ema200 = df["EMA_200"].iloc[-1]

                if price > ema200 and ema50 > ema200:
                    status = "🟢 Uptrend"
                    uptrend_count += 1
                elif price < ema200 and ema50 < ema200:
                    status = "🔴 Downtrend"
                else:
                    status = "🟡 Sideways"

                msg += f"• {trade_symbol}: {status}\n"

            except Exception as e:
                print(f"   ❌ {trade_symbol} Trend check failed: {e}")

        msg += (
            f"━━━━━━━━━━━━━━━━\nSummary: Uptrend {uptrend_count}/{len(portfolio_config)}"
        )
        notifier.send(msg)
        print("[+] Weekly trend summary sent.")
    except Exception as e:
        print(f"[-] Failed to run weekly trend check: {e}")


def send_daily_summary(investor, account_no, notifier):
    try:
        equity = investor.Equity(account_no=account_no)

        # 1. Portfolio Summary
        port_list = equity.get_portfolios()
        try:
            total_value = float(port_list.get("total_portfolio_market_value", 0))
        except:
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
        orders = equity.get_orders()
        if not orders:
            msg += "📝 No orders today."
        else:
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
        print("[+] Daily summary sent.")

    except Exception as e:
        print(f"[-] Failed to send summary: {e}")


# ---------------------------------------------------------
# Entry Point
# ---------------------------------------------------------
if __name__ == "__main__":
    print("[*] Starting TK Robo Trade Daemon...")

    # 1. ดึง Config Environment
    APP_ID = os.getenv("APP_ID")
    APP_SECRET = os.getenv("APP_SECRET")
    ACCOUNT_NO = os.getenv("ACCOUNT_NO")
    PIN = os.getenv("PIN")
    BROKER_ID = os.getenv("BROKER_ID", "SANDBOX")
    APP_CODE = os.getenv("APP_CODE", "SANDBOX")

    if not all([APP_ID, APP_SECRET, ACCOUNT_NO, PIN]):
        print("[-] Missing config in .env")
        exit()

    # 2. ดึง Config JSON & Portfolio JSON
    try:
        with open("config.json", "r") as f:
            app_config = json.load(f)
            strategies_config = app_config.get("strategies", {})
    except FileNotFoundError:
        print("[-] config.json not found")
        exit()

    try:
        with open("portfolio.json", "r", encoding="utf-8") as f:
            portfolio_config = json.load(f)
    except FileNotFoundError:
        print("[-] portfolio.json not found")
        exit()

    if not portfolio_config:
        print("[-] No data in portfolio.json")
        exit()

    # 3. เตรียม Tools & Build Strategies Map
    notifier = Notifier()
    strategies_map = {}
    base_strat_name = app_config.get("active_strategy", "EMACrossover")

    for item in portfolio_config:
        symbol = item["symbol"]
        base_conf = strategies_config.get(base_strat_name, {}).copy()
        base_conf = {k: v for k, v in base_conf.items() if not k.startswith("_")}
        override_conf = item.get("strategy_override", {})
        final_conf = {**base_conf, **override_conf}

        if base_strat_name == "SMACrossover":
            strategies_map[symbol] = SMACrossover(final_conf)
        elif base_strat_name == "EMACrossover":
            strategies_map[symbol] = EMACrossover(final_conf)
        elif base_strat_name == "Supertrend":
            strategies_map[symbol] = Supertrend(final_conf)
        elif base_strat_name == "BollingerRSI":
            strategies_map[symbol] = BollingerRSI(final_conf)
        else:
            print(f"[-] Strategy {base_strat_name} not implemented.")
            exit()

    print(f"[+] Active Strategy: {base_strat_name}")
    print(f"[+] Prepared strategies for {len(strategies_map)} symbols.")

    # 4. เชื่อมต่อ API
    try:
        investor = Investor(
            app_id=APP_ID,
            app_secret=APP_SECRET,
            broker_id=BROKER_ID,
            app_code=APP_CODE,
            is_auto_queue=False,
        )
        print("[+] Connected to SETTRADE API successfully!")
        notifier.send(
            f"🤖 TK Robo Trade Started! Monitoring {len(portfolio_config)} symbols."
        )
    except Exception as e:
        print(f"[-] API Connection failed: {e}")
        exit()

    trade_tracker = {}
    summary_sent = False
    last_heartbeat_hour = -1

    while True:
        now = datetime.now(BANGKOK_TZ)

        if now.hour == 0 and now.minute < 5:
            summary_sent = False

        if is_market_open() or (8 <= now.hour <= 17 and now.weekday() <= 4):
            if now.minute < 5 and now.hour != last_heartbeat_hour:
                try:
                    equity = investor.Equity(account_no=ACCOUNT_NO)
                    equity.get_account_info()
                    notifier.send(
                        f"💓 Heartbeat [{now.strftime('%H:%M')}]\n✅ Status: Online\n📶 API: Connected"
                    )
                    last_heartbeat_hour = now.hour
                except Exception as e:
                    notifier.send(f"⚠️ Heartbeat Failed: API Error {e}")

        if is_market_open():
            run_bot(
                investor,
                ACCOUNT_NO,
                PIN,
                strategies_map,
                notifier,
                portfolio_config,
                trade_tracker,
            )
            time.sleep(300)
        else:
            if (
                now.hour == 17
                and now.minute >= 30
                and not summary_sent
                and now.weekday() <= 4
            ):
                print("📝 Sending Daily Summary...")
                send_daily_summary(investor, ACCOUNT_NO, notifier)
                summary_sent = True

                if now.weekday() == 4:
                    print("📝 Sending Weekly Trend Check...")
                    send_weekly_trend_report(investor, portfolio_config, notifier)

            print(f"[{now.strftime('%H:%M:%S')}] Market Closed... 😴")
            time.sleep(60)
