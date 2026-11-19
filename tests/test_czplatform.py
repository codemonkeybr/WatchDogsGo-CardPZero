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

    def test_a_tap_presses_and_releases_on_the_next_poll(self):
        self.inj.tap(28)
        self.assertEqual(self.fake.calls, [(pyxel.KEY_RETURN, True)])
        self.inj.poll()
        self.assertEqual(self.fake.calls,
                         [(pyxel.KEY_RETURN, True), (pyxel.KEY_RETURN, False)])
        self.inj.poll()                                  # and nothing more
        self.assertEqual(len(self.fake.calls), 2)

    def test_the_filter_can_consume_events(self):
        seen = []
        self.inj.filter = lambda code, value: seen.append((code, value)) or code == 28
        self.send(event(28, 1), event(105, 1))
        self.inj.poll()
        self.assertEqual(seen, [(28, 1), (105, 1)])
        self.assertEqual(self.fake.calls, [(pyxel.KEY_LEFT, True)])   # ENTER never got through

    def test_a_tap_goes_through_the_filter_too(self):
        self.inj.filter = lambda code, value: True
        self.inj.tap(28)
        self.inj.poll()
        self.assertEqual(self.fake.calls, [])

    def test_names_map_back_to_evdev_codes(self):
        self.assertEqual(keys.NAME_TO_EVDEV["RETURN"], 28)
        self.assertEqual(keys.NAME_TO_EVDEV["TAB"], 15)
        self.assertEqual(keys.NAME_TO_EVDEV["UP"], 103)


class ControlTest(unittest.TestCase):
    """``--control``: script steps arriving through a FIFO into a running game."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.fifo = os.path.join(self.tmp.name, "ctl")
        self.fake = FakePyxel()
        self.rt = shim.Runtime(self.fake, panel=None, control=self.fifo)

    def tearDown(self):
        os.close(self.rt._ctl_fd)
        os.close(self.rt._ctl_keep)
        self.tmp.cleanup()

    def write(self, text):
        os.write(self.rt._ctl_keep, text.encode())

    def test_lines_become_script_steps(self):
        self.write("key:RETURN,wait:5\nkey:TAB\n")
        self.rt._read_control()
        self.assertEqual(list(self.rt.script), ["key:RETURN", "wait:5", "key:TAB"])
        self.assertTrue(self.rt._script_on)

    def test_an_empty_pipe_adds_nothing(self):
        self.rt._read_control()
        self.assertEqual(list(self.rt.script), [])

    def test_control_mode_does_not_quit_when_the_steps_run_out(self):
        self.write("wait:1")
        self.rt._read_control()
        for _ in range(3):
            self.rt._step_script()
        self.assertNotIn("quit", self.fake.calls)

    def test_a_plain_script_quits_when_it_ends(self):
        rt = shim.Runtime(self.fake, panel=None, script=["wait:1"])
        rt._step_script()
        rt._step_script()
        self.assertIn("quit", self.fake.calls)

    def test_script_keys_use_the_keyboard_path_when_there_is_one(self):
        path = os.path.join(self.tmp.name, "events")
        os.mkfifo(path)
        inj = keys.KeyInjector(self.fake, device=path)
        self.addCleanup(inj.close)
        inj.filter = lambda code, value: code == 105     # consumes LEFT only
        rt = shim.Runtime(self.fake, panel=None, keys=inj,
                          script=["key:RETURN", "key:LEFT"])
        rt._step_script()
        self.assertEqual(self.fake.calls, [(pyxel.KEY_RETURN, True)])
        inj.poll()                                       # release
        rt._script_wait = 0
        rt._step_script()
        self.assertEqual(self.fake.calls[-1], (pyxel.KEY_RETURN, False))
        self.assertNotIn((pyxel.KEY_LEFT, True), self.fake.calls)   # consumed


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
