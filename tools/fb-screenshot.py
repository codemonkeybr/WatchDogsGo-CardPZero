#!/usr/bin/env python3
"""Screenshot of the CardputerZero panel, read from its framebuffer over SSH.

  .venv/bin/python tools/fb-screenshot.py --ssh USER@HOST [--out shot.png] [--scale 3]

Reads /dev/fb0 (RGB565, 320x170) on the device and writes a PNG. What you get
is what the kernel framebuffer holds, i.e. what APPLaunch — or an app that
draws through the framebuffer, like ours — put on screen. Handy for reviewing
the UI and for README screenshots. Needs Pillow (the repo .venv has it) and
key-based SSH to the device.
"""
import argparse
import subprocess
import sys
from array import array

from PIL import Image

W, H = 320, 170


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ssh", required=True, help="USER@HOST of the device")
    ap.add_argument("--out", default="screenshot.png")
    ap.add_argument("--scale", type=int, default=3, help="integer upscale")
    ap.add_argument("--fb", default="/dev/fb0")
    args = ap.parse_args()

    res = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", args.ssh,
         f"cat {args.fb}"], capture_output=True)
    if res.returncode != 0:
        print(res.stderr.decode(errors="replace").strip(), file=sys.stderr)
        return 1
    need = W * H * 2
    if len(res.stdout) < need:
        print(f"short read: {len(res.stdout)} bytes, expected {need}",
              file=sys.stderr)
        return 1

    px = array("H")
    px.frombytes(res.stdout[:need])
    if sys.byteorder == "big":          # the framebuffer is little endian
        px.byteswap()
    rgb = bytearray(W * H * 3)
    for i, v in enumerate(px):
        rgb[3 * i] = (v >> 11) * 255 // 31
        rgb[3 * i + 1] = ((v >> 5) & 63) * 255 // 63
        rgb[3 * i + 2] = (v & 31) * 255 // 31
    img = Image.frombytes("RGB", (W, H), bytes(rgb))
    if args.scale > 1:
        img = img.resize((W * args.scale, H * args.scale), Image.NEAREST)
    img.save(args.out)
    print(f"wrote {args.out} ({img.width}x{img.height}), "
          f"{len(set(px))} distinct colours")
    return 0


if __name__ == "__main__":
    sys.exit(main())
