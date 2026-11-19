"""Tests for the pure parts of czplatform.ui320 (log window, scrolling, key filter)."""
import sys
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from czplatform import ui320                             # noqa: E402


class LogGeometryTest(unittest.TestCase):
    def test_rows_for_the_panel(self):
        # 170 px: HUD 10 + 10, a title row, then 9 px lines
        self.assertEqual(ui320.log_rows(170, 10, 10), 15)

    def test_window_shows_the_newest_lines_at_the_bottom(self):
        self.assertEqual(ui320.log_window(100, 0, 15), (85, 100))
        self.assertEqual(ui320.log_window(10, 0, 15), (0, 10))    # fewer than a page

    def test_scrolled_window_moves_up(self):
        self.assertEqual(ui320.log_window(100, 20, 15), (65, 80))

    def test_scroll_is_clamped_to_the_oldest_page(self):
        self.assertEqual(ui320.clamp_scroll(999, 100, 15), 85)
        self.assertEqual(ui320.clamp_scroll(-5, 100, 15), 0)
        self.assertEqual(ui320.clamp_scroll(7, 10, 15), 0)        # nothing to scroll
        self.assertEqual(ui320.log_window(100, 999, 15), (0, 15))


class FilterTest(unittest.TestCase):
    def setUp(self):
        from watchdogs import app
        for name, value in (("H", 170), ("HUD_TOP", 10), ("HUD_BOT", 10)):
            patcher = mock.patch.object(app, name, value)   # the 320x170 panel
            patcher.start()
            self.addCleanup(patcher.stop)
        self.game = SimpleNamespace(_cz_view="log", term_scroll=0,
                                    terminal_lines=["x"] * 100,
                                    _term_lock=threading.Lock())
        ui320._GAME[0] = self.game

    def tearDown(self):
        ui320._GAME[0] = None

    def test_nothing_is_consumed_outside_the_log_view(self):
        self.game._cz_view = "map"
        for code in (1, 103, 104, 105, 108):
            self.assertFalse(ui320.input_filter(code, 1))

    def test_no_game_yet_means_nothing_is_consumed(self):
        ui320._GAME[0] = None
        self.assertFalse(ui320.input_filter(103, 1))

    def test_arrows_and_pages_scroll_and_are_consumed(self):
        self.assertTrue(ui320.input_filter(103, 1))               # UP
        self.assertEqual(self.game.term_scroll, 1)
        self.assertTrue(ui320.input_filter(103, 2))               # auto-repeat
        self.assertEqual(self.game.term_scroll, 2)
        self.assertTrue(ui320.input_filter(108, 1))               # DOWN
        self.assertEqual(self.game.term_scroll, 1)
        self.assertTrue(ui320.input_filter(104, 1))               # PAGEUP: rows - 1
        self.assertEqual(self.game.term_scroll, 1 + 14)
        self.assertTrue(ui320.input_filter(107, 1))               # END: newest
        self.assertEqual(self.game.term_scroll, 0)
        self.assertTrue(ui320.input_filter(102, 1))               # HOME: oldest
        self.assertEqual(self.game.term_scroll, 85)

    def test_releases_are_swallowed_without_scrolling(self):
        self.assertTrue(ui320.input_filter(103, 0))
        self.assertEqual(self.game.term_scroll, 0)

    def test_left_right_never_reach_the_map(self):
        self.assertTrue(ui320.input_filter(105, 1))
        self.assertTrue(ui320.input_filter(106, 1))

    def test_esc_returns_to_the_map_and_is_consumed(self):
        self.game.term_scroll = 12
        self.assertTrue(ui320.input_filter(1, 1))
        self.assertEqual(self.game._cz_view, "map")
        self.assertEqual(self.game.term_scroll, 0)
        self.assertFalse(ui320.input_filter(1, 1))                # now it is the game's

    def test_other_keys_pass_through(self):
        for code in (15, 28, 57, 16):                             # TAB, ENTER, SPACE, Q
            self.assertFalse(ui320.input_filter(code, 1))


if __name__ == "__main__":
    unittest.main()
