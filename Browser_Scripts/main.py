'''
TODO:
    - Hosted locally and available from any machine on the closed network
    - Live monitoring: time, current target AZ/EL, actual AZ/EL reported by STM32, error between them
    - Later: STM32 firmware will be updated to send states and error messages which should also show on the broswer
    - Pass countdown and satellite name display would be useful during tracking operations
    - Ground track map showing satellite position over Earth based on TLE data would be a very cool addition. Leaftlet.js could be used for this map.
    - Basic commanding: selecting a satellite to track, or entering manual AZ/EL targets

N.B! The serial port to STM32 can only be opened by one process, so the web server must absorb the UART handling rather than running alongside other scripts.
'''