# DemiRGB Firmware
# Copyright (C) 2018 Velociraptor Aerospace Dynamics
# This is free software; for details, please see COPYING.

# This is loaded by boot.py on the filesystem.

import machine
import time
import gc

BOOT_PIN = 5  # "D1" on the D1 Mini
STATUS_LED = 2  # Blue LED
MODE_NORMAL = 0
MODE_SETUP = 1
MODE_FACTORY = 2


def check_boot_state():
    p = machine.Pin(BOOT_PIN, machine.Pin.IN, machine.Pin.PULL_UP)
    # Not shorted (high)
    if p() == 1:
        return MODE_NORMAL

    led = machine.PWM(machine.Pin(STATUS_LED), freq=1, duty=512)
    # Shorted (low), see if it goes high within 10 seconds
    for i in range(10):
        if p() == 1:
            return MODE_SETUP
        time.sleep(1)

    # Shorted (low) for over 10 seconds
    led.freq(4)  # Flash fast
    while p() == 0:
        time.sleep(1)
    return MODE_FACTORY


boot_state = check_boot_state()
if boot_state == MODE_SETUP:
    import demirgb_websetup
    gc.collect()
    demirgb_websetup.main()
elif boot_state == MODE_FACTORY:
    import demirgb_inisetup
    gc.collect()
    demirgb_inisetup.factory()
else:
    import demirgb
    gc.collect()
    demirgb.main()
