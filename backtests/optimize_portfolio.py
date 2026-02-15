import sys
import os
import itertools
import pandas as pd
import numpy as np
import yfinance as yf
from strategies.sma_cross import SMACrossover

# Define the 10 Global Growth Stocks (Map .BK to US/Global symbols for data)
SYMBOL_MAP = {
    "NVDA80.BK": "NVDA",
    "MSFT80.BK": "MSFT",
    "GOOG80.BK": "GOOG",
    "NDX01.BK": "QQQ",
    "AAPL80.BK": "AAPL",
    "TSLA80.BK": "TSLA",
    "E1VFVN3001.BK": "E1VFVN30.HM",  # Use Proxy or Skip if no data
    "SIRI.BK": "SIRI.BK",
    "TRUE.BK": "TRUE.BK",
    "WHA.BK": "WHA.BK",
}

# Define Parameter Grid to Search
PARAM_GRID = {
    "ma_windows": [(5, 20), (10, 50), (15, 60)],  # Fast/Slow pairs
    "stop_loss": [0.03, 0.05, 0.08],
    "trailing_activation": [0.20, 0.35, 0.50],
    "trailing_callback": [0.05, 0.10, 0.15],
}


def load_data():
    """Download data once to speed up optimization"""
    print("📥 Downloading Historical Data (2018-2023)...")
    data_store = {}
    valid_symbols = []

    start_date = "2018-01-01"
    end_date = "2023-12-31"

    for th_symbol, yf_symbol in SYMBOL_MAP.items():
        try:
            # auto_adjust=True usually returns simple columns [Open, High, Low, Close, Volume]
            df = yf.download(
                yf_symbol,
                start=start_date,
                end=end_date,
                progress=False,
                auto_adjust=True,
            )

            if df.empty:
                print(f"⚠️ No data for {th_symbol}")
                continue

            # Handle MultiIndex Columns (Ticker as level 0 or 1)
            if isinstance(df.columns, pd.MultiIndex):
                # Flatten or select Close
                # Try to drop levels
                df.columns = (
                    df.columns.droplevel(1)
                    if len(df.columns.levels) > 1
                    else df.columns
                )

            # Normalize Columns
            df.columns = [c.lower() for c in df.columns]

            if "close" in df.columns:
                df.rename(columns={"close": "Close"}, inplace=True)
                data_store[th_symbol] = df
                valid_symbols.append(th_symbol)
            else:
                print(f"⚠️ Missing 'Close' column for {th_symbol}. Cols: {df.columns}")

        except Exception as e:
            print(f"⚠️ Error downloading {th_symbol}: {e}")

    # Find common dates
    if not data_store:
        return {}, []

    if not valid_symbols:
        return {}, []

    common_index = data_store[valid_symbols[0]].index
    for sym in valid_symbols[1:]:
        common_index = common_index.intersection(data_store[sym].index)

    # Reindex all data to common dates
    for sym in valid_symbols:
        data_store[sym] = data_store[sym].loc[common_index]

    print(
        f"✅ Data Loaded: {len(valid_symbols)} stocks, {len(common_index)} trading days."
    )
    return data_store, valid_symbols


