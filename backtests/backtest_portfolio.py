import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime
import json
import os
import sys

# ---------------------------------------------------------
# Add Path to access Modules
# ---------------------------------------------------------
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.sma_cross import SMACrossover
from strategies.ema_cross import EMACrossover
from strategies.supertrend import Supertrend
from strategies.bbands_rsi import BollingerRSI


class PortfolioBacktester:
    def __init__(
        self, start_date="2023-01-01", end_date="2023-12-31", initial_capital=100000.0
    ):
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.holdings = {}  # {symbol: {'shares': 0, 'cost_basis': 0}}
        self.portfolio_history = []
        self.dates = []
        self.trade_log = []

        # Load Config
        try:
            with open("config.json", "r") as f:
                self.app_config = json.load(f)
                self.strategies_config = self.app_config.get("strategies", {})
            
            with open("portfolio.json", "r", encoding="utf-8") as f:
                self.portfolio_config = json.load(f)
        except FileNotFoundError as e:
            print(f"[-] Config file not found: {e}")
            sys.exit(1)

        if not self.portfolio_config:
            print("[-] No portfolio settings found in portfolio.json")
            sys.exit(1)

        # Initialize Holdings
        for item in self.portfolio_config:
            self.holdings[item["symbol"]] = {"shares": 0, "cost_basis": 0}

    def reset(self):
        """Reset backtester state for a new run"""
        self.cash = self.initial_capital
        self.holdings = {sym: {"shares": 0, "cost_basis": 0} for sym in self.holdings}
        self.portfolio_history = []
        self.dates = []
        self.trade_log = []

    def run(self, strategy_name=None):
        print(f"[+] Starting Portfolio Backtest ({self.start_date} - {self.end_date})")
        print(f"[+] Initial Capital: {self.initial_capital:,.2f}")

        # 1. Download Data for ALL symbols
        data_store = {}
        for item in self.portfolio_config:
            symbol = item["symbol"]

            # Smart Mapping for Backtest: Use Underlying Asset if it's a DR
            download_symbol = symbol
            if "80.BK" in symbol:
                download_symbol = symbol.replace("80.BK", "")  # AAPL80.BK -> AAPL
            elif "01.BK" in symbol and "NDX" in symbol:
                download_symbol = "QQQ"  # NDX01 approx -> QQQ (ETF)
            elif "E1VFVN3001.BK" in symbol:
                download_symbol = "E1VFVN30.HM"  # Vietnam ETF proxy or skip if hard

            print(f"   -> Downloading {download_symbol} (for {symbol})...")

            try:
                df = yf.download(
                    download_symbol,
                    start=self.start_date,
                    end=self.end_date,
                    progress=False,
                )
            except Exception as e:
                print(f"      ❌ Failed to download {download_symbol}: {e}")
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)

            df.columns = df.columns.str.lower()
            if "date" not in df.columns:
                df.reset_index(inplace=True)
                df.rename(columns={"Date": "time"}, inplace=True)
                df.set_index("time", inplace=True)

            if df.empty:
                print(f"      ⚠️ No data found for {download_symbol}")
                continue

            data_store[symbol] = df  # Store under the original config name

        # 2. Align Data (หาช่วงเวลาที่มีข้อมูลร่วมกัน หรือ Union)
        # เพื่อความง่าย ใช้ Date Intersection ของทุกตัว
        common_dates = None
        for symbol, df in data_store.items():
            if common_dates is None:
                common_dates = df.index
            else:
                common_dates = common_dates.intersection(df.index)

        common_dates = common_dates.sort_values()
        print(f"[+] Found common trading days: {len(common_dates)} days")

        # 3. Pre-calculate Strategy Signals
        signals_store = {}
        strategies_instances = {}

        for item in self.portfolio_config:
            symbol = item["symbol"]

            if symbol not in data_store:
                print(f"⚠️ Skipping {symbol} (No Data)")
                continue

            # Merge base config with override
            base_strat_name = strategy_name if strategy_name else self.app_config.get("active_strategy", "EMACrossover")
            base_config = self.strategies_config.get(base_strat_name, {}).copy()
            override_config = item.get("strategy_override", {})
            final_config = {**base_config, **override_config}

            # Init Strategy
            if base_strat_name == "SMACrossover":
                strategy = SMACrossover(final_config)
            elif base_strat_name == "EMACrossover":
                strategy = EMACrossover(final_config)
            elif base_strat_name == "Supertrend":
                strategy = Supertrend(final_config)
            elif base_strat_name == "BollingerRSI":
                strategy = BollingerRSI(final_config)
            else:
                strategy = EMACrossover(final_config)

            strategies_instances[symbol] = strategy

            # Generate Signals
            try:
                df = data_store[symbol].loc[common_dates].copy()
                # Debug: Check if df is empty after loc
                if df.empty:
                    print(
                        f"⚠️ Data for {symbol} is empty after aligning dates. Skipping."
                    )
                    continue

                df_signals = strategy.generate_signals(df, current_cost=0)
                signals_store[symbol] = df_signals
            except KeyError:
                print(f"⚠️ {symbol} data missing for some dates. Skipping.")
                continue

        # 4. Simulation Loop (Day by Day)
        print("[*] Starting simulation loop...")

        for date in common_dates:
            # 1. Calculate Current Equity (Cash + Market Value of Holdings)
            current_equity = self.cash
            prices_today = {}
            for s_item in self.portfolio_config:
                s_sym = s_item["symbol"]
                try:
                    s_price = signals_store[s_sym].loc[date]["close"]
                    current_equity += self.holdings[s_sym]["shares"] * s_price
                    prices_today[s_sym] = s_price
                except KeyError:
                    prices_today[s_sym] = 0  # No price data means valid 0 value for now

            daily_portfolio_value = current_equity

            # Loop check each stock in portfolio
            for item in self.portfolio_config:
                symbol = item["symbol"]
                allocation_ratio = item.get("allocation_check", 1.0)

                if symbol not in prices_today or prices_today[symbol] == 0:
                    continue

                # Get Data for this date
                try:
                    current_bar = signals_store[symbol].loc[date]
                except KeyError:
                    continue

                current_price = current_bar["close"]
                raw_position = current_bar["Position"]

                # --- Risk Logic Config ---
                base_strat_name = self.app_config.get("active_strategy", "SMACrossover")
                base_config = self.strategies_config.get(base_strat_name, {})
                override_config = item.get("strategy_override", {})
                final_config = {**base_config, **override_config}

                sl_pct = final_config.get("stop_loss_pct", 0.05)
                sl_pct = final_config.get("stop_loss_pct", 0.05)
                # tp_pct = final_config.get("take_profit_pct", 0.10) # OLD: Simple TP

                # New Trailing Stop Config
                ts_activation_pct = final_config.get(
                    "trailing_stop_activation_pct", None
                )
                ts_callback_pct = final_config.get("trailing_stop_pct", None)

                # Fallback to simple TP if TS not set
                simple_tp_pct = final_config.get("take_profit_pct", None)

                # --- Decision Logic ---
                action = None
                forced_sell = False

                my_holding = self.holdings[symbol]

                # Logic: Update High Water Mark (Highest Price since bought)
                if my_holding["shares"] > 0:
                    if "high_water_mark" not in my_holding:
                        my_holding["high_water_mark"] = my_holding["cost_basis"]

                    if current_price > my_holding["high_water_mark"]:
                        my_holding["high_water_mark"] = current_price

                # 1. Risk Management Check
                if my_holding["shares"] > 0:
                    # A. Stop Loss (Fixed % from Cost)
                    if current_price <= my_holding["cost_basis"] * (1 - sl_pct):
                        action = "SELL (Stop Loss)"
                        forced_sell = True

                    # B. Trailing Stop Logic
                    elif ts_activation_pct and ts_callback_pct:
                        # Check if activation threshold met
                        profit_pct = (
                            my_holding["high_water_mark"] - my_holding["cost_basis"]
                        ) / my_holding["cost_basis"]

                        if profit_pct >= ts_activation_pct:
                            # Check if price dropped from High Water Mark
                            drop_from_high = (
                                my_holding["high_water_mark"] - current_price
                            ) / my_holding["high_water_mark"]
                            if drop_from_high >= ts_callback_pct:
                                action = f"SELL (Trailing Stop - Profit {profit_pct * 100:.1f}%)"
                                forced_sell = True

                    # C. Simple Take Profit (Fallback if TS not used)
                    elif simple_tp_pct:
                        if current_price >= my_holding["cost_basis"] * (
                            1 + simple_tp_pct
                        ):
                            action = "SELL (Take Profit)"
                            forced_sell = True

                # 2. Strategy Signal Check
                if not forced_sell:
                    if raw_position >= 1:  # Buy
                        if my_holding["shares"] == 0:
                            action = "BUY"
                    elif raw_position <= -1:  # Sell
                        if my_holding["shares"] > 0:
                            action = "SELL"

                # --- Execution ---
                commission_rate = 0.00168

                if action == "BUY":
                    # Reinvestment: Use Current Equity for Allocation Calculation
                    target_alloc_value = current_equity * allocation_ratio
                    budget = min(self.cash, target_alloc_value)

                    if budget > current_price:
                        shares_to_buy = int(
                            budget / (current_price * (1 + commission_rate))
                        )

                        if shares_to_buy > 0:
                            cost = shares_to_buy * current_price
                            commission = cost * commission_rate
                            total_cost = cost + commission

                            self.cash -= total_cost
                            my_holding["shares"] += shares_to_buy
                            my_holding["cost_basis"] = current_price

                            self.trade_log.append(
                                {
                                    "Date": date,
                                    "Symbol": symbol,
                                    "Action": "BUY",
                                    "Price": current_price,
                                    "Shares": shares_to_buy,
                                    "Value": total_cost,
                                    "Balance": self.cash,
                                }
                            )

                elif action and "SELL" in action:
                    if my_holding["shares"] > 0:
                        revenue = my_holding["shares"] * current_price
                        commission = revenue * commission_rate
                        net_revenue = revenue - commission

                        pnl = net_revenue - (
                            my_holding["shares"] * my_holding["cost_basis"]
                        )

                        self.cash += net_revenue

                        self.trade_log.append(
                            {
                                "Date": date,
                                "Symbol": symbol,
                                "Action": action,
                                "Price": current_price,
                                "Shares": 0,
                                "Value": net_revenue,
                                "Balance": self.cash,
                                "PnL": pnl,
                            }
                        )

                        # Reset Holding
                        my_holding["shares"] = 0
                        my_holding["cost_basis"] = 0

            self.portfolio_history.append(daily_portfolio_value)
            self.dates.append(date)

    def stats(self):
        final_value = self.portfolio_history[-1]
        total_return = (
            (final_value - self.initial_capital) / self.initial_capital
        ) * 100

        print("\n" + "=" * 50)
        print("PORTFOLIO BACKTEST RESULT")
        print("=" * 50)
        print(f"Initial Capital:   {self.initial_capital:,.2f}")
        print(f"Final Value:       {final_value:,.2f}")
        print(f"Total Return:      {total_return:.2f}%")
        print(f"Total Trades:      {len(self.trade_log)}")
        print("=" * 50)

        # Breakdown by Symbol
        df_log = pd.DataFrame(self.trade_log)
        if not df_log.empty:
            print("\n--- Trade History (Last 10) ---")
            print(df_log[["Date", "Symbol", "Action", "Price", "PnL"]].tail(10))

            print("\n--- Performance by Symbol ---")
            pnl_by_symbol = df_log[df_log["PnL"].notna()].groupby("Symbol")["PnL"].sum()
            print(pnl_by_symbol)

    def plot(self):
        plt.figure(figsize=(12, 6))
        plt.plot(self.dates, self.portfolio_history, label="Total Portfolio Value")
        plt.title("Portfolio Performance")
        plt.xlabel("Date")
        plt.ylabel("Value (THB)")
        plt.legend()
        plt.grid(True)
        # plt.show()


if __name__ == "__main__":
    backtester = PortfolioBacktester(
        start_date="2014-01-01", end_date="2023-12-31", initial_capital=10000.0
    )
    
    strategies_to_test = ["EMACrossover", "Supertrend", "BollingerRSI", "SMACrossover"]
    comparison_results = []

    print("="*60)
    print("STARTING 10-YEAR STRATEGY COMPARISON (2014-2023)")
    print("="*60)

    for strat in strategies_to_test:
        print(f"\n[RUNNING] Strategy: {strat}")
        backtester.reset()
        backtester.run(strategy_name=strat)
        
        final_value = backtester.portfolio_history[-1]
        total_return = ((final_value - backtester.initial_capital) / backtester.initial_capital) * 100
        total_trades = len(backtester.trade_log)
        
        comparison_results.append({
            "Strategy": strat,
            "Return (%)": total_return,
            "Final Value": final_value,
            "Trades": total_trades
        })

    # Print Comparison Table
    print("\n" + "="*60)
    print("FINAL STRATEGY COMPARISON SUMMARY")
    print("="*60)
    df_compare = pd.DataFrame(comparison_results)
    print(df_compare.to_string(index=False))
    print("="*60)
    # backtester.plot()
