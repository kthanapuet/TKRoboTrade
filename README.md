# 🤖 TK Robo Trade

**Automated Trading Bot for Global Growth Stocks**  
*Developed by Thanapuet Kaewmanee (TK)*

---

## 📊 Overview

TK Robo Trade is a quantitative trading system that uses **SMA Crossover** with **Trailing Stop** strategies to trade a portfolio of 10 global growth stocks through **PI Securities** (Settrade API).

**Key Features:**
- ✅ **Momentum-Based Entry:** Fast EMA (5) / Slow EMA (20) crossover (Default)
- ✅ **Web Dashboard UI:** Local web app to manage portfolio dynamically with Auto-Validation.
- ✅ **Universal Notifications:** Supports LINE, Telegram, and Discord Webhook alerts.
- ✅ **Smart Risk Management:** 5% Stop Loss + 50% Trailing Activation
- ✅ **Multi-Stock Portfolio:** Automated trading for 10+ stocks

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

### 4. Manage Portfolio (Web UI)
Launch the local dashboard to add, validate (YFinance), or delete stocks:
```bash
python api_server.py
```
👉 Open **http://localhost:5000** in your web browser.

---

## 📂 Project Structure

```text
TKRoboTrade/
├── bot.py                    # Main trading bot
├── api_server.py             # Dashboard API Backend (Flask/HTTP)
├── dashboard.html            # Web UI for Portfolio Management
├── config.json               # Strategy & Portfolio parameters
├── .env                      # API credentials (DO NOT COMMIT)
├── requirements.txt          # Python dependencies
│
├── strategies/               # Trading strategies
│   ├── base.py              # Base strategy class
│   ├── ema_cross.py         # EMA Crossover strategy (Default)
│   └── sma_cross.py         # SMA Crossover strategy 
│
├── utils/                    # Utilities
│   └── notifier.py          # Telegram, Discord, and LINE integration
│
└── backtests/               # Testing & Optimization
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

The bot sends notifications across your preferred platform (**Telegram, Discord, or LINE**):
- ✅ Trading Operations (Buy/Sell signals)
- ✅ Portfolio updates from Dashboard (Add/Delete/Toggle stocks)
- ✅ Hourly heartbeat (market hours) & Daily summary
- ⚠️ Error alerts

To setup, just add these to your `.env`:
```env
# Telegram
TELEGRAM_BOT_TOKEN="your_token"
TELEGRAM_CHAT_ID="your_chat_id"

# Discord
DISCORD_WEBHOOK_URL="your_webhook_url"
```

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
