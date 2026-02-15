"""
Walk-Forward Test for Market Condition Detection
Test if we can detect market conditions in real-time with acceptable accuracy
"""

import pandas as pd
import numpy as np
import yfinance as yf

# Download QQQ as market proxy
print("📥 Downloading QQQ data (2018-2023)...")
df = yf.download('QQQ', start='2018-01-01', end='2024-01-01', progress=False, auto_adjust=True)

if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.droplevel(1)
    
df.columns = [c.lower() for c in df.columns]
df.rename(columns={'close': 'Close'}, inplace=True)

print(f"✅ Data: {len(df)} days\n")

# Walk-forward detection
print("="*80)
print("🔍 WALK-FORWARD MARKET DETECTION TEST")
print("="*80)
print("Testing if we can detect market condition BEFORE knowing the full year\n")

detection_results = []

for year in [2018, 2019, 2020, 2021, 2022, 2023]:
    year_data = df[df.index.year == year]
    
    if len(year_data) < 60:
        continue
    
    # Actual condition (hindsight)
    full_year_return = ((year_data['Close'].iloc[-1] - year_data['Close'].iloc[0]) / year_data['Close'].iloc[0]) * 100
    full_year_vol = year_data['Close'].pct_change().std() * np.sqrt(252) * 100
    
    if full_year_return > 15:
        actual = "BULL"
    elif full_year_return < -10:
        actual = "BEAR"
    else:
        actual = "SIDEWAYS"
    
    # Simulated monthly detection
    monthly_detections = []
    
    for month in range(1, 13):
        month_data = year_data[year_data.index.month <= month]
        
        if len(month_data) < 30:
            continue
        
        # Use only last 60 days for detection (realistic)
        lookback = month_data.tail(60)
        
        # Calculate metrics
        lookback_return = ((lookback['Close'].iloc[-1] - lookback['Close'].iloc[0]) / lookback['Close'].iloc[0]) * 100
        lookback_vol = lookback['Close'].pct_change().std() * np.sqrt(252) * 100
        
        # Detect condition
        if lookback_return > 10 and lookback_vol < 35:
            detected = "BULL"
        elif lookback_return < -10:
            detected = "BEAR"
        else:
            detected = "SIDEWAYS"
        
        monthly_detections.append(detected)
    
    # Calculate accuracy
    if monthly_detections:
        correct = sum(1 for d in monthly_detections if d == actual)
        accuracy = (correct / len(monthly_detections)) * 100
    else:
        accuracy = 0
    
    detection_results.append({
        'year': year,
        'actual': actual,
        'accuracy': accuracy,
        'return': full_year_return,
        'volatility': full_year_vol
    })
    
    print(f"{year}: Actual={actual} | Return={full_year_return:+.1f}% | Detection Accuracy={accuracy:.1f}%")
    
    # Show month-by-month
    print("   Monthly Detections:", " → ".join(monthly_detections[:12]))
    print()

# Overall accuracy
avg_accuracy = np.mean([r['accuracy'] for r in detection_results])

print("="*80)
print("📊 SUMMARY")
print("="*80)
print(f"\nAverage Detection Accuracy: {avg_accuracy:.1f}%")

if avg_accuracy >= 70:
    print("\n✅ Detection is RELIABLE enough for adaptive strategy")
    print("   Recommendation: Proceed with adaptive bot")
elif avg_accuracy >= 50:
    print("\n⚠️ Detection is MODERATE - use with caution")
    print("   Recommendation: Only detect Bear markets (defensive mode)")
else:
    print("\n❌ Detection is UNRELIABLE")
    print("   Recommendation: Stick with single best strategy (EMA 5/20 or Supertrend)")

print("\n" + "="*80)
print("💡 PRACTICAL RECOMMENDATION")
print("="*80)

print("\n🎯 Option 1: SIMPLE APPROACH (Recommended)")
print("   → Use Supertrend (7,2) or EMA 5/20 ALL THE TIME")
print("   → Return: +193-231%")
print("   → Pros: No detection needed, consistent")
print("   → Cons: May underperform in bear markets")

print("\n🎯 Option 2: DEFENSIVE SWITCHING ONLY")
print("   → Use Supertrend (7,2) as default")
print("   → Detect ONLY Bear Market (easier to detect)")
print("   → Switch to BBands+RSI when 60-day return < -15%")
print("   → Return: ~+220% (estimated)")
print("   → Pros: Protect during crashes, simple logic")
print("   → Cons: May miss some transitions")

print("\n🎯 Option 3: FULL ADAPTIVE (Advanced)")
print("   → Detect all conditions monthly")
print("   → Accuracy: ~" + f"{avg_accuracy:.0f}%")
print("   → Return: Depends on detection accuracy")
print("   → Pros: Best in theory")
print("   → Cons: Detection errors can hurt performance")
