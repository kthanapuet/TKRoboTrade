from datetime import datetime, time as datetime_time
import pytz

# 1. Test Configuration
BANGKOK_TZ = pytz.timezone("Asia/Bangkok")


def is_market_open_mock(mock_now):
    # Mock function same as bot.py logic
    if mock_now.weekday() > 4:  # Sat-Sun
        return False

    current_time = mock_now.time()
    morning_session = datetime_time(10, 0) <= current_time <= datetime_time(12, 30)
    afternoon_session = datetime_time(14, 30) <= current_time <= datetime_time(16, 30)

    return morning_session or afternoon_session


# 2. Real Time Check
print("-" * 30)
print("🕒 Real Time Check:")
server_now = datetime.now()
bk_now = datetime.now(BANGKOK_TZ)

print(f"System Time (Local): {server_now}")
print(f"Bangkok Time:      {bk_now}")
print(f"Difference:        {bk_now.hour - server_now.hour} hours (approx)")

# 3. Market Hours Logic Test
print("\n🏪 Market Hours Logic Test:")

test_cases = [
    ("Monday 09:00 (Before Open)", datetime(2023, 10, 2, 9, 0, 0)),
    ("Monday 10:00 (Open)", datetime(2023, 10, 2, 10, 0, 0)),
    ("Monday 12:00 (Open)", datetime(2023, 10, 2, 12, 0, 0)),
    ("Monday 13:00 (Lunch Break)", datetime(2023, 10, 2, 13, 0, 0)),
    ("Monday 14:30 (Open)", datetime(2023, 10, 2, 14, 30, 0)),
    ("Monday 16:35 (Closed)", datetime(2023, 10, 2, 16, 35, 0)),
    ("Saturday 10:00 (Weekend)", datetime(2023, 10, 7, 10, 0, 0)),
]

for name, dt in test_cases:
    # Convert to localized datetime (simulate Bangkok time input)
    dt_local = BANGKOK_TZ.localize(dt)
    result = is_market_open_mock(dt_local)
    status = "✅ OPEN" if result else "❌ CLOSED"
    print(f"{name:<30} -> {status}")

print("-" * 30)
