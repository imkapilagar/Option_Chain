#!/usr/bin/env python3
"""
Fetch lows from specific timeframe (10:00 AM - 11:00 AM) and update dashboard
"""
import requests
import json
from datetime import datetime, time

# Read credentials
with open('upstox_credentials.txt', 'r') as f:
    lines = f.readlines()
    access_token = lines[1].split('=')[1].strip()

def fetch_timeframe_low(instrument_key, start_time, end_time):
    """Fetch low from specific timeframe using intraday candles"""
    url = f'https://api.upstox.com/v2/historical-candle/intraday/{instrument_key}/1minute'
    headers = {'Accept': 'application/json', 'Authorization': f'Bearer {access_token}'}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            candles = data.get('data', {}).get('candles', [])

            if candles:
                # Filter candles within timeframe
                # Candles format: [timestamp, open, high, low, close, volume, oi]
                # Timestamp format: "2025-11-25T10:30:00+05:30"

                timeframe_lows = []
                for candle in candles:
                    if len(candle) > 3:
                        timestamp_str = candle[0]
                        # Extract time from timestamp
                        time_part = timestamp_str.split('T')[1].split('+')[0]  # "10:30:00"
                        hour = int(time_part.split(':')[0])
                        minute = int(time_part.split(':')[1])

                        # Check if within timeframe (10:00 AM - 11:00 AM)
                        if start_time[0] <= hour < end_time[0] or (hour == end_time[0] and minute == 0):
                            timeframe_lows.append(candle[3])  # low price

                if timeframe_lows:
                    return min(timeframe_lows)
    except:
        pass
    return None

# Timeframe: 10:00 AM - 11:00 AM
START_TIME = (10, 0)  # 10:00 AM
END_TIME = (11, 0)    # 11:00 AM

# Fetch option chain
url = 'https://api.upstox.com/v2/option/chain'
headers = {'Accept': 'application/json', 'Authorization': f'Bearer {access_token}'}
params = {'instrument_key': 'NSE_INDEX|Nifty 50', 'expiry_date': '2025-11-25'}

print(f"Fetching option chain...")
print(f"Timeframe: {START_TIME[0]:02d}:{START_TIME[1]:02d} - {END_TIME[0]:02d}:{END_TIME[1]:02d}")
print()

chain_data = requests.get(url, headers=headers, params=params, timeout=10).json()

# Focus on key strikes
key_strikes = [25900, 25950, 26000, 26050, 26100]

results = {'ce': [], 'pe': []}

print("Processing key strikes...")
for strike_data in chain_data.get('data', []):
    strike = strike_data.get('strike_price')

    if strike not in key_strikes:
        continue

    print(f"  Strike {int(strike)}...")

    # CE
    ce_option = strike_data.get('call_options', {})
    ce_inst_key = ce_option.get('instrument_key')
    ce_ltp = ce_option.get('market_data', {}).get('ltp', 0)

    if ce_inst_key and ce_ltp > 0:
        timeframe_low = fetch_timeframe_low(ce_inst_key, START_TIME, END_TIME)
        if timeframe_low:
            distance = abs(timeframe_low - 50)
            results['ce'].append({
                'strike': int(strike),
                'timeframe_low': timeframe_low,
                'ltp': ce_ltp,
                'distance': distance
            })

    # PE
    pe_option = strike_data.get('put_options', {})
    pe_inst_key = pe_option.get('instrument_key')
    pe_ltp = pe_option.get('market_data', {}).get('ltp', 0)

    if pe_inst_key and pe_ltp > 0:
        timeframe_low = fetch_timeframe_low(pe_inst_key, START_TIME, END_TIME)
        if timeframe_low:
            distance = abs(timeframe_low - 50)
            results['pe'].append({
                'strike': int(strike),
                'timeframe_low': timeframe_low,
                'ltp': pe_ltp,
                'distance': distance
            })

# Find nearest to 50
ce_nearest = min(results['ce'], key=lambda x: x['distance']) if results['ce'] else None
pe_nearest = min(results['pe'], key=lambda x: x['distance']) if results['pe'] else None

print("\n" + "="*70)
print(f"RESULTS - Options Nearest to ₹50 ({START_TIME[0]:02d}:{START_TIME[1]:02d}-{END_TIME[0]:02d}:{END_TIME[1]:02d} Timeframe Low):")
print("="*70)

if ce_nearest:
    print(f"📈 CE: Strike {ce_nearest['strike']}")
    print(f"   Timeframe Low: ₹{ce_nearest['timeframe_low']:.2f}")
    print(f"   Current LTP: ₹{ce_nearest['ltp']:.2f}")
    print(f"   Distance: ₹{ce_nearest['distance']:.2f}")

if pe_nearest:
    print(f"📉 PE: Strike {pe_nearest['strike']}")
    print(f"   Timeframe Low: ₹{pe_nearest['timeframe_low']:.2f}")
    print(f"   Current LTP: ₹{pe_nearest['ltp']:.2f}")
    print(f"   Distance: ₹{pe_nearest['distance']:.2f}")

print("="*70)

# Save to JSON
thread_data = {
    'timeframe': '10:00-11:00',
    'start_time': '10:00',
    'end_time': '11:00',
    'status': 'active',
    'last_update': datetime.now().strftime('%H:%M:%S'),
    'ce_strike': {
        'strike': ce_nearest['strike'],
        'low': ce_nearest['timeframe_low'],
        'ltp': ce_nearest['ltp'],
        'distance': ce_nearest['distance'],
        'samples': 1,
        'last_update': datetime.now().strftime('%H:%M:%S')
    } if ce_nearest else None,
    'pe_strike': {
        'strike': pe_nearest['strike'],
        'low': pe_nearest['timeframe_low'],
        'ltp': pe_nearest['ltp'],
        'distance': pe_nearest['distance'],
        'samples': 1,
        'last_update': datetime.now().strftime('%H:%M:%S')
    } if pe_nearest else None
}

output_data = {'thread_1': thread_data}

with open('output/debug_tracking_20251125.json', 'w') as f:
    json.dump(output_data, f, indent=2)

print(f"\n✅ Saved to output/debug_tracking_20251125.json")
print("\nNow run: python3 generate_live_dashboard.py")
