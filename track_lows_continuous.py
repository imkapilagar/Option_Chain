#!/usr/bin/env python3
"""
Continuously track option lows and find options nearest to Rs 50 LOW
This is the CORRECT logic - tracking LOWS, not current LTP
"""
import requests
import pandas as pd
import json
import os
from datetime import datetime
import time

# Read credentials
with open('upstox_credentials.txt', 'r') as f:
    lines = f.readlines()
    access_token = lines[1].split('=')[1].strip()

# Global tracker to maintain lows across multiple fetches
lows_tracker = {}

def fetch_option_chain():
    """Fetch current option chain data"""
    url = 'https://api.upstox.com/v2/option/chain'
    headers = {'Accept': 'application/json', 'Authorization': f'Bearer {access_token}'}
    params = {'instrument_key': 'NSE_INDEX|Nifty 50', 'expiry_date': '2025-11-25'}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            return data.get('data', [])
    except Exception as e:
        print(f"❌ Error fetching data: {e}")
    return []

def update_lows(chain_data):
    """Update the low tracker with new data"""
    global lows_tracker

    for strike_data in chain_data:
        strike = strike_data.get('strike_price')

        # Process CE
        ce_option = strike_data.get('call_options', {})
        ce_market = ce_option.get('market_data', {})
        if ce_market:
            ltp = ce_market.get('ltp', 0)
            if ltp > 0:
                key = f"NIFTY_{strike}_CE"

                if key not in lows_tracker:
                    # First time seeing this option
                    lows_tracker[key] = {
                        'strike': strike,
                        'option_type': 'CE',
                        'low': ltp,          # Initialize low with current LTP
                        'current_ltp': ltp,
                        'first_seen': ltp,
                        'samples': 1,
                        'last_update': datetime.now().strftime('%H:%M:%S')
                    }
                else:
                    # Update existing option
                    old_low = lows_tracker[key]['low']
                    lows_tracker[key]['current_ltp'] = ltp
                    lows_tracker[key]['samples'] += 1
                    lows_tracker[key]['last_update'] = datetime.now().strftime('%H:%M:%S')

                    # Check if we have a NEW LOW
                    if ltp < old_low:
                        lows_tracker[key]['low'] = ltp
                        drop_percent = ((old_low - ltp) / old_low) * 100

                        # Check if near Rs 50
                        distance = abs(ltp - 50)
                        if distance <= 15:
                            print(f"\n{'='*60}")
                            print(f"🔔 NEW LOW NEAR ₹50!")
                            print(f"   Strike: {strike} CE")
                            print(f"   Old Low: ₹{old_low:.2f} → New Low: ₹{ltp:.2f} (↓{drop_percent:.2f}%)")
                            print(f"   Distance from ₹50: ₹{distance:.2f}")
                            print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
                            print(f"{'='*60}\n")
                        else:
                            print(f"📉 NEW LOW: {strike} CE - ₹{old_low:.2f} → ₹{ltp:.2f}")

        # Process PE
        pe_option = strike_data.get('put_options', {})
        pe_market = pe_option.get('market_data', {})
        if pe_market:
            ltp = pe_market.get('ltp', 0)
            if ltp > 0:
                key = f"NIFTY_{strike}_PE"

                if key not in lows_tracker:
                    lows_tracker[key] = {
                        'strike': strike,
                        'option_type': 'PE',
                        'low': ltp,
                        'current_ltp': ltp,
                        'first_seen': ltp,
                        'samples': 1,
                        'last_update': datetime.now().strftime('%H:%M:%S')
                    }
                else:
                    old_low = lows_tracker[key]['low']
                    lows_tracker[key]['current_ltp'] = ltp
                    lows_tracker[key]['samples'] += 1
                    lows_tracker[key]['last_update'] = datetime.now().strftime('%H:%M:%S')

                    if ltp < old_low:
                        lows_tracker[key]['low'] = ltp
                        drop_percent = ((old_low - ltp) / old_low) * 100

                        distance = abs(ltp - 50)
                        if distance <= 15:
                            print(f"\n{'='*60}")
                            print(f"🔔 NEW LOW NEAR ₹50!")
                            print(f"   Strike: {strike} PE")
                            print(f"   Old Low: ₹{old_low:.2f} → New Low: ₹{ltp:.2f} (↓{drop_percent:.2f}%)")
                            print(f"   Distance from ₹50: ₹{distance:.2f}")
                            print(f"   Time: {datetime.now().strftime('%H:%M:%S')}")
                            print(f"{'='*60}\n")
                        else:
                            print(f"📉 NEW LOW: {strike} PE - ₹{old_low:.2f} → ₹{ltp:.2f}")

