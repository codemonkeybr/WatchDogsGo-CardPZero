#!/usr/bin/env python3
"""pyxel smoke test for the CardputerZero port (ROADMAP 0.1 / 0.2).

Checks, in order: pyxel imports, pyxel.init at 320x170 (optionally
headless), the WatchDogsGo BDF fonts load, text renders, the screen buffer
is readable, and a PNG can be written. Run it on the dev machine AND on the
device — a failure on the device is the useful result.

  python3 tools/pyxel-smoke.py --assets /path/to/WatchDogsGo/assets --out smoke.png
  python3 tools/pyxel-smoke.py --assets ... --out smoke.png --headless

Without --headless, pyxel opens an OpenGL window (needs a display server
and GL; on a bare framebuffer/SPI panel it panics at init, which is
exactly what 0.1 needs to find out). With --headless there is no window and
no GL; the frame is read back from pyxel.screen.
"""
import argparse
import os
import sys

W, H = 320, 170


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--assets", required=True,
                    help="dir containing spleen-5x8.bdf and font_8x8.bdf")
    ap.add_argument("--out", default="pyxel-smoke.png", help="PNG to write")
    ap.add_argument("--scale", type=int, default=3, help="PNG upscale factor")
    ap.add_argument("--headless", action="store_true",
                    help="pyxel.init(headless=True): no window, no OpenGL")
    args = ap.parse_args()

    try:
        import pyxel
    except ImportError as exc:
        print(f"FAIL import pyxel: {exc}")
        return 1
    print(f"pyxel {pyxel.VERSION}, python {sys.version.split()[0]}, "
          f"headless={args.headless}", flush=True)

    kwargs = {"headless": True} if args.headless else {}
    pyxel.init(W, H, title="cz smoke", fps=30, **kwargs)
    print(f"OK   init {pyxel.width}x{pyxel.height}", flush=True)

    f5 = pyxel.Font(os.path.join(args.assets, "spleen-5x8.bdf"))
    f8 = pyxel.Font(os.path.join(args.assets, "font_8x8.bdf"))
    print("OK   fonts loaded; spleen width of a 62-char line would be "
          f"{f5.text_width('x' * 62)}px of {W}", flush=True)

    frame = {"n": 0}

    def update():
        frame["n"] += 1
        if frame["n"] < 3:
            return
        raw = bytes(pyxel.screen.data_ptr())
        lit = sum(1 for b in raw if b)
        print(f"{'OK  ' if lit else 'FAIL'} screen buffer {len(raw)} bytes "
              f"(expect {W * H}), {lit} non-black px, palette idx "
              f"{sorted(set(raw))}", flush=True)
        pyxel.screen.save(args.out, args.scale)
        print(f"OK   wrote {args.out}", flush=True)
        import resource
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        print(f"INFO peak RSS {rss / 1024:.1f} MiB (interpreter + pyxel)",
              flush=True)
        print("SMOKE RESULT: ok", flush=True)
        pyxel.quit()

    def draw():
        pyxel.cls(0)
        for x in range(0, W, 40):
            pyxel.line(x, 11, x, H - 11, 1)
        for y in range(11, H - 10, 30):
            pyxel.line(0, y, W, y, 1)
        pyxel.circb(W // 2, 70, 8, 3)
        pyxel.rect(0, 0, W, 10, 0)
        pyxel.text(1, 1, "WATCH DOGS LV:13 GHOST 203343", 3, f5)
        pyxel.text(W - 74, 1, "Z:CITY BAT:82%", 7, f5)
        pyxel.text(2, 14, "BIG 8x8 FONT SAMPLE", 11, f8)
        pyxel.rect(0, H - 46, W, 36, 0)
        for i, line in enumerate((
            "[SYS] ESP32 Watch Dogs v1.0",
            "[OK] ESP32 connected on /dev/ttyACM1",
            "[Lora] Sniffer started: MeshCore 869.618 SF8",
            "[Sync] Connected to server",
        )):
            pyxel.text(2, H - 45 + i * 9, line, 7, f5)
        pyxel.rect(0, H - 10, W, 10, 0)
        pyxel.text(1, H - 9, "BLE:1739 WiFi:6686 HS:22 PWD:58", 10, f5)
        pyxel.text(W - 70, H - 9, "GPS offline", 13, f5)

    pyxel.run(update, draw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
