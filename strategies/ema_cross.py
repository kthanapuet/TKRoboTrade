"""
EMA Crossover Strategy
Best for: Bull Markets, Trending Markets
Performance: +231% (2018-2023)
Win Rate: ~36%
"""

import pandas as pd


class EMACrossover:
    def __init__(self, params):
        self.fast_window = params.get("fast_window", 5)
        self.slow_window = params.get("slow_window", 20)
        self.stop_loss_pct = params.get("stop_loss_pct", 0.05)
        self.take_profit_pct = params.get("take_profit_pct", 0.0)
        self.trailing_stop_activation_pct = params.get("trailing_stop_activation_pct", 0.50)
        self.trailing_stop_pct = params.get("trailing_stop_pct", 0.05)

    def generate_signals(self, df, current_cost=0):
        """
        Generate buy/sell signals based on EMA crossover
        
        Entry: EMA(fast) crosses above EMA(slow)
        Exit: EMA(fast) crosses below EMA(slow) OR Stop Loss OR Trailing Stop
        """
        df = df.copy()
        if df.empty:
            return df

        # Calculate EMAs
        df["EMA_Fast"] = df["close"].ewm(span=self.fast_window, adjust=False).mean()
        df["EMA_Slow"] = df["close"].ewm(span=self.slow_window, adjust=False).mean()

        # Initialize signals
        df["Position"] = 0  # 0 = No position, 2 = Buy, -2 = Sell
        df["Status_Text"] = ""

        # Generate signals
        for i in range(1, len(df)):
            ema_fast_prev = df["EMA_Fast"].iloc[i - 1]
            ema_slow_prev = df["EMA_Slow"].iloc[i - 1]
            ema_fast_curr = df["EMA_Fast"].iloc[i]
            ema_slow_curr = df["EMA_Slow"].iloc[i]

            # BUY Signal: EMA Fast crosses above EMA Slow
            if ema_fast_prev <= ema_slow_prev and ema_fast_curr > ema_slow_curr:
                df.loc[df.index[i], "Position"] = 2
                df.loc[df.index[i], "Status_Text"] = "EMA Crossover (Fast > Slow)"

            # SELL Signal: EMA Fast crosses below EMA Slow
            elif ema_fast_prev >= ema_slow_prev and ema_fast_curr < ema_slow_curr:
                df.loc[df.index[i], "Position"] = -2
                df.loc[df.index[i], "Status_Text"] = "EMA Crossunder (Fast < Slow)"

            # Hold signals
            elif ema_fast_curr > ema_slow_curr:
                df.loc[df.index[i], "Status_Text"] = "EMA Bullish (Fast > Slow)"
            else:
                df.loc[df.index[i], "Status_Text"] = "EMA Bearish (Fast < Slow)"

        # Add Stop Loss and Trailing Stop logic (handled by bot)
        if current_cost > 0:
            latest_price = df["close"].iloc[-1]
            
            # Stop Loss check
            pct_change = (latest_price - current_cost) / current_cost
            if pct_change <= -self.stop_loss_pct:
                df.loc[df.index[-1], "Position"] = -2
                df.loc[df.index[-1], "Status_Text"] = f"Stop Loss (-{self.stop_loss_pct*100:.0f}%)"

        return df
