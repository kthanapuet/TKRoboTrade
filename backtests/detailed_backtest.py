import sys
import pandas as pd
import yfinance as yf
from datetime import datetime

# Define the 10 Global Growth Stocks
SYMBOL_MAP = {
    "NVDA80.BK": "NVDA",
    "MSFT80.BK": "MSFT",
    "GOOG80.BK": "GOOG",
    "NDX01.BK": "QQQ",
    "AAPL80.BK": "AAPL",
    "TSLA80.BK": "TSLA",
    "E1VFVN3001.BK": "E1VFVN30.HM",
    "SIRI.BK": "SIRI.BK",
    "TRUE.BK": "TRUE.BK",
    "WHA.BK": "WHA.BK",
}

# Best Config from Optimization
BEST_CONFIG = {
    "fast_window": 5,
    "slow_window": 20,
    "stop_loss": 0.05,
    "trailing_activation": 0.50,
    "trailing_callback": 0.05,
}


def load_data():
    """Download historical data"""
    print("📥 Downloading Historical Data (2018-2023)...")
    data_store = {}
    valid_symbols = []

    start_date = "2018-01-01"
    end_date = "2023-12-31"

    for th_symbol, yf_symbol in SYMBOL_MAP.items():
        try:
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

            # Handle MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = (
                    df.columns.droplevel(1)
                    if len(df.columns.levels) > 1
                    else df.columns
                )

            # Normalize
            df.columns = [c.lower() for c in df.columns]

            if "close" in df.columns:
                df.rename(columns={"close": "Close"}, inplace=True)
                data_store[th_symbol] = df
                valid_symbols.append(th_symbol)
            else:
                print(f"⚠️ Missing 'Close' for {th_symbol}")

        except Exception as e:
            print(f"⚠️ Error downloading {th_symbol}: {e}")

    if not data_store or not valid_symbols:
        return {}, []

    # Common dates
    common_index = data_store[valid_symbols[0]].index
    for sym in valid_symbols[1:]:
        common_index = common_index.intersection(data_store[sym].index)

    for sym in valid_symbols:
        data_store[sym] = data_store[sym].loc[common_index]

    print(
        f"✅ Data Loaded: {len(valid_symbols)} stocks, {len(common_index)} trading days."
    )
    return data_store, valid_symbols


