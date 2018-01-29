# DemiRGB Firmware
# Copyright (C) 2018 Velociraptor Aerospace Dynamics
# This is free software; for details, please see COPYING.

def recv(file=None, port=9999):
    import usocket as socket
    try:
        import network
        print('Station: {}'.format(network.WLAN(network.STA_IF).ifconfig()))
        print('AP: {}'.format(network.WLAN(network.AP_IF).ifconfig()))
    except:
        pass

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(socket.getaddrinfo('0.0.0.0', port)[0][-1])
    s.listen(1)
    print('Listening on port {}'.format(port))

    while True:
        (cl, addr) = s.accept()
        print('Accepted from {}'.format(addr))
        if file is None:
            header = cl.readline()
            if not header.startswith('RECV:'):
                print('file not provided on recv() call or as header')
                cl.close()
                continue
            fn = header.rstrip()[5:]
        else:
            fn = file
        print('New connection: {}'.format(addr))
        f = open(fn, 'w')
        written = 0
        while True:
            buf = cl.recv(1024)
            if not buf:
                break
            f.write(buf)
            written += len(buf)
        f.close()
        cl.close()
        print('{} bytes written to {}'.format(written, fn))
    s.close()
