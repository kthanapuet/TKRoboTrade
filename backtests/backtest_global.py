import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from strategies.sma_cross import SMACrossover


class GlobalBacktester:
    def __init__(
        self, start_date="2014-01-01", end_date="2023-12-31", initial_capital=10000.0
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.holdings = {}
        self.portfolio_history = []
        self.dates = []
        self.trade_log = []

        # หุ้น Tech ยักษ์ใหญ่สหรัฐฯ
        self.portfolio_config = [
            {"symbol": "AAPL", "allocation": 0.14},  # Apple
            {"symbol": "MSFT", "allocation": 0.14},  # Microsoft
            {"symbol": "GOOGL", "allocation": 0.14},  # Google
            {"symbol": "AMZN", "allocation": 0.14},  # Amazon
            {"symbol": "NVDA", "allocation": 0.14},  # Nvidia
            {"symbol": "TSLA", "allocation": 0.14},  # Tesla
            {"symbol": "META", "allocation": 0.16},  # Meta (Facebook)
        ]

        # ใช้ Config กลางๆ สำหรับหุ้น Growth
        self.strategy_config = {
            "fast_window": 10,
            "slow_window": 50,
            "stop_loss_pct": 0.08,  # หุ้นนอกผันผวนสูงกว่าไทย เผื่อ Buffer หน่อย
            "take_profit_pct": 0.25,
        }

        # Initialize Holdings
        for item in self.portfolio_config:
            self.holdings[item["symbol"]] = {"shares": 0, "cost_basis": 0}

    def run(self):
        print(f"📥 เริ่มต้น Global Backtest ({self.start_date} - {self.end_date})")
        print(f"💰 เงินทุนเริ่มต้น: ${self.initial_capital:,.2f}")

        # 1. Download Data
        data_store = {}
        for item in self.portfolio_config:
            symbol = item["symbol"]
            print(f"   -> Downloading {symbol}...")
            df = yf.download(
                symbol, start=self.start_date, end=self.end_date, progress=False
            )
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
            df.columns = df.columns.str.lower()
            if "date" not in df.columns:
                df.reset_index(inplace=True)
                df.rename(columns={"Date": "time"}, inplace=True)
                df.set_index("time", inplace=True)
            data_store[symbol] = df

        # 2. Align Data
        common_dates = None
        for symbol, df in data_store.items():
            if common_dates is None:
                common_dates = df.index
            else:
                common_dates = common_dates.intersection(df.index)
        common_dates = common_dates.sort_values()

        # 3. Pre-calculate Signals
        signals_store = {}
        strategy = SMACrossover(self.strategy_config)

        for item in self.portfolio_config:
            symbol = item["symbol"]
            df = data_store[symbol].loc[common_dates].copy()
            df_signals = strategy.generate_signals(df, current_cost=0)
            signals_store[symbol] = df_signals

        # 4. Simulation
        print("🔄 เริ่มเดินเวลาแบบจำลอง (Reinvestment Mode)...")

        for date in common_dates:
            # Calculate Equity
            current_equity = self.cash
            prices_today = {}
            for item in self.portfolio_config:
                sym = item["symbol"]
                try:
                    price = signals_store[sym].loc[date]["close"]
                    current_equity += self.holdings[sym]["shares"] * price
                    prices_today[sym] = price
                except:
                    prices_today[sym] = 0

            daily_portfolio_value = current_equity

            for item in self.portfolio_config:
                symbol = item["symbol"]
                alloc = item["allocation"]

                if prices_today[symbol] == 0:
                    continue

                curr_bar = signals_store[symbol].loc[date]
                price = curr_bar["close"]
                pos = curr_bar["Position"]
                my_hold = self.holdings[symbol]

                action = None
                forced_sell = False

                sl = self.strategy_config["stop_loss_pct"]
                tp = self.strategy_config["take_profit_pct"]

                # Risk Logic
                if my_hold["shares"] > 0:
                    if price <= my_hold["cost_basis"] * (1 - sl):
                        action = "SELL_SL"
                        forced_sell = True
                    elif price >= my_hold["cost_basis"] * (1 + tp):
                        action = "SELL_TP"
                        forced_sell = True

                if not forced_sell:
                    if pos >= 1 and my_hold["shares"] == 0:
                        action = "BUY"
                    elif pos <= -1 and my_hold["shares"] > 0:
                        action = "SELL"

                # Execution
                comm = 0.001  # US Tech commission usually very low or $0, but let's assume 0.1% impact

                if action == "BUY":
                    target_val = current_equity * alloc
                    budget = min(self.cash, target_val)
                    if budget > price:
                        shares = int(budget / (price * (1 + comm)))
                        if shares > 0:
                            cost = shares * price
                            self.cash -= cost * (1 + comm)
                            my_hold["shares"] += shares
                            my_hold["cost_basis"] = price
                            self.trade_log.append(
                                {
                                    "Date": date,
                                    "Symbol": symbol,
                                    "Action": "BUY",
                                    "Price": price,
                                    "Shares": shares,
                                    "PnL": 0,
                                }
                            )

                elif action and "SELL" in action:
                    if my_hold["shares"] > 0:
                        rev = my_hold["shares"] * price
                        net_rev = rev * (1 - comm)
                        pnl = net_rev - (my_hold["shares"] * my_hold["cost_basis"])
                        self.cash += net_rev
                        my_hold["shares"] = 0
                        my_hold["cost_basis"] = 0
                        self.trade_log.append(
                            {
                                "Date": date,
                                "Symbol": symbol,
                                "Action": action,
                                "Price": price,
                                "Shares": 0,
                                "PnL": pnl,
                            }
                        )

            self.portfolio_history.append(daily_portfolio_value)
            self.dates.append(date)

    def stats(self):
        final_val = self.portfolio_history[-1]
        ret = ((final_val - self.initial_capital) / self.initial_capital) * 100
        print(f"\n📊 GLOBAL PORTFOLIO RESULT (US TECH)")
        print(f"💰 Start: ${self.initial_capital:,.2f}")
        print(f"💸 End:   ${final_val:,.2f}")
        print(f"📈 Return: {ret:.2f}%")

        df = pd.DataFrame(self.trade_log)
        if not df.empty:
            print("\n--- Top Profits by Stock ---")
            print(df.groupby("Symbol")["PnL"].sum().sort_values(ascending=False))


if __name__ == "__main__":
    tester = GlobalBacktester()
    tester.run()
    tester.stats()
