# DemiRGB Firmware
# Copyright (C) 2018 Velociraptor Aerospace Dynamics
# This is free software; for details, please see COPYING.

import os
import ubinascii
import network
import machine


def setup_network():
    sta_if = network.WLAN(network.STA_IF)
    sta_if.active(False)

    ap_if = network.WLAN(network.AP_IF)
    ap_if.active(True)
    essid = b'DemiRGB-%s' % ubinascii.hexlify(ap_if.config('mac')[-3:])
    ap_if.config(essid=essid, authmode=network.AUTH_WPA_WPA2_PSK, password=b'RGBControl')


def setup_diagnostic():
    # Flash the blue LED slowly on first boot after success.
    machine.PWM(machine.Pin(2), freq=1, duty=512)


def factory():
    setup(force=True)


def setup(force=False, wait=False):
    if not force:
        try:
            os.stat('demirgb.json')
        except OSError:
            pass
        else:
            print('Initial DemiRGB setup already appears to have been done')
            return
    print('Performing initial DemiRGB setup')
    setup_network()
    with open('boot.py', 'w') as f:
        f.write("""\
# This file is executed on every boot (including wake-boot from deepsleep)
import gc
gc.collect()
# DemiRGB
import demirgb_boot
""")
    with open('demirgb.json', 'w') as f:
        f.write('{}')
    setup_diagnostic()
    if wait:
        import time
        while True:
            time.sleep(1)
