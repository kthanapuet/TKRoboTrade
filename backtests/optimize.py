import pandas as pd
import yfinance as yf
import json
import os
import sys
import itertools
from concurrent.futures import ProcessPoolExecutor

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from strategies.sma_cross import SMACrossover


class GridSearchBacktester:
    def __init__(self, symbol="PTT.BK", start_date="2014-01-01", end_date="2023-12-31"):
        self.symbol = symbol
        self.start_date = start_date
        self.end_date = end_date
        self.data = self._download_data()

    def _download_data(self):
        print(f"📥 Downloading data for {self.symbol}...")
        df = yf.download(
            self.symbol, start=self.start_date, end=self.end_date, progress=False
        )
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
        df.columns = df.columns.str.lower()
        if "date" not in df.columns:
            df.reset_index(inplace=True)
            df.rename(columns={"Date": "time"}, inplace=True)
            df.set_index("time", inplace=True)
        return df

    def run_strategy(self, params):
        fast, slow, sl, tp = params
        if fast >= slow:
            return -9999  # Invalid combination

        config = {
            "fast_window": fast,
            "slow_window": slow,
            "stop_loss_pct": sl,
            "take_profit_pct": tp,
        }

        # Init Strategy
        strategy = SMACrossover(config)
        df = self.data.copy()

        # Pre-calc signals
        df = strategy.generate_signals(df, current_cost=0)

        initial_capital = 100000
        cash = initial_capital
        holdings = 0
        cost_basis = 0

        # Fast Simulation Loop
        # Vectorizing trade logic is hard with state-dependent sl/tp, so using fast loop
        # Optimization: Pre-convert columns to numpy arrays for speed

        closes = df["close"].values
        positions = df["Position"].values
        dates = df.index
        n = len(df)

        commission_rate = 0.00168

        for i in range(n):
            price = closes[i]
            pos = positions[i]

            action = None
            forced_sell = False

            # Risk Check
            if holdings > 0:
                if price <= cost_basis * (1 - sl):
                    action = "SELL"
                    forced_sell = True
                elif price >= cost_basis * (1 + tp):
                    action = "SELL"
                    forced_sell = True

            # Signal Check
            if not forced_sell:
                if pos >= 1 and holdings == 0:
                    action = "BUY"
                elif pos <= -1 and holdings > 0:
                    action = "SELL"

            if action == "BUY":
                if cash > price:
                    shares = int(cash / (price * (1 + commission_rate)))
                    if shares > 0:
                        cost = shares * price
                        cash -= cost * (1 + commission_rate)
                        holdings = shares
                        cost_basis = price

            elif action == "SELL":
                if holdings > 0:
                    revenue = holdings * price
                    cash += revenue * (1 - commission_rate)
                    holdings = 0
                    cost_basis = 0

        final_value = cash + (holdings * closes[-1])
        return_pct = ((final_value - initial_capital) / initial_capital) * 100
        return return_pct


def optimize(symbol):
    # Parameter Grid
    # Parameter Grid
    fast_range = [3, 5, 8, 10, 12, 15, 20]
    slow_range = [20, 30, 40, 50, 60, 80, 100, 150, 200]
    sl_range = [0.03, 0.05, 0.08, 0.10, 0.12]
    tp_range = [0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]

    combinations = list(itertools.product(fast_range, slow_range, sl_range, tp_range))
    print(f"🔍 Testing {len(combinations)} combinations for {symbol}...")

    tester = GridSearchBacktester(symbol)

    best_return = -9999
    best_params = None

    # Simple Loop (Can be parallelized)
    for i, params in enumerate(combinations):
        if i % 100 == 0:
            print(f"   Progress: {i}/{len(combinations)}", end="\r")
        ret = tester.run_strategy(params)
        if ret > best_return:
            best_return = ret
            best_params = params

    print(f"\n✅ Best Result for {symbol}:")
    print(f"   Return: {best_return:.2f}%")
    print(
        f"   Params: Fast={best_params[0]}, Slow={best_params[1]}, SL={best_params[2]}, TP={best_params[3]}"
    )
    return best_params


if __name__ == "__main__":
    # Optimize PTT
    optimize("PTT.BK")
    # Optimize KBANK
    optimize("KBANK.BK")
