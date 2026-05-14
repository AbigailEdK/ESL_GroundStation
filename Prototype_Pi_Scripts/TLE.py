#!/usr/bin/env python3
"""
TLE-based satellite tracker for Pi Zero 2W
Loads TLE data from CSV, calculates pass predictions, and tracks LEO satellite
"""

import sys
import csv
import time
from datetime import datetime, timedelta, timezone 

from ESL_GroundStation.Prototype_Pi_Scripts.tracker import SatelliteTracker
from ESL_GroundStation.Prototype_Pi_Scripts.uart import UARTComm


# ===== CONFIGURATION =====
LATITUDE = -33.9279    
LONGITUDE = 18.8653  
ELEVATION_M = 121       

AZ_MIN = 0.0
AZ_MAX = 360.0
EL_MIN = 10.0
EL_MAX = 85.0

TLE_CSV_FILE = "TLE.csv"
TLE_MAX_AGE_DAYS = 7
MAX_SEARCH_HOURS = 24
REFRESH_RATE = 1.0       # seconds

# ===== END CONFIGURATION =====

def load_tle_names_from_csv(csv_file):
    """Load all satellite names from TLE.csv"""
    try:
        with open(csv_file, 'r') as f:
            reader = csv.reader(f)
            lines = [line[0].strip() for line in reader if line and line[0].strip()]
        
        # Extract satellite names (every 3rd line starting at 0)
        names = [lines[i] for i in range(0, len(lines), 3) if i < len(lines)]
        return names
    except Exception as e:
        print(f"Error reading TLE.csv: {e}")
        return []

def load_tle_by_name(csv_file, sat_name):
    """Load TLE data for a specific satellite by name"""
    try:
        with open(csv_file, 'r') as f:
            reader = csv.reader(f)
            lines = [line[0].strip() for line in reader if line and line[0].strip()]
        
        # Find satellite by name
        for i in range(0, len(lines), 3):
            if i + 2 < len(lines) and lines[i].upper() == sat_name.upper():
                return lines[i], lines[i+1], lines[i+2]
        
        print(f"Satellite '{sat_name}' not found in TLE.csv")
        return None, None, None
    except Exception as e:
        print(f"Error loading TLE: {e}")
        return None, None, None

def check_tle_age(tle_line1, max_age_days):
    """Check if TLE is older than max_age_days. Returns (age_days, is_old, warning_msg)"""
    try:
        yy = int(tle_line1[18:20])
        ddd = float(tle_line1[20:32])
        
        year = 2000 + yy if yy < 70 else 1900 + yy
        
        epoch = datetime(year, 1, 1, tzinfo=timezone.utc) + timedelta(days=ddd - 1)
        age = datetime.now(timezone.utc) - epoch
        age_days = age.days
        
        is_old = age_days > max_age_days
        msg = f"TLE Epoch: {epoch.strftime('%Y-%m-%d %H:%M:%S UTC')} ({age_days} days old)"
        
        if is_old:
            msg += f" WARNING: TLE is older than {max_age_days} days"
        
        return age_days, is_old, msg
    except Exception as e:
        print(f"Error parsing TLE age: {e}")
        return None, False, "Could not determine TLE age"

def find_next_pass(tracker, max_search_hours):
    """Find when satellite rises above EL_MIN using Skyfield. Returns (rise_time, rise_az)"""
    from skyfield.api import load
    
    ts = load.timescale()
    t0 = ts.now()
    end_time = datetime.now(timezone.utc) + timedelta(hours=max_search_hours)
    t1 = ts.utc(end_time)
    
    # Find events where satellite crosses EL_MIN
    t_events, events = tracker.satellite.find_events(
        tracker.observer, t0, t1, altitude_degrees=EL_MIN
    )
    
    # Event types: 0=rise, 1=culminate, 2=set
    for t_event, event in zip(t_events, events):
        if event == 0:  # Rise event
            rise_time = t_event.utc_datetime() # <-- FIX: Keep timezone info
            az, el, dist, _ = tracker.get_position(rise_time)
            return rise_time, az
    
    return None, None

