"""Panel output: palette-index frames -> RGB565 -> the CardputerZero framebuffer.

The panel is a 320x170, 16 bpp (RGB565) SPI display exposed as ``/dev/fb0``.
APPLaunch pauses its own refresh while an app runs, so an app owns the screen
and may draw into an ``mmap`` of the device (M5's own framebuffer examples do
exactly this). ``write()`` is not enough on this kernel — use the mmap.

Frames arrive from headless pyxel as one byte per pixel (an index into the
16-colour palette), at the game's canvas size. ``make_view`` reduces any canvas
to the panel size; ``Panel.present`` converts and writes it.
"""
from __future__ import annotations

import fcntl
import mmap
import operator
import os
import stat
import struct

PANEL_W, PANEL_H = 320, 170
FRAME_BYTES = PANEL_W * PANEL_H * 2
RGB565 = ((11, 5), (5, 6), (0, 5))          # (bit offset, length) for R, G, B
_FBIOGET_VSCREENINFO = 0x4600

VIEWS = ("scale", "crop")


def fb_info(fd):
    """(xres, yres, bpp, ((r_off, r_len), (g_off, g_len), (b_off, b_len)))."""
    v = fcntl.ioctl(fd, _FBIOGET_VSCREENINFO, bytes(160))
    xres, yres, _xv, _yv, _xo, _yo, bpp, _gray = struct.unpack_from("8I", v, 0)
    r = struct.unpack_from("3I", v, 32)
    g = struct.unpack_from("3I", v, 44)
    b = struct.unpack_from("3I", v, 56)
    return xres, yres, bpp, ((r[0], r[1]), (g[0], g[1]), (b[0], b[1]))


def build_tables(palette, fmt=RGB565):
    """Per palette index, the low and high byte of the little-endian pixel."""
    (ro, rl), (go, gl), (bo, bl) = fmt
    lo, hi = bytearray(256), bytearray(256)
    for i, rgb in enumerate(palette):
        r, g, b = (rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255
        px = (((r >> (8 - rl)) << ro) | ((g >> (8 - gl)) << go)
              | ((b >> (8 - bl)) << bo))
        lo[i], hi[i] = px & 255, px >> 8
    return bytes(lo), bytes(hi)


def make_view(cw, ch, mode="scale"):
    """Return ``f(raw) -> bytes`` mapping a cw x ch index buffer to the panel.

    * identical size -> unchanged
    * ``crop``  -> the top-left PANEL_W x PANEL_H window (text stays legible)
    * ``scale`` -> nearest-neighbour over the whole canvas (everything visible,
      text unreadable) — for a 640x360 canvas that is 2:1 horizontally and
      ~2.12:1 vertically.
    Interim aids until the UI itself is laid out for 320x170 (ROADMAP 1.2).
    """
    if mode not in VIEWS:
        raise ValueError(f"view must be one of {VIEWS}")
    if (cw, ch) == (PANEL_W, PANEL_H):
        return lambda raw: raw
    if mode == "crop":
        if cw < PANEL_W or ch < PANEL_H:
            raise ValueError(f"canvas {cw}x{ch} is smaller than the panel")
        return lambda raw: b"".join(
            raw[y * cw:y * cw + PANEL_W] for y in range(PANEL_H))
    rows = [min(ch - 1, y * ch // PANEL_H) for y in range(PANEL_H)]
    if cw % PANEL_W == 0:
        k = cw // PANEL_W
        return lambda raw: b"".join(raw[r * cw:(r + 1) * cw:k] for r in rows)
    cols = operator.itemgetter(*[min(cw - 1, x * cw // PANEL_W)
                                 for x in range(PANEL_W)])
    return lambda raw: b"".join(
        bytes(cols(raw[r * cw:(r + 1) * cw])) for r in rows)


class Panel:
    """Where frames go: a framebuffer device, a plain file (dry-run), or nowhere."""

    def __init__(self, path=None, view="scale"):
        self.view_mode = view
        self._view = None
        self._canvas = None
        self._palette = None
        self._tables = None
        self._fmt = RGB565
        self.last_view = None                   # last PANEL_W*PANEL_H indices
        self._fd = None
        self._mm = None
        if path:
            self._open(path)

    # -- setup ---------------------------------------------------------------

    def _open(self, path):
        st = os.stat(path) if os.path.exists(path) else None
        if st is None or stat.S_ISREG(st.st_mode):
            # dry-run: any regular file behaves like a framebuffer
            with open(path, "ab"):
                pass
            if os.path.getsize(path) < FRAME_BYTES:
                os.truncate(path, FRAME_BYTES)
            self._fd = os.open(path, os.O_RDWR)
        else:
            self._fd = os.open(path, os.O_RDWR)
            xres, yres, bpp, self._fmt = fb_info(self._fd)
            if (xres, yres, bpp) != (PANEL_W, PANEL_H, 16):
                raise RuntimeError(
                    f"{path} is {xres}x{yres}@{bpp}, expected 320x170@16")
            stride = int(open("/sys/class/graphics/fb0/stride").read())
            if stride != PANEL_W * 2:
                raise RuntimeError(f"unexpected framebuffer stride {stride}")
        self._mm = mmap.mmap(self._fd, FRAME_BYTES, mmap.MAP_SHARED,
                             mmap.PROT_READ | mmap.PROT_WRITE)

    def set_canvas(self, cw, ch):
        self._canvas = (cw, ch)
        self._view = make_view(cw, ch, self.view_mode)

    # -- per frame -----------------------------------------------------------

    def present(self, raw, palette):
        """Show one canvas-sized index buffer (``bytes``) on the panel."""
        view = self._view(raw)
        self.last_view = view
        if self._palette != palette:
            self._palette = tuple(palette)
            self._tables = build_tables(palette, self._fmt)
        if self._mm is not None:
            lo, hi = self._tables
            out = bytearray(FRAME_BYTES)
            out[0::2] = view.translate(lo)
            out[1::2] = view.translate(hi)
            self._mm[:] = out

    # -- helpers -------------------------------------------------------------

    def save_png(self, path, scale=3):
        """Write the last panel frame as an RGB PNG (needs Pillow)."""
        from PIL import Image
        if self.last_view is None or self._palette is None:
            raise RuntimeError("no frame has been presented yet")
        img = Image.frombytes("P", (PANEL_W, PANEL_H), self.last_view)
        flat = []
        for rgb in self._palette:
            flat += [(rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255]
        img.putpalette(flat + [0] * (768 - len(flat)))
        img = img.convert("RGB")
        if scale > 1:
            img = img.resize((PANEL_W * scale, PANEL_H * scale), Image.NEAREST)
        img.save(path)

    def close(self):
        if self._mm is not None:
            self._mm.close()
            self._mm = None
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
