# DemiRGB Firmware
# Copyright (C) 2018 Velociraptor Aerospace Dynamics
# This is free software; for details, please see COPYING.

# This is loaded by _boot immediately after _core_boot (which is what
# would be _boot on a normal MicroPython distribution).

import os


try:
    os.stat('demirgb.json')
except OSError:
    import demirgb_inisetup
    demirgb_inisetup.setup(force=True, wait=True)
