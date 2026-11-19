"""Swap the desktop pieces of pyxel that the vendored game relies on.

The game (``watchdogs/app.py``) calls ``pyxel.init(W, H, ..., display_scale=2)``,
``pyxel.fullscreen(True)``, ``pyxel.mouse(False)`` and finally
``pyxel.run(update, draw)`` from its constructor. ``Runtime.install`` replaces
those module attributes *before* the game is constructed, so the game's code
needs no change:

* ``init``  -> headless pyxel (no window, no OpenGL) + tell the panel the canvas size
* ``run``   -> the real loop with two wrappers: ``update`` first injects the
               keyboard and honours SIGINT/SIGTERM (running the game's own
               ``_cleanup()``), ``draw`` pushes the finished frame to the panel
* ``fullscreen`` / ``mouse`` -> no-ops

``pyxel.quit()`` ends the process (``atexit`` handlers still run); nothing after
it executes, so cleanup must happen *before* calling it.
"""
from __future__ import annotations

import logging
import os
import time

log = logging.getLogger("czplatform.shim")


def rss_mib():
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


class Runtime:
    def __init__(self, pyxel, panel, keys=None, png=None, frames=0,
                 stats_every=5.0):
        self.pyxel = pyxel
        self.panel = panel
        self.keys = keys
        self.png = png
        self.frames = frames
        self.stats_every = stats_every
        self.stop_requested = False
        self.game = None
        self.frame = 0
        self._real_run = None
        self._reset_window(time.perf_counter())

    # -- installation --------------------------------------------------------

    def install(self):
        px = self.pyxel
        real_init = px.init
        self._real_run = px.run

        def init(width, height, title=None, fps=None, quit_key=None,
                 display_scale=None, capture_scale=None, capture_sec=None,
                 headless=None):
            kwargs = {"headless": True}
            if title is not None:
                kwargs["title"] = title
            if fps is not None:
                kwargs["fps"] = fps
            if quit_key is not None:
                kwargs["quit_key"] = quit_key
            real_init(width, height, **kwargs)
            self.panel.set_canvas(width, height)
            log.info("pyxel headless %dx%d @ %s fps -> panel view '%s'",
                     width, height, fps, self.panel.view_mode)

        px.init = init
        px.fullscreen = lambda *a, **k: None
        px.mouse = lambda *a, **k: None
        px.run = self.run

    def request_stop(self, *_args):
        """Signal handler: only sets a flag; ``update`` does the shutdown."""
        self.stop_requested = True

    # -- main loop -----------------------------------------------------------

    def run(self, update, draw):
        self.game = getattr(update, "__self__", None)

        def update_wrapper():
            if self.keys is not None:
                self.keys.poll()
            if self.stop_requested:
                self.shutdown("signal")
            update()

        def draw_wrapper():
            t0 = time.perf_counter()
            draw()
            t1 = time.perf_counter()
            raw = bytes(self.pyxel.screen.data_ptr())
            self.panel.present(raw, list(self.pyxel.colors))
            t2 = time.perf_counter()
            self._account(t0, t1, t2)
            if self.png and self.frame >= self.frames:
                self._capture()

        self._real_run(update_wrapper, draw_wrapper)

    # -- bookkeeping ---------------------------------------------------------

    def _reset_window(self, now):
        self._win_t0 = now
        self._win_cpu0 = time.process_time()
        self._win_frames = 0
        self._win_draw = 0.0
        self._win_present = 0.0

    def _account(self, t0, t1, t2):
        self.frame += 1
        self._win_frames += 1
        self._win_draw += t1 - t0
        self._win_present += t2 - t1
        dt = t2 - self._win_t0
        if dt >= self.stats_every:
            n = self._win_frames
            log.info("fps=%.1f draw=%.1fms present=%.1fms cpu=%.0f%% rss=%.0fMiB",
                     n / dt, 1000 * self._win_draw / n,
                     1000 * self._win_present / n,
                     100 * (time.process_time() - self._win_cpu0) / dt,
                     rss_mib())
            self._reset_window(t2)

    def _capture(self):
        try:
            self.panel.save_png(self.png)
            canvas = os.path.splitext(self.png)[0] + "-canvas.png"
            self.pyxel.screen.save(canvas, 1)
            log.info("captured %s (+ %s)", self.png, canvas)
        except Exception:
            log.exception("capture failed")
        self.shutdown("capture done")

    # -- shutdown ------------------------------------------------------------

    def shutdown(self, reason):
        """Run the game's own cleanup, then end the process."""
        log.info("shutting down: %s (frame %d, rss %.0f MiB)", reason,
                 self.frame, rss_mib())
        cleanup = getattr(self.game, "_cleanup", None)
        if callable(cleanup):
            try:
                cleanup()
            except Exception:
                log.exception("game cleanup failed")
        self.pyxel.quit()
