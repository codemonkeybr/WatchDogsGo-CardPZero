#!/usr/bin/env python3
"""Headless pyxel -> /dev/fb0 blit test (ROADMAP 0.1 / 1.7).

Renders an animated 320x170 mock HUD with headless pyxel, converts the
palette-index screen buffer to the framebuffer's pixel format and writes it
to /dev/fb0 for a few seconds, then reports the achievable frame rate and
CPU use. By default it saves the framebuffer first and puts it back at the
end, so the launcher screen returns as it was.

  .venv/bin/python tools/fb-blit-test.py --assets ~/WatchDogsGo-CardPZero/assets \
      [--seconds 6] [--fps 30] [--no-restore]

Needs access to /dev/fb0 (group `video`). The launcher keeps the same device
open and may redraw over our frames while this runs.
"""
import argparse
import fcntl
import math
import os
import struct
import sys
import time

W, H = 320, 170
FBIOGET_VSCREENINFO = 0x4600


def fb_format(fd):
    """(xres, yres, bpp, red, green, blue) with each channel as
    (offset, length, msb_right), from FBIOGET_VSCREENINFO."""
    v = fcntl.ioctl(fd, FBIOGET_VSCREENINFO, bytes(160))
    xres, yres, _xv, _yv, _xo, _yo, bpp, _gray = struct.unpack_from("8I", v, 0)
    return (xres, yres, bpp,
            struct.unpack_from("3I", v, 32),
            struct.unpack_from("3I", v, 44),
            struct.unpack_from("3I", v, 56))


def build_tables(palette, red, green, blue):
    """Per-palette-index low/high byte of the 16-bit pixel, little endian."""
    lo, hi = bytearray(256), bytearray(256)
    for i, rgb in enumerate(palette):
        r, g, b = (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255
        px = (((r >> (8 - red[1])) << red[0])
              | ((g >> (8 - green[1])) << green[0])
              | ((b >> (8 - blue[1])) << blue[0]))
        lo[i], hi[i] = px & 255, px >> 8
    return bytes(lo), bytes(hi)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--assets", required=True,
                    help="dir containing spleen-5x8.bdf")
    ap.add_argument("--fb", default="/dev/fb0")
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--no-restore", action="store_true",
                    help="leave the last frame on screen instead of restoring")
    args = ap.parse_args()
    # pyxel changes the working directory to the script's folder when it
    # starts, so resolve user-supplied paths before that happens.
    args.assets = os.path.abspath(args.assets)

    import pyxel

    fd = os.open(args.fb, os.O_RDWR)
    xres, yres, bpp, red, green, blue = fb_format(fd)
    stride = int(open("/sys/class/graphics/fb0/stride").read())
    print(f"fb: {xres}x{yres} {bpp}bpp stride={stride} "
          f"R{red[1]}@{red[0]} G{green[1]}@{green[0]} B{blue[1]}@{blue[0]}",
          flush=True)
    if (xres, yres) != (W, H) or bpp != 16:
        print("FAIL: expected a 320x170 16bpp framebuffer")
        return 1

    saved = None
    if not args.no_restore:
        try:
            saved = os.pread(fd, stride * yres, 0)
            print(f"saved {len(saved)} bytes of the current screen", flush=True)
        except OSError as exc:
            print(f"WARN: cannot read the framebuffer back ({exc}); "
                  "the launcher screen will not be restored")

    pyxel.init(W, H, title="fb blit", fps=args.fps, headless=True)
    palette = list(pyxel.colors)
    lo, hi = build_tables(palette, red, green, blue)
    f5 = pyxel.Font(os.path.join(args.assets, "spleen-5x8.bdf"))
    row_bytes = W * 2
    contiguous = stride == row_bytes

    st = {"n": 0, "t0": None, "cpu0": None, "draw": 0.0, "conv": 0.0,
          "write": 0.0, "worst": 0.0}

    def draw_frame(n):
        pyxel.cls(0)
        for x in range(0, W, 40):
            pyxel.line(x, 22, x, 125, 1)
        for y in range(22, 126, 25):
            pyxel.line(0, y, W, y, 1)
        for i in range(16):                      # palette swatches
            pyxel.rect(i * 20, 11, 20, 9, i)
        cx = 20 + (n * 3) % (W - 40)
        cy = 72 + int(20 * math.sin(n / 10))
        pyxel.circb(cx, cy, 8, 3)
        pyxel.circ(cx, cy, 2, 7)
        pyxel.rect(0, 0, W, 10, 0)
        pyxel.text(1, 1, "WATCH DOGS LV:13 GHOST 203343", 3, f5)
        pyxel.text(W - 74, 1, "Z:CITY BAT:82%", 7, f5)
        pyxel.rect(0, H - 46, W, 36, 0)
        for i, line in enumerate((
            "[SYS] fb0 blit test from headless pyxel",
            "[OK] 320x170 RGB565 via /dev/fb0",
            "[Lora] palette swatches above, marker moves",
            f"[Sync] frame {n}",
        )):
            pyxel.text(2, H - 45 + i * 9, line, 7, f5)
        pyxel.rect(0, H - 10, W, 10, 0)
        pyxel.text(1, H - 9, "BLE:1739 WiFi:6686 HS:22 PWD:58", 10, f5)
        pyxel.text(W - 70, H - 9, "GPS offline", 13, f5)

    def blit():
        tc = time.perf_counter()
        raw = bytes(pyxel.screen.data_ptr())
        out = bytearray(len(raw) * 2)
        out[0::2] = raw.translate(lo)
        out[1::2] = raw.translate(hi)
        tw = time.perf_counter()
        if contiguous:
            os.pwrite(fd, out, 0)
        else:
            for y in range(H):
                os.pwrite(fd, out[y * row_bytes:(y + 1) * row_bytes],
                          y * stride)
        st["conv"] += tw - tc
        st["write"] += time.perf_counter() - tw

    def finish():
        wall = time.perf_counter() - st["t0"]
        cpu = time.process_time() - st["cpu0"]
        n = max(st["n"], 1)
        print(f"frames: {st['n']} in {wall:.2f}s -> {st['n'] / wall:.1f} fps "
              f"(target {args.fps})")
        print(f"per frame (ms): draw {1000 * st['draw'] / n:.2f}  convert "
              f"{1000 * st['conv'] / n:.2f}  write {1000 * st['write'] / n:.2f}"
              f"  worst total {1000 * st['worst']:.1f}")
        print(f"process CPU: {100 * cpu / wall:.0f}% of one core")
        if saved is not None:
            os.pwrite(fd, saved, 0)
            print("restored the previous screen contents")
        print("BLIT RESULT: ok", flush=True)
        pyxel.quit()

    def update():
        if st["t0"] is not None and time.perf_counter() - st["t0"] >= args.seconds:
            finish()

    def draw():
        t0 = time.perf_counter()
        if st["t0"] is None:
            st["t0"], st["cpu0"] = t0, time.process_time()
        draw_frame(st["n"])
        t1 = time.perf_counter()
        blit()
        t2 = time.perf_counter()
        st["draw"] += t1 - t0
        st["worst"] = max(st["worst"], t2 - t0)
        st["n"] += 1

    pyxel.run(update, draw)
    return 0


if __name__ == "__main__":
    sys.exit(main())
