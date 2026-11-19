"""CardputerZero platform layer for the vendored WatchDogsGo game.

Our own code (the vendored ``watchdogs/`` package stays untouched). It lets the
unmodified game run on the CardputerZero by replacing the three things the game
expects from a desktop pyxel:

* the window      -> headless pyxel; the frame is converted to RGB565 and
                     written into an ``mmap`` of ``/dev/fb0``        (display.py)
* the keyboard    -> evdev events from the TCA8418 injected with
                     ``pyxel.set_btn()``                              (keys.py)
* the process     -> SIGINT/SIGTERM (what APPLaunch sends on a Home long-press)
                     run the game's own cleanup, then exit             (shim.py)

Entry point: ``python -m czplatform`` (see ``__main__.py``).
"""

__version__ = "0.1.0"
