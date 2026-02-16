# 🚀 Google Cloud Platform Deployment Guide

Complete step-by-step guide to deploy TK Robo Trade on Google Cloud Free Tier

---

## **📋 Prerequisites**

- Google Account
- Credit/Debit Card (for verification, won't be charged in Free Tier)
- GitHub repository: https://github.com/kthanapuet/TKRoboTrade
- PI Securities API credentials

---

## **💰 Free Tier Details**

### **What's Free Forever:**
- 1 **e2-micro** instance (US regions only)
- 30 GB HDD storage
- 1 GB egress per month
- ~$5-7 value monthly

### **Eligible Regions (Free Tier):**
- `us-west1` (Oregon)
- `us-central1` (Iowa)
- `us-east1` (South Carolina)

⚠️ **Important:** Other regions will be charged!

---

## **🎯 Step-by-Step Deployment**

### **Step 1: Create GCP Account**

1. Go to: https://cloud.google.com/free
2. Click "Get started for free"
3. Sign in with Google Account
4. Fill in:
   - Country
   - Accept terms
   - **Add Payment Method** (Required but won't charge)
5. Verify identity
6. Complete signup

✅ You get **$300 credit** for 90 days + Always Free tier

---

### **Step 2: Create VM Instance**

#### **2.1 Navigate to Compute Engine:**
```
GCP Console → Menu (☰) → Compute Engine → VM instances
```

#### **2.2 Enable Compute Engine API:**
- First time: Click "Enable"
- Wait ~1 minute

#### **2.3 Create Instance:**

Click **"CREATE INSTANCE"**

**Configuration:**

| Setting | Value | Notes |
|:---|:---|:---|
| **Name** | `tk-robo-trade` | Any name |
| **Region** | `us-west1` | **Must be US region** |
| **Zone** | `us-west1-b` | Any zone in region |
| **Machine type** | `e2-micro` | **2 vCPU, 1 GB RAM** |
| **Boot disk** | Ubuntu 22.04 LTS | Click "Change" |
| **Size** | 30 GB | Maximum for Free Tier |
| **Firewall** | ☐ Allow HTTP<br>☐ Allow HTTPS | No need |

**Advanced Options → Security:**
- Add SSH key (optional but recommended)

Click **"CREATE"** (bottom of page)

⏱️ Wait ~30 seconds for VM to start

---

### **Step 3: Connect to VM**

#### **3.1 SSH via Browser:**
```
In VM instances list → Click "SSH" button next to your instance
```

A terminal will open in browser ✅

#### **3.2 (Alternative) SSH from Local:**
```bash
# Get External IP from GCP Console
# Then:
ssh YOUR_USERNAME@EXTERNAL_IP
```

---

### **Step 4: Run Auto Setup Script**

```bash
# Download and run setup script
wget https://raw.githubusercontent.com/kthanapuet/TKRoboTrade/main/gcp_setup.sh
chmod +x gcp_setup.sh
./gcp_setup.sh
```

This will:
- ✅ Update system
- ✅ Install Python 3, pip, git
- ✅ Clone repository
- ✅ Create virtual environment
- ✅ Install all dependencies

⏱️ Takes ~2-3 minutes

---

### **Step 5: Configure API Credentials**

```bash
cd TKRoboTrade

# Create .env file
nano .env
```

**Paste your credentials:**
```env
# PI Securities API
APP_ID=your_app_id_here
APP_SECRET=your_app_secret_here
ACCOUNT_NO=your_account_number
PIN=your_pin
BROKER_ID=PI
APP_CODE=YOUR_APP_CODE

# Line Notify
LINE_NOTIFY_TOKEN=your_line_token_here
```

**Save:** Press `Ctrl+X`, then `Y`, then `Enter`

---

### **Step 6: Test Run Bot**

```bash
# Activate virtual environment
source venv/bin/activate

# Test run
python bot.py
```

**Expected Output:**
```
🚀 Starting TK Robo Trade Daemon...
✅ Active Strategy: EMACrossover
✅ เตรียมกลยุทธ์สำหรับ 10 หุ้นสำเร็จ
✅ เชื่อมต่อ SETTRADE API สำเร็จ พร้อมทำงาน!
🤖 TK Robo Trade Started! Monitoring 10 symbols.
[10:30:45] นอกเวลาทำการ ตลาดปิด... 😴
```

✅ If you see this → **SUCCESS!**

Press `Ctrl+C` to stop

---

### **Step 7: Run in Background with Screen**

```bash
# Install screen (if not installed)
sudo apt-get install screen -y

# Start screen session
screen -S trading-bot

# Activate venv and run bot
source venv/bin/activate
python bot.py

# Detach screen: Press Ctrl+A then D

# Bot is now running in background! ✅
```

**Useful Screen Commands:**
```bash
# List all sessions
screen -ls

# Reattach to session
screen -r trading-bot

# Kill session (from inside)
Ctrl+C then type: exit
```

---

### **Step 8: (Optional) Auto-Start with systemd**

For automatic restart on reboot:

```bash
# Create logs directory
mkdir -p ~/TKRoboTrade/logs

# Copy service file
cd ~/TKRoboTrade
sudo cp trading-bot.service /etc/systemd/system/

# Edit with your username
sudo nano /etc/systemd/system/trading-bot.service

# Replace ALL occurrences of YOUR_USERNAME with your actual username
# (Usually same as your email before @)
# Example: john_doe

# Save: Ctrl+X, Y, Enter

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl start trading-bot

# Check status
sudo systemctl status trading-bot

# View logs
sudo journalctl -u trading-bot -f

# Stop service
sudo systemctl stop trading-bot
```

---

## **🔒 Security Setup**

### **1. Firewall Rules**

```bash
# GCP automatically has firewall
# But if you want to restrict SSH:

# In GCP Console:
# VPC Network → Firewall → Create Firewall Rule

# Name: allow-ssh-my-ip
# Direction: Ingress
# Target: All instances
# Source IP ranges: YOUR_HOME_IP/32
# Protocols: tcp:22
```

### **2. Disable Password Authentication (SSH Key Only)**

```bash
sudo nano /etc/ssh/sshd_config

# Find and change:
PasswordAuthentication no

# Save and restart SSH
sudo systemctl restart sshd
```

### **3. Keep System Updated**

```bash
# Run weekly:
sudo apt-get update && sudo apt-get upgrade -y
```

---

## **📊 Monitoring**

### **View Bot Logs:**

```bash
# If using screen:
screen -r trading-bot

# If using systemd:
sudo journalctl -u trading-bot -f

# Last 100 lines:
sudo journalctl -u trading-bot -n 100
```

### **Check Resource Usage:**

```bash
# CPU and RAM usage
htop

# Install if not available:
sudo apt-get install htop -y
```

### **GCP Monitoring:**

```
GCP Console → Monitoring → Dashboards → VM Instances
```
- CPU usage
- Network traffic
- Disk I/O

---

## **💸 Cost Management**

### **Stay in Free Tier:**

✅ **DO:**
- Use only 1 e2-micro instance
- Choose US regions only
- Stay under 30 GB disk
- Monitor usage in Billing Dashboard

❌ **DON'T:**
- Create multiple instances
- Use non-US regions
- Add GPUs or extra disks
- Exceed egress limits

### **Monitor Billing:**

```
GCP Console → Billing → Reports
```

**Set Budget Alert:**
```
Billing → Budgets & alerts → Create Budget
Amount: $1
Alert: 50%, 90%, 100%
```

You'll get email if costs approach $1

---

## **🔄 Updating Bot**

```bash
cd ~/TKRoboTrade

# Pull latest changes
git pull origin main

# Reinstall dependencies (if needed)
source venv/bin/activate
pip install -r requirements.txt

# Restart bot
# If using screen:
screen -r trading-bot
Ctrl+C
python bot.py

# If using systemd:
sudo systemctl restart trading-bot
```

---

## **🛠️ Troubleshooting**

### **Problem: Can't connect via SSH**

**Solution:**
```
GCP Console → VM Instances → Click "SSH" button
(Uses browser-based SSH, always works)
```

### **Problem: Bot crashes**

**Solution:**
```bash
# Check logs
sudo journalctl -u trading-bot -n 50

# Or if using screen:
screen -r trading-bot
# Look for error messages
```

### **Problem: API connection fails**

**Solution:**
```bash
# Test API credentials
source venv/bin/activate
python -c "from settrade_v2 import Investor; print('OK')"

# Check .env file
cat .env
```

### **Problem: Out of Memory**

**Solution:**

e2-micro has only 1 GB RAM. If bot crashes due to memory:

```bash
# Add swap space
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## **📱 Line Notifications Setup**

Already configured in bot! You'll receive:

- 🤖 Bot startup notification
- 💚 BUY orders with details
- 🔴 SELL orders with P&L
- 💓 Hourly heartbeat
- 📊 Daily summary (5:30 PM)

---

## **✅ Success Checklist**

- [ ] GCP account created
- [ ] VM instance running (e2-micro, US region)
- [ ] SSH connected
- [ ] Setup script completed
- [ ] .env configured
- [ ] Bot tested successfully
- [ ] Running in screen/systemd
- [ ] Line notifications working
- [ ] Billing alerts set

---

## **🎯 Next Steps**

1. **Monitor for 1 week** - Check logs daily
2. **Verify trades** in sandbox/paper mode first
3. **Go live** when confident
4. **Set budget alerts** in GCP
5. **Update bot** weekly

---

## **📞 Support**

If you encounter issues:

1. Check logs: `sudo journalctl -u trading-bot -f`
2. Review this guide
3. Check GitHub issues: https://github.com/kthanapuet/TKRoboTrade/issues

---

**Happy Trading! 🚀**

*TK Robo Trade - Powered by Google Cloud Platform*
