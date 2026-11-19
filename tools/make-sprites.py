#!/usr/bin/env python3
"""Generate the half-size menu sprites for the 320x170 UI (ROADMAP 1.2 / 1.9).

Same pipeline as the vendored ``watchdogs/convert_sprite.py`` — LANCZOS resize,
a little contrast/brightness boost, then every pixel snapped to pyxel's 16-colour
palette with near-black as palette 0 (the transparent colour) — but at a height
of 128 px instead of 256, from the hi-res art in ``assets/``. Output goes to
``assets/cz/``; the compact UI loads these directly, so the game no longer
re-converts the 848x1264 sources with Pillow on every start.

  .venv/bin/python tools/make-sprites.py
"""
import sys
from pathlib import Path

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from watchdogs.convert_sprite import PYXEL_PALETTE_RGB, nearest_palette  # noqa: E402

ASSETS = ROOT / "assets"
OUT = ASSETS / "cz"
MENU_HEIGHT = 128           # half of the original 256
RADIO_HEIGHT = 24           # the MeshCore radio icon (original: 48)
MENU_SPRITES = ("hacker", "scan", "sniff", "attack", "addons")


def to_pyxel_palette(src: Path, dst: Path, target_h: int):
    img = Image.open(src).convert("RGB")
    ratio = target_h / img.size[1]
    target_w = min(256, int(img.size[0] * ratio))
    img = img.resize((target_w, target_h), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.3)
    img = ImageEnhance.Brightness(img).enhance(1.2)
    px = img.load()
    lut = {}
    for y in range(target_h):
        for x in range(target_w):
            rgb = px[x, y]
            if rgb not in lut:
                r, g, b = rgb
                lut[rgb] = 0 if (r + g + b) // 3 < 18 else nearest_palette(r, g, b)
            px[x, y] = PYXEL_PALETTE_RGB[lut[rgb]]
    img.save(dst)
    return img.size


def main() -> int:
    OUT.mkdir(exist_ok=True)
    for name in MENU_SPRITES:
        w, h = to_pyxel_palette(ASSETS / f"{name}.png", OUT / f"{name}_sprite.png",
                                MENU_HEIGHT)
        print(f"{name:8s} -> assets/cz/{name}_sprite.png  {w}x{h}")
    from watchdogs.convert_radio_sprite import convert as convert_radio
    convert_radio(str(ASSETS / "radio.png"), str(OUT / "radio_sprite.png"),
                  target_h=RADIO_HEIGHT)
    print("radio    -> assets/cz/radio_sprite.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