def run_detailed_backtest(data_store, symbols, config):
    """Run backtest with detailed trade logging"""

    fast_w = config["fast_window"]
    slow_w = config["slow_window"]
    sl_pct = config["stop_loss"]
    ts_act_pct = config["trailing_activation"]
    ts_cb_pct = config["trailing_callback"]

    initial_capital = 10000.0
    cash = initial_capital
    holdings = {sym: 0 for sym in symbols}
    entry_price = {sym: 0.0 for sym in symbols}
    entry_date = {sym: None for sym in symbols}
    max_price_since_entry = {sym: 0.0 for sym in symbols}

    # Trade Log
    trade_log = []

    # Portfolio Value Tracking
    portfolio_history = []

    # Pre-compute indicators
    indicators = {}
    for sym in symbols:
        df = data_store[sym].copy()
        df["SMA_Fast"] = df["Close"].rolling(window=fast_w).mean()
        df["SMA_Slow"] = df["Close"].rolling(window=slow_w).mean()
        indicators[sym] = df

    common_idx = indicators[symbols[0]].index

    for date in common_idx:
        # Calculate current portfolio value
        current_port_value = cash
        for sym in symbols:
            try:
                price = indicators[sym].loc[date]["Close"]
            except:
                continue
            current_port_value += holdings[sym] * price

        # Record portfolio value
        portfolio_history.append(
            {"Date": date, "Portfolio_Value": current_port_value, "Cash": cash}
        )

        # Trading Logic
        for sym in symbols:
            if date not in indicators[sym].index:
                continue

            row = indicators[sym].loc[date]
            price = row["Close"]
            sma_fast = row["SMA_Fast"]
            sma_slow = row["SMA_Slow"]

            if pd.isna(sma_fast) or pd.isna(sma_slow):
                continue

            # BUY LOGIC
            if holdings[sym] == 0:
                if sma_fast > sma_slow:
                    target_amt = 0.10 * current_port_value
                    if cash >= target_amt:
                        qty = int(target_amt / price)
                        if qty > 0:
                            cash -= qty * price
                            holdings[sym] = qty
                            entry_price[sym] = price
                            entry_date[sym] = date
                            max_price_since_entry[sym] = price

            # SELL LOGIC
            elif holdings[sym] > 0:
                # Update trailing max
                if price > max_price_since_entry[sym]:
                    max_price_since_entry[sym] = price

                exit_signal = False
                exit_reason = None

                # Check exit conditions
                if sma_fast < sma_slow:
                    exit_signal = True
                    exit_reason = "SMA_Crossunder"

                pct_change = (price - entry_price[sym]) / entry_price[sym]
                if pct_change <= -sl_pct:
                    exit_signal = True
                    exit_reason = "Stop_Loss"

                profit_pct = (
                    max_price_since_entry[sym] - entry_price[sym]
                ) / entry_price[sym]
                if profit_pct >= ts_act_pct:
                    drawdown = (
                        max_price_since_entry[sym] - price
                    ) / max_price_since_entry[sym]
                    if drawdown >= ts_cb_pct:
                        exit_signal = True
                        exit_reason = "Trailing_Stop"

                if exit_signal:
                    exit_value = holdings[sym] * price
                    cash += exit_value

                    # Calculate P&L
                    entry_value = holdings[sym] * entry_price[sym]
                    pnl = exit_value - entry_value
                    pnl_pct = (pnl / entry_value) * 100

                    # Duration
                    duration = (date - entry_date[sym]).days

                    # Log trade
                    trade_log.append(
                        {
                            "Symbol": sym,
                            "Entry_Date": entry_date[sym],
                            "Exit_Date": date,
                            "Duration_Days": duration,
                            "Entry_Price": entry_price[sym],
                            "Exit_Price": price,
                            "Max_Price": max_price_since_entry[sym],
                            "Quantity": holdings[sym],
                            "Entry_Value": entry_value,
                            "Exit_Value": exit_value,
                            "P&L": pnl,
                            "P&L_%": pnl_pct,
                            "Exit_Reason": exit_reason,
                        }
                    )

                    # Reset
                    holdings[sym] = 0
                    entry_price[sym] = 0
                    entry_date[sym] = None
                    max_price_since_entry[sym] = 0

    # Final portfolio value
    final_value = cash
    for sym in symbols:
        if holdings[sym] > 0:
            try:
                final_price = indicators[sym].iloc[-1]["Close"]
                final_value += holdings[sym] * final_price
            except:
                pass

    return trade_log, portfolio_history, final_value


