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