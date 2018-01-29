# DemiRGB Firmware
# Copyright (C) 2018 Velociraptor Aerospace Dynamics
# This is free software; for details, please see COPYING.

# Note that this file exceeds ESP8266 memory limitations if shipped
# verbatim to and run from the device.  It must be compiled with
# mpy-cross and the .mpy must be shipped to the device.

import socket
import json
import time
import math
import machine
import gc
import ubinascii
import os


CONFIG = {
    'listen_addr': '0.0.0.0',
    'listen_port': 80,
    'auth_secret': '',
    'syslog_host': '',
    'syslog_id': 'demirgb',
    'led_r_pin': 13,
    'led_g_pin': 12,
    'led_b_pin': 14,
    'disable_pins': [5, 4],
    'init_light_test': True,
    'brightness_scale': 1.0,
}

STATE = {
    'switch': 'off',
    'hue': 11.7647,
    'saturation': 6.71937,
    'level': 100,
    'frequency': 240,
    'fadetime': 1000,
    'brnorm': True,
}

# Unused pins which do not have default pullups/pulldowns.
# We want to pull these up.
for pin in CONFIG['disable_pins']:
    machine.Pin(pin, machine.Pin.IN, machine.Pin.PULL_UP)

LED_R = machine.PWM(machine.Pin(CONFIG['led_r_pin']), freq=STATE['frequency'], duty=0)
LED_G = machine.PWM(machine.Pin(CONFIG['led_g_pin']), freq=STATE['frequency'], duty=0)
LED_B = machine.PWM(machine.Pin(CONFIG['led_b_pin']), freq=STATE['frequency'], duty=0)
SYSLOG_SOCKET = None


def debug(text):
    print(text)
    if SYSLOG_SOCKET and text:
        SYSLOG_SOCKET.sendto(
            '<135>{} demirgb: {}'.format(CONFIG['syslog_id'], text).encode('ASCII'),
            (CONFIG['syslog_host'], 514),
        )


def hsv_to_rgb(h, s, v):
    # In: 0.0 to 1.0 ranges
    # Out: 0.0 to 1.0 ranges
    if s == 0.0:
        return (v, v, v)
    i = int(h*6.)  # assume int() truncates
    f = (h*6.)-i
    p, q, t = v*(1.-s), v*(1.-s*f), v*(1.-s*(1.-f))
    i %= 6
    if i == 0:
        return (v, t, p)
    elif i == 1:
        return (q, v, p)
    elif i == 2:
        return (p, v, t)
    elif i == 3:
        return (p, q, v)
    elif i == 4:
        return (t, p, v)
    elif i == 5:
        return (v, p, q)


def rgb_to_hsv(r, g, b):
    # In: 0.0 to 1.0 ranges
    # Out: 0.0 to 1.0 ranges
    mx = max(r, g, b)
    mn = min(r, g, b)
    df = mx-mn
    if mx == mn:
        h = 0
    elif mx == r:
        h = (60 * ((g-b)/df) + 360) % 360
    elif mx == g:
        h = (60 * ((b-r)/df) + 120) % 360
    elif mx == b:
        h = (60 * ((r-g)/df) + 240) % 360
    if mx == 0:
        s = 0
    else:
        s = df/mx
    v = mx
    return h / 360.0, s, v


def init_lights():
    if not CONFIG['init_light_test']:
        set_lights()
        return
    if STATE['fadetime']:
        fadesteps = int(STATE['fadetime'] / 50.0)
        # 1020, not 1023.  If we step up to full 1023, there's a noticable
        # flash (PWM turning off for efficiency maybe?)
        fadeduties = [int(math.sin((i+1) / fadesteps * math.pi) * 1020 * CONFIG['brightness_scale']) for i in range(fadesteps)]
        fadedelay = 50
    else:
        fadeduties = [int(1023 * CONFIG['brightness_scale'])]
        fadedelay = 1000
    for i in (
        (LED_R, LED_G, LED_B),
        (LED_R,), (LED_G,), (LED_B,),
        (LED_R, LED_G), (LED_G, LED_B), (LED_R, LED_B),
        (LED_R, LED_G, LED_B)
    ):
        debug('Testing: {}'.format(i))
        for fadeduty in fadeduties:
            for j in i:
                j.duty(fadeduty)
            time.sleep_ms(fadedelay)
        for j in i:
            j.duty(0)
    set_lights()


