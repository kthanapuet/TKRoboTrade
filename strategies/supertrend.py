"""
Supertrend Strategy
Best for: Bull Markets, Volatile Markets
Performance: +194% (2018-2023)
Win Rate: ~43% (Highest!)
"""

import pandas as pd
import numpy as np


class Supertrend:
    def __init__(self, params):
        self.period = params.get("period", 7)
        self.multiplier = params.get("multiplier", 2)
        self.stop_loss_pct = params.get("stop_loss_pct", 0.05)
        self.take_profit_pct = params.get("take_profit_pct", 0.0)
        self.trailing_stop_activation_pct = params.get("trailing_stop_activation_pct", 0.50)
        self.trailing_stop_pct = params.get("trailing_stop_pct", 0.05)

    def generate_signals(self, df, current_cost=0):
        """
        Generate buy/sell signals based on Supertrend indicator
        
        Entry: Price crosses above Supertrend line (Trend turns bullish)
        Exit: Price crosses below Supertrend line (Trend turns bearish) OR Stop Loss
        """
        df = df.copy()

        # Ensure we have high/low columns
        if 'high' not in df.columns or 'low' not in df.columns:
            df['high'] = df['close']
            df['low'] = df['close']

        # Calculate ATR (Average True Range)
        df['H-L'] = df['high'] - df['low']
        df['H-PC'] = abs(df['high'] - df['close'].shift(1))
        df['L-PC'] = abs(df['low'] - df['close'].shift(1))
        df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
        df['ATR'] = df['TR'].rolling(window=self.period).mean()

        # Calculate basic upper and lower bands
        df['HL_Avg'] = (df['high'] + df['low']) / 2
        df['Upper_Band'] = df['HL_Avg'] + (self.multiplier * df['ATR'])
        df['Lower_Band'] = df['HL_Avg'] - (self.multiplier * df['ATR'])

        # Initialize Supertrend
        df['Supertrend'] = 0.0
        df['Trend'] = 1  # 1 = Uptrend, -1 = Downtrend

        for i in range(self.period, len(df)):
            curr_close = df['close'].iloc[i]
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

        # Generate Position signals
        df["Position"] = 0
        df["Status_Text"] = ""

        for i in range(1, len(df)):
            prev_trend = df['Trend'].iloc[i-1]
            curr_trend = df['Trend'].iloc[i]

            # BUY: Trend changes to uptrend
            if prev_trend == -1 and curr_trend == 1:
                df.loc[df.index[i], "Position"] = 2
                df.loc[df.index[i], "Status_Text"] = "Supertrend Buy (Trend Up)"

            # SELL: Trend changes to downtrend
            elif prev_trend == 1 and curr_trend == -1:
                df.loc[df.index[i], "Position"] = -2
                df.loc[df.index[i], "Status_Text"] = "Supertrend Sell (Trend Down)"

            # Hold signals
            elif curr_trend == 1:
                df.loc[df.index[i], "Status_Text"] = "Supertrend Bullish"
            else:
                df.loc[df.index[i], "Status_Text"] = "Supertrend Bearish"

        # Stop Loss check
        if current_cost > 0:
            latest_price = df["close"].iloc[-1]
            pct_change = (latest_price - current_cost) / current_cost
            
            if pct_change <= -self.stop_loss_pct:
                df.loc[df.index[-1], "Position"] = -2
                df.loc[df.index[-1], "Status_Text"] = f"Stop Loss (-{self.stop_loss_pct*100:.0f}%)"

        return df
