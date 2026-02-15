"""
Strategy Comparison Script
Compare different technical indicators to find the best one for Global Growth Stocks portfolio
"""

import sys
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

# Symbol mapping
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

# Universal exit conditions
STOP_LOSS = 0.05
TRAILING_ACTIVATION = 0.50
TRAILING_CALLBACK = 0.05


def load_data():
    """Download historical data"""
    print("📥 Downloading Historical Data (2018-2023)...")
    data_store = {}
    valid_symbols = []
    
    start_date = "2018-01-01"
    end_date = "2023-12-31"
    
    for th_symbol, yf_symbol in SYMBOL_MAP.items():
        try:
            df = yf.download(yf_symbol, start=start_date, end=end_date, progress=False, auto_adjust=True)
            
            if df.empty:
                print(f"⚠️ No data for {th_symbol}")
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1) if len(df.columns.levels) > 1 else df.columns
                
            df.columns = [c.lower() for c in df.columns]
            
            if 'close' in df.columns:
                df.rename(columns={'close': 'Close'}, inplace=True)
                data_store[th_symbol] = df
                valid_symbols.append(th_symbol)
                
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
        
    print(f"✅ Data Loaded: {len(valid_symbols)} stocks, {len(common_index)} trading days.")
    return data_store, valid_symbols


def calculate_sma_signals(df, fast=5, slow=20):
    """Calculate SMA Crossover signals"""
    df = df.copy()
    df['SMA_Fast'] = df['Close'].rolling(window=fast).mean()
    df['SMA_Slow'] = df['Close'].rolling(window=slow).mean()
    
    df['Signal'] = 0
    df.loc[df['SMA_Fast'] > df['SMA_Slow'], 'Signal'] = 1  # Buy
    df.loc[df['SMA_Fast'] < df['SMA_Slow'], 'Signal'] = -1  # Sell
    
    return df


def calculate_ema_signals(df, fast=5, slow=20):
    """Calculate EMA Crossover signals"""
    df = df.copy()
    df['EMA_Fast'] = df['Close'].ewm(span=fast, adjust=False).mean()
    df['EMA_Slow'] = df['Close'].ewm(span=slow, adjust=False).mean()
    
    df['Signal'] = 0
    df.loc[df['EMA_Fast'] > df['EMA_Slow'], 'Signal'] = 1
    df.loc[df['EMA_Fast'] < df['EMA_Slow'], 'Signal'] = -1
    
    return df


def calculate_macd_signals(df):
    """Calculate MACD signals"""
    df = df.copy()
    
    # MACD components
    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    df['Signal'] = 0
    df.loc[df['MACD'] > df['Signal_Line'], 'Signal'] = 1  # Buy
    df.loc[df['MACD'] < df['Signal_Line'], 'Signal'] = -1  # Sell
    
    return df


def calculate_rsi_signals(df, period=14, oversold=30, overbought=70):
    """Calculate RSI signals"""
    df = df.copy()
    
    # RSI calculation
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['Signal'] = 0
    df.loc[df['RSI'] < oversold, 'Signal'] = 1  # Buy when oversold
    df.loc[df['RSI'] > overbought, 'Signal'] = -1  # Sell when overbought
    
    return df


def calculate_bbands_rsi_signals(df):
    """Calculate Bollinger Bands + RSI combination signals"""
    df = df.copy()
    
    # Bollinger Bands
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['BB_Upper'] = df['SMA_20'] + 2 * df['Close'].rolling(window=20).std()
    df['BB_Lower'] = df['SMA_20'] - 2 * df['Close'].rolling(window=20).std()
    
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Combined signal
    df['Signal'] = 0
    # Buy: Price near lower band AND RSI oversold
    df.loc[(df['Close'] <= df['BB_Lower']) & (df['RSI'] < 40), 'Signal'] = 1
    # Sell: Price near upper band AND RSI overbought
    df.loc[(df['Close'] >= df['BB_Upper']) & (df['RSI'] > 60), 'Signal'] = -1
    
    return df


def calculate_ema_macd_signals(df):
    """Calculate EMA + MACD combination signals"""
    df = df.copy()
    
    # EMA
    df['EMA_Fast'] = df['Close'].ewm(span=12, adjust=False).mean()
    df['EMA_Slow'] = df['Close'].ewm(span=26, adjust=False).mean()
    
    # MACD
    df['MACD'] = df['EMA_Fast'] - df['EMA_Slow']
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # Combined signal (both must agree)
    df['Signal'] = 0
    df.loc[(df['EMA_Fast'] > df['EMA_Slow']) & (df['MACD'] > df['Signal_Line']), 'Signal'] = 1
    df.loc[(df['EMA_Fast'] < df['EMA_Slow']) & (df['MACD'] < df['Signal_Line']), 'Signal'] = -1
    
    return df


