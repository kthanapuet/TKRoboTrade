# 🤖 TK Robo Trade

**Automated Trading Bot for Global Growth Stocks**  
*Developed by Thanapuet Kaewmanee (TK)*

---

## 📊 Overview

TK Robo Trade is a quantitative trading system that uses **SMA Crossover** with **Trailing Stop** strategies to trade a portfolio of 10 global growth stocks through **PI Securities** (Settrade API).

**Key Features:**
- ✅ **Momentum-Based Entry:** Fast SMA (5) / Slow SMA (20) crossover
- ✅ **Smart Risk Management:** 5% Stop Loss + 50% Trailing Activation
- ✅ **Multi-Stock Portfolio:** Automated trading for 10 stocks
- ✅ **Real-time Monitoring:** Line Notify alerts + Daily summaries
- ✅ **Backtested & Optimized:** +200% return on 5-year historical data

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Keys
Edit `.env` file:
```env
APP_ID=your_app_id
APP_SECRET=your_app_secret
BROKER_ID=PI
APP_CODE=your_app_code
ACCOUNT_NO=your_account_number
PIN=your_pin
LINE_TOKEN=your_line_notify_token
```

### 3. Run the Bot
```bash
python bot.py
```

---

## 📂 Project Structure

```
TKRoboTrade/
├── bot.py                    # Main trading bot
├── config.json               # Strategy parameters
├── .env                      # API credentials (DO NOT COMMIT)
├── requirements.txt          # Python dependencies
│
├── strategies/               # Trading strategies
│   ├── base.py              # Base strategy class
│   └── sma_cross.py         # SMA Crossover strategy
│
├── utils/                    # Utilities
│   └── notifier.py          # Line Notify integration
│
└── backtests/               # Testing & Optimization
    ├── optimize_portfolio.py      # Grid search optimization
    ├── backtest_portfolio.py      # Portfolio backtesting
    ├── test_bot_cycle.py          # Bot cycle testing
    └── optimization_results.csv   # Latest optimization results
```

---

## 📈 Strategy Details

### SMA Crossover (Optimized)
- **Entry:** Fast SMA (5) crosses above Slow SMA (20)
- **Exit Conditions:**
  1. Fast SMA crosses below Slow SMA
  2. Stop Loss: -5%
  3. Trailing Stop: Activates at +50% profit, exits on -5% drawdown from peak

### Portfolio Allocation
- **10 Global Growth Stocks** (10% each):
  - NVDA80.BK, MSFT80.BK, GOOG80.BK, NDX01.BK, AAPL80.BK
  - TSLA80.BK, E1VFVN3001.BK, SIRI.BK, TRUE.BK, WHA.BK

---

## 🧪 Backtesting & Optimization

Run optimization to find best parameters:
```bash
python backtests/optimize_portfolio.py
```

**Latest Results (2018-2023):**
- **Best Return:** +200.36% (40% annualized)
- **Best Config:** SMA 5/20, Stop Loss 5%, Trailing 50%/5%

---

## 🔔 Monitoring

The bot sends notifications via **Line Notify**:
- ✅ Buy/Sell signals
- ✅ Hourly heartbeat (market hours)
- ✅ Daily portfolio summary
- ⚠️ Error alerts

---

## ⚙️ Configuration

Edit `config.json` to customize:
- Strategy parameters (SMA windows, stop loss, trailing stop)
- Portfolio stocks and allocation
- Strategy overrides (per-stock customization)

---

## 📜 License

Personal project by Thanapuet Kaewmanee (TK)

---

## 🛠️ Tech Stack

- **Language:** Python 3.10+
- **Broker API:** Settrade (PI Securities)
- **Libraries:** `settrade-v2`, `pandas`, `yfinance`, `python-dotenv`
- **Notifications:** Line Notify

---

**Happy Trading! 📈🤖**
