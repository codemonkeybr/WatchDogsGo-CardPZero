#!/usr/bin/env python3
"""CardputerZero launcher-integration demo (ROADMAP 0.1b / 1.3 / 1.7 / 3.x).

Start it FROM the APPLaunch carousel (a `.desktop` entry with Terminal=false —
see tools/make-dev-entry.sh). For such entries the launcher forks/execs the
program and pauses its own screen refresh while it runs (M5's APPLaunch
packaging guide), so what we draw stays on the panel.

It follows the pattern of M5's own framebuffer / Python examples: draw into
/dev/fb0 through mmap and read the TCA8418 keyboard from evdev. Frames come
from headless pyxel (palette-index buffer -> RGB565). The last key events are
shown on screen and logged to a file, so the fn layer can be checked live.

Exit: ESC, the --seconds timeout, or SIGINT/SIGTERM (the launcher sends SIGINT
after a 5 s long-press of Home (fn+K), then SIGKILL 3 s later).
"""
import argparse
import collections
import fcntl
import math
import mmap
import os
import re
import signal
import struct
import sys
import time

W, H = 320, 170
FBIOGET_VSCREENINFO = 0x4600
EV_KEY = 1
EVENT = struct.Struct("llHHi")          # struct input_event, 64-bit Linux
STOP = {"flag": False}


def key_names():
    names = {1: "ESC", 14: "BACKSPACE", 15: "TAB", 28: "ENTER", 57: "SPACE",
             29: "LCTRL", 42: "LSHIFT", 54: "RSHIFT", 56: "LALT", 58: "CAPS",
             102: "HOME", 103: "UP", 104: "PAGEUP", 105: "LEFT", 106: "RIGHT",
             107: "END", 108: "DOWN", 109: "PAGEDOWN", 110: "INSERT",
             111: "DELETE", 99: "PRINT", 87: "F11", 88: "F12",
             113: "MUTE", 114: "VOL-", 115: "VOL+", 163: "NEXT",
             164: "PLAYPAUSE", 165: "PREV", 41: "`", 12: "-", 13: "=",
             26: "[", 27: "]", 39: ";", 40: "'", 43: "\\", 51: ",", 52: ".",
             53: "/"}
    for codes, letters in ((range(16, 26), "qwertyuiop"),
                           (range(30, 39), "asdfghjkl"),
                           (range(44, 51), "zxcvbnm"),
                           (range(2, 12), "1234567890")):
        names.update(dict(zip(codes, letters)))
    names.update({59 + i: f"F{i + 1}" for i in range(10)})
    return names


KEYNAMES = key_names()


def find_keyboard():
    try:
        text = open("/proc/bus/input/devices").read()
    except OSError:
        text = ""
    for block in text.split("\n\n"):
        if 'Name="tca8418c"' in block:
            m = re.search(r"event(\d+)", block)
            if m:
                return f"/dev/input/event{m.group(1)}"
    return "/dev/input/cardputer-zero-internal"


def fb_format(fd):
    v = fcntl.ioctl(fd, FBIOGET_VSCREENINFO, bytes(160))
    xres, yres, _xv, _yv, _xo, _yo, bpp, _g = struct.unpack_from("8I", v, 0)
    return (xres, yres, bpp, struct.unpack_from("3I", v, 32),
            struct.unpack_from("3I", v, 44), struct.unpack_from("3I", v, 56))


