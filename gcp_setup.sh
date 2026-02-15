#!/bin/bash

# TK Robo Trade - GCP Setup Script
# Auto-setup for Google Cloud Compute Engine

echo "=========================================="
echo "TK Robo Trade - Auto Setup for GCP"
echo "=========================================="

# Update system
echo "📦 Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# Install Python 3 and dependencies
echo "🐍 Installing Python 3 and tools..."
sudo apt-get install -y python3 python3-pip python3-venv git

# Install screen for persistent sessions
echo "📺 Installing screen..."
sudo apt-get install -y screen

# Navigate to home
cd /home/$(whoami)

# Clone repository (if not exists)
if [ ! -d "TKRoboTrade" ]; then
    echo "📥 Cloning TKRoboTrade repository..."
    git clone https://github.com/kthanapuet/TKRoboTrade.git
else
    echo "✅ Repository already exists"
fi

cd TKRoboTrade

# Create virtual environment
echo "🌐 Creating Python virtual environment..."
python3 -m venv venv

# Activate and install dependencies
echo "📦 Installing Python dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Create .env file:"
echo "   nano .env"
echo ""
echo "2. Add your API credentials"
echo ""
echo "3. Run the bot:"
echo "   source venv/bin/activate"
echo "   python bot.py"
echo ""
echo "Or run in background with screen:"
echo "   screen -S bot"
echo "   source venv/bin/activate"
echo "   python bot.py"
echo "   # Press Ctrl+A then D to detach"
echo ""