def format_time_remaining(target_time):
    """Format remaining time until target"""
    now = datetime.now(timezone.utc) # <-- FIX: Use timezone-aware 'now'
    remaining = target_time - now
    
    if remaining.total_seconds() < 0:
        return "NOW"
    
    hours, remainder = divmod(int(remaining.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def main():
    print("TLE Satellite Tracker\n")
    print(f"Current time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    tracker = SatelliteTracker(LATITUDE, LONGITUDE, ELEVATION_M)
    
    sat_names = load_tle_names_from_csv(TLE_CSV_FILE)
    if not sat_names:
        print("No satellites found in TLE.csv")
        return
    
    print(f"Available satellites ({len(sat_names)}):")
    for i, name in enumerate(sat_names, 1):
        print(f"  {i}. {name}")
    
    print("\nEnter satellite name to load (or 'exit' to quit):")
    sat_input = input("Satellite> ").strip()
    
    if sat_input.lower() == 'exit':
        return
    
    name, tle1, tle2 = load_tle_by_name(TLE_CSV_FILE, sat_input)
    if not name:
        print("Failed to load satellite data.")
        return
    
    age_days, is_old, age_msg = check_tle_age(tle1, TLE_MAX_AGE_DAYS)
    print(f"\n{age_msg}")
    
    if is_old:
        confirm = input("Continue anyway? (yes/no): ").strip().lower()
        if confirm != 'yes':
            print("Cancelled.")
            return
    
    if not tracker.load_tle_from_csv_data(name, tle1, tle2):
        print("Failed to load satellite into tracker.")
        return
    
    print(f"\nSearching for next pass (within {MAX_SEARCH_HOURS} hours)...")
    rise_time, rise_az = find_next_pass(tracker, MAX_SEARCH_HOURS)
    
    if not rise_time:
        print(f"No pass found within {MAX_SEARCH_HOURS} hours.")
        return
    
    time_str = format_time_remaining(rise_time)
    
    print(f"\nPass Information")
    print(f"Rise time:     {rise_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"Time until:    {time_str}")
    print(f"Park Az/El:    {rise_az:.1f} / {EL_MIN}")
    print(f"Elevation range: {EL_MIN} - {EL_MAX}")
    
    print("\nReady to track? (yes/no):")
    confirm = input("> ").strip().lower()
    
    if confirm != 'yes':
        print("Cancelled.")
        return
    
    uart = UARTComm()
    print(f"\nSending park position: AZ={rise_az:.1f} EL={EL_MIN}")
    uart.send_position(azimuth=rise_az, elevation=EL_MIN)
    
    print(f"\nWaiting for pass to begin...")
    print(f"Will start tracking at: {rise_time.strftime('%H:%M:%S UTC')}")
    
    while datetime.now(timezone.utc) < rise_time: # <-- FIX: Use timezone-aware 'now'
        remaining = format_time_remaining(rise_time)
        sys.stdout.write(f"\rCountdown: {remaining} (press Ctrl+C to cancel)")
        sys.stdout.flush()
        time.sleep(0.5)
    
    print("\n\nTRACKING STARTED")
    print(f"{'Time (UTC)':<20} {'AZ':<8} {'EL':<8} {'Dist (km)':<10}")
    print("-" * 60)
    
    tracking = True
    last_send = time.time()
    
    while tracking:
        now_utc = datetime.now(timezone.utc) # <-- FIX: Use timezone-aware 'now'
        az, el, dist, visible = tracker.get_position(now_utc)
        
        current = time.time()
        if current - last_send >= REFRESH_RATE:
            uart.send_position(azimuth=az, elevation=el)
            
            time_str = now_utc.strftime('%H:%M:%S')
            print(f"{time_str:<20} {az:>6.1f} {el:>6.1f} {dist:>8.1f}")
            
            last_send = current
        
        if el < EL_MIN:
            print("\nSatellite has set below horizon. Tracking complete.")
            tracking = False
        else:
            time.sleep(0.1)  
    
    uart.close()
    print("\nProgram terminated")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")