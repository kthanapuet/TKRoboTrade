import pandas as pd
from .base import BaseStrategy


class SMACrossover(BaseStrategy):
    def generate_signals(
        self, df: pd.DataFrame, current_cost: float = 0.0
    ) -> pd.DataFrame:
        if df.empty:
            return df
        fast = self.config.get("fast_window", 15)
        slow = self.config.get("slow_window", 50)
        sl_pct = self.config.get("stop_loss_pct", 0.05)
        tp_pct = self.config.get("take_profit_pct", 0.10)

        df[f"SMA_{fast}"] = df["close"].rolling(window=fast).mean()
        df[f"SMA_{slow}"] = df["close"].rolling(window=slow).mean()

        df["Signal"] = 0
        df.loc[df[f"SMA_{fast}"] > df[f"SMA_{slow}"], "Signal"] = 1
        df.loc[df[f"SMA_{fast}"] < df[f"SMA_{slow}"], "Signal"] = -1
        df["Position"] = df["Signal"].diff()

        df["Status_Text"] = (
            f"SMA{fast}: "
            + df[f"SMA_{fast}"].round(2).astype(str)
            + f" | SMA{slow}: "
            + df[f"SMA_{slow}"].round(2).astype(str)
        )

        # ---------------------------------------------------------
        # RISK MANAGEMENT LOGIC (เช็คเฉพาะแท่งล่าสุด)
        # ---------------------------------------------------------
        if current_cost > 0:
            latest_close = df["close"].iloc[-1]

            # เช็ค Stop Loss
            if latest_close <= current_cost * (1 - sl_pct):
                df.iloc[-1, df.columns.get_loc("Position")] = -2
                df.iloc[-1, df.columns.get_loc("Status_Text")] = (
                    f"⚠️ [STOP LOSS ทะลุ {-sl_pct * 100}%] ทุน: {current_cost}"
                )

            # เช็ค Take Profit
            elif latest_close >= current_cost * (1 + tp_pct):
                df.iloc[-1, df.columns.get_loc("Position")] = -2
                df.iloc[-1, df.columns.get_loc("Status_Text")] = (
                    f"🎯 [TAKE PROFIT ทะลุ {tp_pct * 100}%] ทุน: {current_cost}"
                )

        return df
