"""
Bollinger Bands + RSI Strategy (Mean Reversion)
Best for: Bear Markets, Sideways Markets, Defensive Mode
Performance: +30% in Bear, +2% in 2022 Bear (vs -12% for SMA)
Win Rate: ~41%
"""

import pandas as pd
import numpy as np


class BollingerRSI:
    def __init__(self, params):
        self.bb_period = params.get("bb_period", 20)
        self.bb_std = params.get("bb_std", 2)
        self.rsi_period = params.get("rsi_period", 14)
        self.rsi_oversold = params.get("rsi_oversold", 40)
        self.rsi_overbought = params.get("rsi_overbought", 60)
        self.stop_loss_pct = params.get("stop_loss_pct", 0.05)
        self.take_profit_pct = params.get("take_profit_pct", 0.0)
        self.trailing_stop_activation_pct = params.get("trailing_stop_activation_pct", 0.50)
        self.trailing_stop_pct = params.get("trailing_stop_pct", 0.05)

    def generate_signals(self, df, current_cost=0):
        """
        Generate buy/sell signals based on Bollinger Bands + RSI
        
        Entry: Price touches lower BB AND RSI oversold (mean reversion)
        Exit: Price touches upper BB AND RSI overbought OR Stop Loss
        """
        df = df.copy()

        # Calculate Bollinger Bands
        df['SMA'] = df['close'].rolling(window=self.bb_period).mean()
        df['BB_Std'] = df['close'].rolling(window=self.bb_period).std()
        df['BB_Upper'] = df['SMA'] + (self.bb_std * df['BB_Std'])
        df['BB_Lower'] = df['SMA'] - (self.bb_std * df['BB_Std'])
        df['BB_Middle'] = df['SMA']

        # Calculate RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))

        # Initialize signals
        df["Position"] = 0
        df["Status_Text"] = ""

        # Generate signals
        for i in range(1, len(df)):
            close = df['close'].iloc[i]
            bb_upper = df['BB_Upper'].iloc[i]
            bb_lower = df['BB_Lower'].iloc[i]
            bb_middle = df['BB_Middle'].iloc[i]
            rsi = df['RSI'].iloc[i]

            # BUY Signal: Price near lower band AND RSI oversold
            if close <= bb_lower and rsi < self.rsi_oversold:
                df.loc[df.index[i], "Position"] = 2
                df.loc[df.index[i], "Status_Text"] = f"BB+RSI Buy (Oversold RSI={rsi:.0f})"

            # SELL Signal: Price near upper band AND RSI overbought
            elif close >= bb_upper and rsi > self.rsi_overbought:
                df.loc[df.index[i], "Position"] = -2
                df.loc[df.index[i], "Status_Text"] = f"BB+RSI Sell (Overbought RSI={rsi:.0f})"

            # Hold signals
            elif close < bb_middle and rsi < 50:
                df.loc[df.index[i], "Status_Text"] = f"Below BB Mid (RSI={rsi:.0f})"
            elif close > bb_middle and rsi > 50:
                df.loc[df.index[i], "Status_Text"] = f"Above BB Mid (RSI={rsi:.0f})"
            else:
                df.loc[df.index[i], "Status_Text"] = f"Neutral (RSI={rsi:.0f})"

        # Stop Loss check
        if current_cost > 0:
            latest_price = df["close"].iloc[-1]
            pct_change = (latest_price - current_cost) / current_cost
            
            if pct_change <= -self.stop_loss_pct:
                df.loc[df.index[-1], "Position"] = -2
                df.loc[df.index[-1], "Status_Text"] = f"Stop Loss (-{self.stop_loss_pct*100:.0f}%)"

        return df
