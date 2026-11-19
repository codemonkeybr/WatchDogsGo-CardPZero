"""Unit tests for czplatform — no hardware needed.

  .venv/bin/python -m unittest discover -s tests -v
"""
import os
import struct
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pyxel                                            # noqa: E402

from czplatform import display, keys, shim              # noqa: E402


class TablesTest(unittest.TestCase):
    def test_rgb565_little_endian_bytes(self):
        lo, hi = display.build_tables(
            [0x000000, 0xFF0000, 0x00FF00, 0x0000FF, 0xFFFFFF])
        px = lambda i: lo[i] | (hi[i] << 8)             # noqa: E731
        self.assertEqual(px(0), 0x0000)
        self.assertEqual(px(1), 0xF800)                 # red
        self.assertEqual(px(2), 0x07E0)                 # green
        self.assertEqual(px(3), 0x001F)                 # blue
        self.assertEqual(px(4), 0xFFFF)                 # white
        self.assertEqual((lo[1], hi[1]), (0x00, 0xF8))  # low byte first


class ViewTest(unittest.TestCase):
    W, H = display.PANEL_W, display.PANEL_H

    def canvas(self, cw, ch):
        return bytes((x * 3 + y * 5) & 15 for y in range(ch) for x in range(cw))

    def test_identity_returns_the_same_buffer(self):
        raw = bytes(self.W * self.H)
        self.assertIs(display.make_view(self.W, self.H)(raw), raw)

    def test_crop_takes_the_top_left_window(self):
        raw = self.canvas(640, 360)
        out = display.make_view(640, 360, "crop")(raw)
        self.assertEqual(len(out), self.W * self.H)
        for x, y in ((0, 0), (319, 0), (0, 169), (123, 77), (319, 169)):
            self.assertEqual(out[y * self.W + x], raw[y * 640 + x])

    def test_scale_640x360_is_nearest_neighbour(self):
        raw = self.canvas(640, 360)
        out = display.make_view(640, 360, "scale")(raw)
        self.assertEqual(len(out), self.W * self.H)
        for x, y in ((0, 0), (319, 169), (10, 20), (200, 100), (1, 168)):
            sy = min(359, y * 360 // self.H)
            self.assertEqual(out[y * self.W + x], raw[sy * 640 + 2 * x])

    def test_scale_non_integer_factor(self):
        raw = self.canvas(400, 200)
        out = display.make_view(400, 200, "scale")(raw)
        self.assertEqual(len(out), self.W * self.H)
        for x, y in ((0, 0), (319, 169), (77, 33), (250, 120)):
            sx, sy = min(399, x * 400 // self.W), min(199, y * 200 // self.H)
            self.assertEqual(out[y * self.W + x], raw[sy * 400 + sx])

    def test_crop_rejects_a_canvas_smaller_than_the_panel(self):
        with self.assertRaises(ValueError):
            display.make_view(200, 100, "crop")


class PanelTest(unittest.TestCase):
    def test_a_regular_file_acts_as_a_framebuffer(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "fb")
            panel = display.Panel(path, view="crop")
            panel.set_canvas(self.W, self.H)
            panel.present(bytes([1]) * (self.W * self.H), [0x000000, 0xFF0000])
            panel.close()
            with open(path, "rb") as f:
                data = f.read()
        self.assertEqual(len(data), display.FRAME_BYTES)
        self.assertEqual(data[:2], b"\x00\xf8")           # red, little endian
        self.assertEqual(data[-2:], b"\x00\xf8")

    W, H = display.PANEL_W, display.PANEL_H


class KeymapTest(unittest.TestCase):
    def test_every_mapped_name_exists_in_pyxel(self):
        missing = {c: n for c, n in keys.EVDEV_TO_PYXEL_NAME.items()
                   if not hasattr(pyxel, n)}
        self.assertEqual(missing, {})

    def test_the_arrows_and_navigation_keys_are_mapped(self):
        for code, name in ((103, "UP"), (108, "DOWN"), (105, "LEFT"),
                           (106, "RIGHT"), (104, "PAGEUP"), (109, "PAGEDOWN"),
                           (102, "HOME"), (107, "END"), (1, "ESCAPE"),
                           (28, "RETURN"), (15, "TAB"), (57, "SPACE")):
            self.assertEqual(keys.EVDEV_TO_PYXEL_NAME[code], f"KEY_{name}")

    def test_letters_and_digits_follow_the_keyboard_layout(self):
        self.assertEqual(keys.EVDEV_TO_PYXEL_NAME[16], "KEY_Q")
        self.assertEqual(keys.EVDEV_TO_PYXEL_NAME[30], "KEY_A")
        self.assertEqual(keys.EVDEV_TO_PYXEL_NAME[44], "KEY_Z")
        self.assertEqual(keys.EVDEV_TO_PYXEL_NAME[2], "KEY_1")
        self.assertEqual(keys.EVDEV_TO_PYXEL_NAME[11], "KEY_0")


class FakePyxel:
    """Real pyxel constants, recording ``set_btn`` and ``quit`` calls."""

    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        return getattr(pyxel, name)

    def set_btn(self, key, state):
        self.calls.append((key, state))

    def quit(self):
        self.calls.append("quit")


def event(code, value):
    return struct.pack("llHHi", 0, 0, keys.EV_KEY, code, value)


class InjectorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "events")
        os.mkfifo(self.path)
        self.fake = FakePyxel()
        self.inj = keys.KeyInjector(self.fake, device=self.path)
        self.writer = os.open(self.path, os.O_WRONLY | os.O_NONBLOCK)

    def tearDown(self):
        os.close(self.writer)
        self.inj.close()
        self.tmp.cleanup()

    def send(self, *events):
        os.write(self.writer, b"".join(events))

    def test_press_and_release_in_one_frame_keeps_the_press_visible(self):
        left = pyxel.KEY_LEFT
        self.send(event(105, 1), event(105, 0))
        self.inj.poll()
        self.assertEqual(self.fake.calls, [(left, True)])
        self.inj.poll()                                  # next frame: release
        self.assertEqual(self.fake.calls, [(left, True), (left, False)])

    def test_release_in_a_later_frame_is_immediate(self):
        a = pyxel.KEY_A
        self.send(event(30, 1))
        self.inj.poll()
        self.send(event(30, 0))
        self.inj.poll()
        self.assertEqual(self.fake.calls, [(a, True), (a, False)])

    def test_the_fn_key_and_autorepeat_are_ignored(self):
        self.send(event(keys.FN_CODE, 1), event(keys.FN_CODE, 0),
                  event(105, 2))
        self.inj.poll()
        self.assertEqual(self.fake.calls, [])

    def test_unknown_codes_are_ignored(self):
        self.send(event(250, 1))
        self.inj.poll()
        self.assertEqual(self.fake.calls, [])

    def test_repress_cancels_a_deferred_release(self):
        left = pyxel.KEY_LEFT
        self.send(event(105, 1), event(105, 0), event(105, 1))
        self.inj.poll()
        self.inj.poll()
        self.assertEqual(self.fake.calls, [(left, True), (left, True)])


class ShutdownTest(unittest.TestCase):
    def test_cleanup_runs_before_quit(self):
        order = []
        fake = FakePyxel()
        fake.quit = lambda: order.append("quit")

        class Game:
            def _cleanup(self):
                order.append("cleanup")

        rt = shim.Runtime(fake, panel=None)
        rt.game = Game()
        rt.shutdown("test")
        self.assertEqual(order, ["cleanup", "quit"])

    def test_a_failing_cleanup_still_quits(self):
        order = []
        fake = FakePyxel()
        fake.quit = lambda: order.append("quit")

        class Game:
            def _cleanup(self):
                raise RuntimeError("boom")

        rt = shim.Runtime(fake, panel=None)
        rt.game = Game()
        rt.shutdown("test")
        self.assertEqual(order, ["quit"])


if __name__ == "__main__":
    unittest.main()
