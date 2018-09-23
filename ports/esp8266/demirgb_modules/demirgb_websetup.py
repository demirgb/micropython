# DemiRGB Firmware
# Copyright (C) 2018 Velociraptor Aerospace Dynamics
# This is free software; for details, please see COPYING.

# Note that this file exceeds ESP8266 memory limitations if shipped
# verbatim to and run from the device.  It must be compiled with
# mpy-cross and the .mpy must be shipped to the device.

import socket
import time
import gc
import ubinascii
import network
import json


def debug(text):
    print(text)


def http_error(cl, code, desc):
    debug('ERROR: {} ({})'.format(desc, code))
    cl.write(b'HTTP/1.0 {} {}\r\n'.format(code, desc))
    cl.write(b'\r\n{}\r\n'.format(desc))
    cl.close()


def urldecode(input):
    def _d(i):
        o = ''
        l = len(i)
        pos = 0
        while pos < l:
            if i[pos] == '+':
                o += ' '
                pos += 1
            elif i[pos] == '%':
                o += ubinascii.unhexlify(i[pos+1:pos+3]).decode('ASCII')
                pos += 3
            else:
                o += i[pos]
                pos += 1
        return o
    output = {}
    for p in input.split('&'):
        ki, vi = p.split('=')
        output[_d(ki)] = _d(vi)
    return(output)


def process_connection(cl, addr):
    debug('New connection: {}'.format(addr))
    in_firstline = True
    in_dataarea = False
    httpmethod = None
    httpuri = None
    httpver = None
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
        elif line == b'\r\n':
            if httpmethod in (b'POST', b'PUT'):
                in_dataarea = True
            else:
                break
    debug('IN: {} {} {} - {}'.format(httpmethod, httpuri, httpver, reqdata))

    sta_if = network.WLAN(network.STA_IF)
    ap_if = network.WLAN(network.AP_IF)

    if httpuri == b'/':
        response = b'<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"></head><body><a href="/config">Configure</a></body></html>'
        cl.write(b'HTTP/1.1 200 OK\r\n')
        cl.write(b'Content-Type: text/html\r\n')
        cl.write(b'Content-Length: ' + str(len(response)).encode('ASCII') + b'\r\n')
        cl.write(b'\r\n')
        cl.write(response)
        cl.close()
        return
    elif httpuri == b'/config_apply':
        if httpmethod != b'POST':
            http_error(cl, 404, 'Not Found')
            return
        try:
            urldata = urldecode(reqdata.decode('ASCII'))
        except:
            http_error(cl, 500, 'Internal Server Error')
            return
        response = b'<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"></head><body>Applying and resetting (10s), <a href="/config">go back</a></body></html>'
        cl.write(b'HTTP/1.1 200 OK\r\n')
        cl.write(b'Content-Type: text/html\r\n')
        cl.write(b'Content-Length: ' + str(len(response)).encode('ASCII') + b'\r\n')
        cl.write(b'\r\n')
        cl.write(response)
        cl.close()
        time.sleep(1)
        debug(urldata)
        enable_ap = (True if ('enable_ap' in urldata and urldata['enable_ap']) else False)
        if ap_if.active() != enable_ap:
            debug('Setting AP to {}'.format(enable_ap))
            ap_if.active(enable_ap)
        enable_sta = (True if ('enable_sta' in urldata and urldata['enable_sta']) else False)
        if sta_if.active() != enable_sta:
            debug('Setting STA to {}'.format(enable_sta))
            sta_if.active(enable_sta)
        if (
            'ap_essid' in urldata and urldata['ap_essid'] and
            'ap_password' in urldata and urldata['ap_password']
        ):
            essid = urldata['ap_essid'].encode('ASCII')
            password = urldata['ap_password'].encode('ASCII')
            debug('Configuring AP: {} - {}'.format(essid, password))
            ap_if.config(
                essid=essid,
                authmode=network.AUTH_WPA_WPA2_PSK,
                password=password,
            )
        if (
            'sta_essid' in urldata and urldata['sta_essid'] and
            'sta_password' in urldata and urldata['sta_password']
        ):
            debug('Configuring STA: {} - {}'.format(urldata['sta_essid'], urldata['sta_password']))
            sta_if.connect(urldata['sta_essid'], urldata['sta_password'])
        if 'auth_secret' in urldata:
            try:
                with open('demirgb.json') as f:
                    conf = json.load(f)
            except ImportError:
                conf = {}
            conf['auth_secret'] = urldata['auth_secret']
            with open('demirgb.json', 'w') as f:
                f.write(json.dumps(conf))
    elif httpuri == b'/config':
        try:
            with open('demirgb.json') as f:
                conf = json.load(f)
        except ImportError:
            conf = {}
        auth_secret = ''
        if ('auth_secret' in conf) and conf['auth_secret']:
            auth_secret = conf['auth_secret']
        ap_mac_h = ubinascii.hexlify(ap_if.config('mac')).decode('ASCII')
        sta_mac_h = ubinascii.hexlify(sta_if.config('mac')).decode('ASCII')
        response = b"""\
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"></head><body>
<form method="post" action="/config_apply">
Enable Wifi client: <input type="checkbox" name="enable_sta"{enable_sta}><ul>
<li>MAC address: {sta_mac}
<li>Connected: {sta_connected}
<li>ESSID: <input name="sta_essid">
<li>Password: <input type="password" name="sta_password"></ul>
Enable access point: <input type="checkbox" name="enable_ap"{enable_ap}><ul>
<li>MAC address: {ap_mac}
<li>ESSID: <input name="ap_essid" value="{ap_essid}">
<li>Password: <input type="password" name="ap_password"></ul>
Set device password: <input type="password" name="auth_secret" value="{auth_secret}"><br><br>
<input type="submit">
</form>
</body></html>
""".format(
            sta_mac=(
                sta_mac_h[0:2] + ':' + sta_mac_h[2:4] + ':' + sta_mac_h[4:6] + ':' +
                sta_mac_h[6:8] + ':' + sta_mac_h[8:10] + ':' + sta_mac_h[10:12]
            ),
            ap_mac=(
                ap_mac_h[0:2] + ':' + ap_mac_h[2:4] + ':' + ap_mac_h[4:6] + ':' +
                ap_mac_h[6:8] + ':' + ap_mac_h[8:10] + ':' + ap_mac_h[10:12]
            ),
            enable_sta=(' checked' if sta_if.active() else ''),
            enable_ap=(' checked' if ap_if.active() else ''),
            sta_connected=('Yes, {}'.format(sta_if.ifconfig()[0]) if sta_if.isconnected() else 'No'),
            ap_essid=ap_if.config('essid'),
            auth_secret=auth_secret,
        )
        cl.write(b'HTTP/1.1 200 OK\r\n')
        cl.write(b'Content-Type: text/html\r\n')
        cl.write(b'Content-Length: ' + str(len(response)).encode('ASCII') + b'\r\n')
        cl.write(b'\r\n')
        cl.write(response)
        cl.close()
    else:
        http_error(cl, 404, 'Not Found')


def main():
    addr = socket.getaddrinfo('0.0.0.0', 80)[0][-1]
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