def build_tables(palette, red, green, blue):
    lo, hi = bytearray(256), bytearray(256)
    for i, rgb in enumerate(palette):
        r, g, b = (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255
        px = (((r >> (8 - red[1])) << red[0]) | ((g >> (8 - green[1])) << green[0])
              | ((b >> (8 - blue[1])) << blue[0]))
        lo[i], hi[i] = px & 255, px >> 8
    return bytes(lo), bytes(hi)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--assets", required=True, help="dir with spleen-5x8.bdf")
    ap.add_argument("--seconds", type=float, default=120.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--fb", default="/dev/fb0")
    ap.add_argument("--input", default=None, help="evdev node (default: auto)")
    ap.add_argument("--log", default=os.path.expanduser("~/cz-demo.log"))
    args = ap.parse_args()
    # pyxel changes the working directory to the script's folder when it
    # starts, so resolve every user-supplied path before that happens.
    args.assets = os.path.abspath(args.assets)
    args.log = os.path.abspath(args.log)

    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: STOP.update(flag=True))

    import pyxel

    log = open(args.log, "w", buffering=1)

    def say(msg):
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        log.write(line + "\n")
        print(line, flush=True)

    fb_fd = os.open(args.fb, os.O_RDWR)
    xres, yres, bpp, red, green, blue = fb_format(fb_fd)
    if (xres, yres, bpp) != (W, H, 16):
        say(f"FAIL: framebuffer is {xres}x{yres}@{bpp}, expected 320x170@16")
        return 1
    fbmap = mmap.mmap(fb_fd, W * H * 2, mmap.MAP_SHARED,
                      mmap.PROT_READ | mmap.PROT_WRITE)
    kdev = args.input or find_keyboard()
    kfd = os.open(kdev, os.O_RDONLY | os.O_NONBLOCK)
    say(f"fb0 mmap ok; keyboard {kdev}; pid {os.getpid()}")

    pyxel.init(W, H, title="cz demo", fps=args.fps, headless=True)
    lo, hi = build_tables(list(pyxel.colors), red, green, blue)
    f5 = pyxel.Font(os.path.join(args.assets, "spleen-5x8.bdf"))
    st = {"n": 0, "t0": time.monotonic()}
    keys = collections.deque(maxlen=8)

    def poll_keys():
        try:
            data = os.read(kfd, EVENT.size * 64)
        except BlockingIOError:
            return
        for off in range(0, len(data) - EVENT.size + 1, EVENT.size):
            _s, _us, typ, code, val = EVENT.unpack_from(data, off)
            if typ != EV_KEY:
                continue
            name = KEYNAMES.get(code, f"KEY_{code}")
            state = {0: "up", 1: "down", 2: "hold"}.get(val, str(val))
            keys.append(f"{name} ({code}) {state}")
            say(f"key {name} code={code} {state}")
            if code == 1 and val == 1:
                STOP["flag"] = True

    def finish(reason):
        up = time.monotonic() - st["t0"]
        say(f"exit ({reason}) after {up:.1f}s, {st['n']} frames "
            f"({st['n'] / max(up, 0.001):.1f} fps)")
        say("DEMO RESULT: ok")
        log.close()
        pyxel.quit()

    def update():
        poll_keys()
        if STOP["flag"]:
            finish("signal/ESC")
        elif time.monotonic() - st["t0"] >= args.seconds:
            finish("timeout")

    def draw():
        n = st["n"]
        pyxel.cls(0)
        for x in range(0, W, 40):
            pyxel.line(x, 11, x, H - 11, 1)
        for y in range(11, H - 10, 30):
            pyxel.line(0, y, W, y, 1)
        cx = 20 + (n * 2) % (W - 40)
        cy = 40 + int(14 * math.sin(n / 12))
        pyxel.circb(cx, cy, 7, 3)
        pyxel.circ(cx, cy, 2, 7)
        pyxel.rect(0, 0, W, 10, 0)
        pyxel.text(1, 1, "WDG DEMO  fb0 + evdev via launcher", 3, f5)
        pyxel.text(W - 62, 1, f"{time.monotonic() - st['t0']:5.1f}s", 7, f5)
        pyxel.text(4, 62, "press keys (try fn+F/X/Z/C, fn+L/M);", 13, f5)
        pyxel.text(4, 71, "ESC exits, Home (fn+K) 5 s kills", 13, f5)
        for i, line in enumerate(reversed(keys)):
            pyxel.text(4, 84 + i * 9, line, 11 if i == 0 else 5, f5)
        pyxel.rect(0, H - 10, W, 10, 0)
        pyxel.text(1, H - 9, f"frame {n}", 10, f5)
        raw = bytes(pyxel.screen.data_ptr())
        out = bytearray(len(raw) * 2)
        out[0::2] = raw.translate(lo)
        out[1::2] = raw.translate(hi)
        fbmap[:] = out
        st["n"] += 1

    pyxel.run(update, draw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