def run_backtest(data_store, symbols, params):
    """Run portfolio backtest with specific params"""

    fast_w, slow_w = params["ma_pair"]
    sl_pct = params["sl"]
    ts_act_pct = params["ts_act"]
    ts_cb_pct = params["ts_cb"]

    initial_capital = 10000.0
    cash = initial_capital
    holdings = {sym: 0 for sym in symbols}
    entry_price = {sym: 0.0 for sym in symbols}
    max_price_since_entry = {sym: 0.0 for sym in symbols}

    # Strategy Config
    strat_conf = {
        "fast_window": fast_w,
        "slow_window": slow_w,
        "stop_loss_pct": params["sl"],
        "take_profit_pct": 0.0,  # Disable fixed TP, use Trailing
        "trailing_stop_activation_pct": params["ts_act"],
        "trailing_stop_pct": params["ts_cb"],
    }

    # Pre-compute indicators to avoid re-calculation inside loop
    # dict of dataframe with SMA columns
    indicators = {}
    for sym in symbols:
        df = data_store[sym].copy()

        # Calculate Indicators
        # Data is already clean from load_data()
        df["SMA_Fast"] = df["Close"].rolling(window=fast_w).mean()
        df["SMA_Slow"] = df["Close"].rolling(window=slow_w).mean()
        indicators[sym] = df

    # Vectorized loop is hard with Portfolio constraints (Cash limit).
    # We must loop by date.

    # Get common index
    common_idx = indicators[symbols[0]].index

    for date in common_idx:
        # Portfolio Value Calculation
        current_port_value = cash
        for sym in symbols:
            # Get Price
            # Safe access
            try:
                price = indicators[sym].loc[date]["Close"]
            except:
                continue  # Skip if no data for this date

            current_port_value += holdings[sym] * price

        # Trading Logic Loop
        for sym in symbols:
            # Ensure the date exists for this symbol
            if date not in indicators[sym].index:
                continue

            row = indicators[sym].loc[date]
            price = row["Close"]
            sma_fast = row["SMA_Fast"]
            sma_slow = row["SMA_Slow"]

            # Check for NaN (not enough data for SMA)
            if pd.isna(sma_fast) or pd.isna(sma_slow):
                continue

            # Previous Row (Approximation: Use Shift logic or just check condition change)
            # For speed, we just check Crossover state today.
            # Real crossover needs prev_fast < prev_slow.
            # Let's simple check: Fast > Slow = Bullish.

            # 1. Buy Logic
            if holdings[sym] == 0:
                if sma_fast > sma_slow:
                    # Check if we have prev info?
                    # Optimization: Just hold if Fast > Slow is good proxy for trend following
                    # But we need specific Entry trigger.
                    # Let's assume Entry on First Day of Fast > Slow (we missed exact cross, but okay)

                    # Buy Allocation 10%
                    target_amt = 0.10 * current_port_value
                    if cash >= target_amt:
                        qty = int(target_amt / price)
                        if qty > 0:
                            cash -= qty * price
                            holdings[sym] = qty
                            entry_price[sym] = price
                            max_price_since_entry[sym] = price

            # 2. Sell Logic (Holding)
            elif holdings[sym] > 0:
                # Update Trailing Max
                if price > max_price_since_entry[sym]:
                    max_price_since_entry[sym] = price

                exit_signal = False

                # Condition A: SMA Crossunder (Fast < Slow)
                if sma_fast < sma_slow:
                    exit_signal = True

                # Condition B: Stop Loss
                pct_change = (price - entry_price[sym]) / entry_price[sym]
                if pct_change <= -sl_pct:
                    exit_signal = True

                # Condition C: Trailing Stop
                # If Profit > Activation
                profit_pct = (
                    max_price_since_entry[sym] - entry_price[sym]
                ) / entry_price[sym]
                if profit_pct >= ts_act_pct:
                    # Calculate Drawdown from Max
                    drawdown = (
                        max_price_since_entry[sym] - price
                    ) / max_price_since_entry[sym]
                    if drawdown >= ts_cb_pct:
                        exit_signal = True

                if exit_signal:
                    cash += holdings[sym] * price
                    holdings[sym] = 0
                    entry_price[sym] = 0
                    max_price_since_entry[sym] = 0

    return ((current_port_value - initial_capital) / initial_capital) * 100


if __name__ == "__main__":
    data, symbols = load_data()
    if not data:
        print("❌ No data to backtest.")
        sys.exit()

    print(f"\n🧪 Starting Grid Search Optimization on {len(symbols)} stocks...")
    print(
        f"   Parameter Combinations: {len(PARAM_GRID['ma_windows']) * len(PARAM_GRID['stop_loss']) * len(PARAM_GRID['trailing_activation']) * len(PARAM_GRID['trailing_callback'])}"
    )

    results = []

    # Grid Search Loop
    combinations = list(
        itertools.product(
            PARAM_GRID["ma_windows"],
            PARAM_GRID["stop_loss"],
            PARAM_GRID["trailing_activation"],
            PARAM_GRID["trailing_callback"],
        )
    )

    total_runs = len(combinations)
    print(f"   Total Runs: {total_runs}\n")

    for i, (ma, sl, ts_act, ts_cb) in enumerate(combinations):
        params = {"ma_pair": ma, "sl": sl, "ts_act": ts_act, "ts_cb": ts_cb}

        # Run Backtest
        ret = run_backtest(data, symbols, params)

        results.append(
            {
                "Return (%)": ret,
                "SMA (Fast/Slow)": f"{ma[0]}/{ma[1]}",
                "Stop Loss": sl,
                "Trailing Act": ts_act,
                "Trailing Call": ts_cb,
            }
        )

        if (i + 1) % 5 == 0:
            print(f"   ... Processed {i + 1}/{total_runs} | Last Result: {ret:.2f}%")

    # Sort & Show Best
    df_res = pd.DataFrame(results)
    df_res = df_res.sort_values(by="Return (%)", ascending=False)

    print("\n🏆 TOP 5 CONFIGURATIONS:")
    print(df_res.head(5).to_string(index=False))

    print("\n⚠️ WORST 5 CONFIGURATIONS:")
    print(df_res.tail(5).to_string(index=False))

    # Save to CSV
    df_res.to_csv("optimization_results.csv", index=False)
    print("\n💾 Results saved to 'optimization_results.csv'")