def analyze_trades(trade_log, portfolio_history, initial_capital, final_value):
    """Analyze trade log and generate detailed statistics"""

    print("\n" + "=" * 80)
    print("📊 DETAILED BACKTEST ANALYSIS (2018-2023)")
    print("=" * 80)

    # Overall Performance
    total_return = ((final_value - initial_capital) / initial_capital) * 100
    print(f"\n💰 OVERALL PERFORMANCE:")
    print(f"   Initial Capital: ${initial_capital:,.2f}")
    print(f"   Final Value: ${final_value:,.2f}")
    print(f"   Total Return: {total_return:.2f}%")
    print(f"   Annualized Return: {(total_return / 5):.2f}%")

    if not trade_log:
        print("\n⚠️ No trades executed!")
        return

    df_trades = pd.DataFrame(trade_log)

    # Trade Statistics
    total_trades = len(df_trades)
    winning_trades = df_trades[df_trades["P&L"] > 0]
    losing_trades = df_trades[df_trades["P&L"] <= 0]

    num_wins = len(winning_trades)
    num_losses = len(losing_trades)
    win_rate = (num_wins / total_trades) * 100

    avg_win = winning_trades["P&L_%"].mean() if num_wins > 0 else 0
    avg_loss = losing_trades["P&L_%"].mean() if num_losses > 0 else 0

    max_win = df_trades["P&L_%"].max()
    max_loss = df_trades["P&L_%"].min()

    print(f"\n📈 TRADE STATISTICS:")
    print(f"   Total Trades: {total_trades}")
    print(f"   Winning Trades: {num_wins} ({win_rate:.1f}%)")
    print(f"   Losing Trades: {num_losses} ({100 - win_rate:.1f}%)")
    print(f"\n   Average Win: {avg_win:.2f}%")
    print(f"   Average Loss: {avg_loss:.2f}%")
    print(
        f"   Win/Loss Ratio: {abs(avg_win / avg_loss):.2f}x"
        if avg_loss != 0
        else "   Win/Loss Ratio: N/A"
    )
    print(f"\n   Best Trade: {max_win:.2f}%")
    print(f"   Worst Trade: {max_loss:.2f}%")

    # Holding Period
    avg_duration = df_trades["Duration_Days"].mean()
    print(f"\n⏱️ HOLDING PERIOD:")
    print(f"   Average: {avg_duration:.0f} days")
    print(f"   Shortest: {df_trades['Duration_Days'].min()} days")
    print(f"   Longest: {df_trades['Duration_Days'].max()} days")

    # Exit Reasons
    print(f"\n🚪 EXIT REASONS:")
    exit_counts = df_trades["Exit_Reason"].value_counts()
    for reason, count in exit_counts.items():
        pct = (count / total_trades) * 100
        print(f"   {reason}: {count} ({pct:.1f}%)")

    # Per-Stock Performance
    print(f"\n📊 PER-STOCK PERFORMANCE:")
    stock_stats = (
        df_trades.groupby("Symbol")
        .agg({"P&L_%": ["count", "mean", "sum"], "P&L": "sum"})
        .round(2)
    )
    stock_stats.columns = ["Trades", "Avg_Return_%", "Total_Return_%", "Total_P&L_$"]
    print(stock_stats.to_string())

    # Drawdown Analysis
    df_port = pd.DataFrame(portfolio_history)
    df_port["Peak"] = df_port["Portfolio_Value"].cummax()
    df_port["Drawdown_%"] = (
        (df_port["Portfolio_Value"] - df_port["Peak"]) / df_port["Peak"]
    ) * 100
    max_dd = df_port["Drawdown_%"].min()
    max_dd_date = df_port.loc[df_port["Drawdown_%"].idxmin(), "Date"]

    print(f"\n📉 DRAWDOWN ANALYSIS:")
    print(f"   Maximum Drawdown: {max_dd:.2f}%")
    print(f"   Max DD Date: {max_dd_date.strftime('%Y-%m-%d')}")

    # Losing Streaks
    df_trades["Is_Win"] = df_trades["P&L"] > 0
    df_trades["Streak"] = (df_trades["Is_Win"] != df_trades["Is_Win"].shift()).cumsum()
    losing_streaks = df_trades[~df_trades["Is_Win"]].groupby("Streak").size()
    if len(losing_streaks) > 0:
        max_losing_streak = losing_streaks.max()
        print(f"\n🔴 LOSING STREAKS:")
        print(f"   Longest Losing Streak: {max_losing_streak} trades")

    # Save detailed logs
    df_trades.to_csv("trade_log_detailed.csv", index=False)
    df_port.to_csv("portfolio_history.csv", index=False)
    print(f"\n💾 Trade log saved to: trade_log_detailed.csv")
    print(f"💾 Portfolio history saved to: portfolio_history.csv")


if __name__ == "__main__":
    data, symbols = load_data()
    if not data:
        print("❌ No data to backtest.")
        sys.exit()

    print(f"\n🧪 Running Detailed Backtest with Best Config:")
    print(f"   SMA: {BEST_CONFIG['fast_window']}/{BEST_CONFIG['slow_window']}")
    print(f"   Stop Loss: {BEST_CONFIG['stop_loss'] * 100}%")
    print(
        f"   Trailing: {BEST_CONFIG['trailing_activation'] * 100}% / {BEST_CONFIG['trailing_callback'] * 100}%"
    )

    trade_log, portfolio_history, final_value = run_detailed_backtest(
        data, symbols, BEST_CONFIG
    )

    analyze_trades(trade_log, portfolio_history, 10000.0, final_value)
