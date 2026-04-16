import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from datetime import datetime
import json
import os
import sys

# ---------------------------------------------------------
# เพิ่ม Path เพื่อเรียก Module Strategies/Utils ได้
# ---------------------------------------------------------
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from strategies.ema_cross import EMACrossover


class Backtester:
    def __init__(
        self,
        strategy_class,
        symbol="PTT.BK",
        initial_capital=100000,
        start_date="2023-01-01",
        end_date="2023-12-31",
    ):
        self.strategy_class = strategy_class
        self.symbol = symbol
        self.initial_capital = initial_capital
        self.cash = initial_capital
        self.holdings = 0
        self.cost_basis = 0
        self.trade_log = []
        self.equity_curve = []
        self.dates = []
        self.start_date = start_date
        self.end_date = end_date

        # Load Config
        try:
            with open("config.json", "r") as f:
                self.config = json.load(f)["strategies"].get("EMACrossover", {})
        except FileNotFoundError:
            self.config = {}

    def run(self):
        print(
            f"📥 กำลังดึงข้อมูล {self.symbol} จาก Yahoo Finance ({self.start_date} - {self.end_date})..."
        )
        df = yf.download(self.symbol, start=self.start_date, end=self.end_date)

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)

        # แปลงชื่อ Column ให้ตรงกับ Strategy (Yahoo Finance: 'Close' -> 'close')
        df.columns = df.columns.str.lower()
        if "date" not in df.columns:
            df.reset_index(inplace=True)
            df.rename(columns={"Date": "time"}, inplace=True)
            df.set_index("time", inplace=True)

        print(f"✅ ได้ข้อมูลมาทั้งหมด {len(df)} วันทำการ")

        strategy = self.strategy_class(self.config)

        # Loop Backtest (Simulate passing time)
        print("🔄 เริ่มต้นการ Backtest...")

        # ต้อง Pre-calculate indicators เพื่อความเร็ว (ถ้าทำได้)
        # แต่เพื่อความแม่นยำสูงสุด ให้ Loop ทีละวันเสมือนจริง

        # หมายเหตุ: การ Loop DataFrame ช้าหน่อย แต่ชัวร์เรื่อง Logic (Look-ahead Bias Prevention)
        # เราจะส่ง Window เล็กๆ เข้าไป แต่เพื่อความง่าย เราส่ง DF ทั้งหมดไปก่อน แล้วตัด Logic เอา
        # แต่เดี๋ยวก่อน! Strategies เราเขียนแบบ vectorized ไว้แล้ว (df['Signal'])
        # ดังนั้น เราควร Run Strategy ครั้งเดียวก่อน เพื่อเอา Signal ดิบมา
        # แล้วค่อย Loop Risk Management Logic ตาม index

        full_df = strategy.generate_signals(
            df.copy(), current_cost=0
        )  # Pre-calculate vectorized part

        print(
            "DEBUG: Non-zero Position events:\n",
            full_df[full_df["Position"] != 0][
                ["close", "EMA_Fast", "EMA_Slow", "Position"]
            ],
        )

        for i in range(len(full_df)):
            # จำลองข้อมูล ณ วันนั้น (Current Slice)
            current_bar = full_df.iloc[i]
            current_price = current_bar["close"]
            current_date = full_df.index[i]

            # ตรวจสอบ Signal จาก Strategy (Vectorized Part)
            signal = 0
            # Strategy ของเราให้ Signal 1/-1 ตอน Cross, แล้ว 0 ตอน Hold
            # แต่ Position Column เป็น Diff ดังนั้น:
            # 2 = Buy (1 - (-1) or 1 - 0 invalid logic here check sma_cross.py)
            # sma_cross.py Compute:
            # Signal = 1 (Fast > Slow), -1 (Fast < Slow)
            # Position = Signal.diff() -> 2 (Button -1 -> 1), -2 (Top 1 -> -1)

            raw_position = current_bar["Position"]

            # --- Simulation Logic ---

            action = None

            # 1. Check Exit Logic (Stop Loss / Take Profit)
            # Logic นี้ต้อง manual เพราะมันขึ้นอยู่กับ 'current_cost' ซึ่งเปลี่ยนไปตามการซื้อขายจริง
            # เราต้อง replicate logic จาก bot.py มาใส่ตรงนี้ หรือปรับ Strategy ให้ return logic นี้มา

            # เพื่อความง่ายและแม่นยำ เราจะใช้ค่าที่ Strategy คำนวณมา 'ไม่ได้' 100%
            # เพราะ Strategy.generate_signals ในโหมดปกติ มันคำนวณ based on 'current_cost' ที่ส่งเข้าไป
            # ซึ่งใน Vectorized run ครั้งแรก current_cost = 0 ตลอด

            # *** วิธีที่ถูกคือต้อง Re-run generate_signals โดยส่ง current_cost เข้าไปใน loop ทุกครั้ง ***
            # แต่มันจะช้ามาก (O(N^2))
            # ทางแก้: เราจะ Manual Implement Risk Logic ตรงนี้เลียนแบบ Strategy

            sl_pct = self.config.get("stop_loss_pct", 0.05)
            tp_pct = self.config.get("take_profit_pct", 0.10)

            forced_sell = False

            if self.holdings > 0:
                # Check Stop Loss / Take Profit
                if current_price <= self.cost_basis * (1 - sl_pct):
                    action = "SELL (Stop Loss)"
                    forced_sell = True
                elif current_price >= self.cost_basis * (1 + tp_pct):
                    action = "SELL (Take Profit)"
                    forced_sell = True

            # 2. Check Standard Strategy Signal (ถ้ายังไม่ได้ขายจาก Risk Logic)
            if not forced_sell:
                if raw_position >= 1:  # Golden Cross (Buy) or Trend Start
                    if self.holdings == 0:
                        action = "BUY"
                elif raw_position <= -1:  # Death Cross (Sell) or Trend End
                    if self.holdings > 0:
                        action = "SELL"

            # if raw_position != 0 and not pd.isna(raw_position):
            #     print(
            #         f"DEBUG: {current_date.date()} Position={raw_position} Holdings={self.holdings} Action={action}"
            #     )

            # --- Execution ---
            if action == "BUY":
                # ซื้อหมดตัว (All-in)
                # คำนวณจำนวนหุ้นที่ซื้อได้โดยหักค่าคอมมิชชั่นแล้ว
                commission_rate = 0.00168
                shares_to_buy = int(self.cash / (current_price * (1 + commission_rate)))

                if shares_to_buy > 0:
                    cost = shares_to_buy * current_price
                    commission = cost * commission_rate
                    total_cost = cost + commission

                    if self.cash >= total_cost:
                        self.cash -= total_cost
                        self.holdings += shares_to_buy
                        self.cost_basis = current_price
                        self.trade_log.append(
                            {
                                "Date": current_date,
                                "Action": "BUY",
                                "Price": current_price,
                                "Shares": shares_to_buy,
                                "Value": total_cost,
                                "Balance": self.cash,
                            }
                        )
                        # print(f"🟢 {current_date.date()} BUY  @ {current_price:.2f}")

            elif action and "SELL" in action:
                if self.holdings > 0:
                    revenue = self.holdings * current_price
                    commission = revenue * 0.00168
                    net_revenue = revenue - commission

                    # Profit/Loss
                    pnl = net_revenue - (self.holdings * self.cost_basis)

                    self.cash += net_revenue
                    self.holdings = 0
                    self.cost_basis = 0

                    self.trade_log.append(
                        {
                            "Date": current_date,
                            "Action": action,
                            "Price": current_price,
                            "Shares": 0,
                            "Value": net_revenue,
                            "Balance": self.cash,
                            "PnL": pnl,
                        }
                    )
                    print(
                        f"🔴 {current_date.date()} {action} @ {current_price:.2f} | PnL: {pnl:.2f}"
                    )

            # Update Equity Curve
            equity = self.cash + (self.holdings * current_price)
            self.equity_curve.append(equity)
            self.dates.append(current_date)

    def stats(self):
        total_return = (
            (self.equity_curve[-1] - self.initial_capital) / self.initial_capital
        ) * 100
        print("\n" + "=" * 40)
        print(f"📊 สรุปผลการทดสอบ ({self.symbol})")
        print("=" * 40)
        print(f"💰 เงินเริ่มต้น: {self.initial_capital:,.2f}")
        print(f"💸 เงินสุดท้าย:  {self.equity_curve[-1]:,.2f}")
        print(f"📈 กำไรขาดทุน:  {total_return:.2f}%")
        print(f"📝 จำนวนเทรด:   {len(self.trade_log)}")
        print("=" * 40)

        # Show trade logs
        df_log = pd.DataFrame(self.trade_log)
        if not df_log.empty:
            print(df_log[["Date", "Action", "Price", "PnL"]].tail(10))

    def plot(self):
        plt.figure(figsize=(12, 6))
        plt.plot(self.dates, self.equity_curve, label="Portfolio Equity")
        plt.title(f"Backtest Result: {self.symbol}")
        plt.xlabel("Date")
        plt.ylabel("Portfolio Value (THB)")
        plt.legend()
        plt.grid(True)
        # plt.show()


if __name__ == "__main__":
    backtester = Backtester(
        EMACrossover, symbol="PTT.BK", start_date="2022-01-01", end_date="2023-12-31"
    )
    backtester.run()
    backtester.stats()
    # backtester.plot()