def demo_lights():
    # 1020, not 1023.  If we step up to full 1023, there's a noticable
    # flash (PWM turning off for efficiency maybe?)
    fade_lights(int(1020 * CONFIG['brightness_scale']), 0, 0)
    for l in range(3):
        for i in range(40):
            r, g, b = hsv_to_rgb(i / 40.0, 1.0, 1.0)
            LED_R.duty(int(r * 1020 * CONFIG['brightness_scale']))
            LED_G.duty(int(g * 1020 * CONFIG['brightness_scale']))
            LED_B.duty(int(b * 1020 * CONFIG['brightness_scale']))
            time.sleep_ms(50)
    set_lights()


def fade_lights(ledto_r, ledto_g, ledto_b):
    ledfrom_r = LED_R.duty()
    ledfrom_g = LED_G.duty()
    ledfrom_b = LED_B.duty()
    freq = STATE['frequency']
    if LED_R.freq() != freq:
        # Deinit all first, as all PWMs must be running at the
        # same frequency at the same time
        for i in (LED_R, LED_G, LED_B):
            debug('{}.deinit()'.format(i))
            i.deinit()
        debug('LED_R.init(freq={}, duty={})'.format(freq, ledfrom_r))
        LED_R.init(freq=freq, duty=ledfrom_r)
        debug('LED_G.init(freq={}, duty={})'.format(freq, ledfrom_g))
        LED_G.init(freq=freq, duty=ledfrom_g)
        debug('LED_B.init(freq={}, duty={})'.format(freq, ledfrom_b))
        LED_B.init(freq=freq, duty=ledfrom_b)

    if (ledfrom_r != ledto_r) or (ledfrom_g != ledto_g) or (ledfrom_b != ledto_b):
        debug('PWM: Setting to R={}, G={}, B={}'.format(ledto_r, ledto_g, ledto_b))
        if STATE['fadetime']:
            fadesteps = int(STATE['fadetime'] / 50.0)
            fadeduties = [[
                (
                    ledto + ((ledfrom-ledto) - int(math.sin((fadestep+1) / (fadesteps*2) * math.pi) * (ledfrom-ledto)))
                ) for (ledfrom, ledto) in (
                    (ledfrom_r, ledto_r), (ledfrom_g, ledto_g), (ledfrom_b, ledto_b)
                )
            ] for fadestep in range(fadesteps)]
            fadedelay = 50
        else:
            fadeduties = [(ledto_r, ledto_g, ledto_b)]
            fadedelay = 0

        for (r, g, b) in fadeduties:
            LED_R.duty(r)
            LED_G.duty(g)
            LED_B.duty(b)
            time.sleep_ms(fadedelay)


def set_lights():
    if STATE['switch'] == 'on':
        r, g, b = hsv_to_rgb(STATE['hue'] / 100.0, STATE['saturation'] / 100.0, STATE['level'] / 100.0)
        ledto_r = r * 1023.0 * CONFIG['brightness_scale']
        ledto_g = g * 1023.0 * CONFIG['brightness_scale']
        ledto_b = b * 1023.0 * CONFIG['brightness_scale']
        # Ensure that brightness is equalized no matter what combination
        # of R/G/B are set.
        if STATE['brnorm']:
            total = r + g + b
            ledto_r = ledto_r * (r / total)
            ledto_g = ledto_g * (g / total)
            ledto_b = ledto_b * (b / total)
    else:
        ledto_r = 0
        ledto_g = 0
        ledto_b = 0
    fade_lights(int(ledto_r), int(ledto_g), int(ledto_b))


def parse_data(reqdata):
    return json.loads(reqdata)


def parse_user_state(j):
    soft_ignore = ('red', 'green', 'blue')
    tomerge = {}
    for k in j:
        if j[k] is None:
            continue
        if k in ('hex',):
            continue
        elif k in soft_ignore:
            pass
        elif k not in STATE:
            continue
        tomerge[k] = j[k]

    # Minimum 50ms needed if > 0
    if 'fadetime' in tomerge and tomerge['fadetime'] < 50:
        tomerge['fadetime'] = 50

    # If red/green/blue are provided, convert to hue/saturation/level
    if ('red' in tomerge) and ('green' in tomerge) and ('blue' in tomerge):
        h, s, v = rgb_to_hsv(tomerge['red'] / 255.0, tomerge['green'] / 255.0, tomerge['blue'] / 255.0)
        tomerge['hue'] = h * 100.0
        tomerge['saturation'] = s * 100.0
        tomerge['level'] = int(v * 100.0)

    for i in soft_ignore:
        if i in tomerge:
            del(tomerge[i])

    for k in tomerge:
        STATE[k] = tomerge[k]


