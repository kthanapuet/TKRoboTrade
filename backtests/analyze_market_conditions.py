"""
Market Condition Analysis & Adaptive Strategy Selector
Analyze market conditions (Bull/Bear/Sideways) and find best strategy for each
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
    end_date = "2024-01-01"
    
    for th_symbol, yf_symbol in SYMBOL_MAP.items():
        try:
            df = yf.download(yf_symbol, start=start_date, end=end_date, progress=False, auto_adjust=True)
            
            if df.empty:
                continue
                
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.droplevel(1)
                
            df.columns = [c.lower() for c in df.columns]
            
            if 'close' in df.columns:
                df.rename(columns={'close': 'Close'}, inplace=True)
                data_store[th_symbol] = df
                valid_symbols.append(th_symbol)
                
        except:
            pass
            
    # Common dates
    common_index = data_store[valid_symbols[0]].index
    for sym in valid_symbols[1:]:
        common_index = common_index.intersection(data_store[sym].index)
        
    for sym in valid_symbols:
        data_store[sym] = data_store[sym].loc[common_index]
        
    print(f"✅ Data Loaded: {len(valid_symbols)} stocks, {len(common_index)} days.")
    return data_store, valid_symbols


def classify_market_condition(data_store, symbols):
    """Classify market condition for each year"""
    
    print("\n" + "="*80)
    print("📊 MARKET CONDITION ANALYSIS (2018-2023)")
    print("="*80)
    
    years = [2018, 2019, 2020, 2021, 2022, 2023]
    market_conditions = {}
    
    for year in years:
        # Calculate average portfolio performance for the year
        year_returns = []
        volatilities = []
        
        for sym in symbols:
            df = data_store[sym]
            year_data = df[df.index.year == year]
            
            if len(year_data) < 10:
                continue
                
            # Calculate return
            start_price = year_data['Close'].iloc[0]
            end_price = year_data['Close'].iloc[-1]
            year_return = ((end_price - start_price) / start_price) * 100
            year_returns.append(year_return)
            
            # Calculate volatility (std of daily returns)
            daily_returns = year_data['Close'].pct_change().dropna()
            volatility = daily_returns.std() * np.sqrt(252) * 100  # Annualized
            volatilities.append(volatility)
            
        avg_return = np.mean(year_returns)
        avg_volatility = np.mean(volatilities)
        
        # Classify market condition
        if avg_return > 15 and avg_volatility < 40:
            condition = "BULL (Strong Uptrend)"
            emoji = "🐂"
        elif avg_return > 5 and avg_volatility < 40:
            condition = "BULL (Moderate Uptrend)"
            emoji = "📈"
        elif avg_return < -10:
            condition = "BEAR (Downtrend)"
            emoji = "🐻"
        elif abs(avg_return) <= 10 and avg_volatility < 30:
            condition = "SIDEWAYS (Range-bound)"
            emoji = "↔️"
        elif avg_volatility > 50:
            condition = "VOLATILE (Choppy)"
            emoji = "⚡"
        else:
            condition = "MIXED"
            emoji = "🔀"
            
        market_conditions[year] = {
            'condition': condition,
            'return': avg_return,
            'volatility': avg_volatility,
            'emoji': emoji
        }
        
        print(f"\n{emoji} {year}: {condition}")
        print(f"   Return: {avg_return:+.2f}%")
        print(f"   Volatility: {avg_volatility:.2f}%")
        
    return market_conditions


def calculate_sma_signals(df, fast=5, slow=20):
    """SMA Crossover"""
    df = df.copy()
    df['SMA_Fast'] = df['Close'].rolling(window=fast).mean()
    df['SMA_Slow'] = df['Close'].rolling(window=slow).mean()
    df['Signal'] = 0
    df.loc[df['SMA_Fast'] > df['SMA_Slow'], 'Signal'] = 1
    df.loc[df['SMA_Fast'] < df['SMA_Slow'], 'Signal'] = -1
    return df


def calculate_ema_signals(df, fast=5, slow=20):
    """EMA Crossover"""
    df = df.copy()
    df['EMA_Fast'] = df['Close'].ewm(span=fast, adjust=False).mean()
    df['EMA_Slow'] = df['Close'].ewm(span=slow, adjust=False).mean()
    df['Signal'] = 0
    df.loc[df['EMA_Fast'] > df['EMA_Slow'], 'Signal'] = 1
    df.loc[df['EMA_Fast'] < df['EMA_Slow'], 'Signal'] = -1
    return df


def calculate_supertrend_signals(df, period=7, multiplier=2):
    """Supertrend"""
    df = df.copy()
    
    if 'high' not in df.columns or 'low' not in df.columns:
        df['high'] = df['Close']
        df['low'] = df['Close']
    
    df['H-L'] = df['high'] - df['low']
    df['H-PC'] = abs(df['high'] - df['Close'].shift(1))
    df['L-PC'] = abs(df['low'] - df['Close'].shift(1))
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(window=period).mean()
    
    df['HL_Avg'] = (df['high'] + df['low']) / 2
    df['Upper_Band'] = df['HL_Avg'] + (multiplier * df['ATR'])
    df['Lower_Band'] = df['HL_Avg'] - (multiplier * df['ATR'])
    
    df['Supertrend'] = 0.0
    df['Trend'] = 1
    
    for i in range(period, len(df)):
        curr_close = df['Close'].iloc[i]
        curr_upper = df['Upper_Band'].iloc[i]
        curr_lower = df['Lower_Band'].iloc[i]
        prev_supertrend = df['Supertrend'].iloc[i-1]
        prev_trend = df['Trend'].iloc[i-1]
        
        if prev_trend == 1:
            if curr_close <= prev_supertrend:
                df.loc[df.index[i], 'Supertrend'] = curr_upper
                df.loc[df.index[i], 'Trend'] = -1
            else:
                df.loc[df.index[i], 'Supertrend'] = max(curr_lower, prev_supertrend)
                df.loc[df.index[i], 'Trend'] = 1
        else:
            if curr_close >= prev_supertrend:
                df.loc[df.index[i], 'Supertrend'] = curr_lower
                df.loc[df.index[i], 'Trend'] = 1
            else:
                df.loc[df.index[i], 'Supertrend'] = min(curr_upper, prev_supertrend)
                df.loc[df.index[i], 'Trend'] = -1
    
    df['Signal'] = 0
    df.loc[df['Trend'] == 1, 'Signal'] = 1
    df.loc[df['Trend'] == -1, 'Signal'] = -1
    return df


def calculate_bbands_rsi_signals(df):
    """Bollinger Bands + RSI"""
    df = df.copy()
    
    df['SMA_20'] = df['Close'].rolling(window=20).mean()
    df['BB_Upper'] = df['SMA_20'] + 2 * df['Close'].rolling(window=20).std()
    df['BB_Lower'] = df['SMA_20'] - 2 * df['Close'].rolling(window=20).std()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    df['Signal'] = 0
    df.loc[(df['Close'] <= df['BB_Lower']) & (df['RSI'] < 40), 'Signal'] = 1
    df.loc[(df['Close'] >= df['BB_Upper']) & (df['RSI'] > 60), 'Signal'] = -1
    
    return df


def run_backtest_year(data_store, symbols, strategy_func, year):
    """Run backtest for specific year"""
    
    initial_capital = 10000.0
    cash = initial_capital
    holdings = {sym: 0 for sym in symbols}
    entry_price = {sym: 0.0 for sym in symbols}
    max_price_since_entry = {sym: 0.0 for sym in symbols}
    
    # Calculate indicators
    indicators = {}
    for sym in symbols:
        df = data_store[sym].copy()
        df = df[df.index.year == year]
        if len(df) < 50:
            continue
        df = strategy_func(df)
        indicators[sym] = df
        
    if not indicators:
        return None
        
    common_idx = indicators[list(indicators.keys())[0]].index
    
    for date in common_idx:
        current_port_value = cash
        for sym in symbols:
            if sym in indicators and date in indicators[sym].index:
                price = indicators[sym].loc[date]['Close']
                current_port_value += holdings[sym] * price
                
        for sym in symbols:
            if sym not in indicators or date not in indicators[sym].index:
                continue
                
            row = indicators[sym].loc[date]
            price = row['Close']
            signal = row.get('Signal', 0)
            
            if pd.isna(price) or pd.isna(signal):
                continue
                
            # BUY
            if holdings[sym] == 0 and signal == 1:
                target_amt = 0.10 * current_port_value
                if cash >= target_amt:
                    qty = int(target_amt / price)
                    if qty > 0:
                        cash -= qty * price
                        holdings[sym] = qty
                        entry_price[sym] = price
                        max_price_since_entry[sym] = price
                        
            # SELL
            elif holdings[sym] > 0:
                if price > max_price_since_entry[sym]:
                    max_price_since_entry[sym] = price
                    
                exit_signal = False
                
                if signal == -1:
                    exit_signal = True
                    
                pct_change = (price - entry_price[sym]) / entry_price[sym]
                if pct_change <= -STOP_LOSS:
                    exit_signal = True
                    
                profit_pct = (max_price_since_entry[sym] - entry_price[sym]) / entry_price[sym]
                if profit_pct >= TRAILING_ACTIVATION:
                    drawdown = (max_price_since_entry[sym] - price) / max_price_since_entry[sym]
                    if drawdown >= TRAILING_CALLBACK:
                        exit_signal = True
                        
                if exit_signal:
                    cash += holdings[sym] * price
                    holdings[sym] = 0
                    entry_price[sym] = 0
                    max_price_since_entry[sym] = 0
                    
    # Final value
    final_value = cash
    for sym in symbols:
        if sym in indicators and holdings[sym] > 0:
            try:
                final_price = indicators[sym].iloc[-1]['Close']
                final_value += holdings[sym] * final_price
            except:
                pass
                
    total_return = ((final_value - initial_capital) / initial_capital) * 100
    return total_return


def test_strategies_by_market_condition(data_store, symbols, market_conditions):
    """Test all strategies in different market conditions"""
    
    print("\n" + "="*80)
    print("🧪 TESTING STRATEGIES BY MARKET CONDITION")
    print("="*80)
    
    strategies = {
        'SMA 5/20': lambda df: calculate_sma_signals(df, 5, 20),
        'EMA 5/20': lambda df: calculate_ema_signals(df, 5, 20),
        'Supertrend (7,2)': lambda df: calculate_supertrend_signals(df, 7, 2),
        'BBands + RSI': calculate_bbands_rsi_signals,
    }
    
    # Group years by condition
    bull_years = [y for y, m in market_conditions.items() if 'BULL' in m['condition']]
    bear_years = [y for y, m in market_conditions.items() if 'BEAR' in m['condition']]
    sideways_years = [y for y, m in market_conditions.items() if 'SIDEWAYS' in m['condition'] or 'MIXED' in m['condition']]
    volatile_years = [y for y, m in market_conditions.items() if 'VOLATILE' in m['condition']]
    
    results = {
        'BULL Market': {},
        'BEAR Market': {},
        'SIDEWAYS Market': {},
        'VOLATILE Market': {}
    }
    
    # Test each strategy in each condition
    for strat_name, strat_func in strategies.items():
        print(f"\n📊 Testing: {strat_name}")
        
        # BULL
        if bull_years:
            bull_returns = []
            for year in bull_years:
                ret = run_backtest_year(data_store, symbols, strat_func, year)
                if ret is not None:
                    bull_returns.append(ret)
            avg_bull = np.mean(bull_returns) if bull_returns else 0
            results['BULL Market'][strat_name] = avg_bull
            print(f"   🐂 BULL: {avg_bull:+.2f}%")
            
        # BEAR
        if bear_years:
            bear_returns = []
            for year in bear_years:
                ret = run_backtest_year(data_store, symbols, strat_func, year)
                if ret is not None:
                    bear_returns.append(ret)
            avg_bear = np.mean(bear_returns) if bear_returns else 0
            results['BEAR Market'][strat_name] = avg_bear
            print(f"   🐻 BEAR: {avg_bear:+.2f}%")
            
        # SIDEWAYS
        if sideways_years:
            sideways_returns = []
            for year in sideways_years:
                ret = run_backtest_year(data_store, symbols, strat_func, year)
                if ret is not None:
                    sideways_returns.append(ret)
            avg_sideways = np.mean(sideways_returns) if sideways_returns else 0
            results['SIDEWAYS Market'][strat_name] = avg_sideways
            print(f"   ↔️  SIDEWAYS: {avg_sideways:+.2f}%")
            
        # VOLATILE
        if volatile_years:
            volatile_returns = []
            for year in volatile_years:
                ret = run_backtest_year(data_store, symbols, strat_func, year)
                if ret is not None:
                    volatile_returns.append(ret)
            avg_volatile = np.mean(volatile_returns) if volatile_returns else 0
            results['VOLATILE Market'][strat_name] = avg_volatile
            print(f"   ⚡ VOLATILE: {avg_volatile:+.2f}%")
    
    return results, bull_years, bear_years, sideways_years, volatile_years


def print_recommendations(results, bull_years, bear_years, sideways_years, volatile_years):
    """Print final recommendations"""
    
    print("\n" + "="*80)
    print("🏆 BEST STRATEGY FOR EACH MARKET CONDITION")
    print("="*80)
    
    for condition, strategies in results.items():
        if not strategies:
            continue
            
        best_strat = max(strategies, key=strategies.get)
        best_return = strategies[best_strat]
        
        # Get emoji
        if 'BULL' in condition:
            emoji = "🐂"
            years = bull_years
        elif 'BEAR' in condition:
            emoji = "🐻"
            years = bear_years
        elif 'SIDEWAYS' in condition:
            emoji = "↔️"
            years = sideways_years
        else:
            emoji = "⚡"
            years = volatile_years
            
        print(f"\n{emoji} {condition} {years if years else ''}")
        print(f"   🥇 Winner: {best_strat} ({best_return:+.2f}%)")
        
        # Show all results
        sorted_strats = sorted(strategies.items(), key=lambda x: x[1], reverse=True)
        for i, (strat, ret) in enumerate(sorted_strats[1:], 2):
            print(f"   {i}. {strat} ({ret:+.2f}%)")
            
    print("\n" + "="*80)
    print("💡 ADAPTIVE STRATEGY RECOMMENDATION")
    print("="*80)
    
    print("\n✨ Design an ADAPTIVE BOT that switches strategies based on market condition:")
    print("\n   1. Detect current market condition (Bull/Bear/Sideways)")
    print("   2. Switch to the best strategy for that condition:")
    
    for condition, strategies in results.items():
        if strategies:
            best = max(strategies, key=strategies.get)
            if 'BULL' in condition:
                print(f"      🐂 Bull Market → Use: {best}")
            elif 'BEAR' in condition:
                print(f"      🐻 Bear Market → Use: {best}")
            elif 'SIDEWAYS' in condition:
                print(f"      ↔️  Sideways → Use: {best}")
                
    print("\n   3. Re-evaluate market condition monthly")
    print("   4. Switch strategy automatically")
    
    print("\n🎯 Expected Benefits:")
    print("   ✅ Better performance in all market conditions")
    print("   ✅ Lower drawdowns during bear markets")
    print("   ✅ Maximize gains during bull markets")


if __name__ == "__main__":
    data, symbols = load_data()
    if not data:
        print("❌ No data.")
        sys.exit()
        
    # Step 1: Classify market conditions
    market_conditions = classify_market_condition(data, symbols)
    
    # Step 2: Test strategies by condition
    results, bull_y, bear_y, side_y, vol_y = test_strategies_by_market_condition(data, symbols, market_conditions)
    
    # Step 3: Print recommendations
    print_recommendations(results, bull_y, bear_y, side_y, vol_y)