def find_nearest_to_50():
    """Find options whose LOW is nearest to Rs 50"""
    global lows_tracker

    if not lows_tracker:
        return None, None

    df = pd.DataFrame.from_dict(lows_tracker, orient='index')

    # IMPORTANT: Calculate distance from LOW, not LTP
    df['distance_from_50'] = abs(df['low'] - 50)

    ce_df = df[df['option_type'] == 'CE'].copy()
    pe_df = df[df['option_type'] == 'PE'].copy()

    ce_nearest = None
    pe_nearest = None

    if not ce_df.empty:
        nearest_ce = ce_df.nsmallest(1, 'distance_from_50').iloc[0]
        ce_nearest = {
            'strike': int(nearest_ce['strike']),
            'low': float(nearest_ce['low']),              # This is the LOW
            'ltp': float(nearest_ce['current_ltp']),      # This is current price
            'distance': float(nearest_ce['distance_from_50']),
            'samples': int(nearest_ce['samples']),
            'last_update': nearest_ce['last_update']
        }

    if not pe_df.empty:
        nearest_pe = pe_df.nsmallest(1, 'distance_from_50').iloc[0]
        pe_nearest = {
            'strike': int(nearest_pe['strike']),
            'low': float(nearest_pe['low']),
            'ltp': float(nearest_pe['current_ltp']),
            'distance': float(nearest_pe['distance_from_50']),
            'samples': int(nearest_pe['samples']),
            'last_update': nearest_pe['last_update']
        }

    return ce_nearest, pe_nearest

def save_tracking_data():
    """Save current tracking data to JSON"""
    ce_nearest, pe_nearest = find_nearest_to_50()

    thread_data = {
        'timeframe': '09:30-10:30',
        'start_time': '09:30',
        'end_time': '10:30',
        'status': 'active',
        'samples': len(lows_tracker),
        'last_update': datetime.now().strftime('%H:%M:%S'),
        'ce_strike': ce_nearest,
        'pe_strike': pe_nearest
    }

    output_dir = 'output'
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, f'debug_tracking_{datetime.now().strftime("%Y%m%d")}.json')

    live_data = {'thread_1': thread_data}

    with open(output_file, 'w') as f:
        json.dump(live_data, f, indent=2)

def continuous_tracking(interval_seconds=30):
    """Continuously track lows"""
    print("="*70)
    print("🎯 CONTINUOUS LOW TRACKER - Finding Options Nearest to ₹50 LOW")
    print("="*70)
    print(f"Started at: {datetime.now().strftime('%H:%M:%S')}")
    print(f"Update interval: {interval_seconds} seconds")
    print(f"Target: Find options whose LOW is closest to ₹50")
    print("="*70)
    print()

    sample_count = 0

    try:
        while True:
            sample_count += 1
            print(f"[Sample {sample_count}] {datetime.now().strftime('%H:%M:%S')} - Fetching option chain...", flush=True)

            # Fetch current data
            chain_data = fetch_option_chain()

            if chain_data:
                # Update lows tracker
                update_lows(chain_data)

                # Find nearest to 50
                ce_nearest, pe_nearest = find_nearest_to_50()

                # Display current status
                print(f"⏰ {datetime.now().strftime('%H:%M:%S')} Status:")
                if ce_nearest:
                    print(f"   📈 CE: Strike {ce_nearest['strike']} - LOW: ₹{ce_nearest['low']:.2f} (Current: ₹{ce_nearest['ltp']:.2f}) - Distance: ₹{ce_nearest['distance']:.2f}")
                if pe_nearest:
                    print(f"   📉 PE: Strike {pe_nearest['strike']} - LOW: ₹{pe_nearest['low']:.2f} (Current: ₹{pe_nearest['ltp']:.2f}) - Distance: ₹{pe_nearest['distance']:.2f}")
                print()

                # Save to file for dashboard
                save_tracking_data()

            else:
                print(f"❌ No data received")

            # Wait for next interval
            time.sleep(interval_seconds)

    except KeyboardInterrupt:
        print("\n\n⏹️  Tracking stopped")
        print(f"Total samples collected: {sample_count}")
        print(f"Total options tracked: {len(lows_tracker)}")

        # Final summary
        ce_nearest, pe_nearest = find_nearest_to_50()
        print("\n" + "="*70)
        print("FINAL SUMMARY - Options Nearest to ₹50 LOW:")
        print("="*70)
        if ce_nearest:
            print(f"📈 CE: Strike {ce_nearest['strike']}")
            print(f"   LOW: ₹{ce_nearest['low']:.2f}")
            print(f"   Current LTP: ₹{ce_nearest['ltp']:.2f}")
            print(f"   Distance from ₹50: ₹{ce_nearest['distance']:.2f}")
            print(f"   Samples: {ce_nearest['samples']}")
        if pe_nearest:
            print(f"📉 PE: Strike {pe_nearest['strike']}")
            print(f"   LOW: ₹{pe_nearest['low']:.2f}")
            print(f"   Current LTP: ₹{pe_nearest['ltp']:.2f}")
            print(f"   Distance from ₹50: ₹{pe_nearest['distance']:.2f}")
            print(f"   Samples: {pe_nearest['samples']}")
        print("="*70)

if __name__ == '__main__':
    continuous_tracking(interval_seconds=30)
