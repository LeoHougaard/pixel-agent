#!/usr/bin/env python3
"""Report the X server's real input clock to the Termux idle monitor."""
import ctypes as C
import json
import os
from pathlib import Path
import time


class SaverInfo(C.Structure):
    _fields_ = [('window', C.c_ulong), ('state', C.c_int), ('kind', C.c_int),
                ('til_or_since', C.c_ulong), ('idle', C.c_ulong), ('eventMask', C.c_ulong)]


def main():
    os.umask(0o077)
    target = Path('/tmp/pixel-desktop-activity.json')
    x11, xss = C.CDLL('libX11.so.6'), C.CDLL('libXss.so.1')
    x11.XOpenDisplay.argtypes = [C.c_char_p]
    x11.XOpenDisplay.restype = C.c_void_p
    x11.XDefaultRootWindow.argtypes = [C.c_void_p]
    x11.XDefaultRootWindow.restype = C.c_ulong
    x11.XInternAtom.argtypes = [C.c_void_p, C.c_char_p, C.c_int]
    x11.XInternAtom.restype = C.c_ulong
    x11.XGetSelectionOwner.argtypes = [C.c_void_p, C.c_ulong]
    x11.XGetSelectionOwner.restype = C.c_ulong
    xss.XScreenSaverQueryInfo.argtypes = [C.c_void_p, C.c_ulong, C.POINTER(SaverInfo)]
    display = x11.XOpenDisplay(b':1')
    if not display:
        raise RuntimeError('Desktop display is unavailable')
    root = x11.XDefaultRootWindow(display)
    wm = x11.XInternAtom(display, b'WM_S0', 0)
    info = SaverInfo()
    while True:
        if not xss.XScreenSaverQueryInfo(display, root, C.byref(info)):
            raise RuntimeError('Desktop input clock is unavailable')
        data = {'time': time.time(), 'idle_seconds': info.idle / 1000,
                'ready': bool(x11.XGetSelectionOwner(display, wm))}
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(data))
        temporary.replace(target)
        time.sleep(3)


if __name__ == '__main__':
    main()