def adjust_state():
    # Convert back to red/green/blue
    # (We don't use these keys directly, but provide them in responses)
    r, g, b = hsv_to_rgb(STATE['hue'] / 100.0, STATE['saturation'] / 100.0, STATE['level'] / 100.0)
    STATE['red'] = int(r * 255.0)
    STATE['green'] = int(g * 255.0)
    STATE['blue'] = int(b * 255.0)

    # "hex" is normalized assuming 100% level
    r, g, b = hsv_to_rgb(STATE['hue'] / 100.0, STATE['saturation'] / 100.0, 1.0)
    STATE['hex'] = '#{:02X}{:02X}{:02X}'.format(
        int(r * 255.0),
        int(g * 255.0),
        int(b * 255.0),
    )


def http_error(cl, code, desc):
    debug('ERROR: {} ({})'.format(desc, code))
    cl.write(b'HTTP/1.0 {} {}\r\n'.format(code, desc))
    if code == 401:
        cl.write(b'WWW-Authenticate: Basic realm="Login"\r\n')
    cl.write(b'\r\n{}\r\n'.format(desc))
    cl.close()


def process_connection(cl, addr):
    debug('New connection: {}'.format(addr))
    in_firstline = True
    in_dataarea = False
    httpmethod = None
    httpuri = None
    httpver = None
    httpauth = None
    reqdata = b''
    content_length = 0
    while True:
        if in_dataarea:
            while True:
                reqdata += cl.recv(1024)
                if len(reqdata) >= content_length:
                    break
            break
        line = cl.readline()
        if not line:
            break
        elif in_firstline:
            httpmethod, httpuri, httpver = line.split(b' ')
            in_firstline = False
        elif line.startswith(b'Content-Length: '):
            content_length = int(line[16:-2])
        elif line.startswith(b'Authorization: Basic '):
            httpauth = ubinascii.a2b_base64(line[21:-2]).split(b':', 1)[1].decode('ASCII')
        elif line == b'\r\n':
            if httpmethod in (b'POST', b'PUT'):
                in_dataarea = True
            else:
                break
    debug('IN: {} {} {} - {}'.format(httpmethod, httpuri, httpver, reqdata))

    if CONFIG['auth_secret']:
        if (httpauth is None) or (httpauth != CONFIG['auth_secret']):
            http_error(cl, 401, 'Unauthorized')
            return

    if httpuri == b'/command':
        if httpmethod != b'POST':
            http_error(cl, 400, 'Bad Request')
            return
    else:
        http_error(cl, 404, 'Not Found')
        return

    try:
        j = parse_data(reqdata)
    except:
        http_error(cl, 500, 'Internal Server Error')
        return
    if 'state' in j:
        parse_user_state(j['state'])

    adjust_state()

    uname = os.uname()
    response = json.dumps({
        'state': STATE,
        'sysinfo': {
            'id': ubinascii.hexlify(machine.unique_id()).decode('ASCII'),
            'freq': str(machine.freq()),
            'release': uname.release,
            'version': uname.version,
            'machine': uname.machine,
        },
    }).encode('ASCII')
    debug('OUT: {}'.format(response))
    cl.write(b'HTTP/1.1 200 OK\r\n')
    cl.write(b'Content-Type: application/json; charset=utf-8\r\n')
    cl.write(b'Content-Length: ' + str(len(response)).encode('ASCII') + b'\r\n')
    cl.write(b'\r\n')
    cl.write(response)
    cl.close()
    if 'cmd' in j:
        if j['cmd'] == 'reset':
            time.sleep(1)
            machine.reset()
            return
        if j['cmd'] == 'demo':
            demo_lights()
    set_lights()


def parse_config():
    global CONFIG

    try:
        with open('demirgb.json') as f:
            conf = json.load(f)
    except:
        return

    for k, v in conf.items():
        CONFIG[k] = v


def main():
    global SYSLOG_SOCKET

    parse_config()

    if CONFIG['syslog_host']:
        SYSLOG_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    init_lights()

    addr = socket.getaddrinfo(CONFIG['listen_addr'], CONFIG['listen_port'])[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    debug('Listen: {}'.format(addr))

    while True:
        debug('Memory free (before GC): {}'.format(gc.mem_free()))
        gc.collect()
        debug('Memory free (after GC):  {}'.format(gc.mem_free()))
        try:
            process_connection(*s.accept())
        except KeyboardInterrupt:
            s.close()
            break
        except Exception as e:
            debug('Caught exception: {}'.format(e))
        debug('')
