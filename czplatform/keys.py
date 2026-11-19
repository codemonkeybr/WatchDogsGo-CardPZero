"""Keyboard: evdev events from the CardputerZero's TCA8418 -> pyxel key state.

The kernel overlay already translates the keyboard layers: with ``fn`` held,
Z/X/C/F arrive as real LEFT/DOWN/RIGHT/UP, K/N as HOME/END, L/M as PAGEUP/DOWN,
number keys as F1-F10 (verified live for the arrows). The ``fn`` key itself
reports code 389, which we ignore.

pyxel's ``KEY_*`` constants are SDL keycodes (letters/digits are ASCII), *not*
evdev codes, hence the table below. Events are injected with
``pyxel.set_btn(key, state)`` at the start of each ``update()``. A key that is
pressed and released inside one frame keeps its press visible for that frame
(the release is applied on the next one), so ``btnp`` never misses a tap.
"""
from __future__ import annotations

import logging
import os
import re
import struct

log = logging.getLogger("czplatform.keys")

EVENT = struct.Struct("llHHi")      # struct input_event on 64-bit Linux
EV_KEY = 1
FN_CODE = 389                       # the fn key's own event — ignored


def _build_map():
    names = {1: "ESCAPE", 12: "MINUS", 13: "EQUALS", 14: "BACKSPACE",
             15: "TAB", 26: "LEFTBRACKET", 27: "RIGHTBRACKET", 28: "RETURN",
             29: "LCTRL", 39: "SEMICOLON", 40: "QUOTE", 41: "BACKQUOTE",
             42: "LSHIFT", 43: "BACKSLASH", 51: "COMMA", 52: "PERIOD",
             53: "SLASH", 54: "RSHIFT", 55: "KP_MULTIPLY", 56: "LALT",
             57: "SPACE", 58: "CAPSLOCK", 74: "KP_MINUS", 78: "KP_PLUS",
             96: "KP_ENTER", 97: "RCTRL", 98: "KP_DIVIDE", 99: "PRINTSCREEN",
             100: "RALT", 102: "HOME", 103: "UP", 104: "PAGEUP", 105: "LEFT",
             106: "RIGHT", 107: "END", 108: "DOWN", 109: "PAGEDOWN",
             110: "INSERT", 111: "DELETE", 83: "KP_PERIOD"}
    for codes, letters in ((range(16, 26), "QWERTYUIOP"),
                           (range(30, 39), "ASDFGHJKL"),
                           (range(44, 51), "ZXCVBNM"),
                           (range(2, 11), "123456789")):
        names.update(dict(zip(codes, letters)))
    names[11] = "0"
    names.update({59 + i: f"F{i + 1}" for i in range(10)})
    names.update({87: "F11", 88: "F12"})
    for code, d in ((71, 7), (72, 8), (73, 9), (75, 4), (76, 5), (77, 6),
                    (79, 1), (80, 2), (81, 3), (82, 0)):
        names[code] = f"KP_{d}"
    return {c: f"KEY_{n}" for c, n in names.items()}


EVDEV_TO_PYXEL_NAME = _build_map()


def find_keyboard():
    """Path of the TCA8418 event node (falls back to M5's stable symlink)."""
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


class KeyInjector:
    """Reads evdev non-blockingly and feeds ``pyxel.set_btn``."""

    def __init__(self, pyxel_module, device=None):
        self.pyxel = pyxel_module
        self.keymap = {}
        for code, name in EVDEV_TO_PYXEL_NAME.items():
            key = getattr(pyxel_module, name, None)
            if key is not None:
                self.keymap[code] = key
        self.filter = None          # optional ``f(code, value) -> bool``: True = consumed
        self._deferred = set()
        self._down_now = set()
        self._unmapped = set()
        self.device = device or find_keyboard()
        self._fd = os.open(self.device, os.O_RDONLY | os.O_NONBLOCK)
        log.info("keyboard %s (%d keys mapped)", self.device, len(self.keymap))

    def poll(self):
        """Call at the start of every ``update()``."""
        for key in self._deferred:
            self.pyxel.set_btn(key, False)
        self._deferred.clear()
        self._down_now.clear()
        try:
            data = os.read(self._fd, EVENT.size * 64)
        except BlockingIOError:
            return
        for off in range(0, len(data) - EVENT.size + 1, EVENT.size):
            _s, _us, typ, code, val = EVENT.unpack_from(data, off)
            if typ == EV_KEY and code != FN_CODE:
                self._apply(code, val)

    def _apply(self, code, val):
        if self.filter is not None and self.filter(code, val):
            return
        key = self.keymap.get(code)
        if key is None:
            if code not in self._unmapped:
                self._unmapped.add(code)
                log.info("unmapped evdev key code %d", code)
            return
        if val == 1:                                # press
            self._deferred.discard(key)
            self.pyxel.set_btn(key, True)
            self._down_now.add(key)
        elif val == 0:                              # release
            if key in self._down_now:
                self._deferred.add(key)             # keep the press visible
            else:
                self.pyxel.set_btn(key, False)
        # val == 2 (auto-repeat): pyxel's btnp(hold, repeat) does its own

    def close(self):
        os.close(self._fd)