def calculate_supertrend_signals(df, period=10, multiplier=3):
    """Calculate Supertrend signals"""
    df = df.copy()
    
    # Ensure we have high, low columns
    if 'high' not in df.columns or 'low' not in df.columns:
        # Approximate with close price if high/low not available
        df['high'] = df['Close']
        df['low'] = df['Close']
    
    # Calculate ATR (Average True Range)
    df['H-L'] = df['high'] - df['low']
    df['H-PC'] = abs(df['high'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(window=period).mean()
    
    # Calculate basic upper and lower bands
    df['HL_Avg'] = (df['high'] + df['low']) / 2
    df['Upper_Band'] = df['HL_Avg'] + (multiplier * df['ATR'])
    df['Lower_Band'] = df['HL_Avg'] - (multiplier * df['ATR'])
    
    # Initialize Supertrend
    df['Supertrend'] = 0.0
    df['Trend'] = 1  # 1 = Uptrend, -1 = Downtrend
    
    for i in range(period, len(df)):
        # Current values
        curr_close = df['Close'].iloc[i]
        curr_upper = df['Upper_Band'].iloc[i]
        curr_lower = df['Lower_Band'].iloc[i]
        prev_supertrend = df['Supertrend'].iloc[i-1]
        prev_trend = df['Trend'].iloc[i-1]
        
        # Determine Supertrend value
        if prev_trend == 1:
            # Was in uptrend
            if curr_close <= prev_supertrend:
                df.loc[df.index[i], 'Supertrend'] = curr_upper
                df.loc[df.index[i], 'Trend'] = -1
            else:
                df.loc[df.index[i], 'Supertrend'] = max(curr_lower, prev_supertrend)
                df.loc[df.index[i], 'Trend'] = 1
        else:
            # Was in downtrend
            if curr_close >= prev_supertrend:
                df.loc[df.index[i], 'Supertrend'] = curr_lower
                df.loc[df.index[i], 'Trend'] = 1
            else:
                df.loc[df.index[i], 'Supertrend'] = min(curr_upper, prev_supertrend)
                df.loc[df.index[i], 'Trend'] = -1
    
    # Generate signals
    df['Signal'] = 0
    df.loc[df['Trend'] == 1, 'Signal'] = 1   # Buy when in uptrend
    df.loc[df['Trend'] == -1, 'Signal'] = -1  # Sell when in downtrend
    
    return df


def calculate_ichimoku_signals(df):
    """Calculate Ichimoku Cloud signals"""
    df = df.copy()
    
    # Ensure we have high, low columns
    if 'high' not in df.columns or 'low' not in df.columns:
        df['high'] = df['Close']
        df['low'] = df['Close']
    
    # Tenkan-sen (Conversion Line): (9-period high + 9-period low) / 2
    period9_high = df['high'].rolling(window=9).max()
    period9_low = df['low'].rolling(window=9).min()
    df['Tenkan'] = (period9_high + period9_low) / 2
    
    # Kijun-sen (Base Line): (26-period high + 26-period low) / 2
    period26_high = df['high'].rolling(window=26).max()
    period26_low = df['low'].rolling(window=26).min()
    df['Kijun'] = (period26_high + period26_low) / 2
    
    # Senkou Span A (Leading Span A): (Tenkan + Kijun) / 2, shifted 26 periods ahead
    df['Senkou_A'] = ((df['Tenkan'] + df['Kijun']) / 2).shift(26)
    
    # Senkou Span B (Leading Span B): (52-period high + 52-period low) / 2, shifted 26 periods ahead
    period52_high = df['high'].rolling(window=52).max()
    period52_low = df['low'].rolling(window=52).min()
    df['Senkou_B'] = ((period52_high + period52_low) / 2).shift(26)
    
    # Chikou Span (Lagging Span): Close shifted 26 periods back
    df['Chikou'] = df['Close'].shift(-26)
    
    # Generate signals
    df['Signal'] = 0
    
    # Buy conditions:
    # 1. Price above cloud (above both Senkou A and B)
    # 2. Tenkan > Kijun (bullish crossover)
    df.loc[
        (df['Close'] > df['Senkou_A']) & 
        (df['Close'] > df['Senkou_B']) & 
        (df['Tenkan'] > df['Kijun']),
        'Signal'
    ] = 1
    
    # Sell conditions:
    # 1. Price below cloud
    # 2. Tenkan < Kijun (bearish crossover)
    df.loc[
        (df['Close'] < df['Senkou_A']) & 
        (df['Close'] < df['Senkou_B']) & 
        (df['Tenkan'] < df['Kijun']),
        'Signal'
    ] = -1
    
    return df


def run_backtest(data_store, symbols, strategy_func, strategy_name):
    """Run backtest for a specific strategy"""
    
    initial_capital = 10000.0
    cash = initial_capital
    holdings = {sym: 0 for sym in symbols}
    entry_price = {sym: 0.0 for sym in symbols}
    max_price_since_entry = {sym: 0.0 for sym in symbols}
    
    trade_log = []
    
    # Calculate indicators for all symbols
    indicators = {}
    for sym in symbols:
        df = data_store[sym].copy()
        df = strategy_func(df)
        indicators[sym] = df
        
    common_idx = indicators[symbols[0]].index
    
    for date in common_idx:
        # Calculate portfolio value
        current_port_value = cash
        for sym in symbols:
            try:
                price = indicators[sym].loc[date]['Close']
                current_port_value += holdings[sym] * price
            except:
                continue
                
        # Trading logic
        for sym in symbols:
            if date not in indicators[sym].index:
                continue
                
            row = indicators[sym].loc[date]
            price = row['Close']
            signal = row.get('Signal', 0)
            
            if pd.isna(price) or pd.isna(signal):
                continue
                
            # BUY Logic
            if holdings[sym] == 0 and signal == 1:
                target_amt = 0.10 * current_port_value
                if cash >= target_amt:
                    qty = int(target_amt / price)
                    if qty > 0:
                        cash -= qty * price
                        holdings[sym] = qty
                        entry_price[sym] = price
                        max_price_since_entry[sym] = price
                        
            # SELL Logic
            elif holdings[sym] > 0:
                # Update trailing max
                if price > max_price_since_entry[sym]:
                    max_price_since_entry[sym] = price
                    
                exit_signal = False
                exit_reason = None
                
                # Condition 1: Strategy Signal
                if signal == -1:
                    exit_signal = True
                    exit_reason = "Strategy_Signal"
                    
                # Condition 2: Stop Loss
                pct_change = (price - entry_price[sym]) / entry_price[sym]
                if pct_change <= -STOP_LOSS:
                    exit_signal = True
                    exit_reason = "Stop_Loss"
                    
                # Condition 3: Trailing Stop
                profit_pct = (max_price_since_entry[sym] - entry_price[sym]) / entry_price[sym]
                if profit_pct >= TRAILING_ACTIVATION:
                    drawdown = (max_price_since_entry[sym] - price) / max_price_since_entry[sym]
                    if drawdown >= TRAILING_CALLBACK:
                        exit_signal = True
                        exit_reason = "Trailing_Stop"
                        
                if exit_signal:
                    exit_value = holdings[sym] * price
                    cash += exit_value
                    
                    entry_value = holdings[sym] * entry_price[sym]
                    pnl = exit_value - entry_value
                    pnl_pct = (pnl / entry_value) * 100
                    
                    trade_log.append({
                        'pnl_pct': pnl_pct,
                        'exit_reason': exit_reason
                    })
                    
                    holdings[sym] = 0
                    entry_price[sym] = 0
                    max_price_since_entry[sym] = 0
                    
    # Calculate final value
    final_value = cash
    for sym in symbols:
        if holdings[sym] > 0:
            try:
                final_price = indicators[sym].iloc[-1]['Close']
                final_value += holdings[sym] * final_price
            except:
                pass
                
    # Calculate metrics
    total_return = ((final_value - initial_capital) / initial_capital) * 100
    
    if trade_log:
        df_trades = pd.DataFrame(trade_log)
        num_trades = len(df_trades)
        winning_trades = df_trades[df_trades['pnl_pct'] > 0]
        win_rate = (len(winning_trades) / num_trades) * 100 if num_trades > 0 else 0
        avg_win = winning_trades['pnl_pct'].mean() if len(winning_trades) > 0 else 0
        avg_loss = df_trades[df_trades['pnl_pct'] <= 0]['pnl_pct'].mean() if len(df_trades[df_trades['pnl_pct'] <= 0]) > 0 else 0
    else:
        num_trades = 0
        win_rate = 0
        avg_win = 0
        avg_loss = 0
        
    return {
        'Strategy': strategy_name,
        'Total_Return_%': total_return,
        'Num_Trades': num_trades,
        'Win_Rate_%': win_rate,
        'Avg_Win_%': avg_win,
        'Avg_Loss_%': avg_loss,
        'Final_Value': final_value
    }


def compare_strategies(data, symbols):
    """Compare all strategies"""
    
    print("\n" + "="*80)
    print("🥊 STRATEGY BATTLE ROYALE - Finding the Best Indicator!")
    print("="*80)
    
    strategies = [
        (lambda df: calculate_sma_signals(df, 5, 20), "SMA 5/20 (Baseline)"),
        (lambda df: calculate_sma_signals(df, 10, 50), "SMA 10/50 (Traditional)"),
        (lambda df: calculate_sma_signals(df, 15, 60), "SMA 15/60 (Conservative)"),
        (calculate_ema_signals, "EMA 5/20"),
        (lambda df: calculate_ema_signals(df, 10, 50), "EMA 10/50"),
        (calculate_macd_signals, "MACD (12,26,9)"),
        (calculate_rsi_signals, "RSI (14) Oversold/Overbought"),
        (calculate_bbands_rsi_signals, "Bollinger Bands + RSI"),
        (calculate_ema_macd_signals, "EMA + MACD Combo"),
        (calculate_supertrend_signals, "Supertrend (10,3)"),
        (lambda df: calculate_supertrend_signals(df, 7, 2), "Supertrend (7,2) Sensitive"),
        (calculate_ichimoku_signals, "Ichimoku Cloud"),
    ]
    
    results = []
    
    for i, (strategy_func, strategy_name) in enumerate(strategies):
        print(f"\n[{i+1}/{len(strategies)}] Testing: {strategy_name}...")
        result = run_backtest(data, symbols, strategy_func, strategy_name)
        results.append(result)
        print(f"   Return: {result['Total_Return_%']:.2f}% | Trades: {result['Num_Trades']} | Win Rate: {result['Win_Rate_%']:.1f}%")
        
    # Sort by total return
    df_results = pd.DataFrame(results)
    df_results = df_results.sort_values(by='Total_Return_%', ascending=False)
    
    # Print results
    print("\n" + "="*80)
    print("🏆 FINAL RESULTS - Ranked by Total Return")
    print("="*80)
    print(df_results.to_string(index=False))
    
    # Save to CSV
    df_results.to_csv('strategy_comparison.csv', index=False)
    print("\n💾 Results saved to: strategy_comparison.csv")
    
    # Analysis
    print("\n" + "="*80)
    print("📊 ANALYSIS & RECOMMENDATIONS")
    print("="*80)
    
    best = df_results.iloc[0]
    worst = df_results.iloc[-1]
    
    print(f"\n🥇 WINNER: {best['Strategy']}")
    print(f"   - Total Return: {best['Total_Return_%']:.2f}%")
    print(f"   - Win Rate: {best['Win_Rate_%']:.1f}%")
    print(f"   - Avg Win: {best['Avg_Win_%']:.2f}%")
    print(f"   - Number of Trades: {best['Num_Trades']}")
    
    print(f"\n🥈 2nd Place: {df_results.iloc[1]['Strategy']} ({df_results.iloc[1]['Total_Return_%']:.2f}%)")
    print(f"🥉 3rd Place: {df_results.iloc[2]['Strategy']} ({df_results.iloc[2]['Total_Return_%']:.2f}%)")
    
    print(f"\n⚠️ WORST: {worst['Strategy']} ({worst['Total_Return_%']:.2f}%)")
    
    # Insights
    print("\n💡 KEY INSIGHTS:")
    
    trend_followers = df_results[df_results['Strategy'].str.contains('SMA|EMA|MACD')]
    mean_reversion = df_results[df_results['Strategy'].str.contains('RSI|Bollinger')]
    
    if not trend_followers.empty:
        best_trend = trend_followers.iloc[0]
        print(f"\n   📈 Best Trend-Following: {best_trend['Strategy']} ({best_trend['Total_Return_%']:.2f}%)")
        
    if not mean_reversion.empty:
        best_mean = mean_reversion.iloc[0]
        print(f"   🔄 Best Mean-Reversion: {best_mean['Strategy']} ({best_mean['Total_Return_%']:.2f}%)")
        
    print("\n   🎯 Takeaway:")
    if best['Total_Return_%'] > 150:
        print(f"      Your winner ({best['Strategy']}) is EXCELLENT for this portfolio!")
        print(f"      Consider using it for your live trading bot.")
    elif best['Total_Return_%'] > 100:
        print(f"      Your winner ({best['Strategy']}) is GOOD but could be better.")
    else:
        print(f"      All strategies underperformed. Consider:")
        print(f"      - Different parameter tuning")
        print(f"      - Portfolio selection")
        print(f"      - Market conditions weren't ideal for technical strategies")


if __name__ == "__main__":
    data, symbols = load_data()
    if not data:
        print("❌ No data to backtest.")
        sys.exit()
        
    compare_strategies(data, symbols)
