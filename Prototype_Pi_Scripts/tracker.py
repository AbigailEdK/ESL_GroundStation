import csv
from skyfield.api import load, EarthSatellite, wgs84

class SatelliteTracker:
    def __init__(self, lat, lon, elevation_m=0):
        """Initialize tracker with ground station coordinates"""
        self.ts = load.timescale()
        self.observer = wgs84.latlon(lat, lon, elevation_m)
        self.satellite = None
        print(f"Ground station: {lat:.4f}°, {lon:.4f}°, {elevation_m}m")
    
    def load_tle_from_csv_data(self, name, tle_line1, tle_line2):
        """Load TLE data from provided strings"""
        try:
            self.satellite = EarthSatellite(tle_line1, tle_line2, name, self.ts)
            print(f"Loaded: {name}")
            print(f"Epoch: {self.satellite.epoch.utc_strftime('%Y-%m-%d %H:%M:%S UTC')}")
            return True
        except Exception as e:
            print(f"Error loading TLE: {e}")
            return False
    
    def get_position(self, time_utc=None):
        """
        Get satellite position relative to ground station
        
        Args:
            time_utc: UTC datetime object (timezone-aware or naive), or None for current time
            
        Returns:
            tuple: (azimuth, elevation, distance_km, is_visible)
        """
        if not self.satellite:
            raise ValueError("No satellite loaded")
        
        if time_utc:
            # Use from_datetime for timezone-aware, handles properly
            if time_utc.tzinfo is not None:
                t = self.ts.from_datetime(time_utc)
            else:
                # Naive datetime, assume UTC
                t = self.ts.utc(time_utc.year, time_utc.month, time_utc.day,
                               time_utc.hour, time_utc.minute, time_utc.second)
        else:
            t = self.ts.now()
        
        # Calculate position
        difference = self.satellite - self.observer
        topocentric = difference.at(t)
        alt, az, distance = topocentric.altaz()
        
        azimuth = az.degrees
        elevation = alt.degrees
        distance_km = distance.km
        is_visible = elevation > 10.0
        
        return azimuth, elevation, distance_km, is_visible