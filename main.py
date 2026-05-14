'''
TODO:
   - Start automatically on boot such as with systemd and integrates all functionalities.
   - Two primary modes: 
        1. External MCS: 
            - Target AZ/EL are received, formatted, and sent to STM32.
        2. Standalone:
            - Sattelite name/TLE data is sent to Pi and Pi must generate the target angles. 
            - Automate the TLE upadate via secure channel. 
    - Add method that can give the STM32 step/ramp reference inputs for when dish control loops and PID gains are tuned.
'''

# region ABOUT
# endregion


# region IMPORTS
import os
import sys
import csv
import time
from datetime import datetime, timedelta, timezone
from ESL_GroundStation.Prototype_Pi_Scripts.tracker import SatelliteTracker
from ESL_GroundStation.Prototype_Pi_Scripts.uart import UARTComm
# endregion

# region PATHS
HOME_DIR = os.path.expanduser("~")
PROJECT_ROOT = os.path.join(HOME_DIR, "Desktop", "ESL_GroundStation")
# endregion

# region CLASSES

# endregion

# region FUNCTIONS
# endregion

# region MAIN
def main():
    print("Starting Ground Station Prototype...")


if __name__ == "__main__": main()
# endregion