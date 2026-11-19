"""Run the vendored WatchDogsGo on the CardputerZero (or headless on a dev box).

  python -m czplatform                       # on the device: fb0 + evdev
  python -m czplatform --dry-run             # dev machine: no hardware, saves a PNG
  python -m czplatform --no-fb --no-input --png shot.png --frames 200

Replaces upstream's ``watchdogs/__main__.py`` flow: no ``setup.sh`` preflight
(that installer is uConsole-specific and not vendored); logging, serial-port
detection and the ``WatchDogsGame(serial_port, loot_path)`` call are the same.
"""
from __future__ import annotations

import argparse
import logging
import os
import signal
import sys
import tempfile
from pathlib import Path


def parse_args(argv):
    ap = argparse.ArgumentParser(prog="python -m czplatform",
                                 description=__doc__.split("\n\n")[0])
    ap.add_argument("--fb", default="/dev/fb0",
                    help="framebuffer device or a plain file (default /dev/fb0)")
    ap.add_argument("--no-fb", action="store_true", help="don't draw anywhere")
    ap.add_argument("--input", default=None,
                    help="evdev node of the keyboard (default: auto-detect)")
    ap.add_argument("--no-input", action="store_true", help="no keyboard")
    ap.add_argument("--view", choices=("scale", "crop"), default="scale",
                    help="how a canvas larger than 320x170 is shown (default scale)")
    ap.add_argument("--canvas", choices=("640x360", "320x170"), default="640x360",
                    help="the game's canvas size: the original 640x360 layout, or "
                         "320x170 (the panel, 1:1) — see profile.py")
    ap.add_argument("--script", default=None,
                    help="comma-separated dev steps, e.g. "
                         "'wait:60,key:RETURN,wait:90,png:main.png,quit' "
                         "(wait:N frames, key:NAME, png:PATH, quit)")
    ap.add_argument("--png", default=None, help="save the panel view to a PNG ...")
    ap.add_argument("--frames", type=int, default=0,
                    help="... after this many frames, then exit")
    ap.add_argument("--data-dir", default=None,
                    help="where loot/ and maps/ live (default: the project root)")
    ap.add_argument("--serial", default=None,
                    help="ESP32 serial port (default: auto-detect)")
    ap.add_argument("--stats-every", type=float, default=5.0,
                    help="seconds between fps/RSS lines in the log (default 5)")
    ap.add_argument("--cap-power", choices=("auto", "on", "off"), default="auto",
                    help="switch the Cap's 5 V rail on while the game runs "
                         "(auto: when writable and not a dry-run)")
    ap.add_argument("--seed", default=None,
                    help="with --dry-run: copy this directory (e.g. "
                         "tests/fixtures/demo-data) into the throw-away data dir")
    ap.add_argument("--verbose", action="store_true",
                    help="also print czplatform's log lines (fps, RSS) to stderr")
    ap.add_argument("--dry-run", action="store_true",
                    help="no hardware, throw-away HOME and data dir, PNG after "
                         "120 frames (default file czplatform-dryrun.png)")
    return ap.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    # pyxel changes the working directory to the script's folder when it
    # starts, so resolve every user-supplied path first.
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    if args.dry_run:
        scratch = tempfile.mkdtemp(prefix="czplatform-")
        os.environ["HOME"] = scratch        # keep ~/.watchdogs* out of the real HOME
        args.no_fb = args.no_input = True
        args.data_dir = args.data_dir or scratch
        if args.seed:
            import shutil
            shutil.copytree(os.path.abspath(args.seed), args.data_dir,
                            dirs_exist_ok=True)
        args.png = args.png or "czplatform-dryrun.png"
        args.frames = args.frames or 120
    if args.png:
        args.png = os.path.abspath(args.png)
    if args.data_dir:
        args.data_dir = os.path.abspath(args.data_dir)

    from . import host
    host.prepare_environment()               # before watchdogs.config is imported

    from watchdogs.__main__ import _setup_logging
    _setup_logging()                         # ~/.watchdogs/last_run.log
    log = logging.getLogger("czplatform")
    if args.verbose or args.dry_run:
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("%(asctime)s %(name)s: %(message)s",
                                               datefmt="%H:%M:%S"))
        log.addHandler(console)
        log.setLevel(logging.INFO)

    import pyxel
    from . import display, keys, shim

    panel = display.Panel(None if args.no_fb else args.fb, view=args.view)
    injector = None if args.no_input else keys.KeyInjector(pyxel, args.input)
    script = [s for s in args.script.split(",") if s] if args.script else None
    if script:
        args.png = None                      # the script decides what to capture
    runtime = shim.Runtime(pyxel, panel, injector, png=args.png,
                           frames=args.frames, stats_every=args.stats_every,
                           script=script)
    runtime.install()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, runtime.request_stop)

    from watchdogs.app import WatchDogsGame
    from watchdogs.serial_manager import detect_esp32_port

    host.adapt_game()                        # AIO v2 inert, LoRa on the Cap's pins
    from . import profile
    profile.apply(args.canvas)               # canvas size (before the game is built)
    if args.cap_power == "on" or (args.cap_power == "auto" and not args.dry_run):
        host.CapRail().on()

    port = args.serial or detect_esp32_port()
    log.info("starting game: serial=%s data_dir=%s view=%s", port,
             args.data_dir or "<project root>", args.view)
    try:
        WatchDogsGame(serial_port=port, loot_path=args.data_dir)
    except Exception:
        log.exception("game crashed")
        raise
    return 0


if __name__ == "__main__":
    sys.exit(main())
