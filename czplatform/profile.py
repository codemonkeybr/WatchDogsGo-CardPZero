"""Display profiles: re-size the game's canvas at run time (ROADMAP 1.2).

The vendored ``watchdogs/app.py`` keeps its layout in module-level globals
(``W, H`` and the HUD/terminal/map bands) that every draw method reads at call
time, and no other module imports them. So the canvas can be changed *before the
game is constructed* without editing the vendored file; whatever the game then
draws relative to those globals adapts by itself, and the literals that still
assume 640x360 are the work list (docs/ui-adaptation.md).

Profiles:
  640x360  the original uConsole layout (unchanged)
  320x170  the CardputerZero panel, 1:1 (no scaling of the text)
"""
from __future__ import annotations

import logging

log = logging.getLogger("czplatform.profile")

PROFILES = {
    "640x360": None,
    "320x170": {"W": 320, "H": 170, "HUD_TOP": 10, "HUD_BOT": 10, "TERM_H": 10},
}


def apply(name):
    """Patch ``watchdogs.app``'s layout globals for the named profile."""
    if name not in PROFILES:
        raise ValueError(f"unknown canvas profile {name!r}; use one of "
                         f"{sorted(PROFILES)}")
    values = PROFILES[name]
    if values is None:
        return
    from watchdogs import app

    app.W, app.H = values["W"], values["H"]
    app.HUD_TOP, app.HUD_BOT = values["HUD_TOP"], values["HUD_BOT"]
    app.TERM_H = values["TERM_H"]
    app.MAP_H = app.H - app.HUD_TOP - app.HUD_BOT - app.TERM_H
    app.TERM_Y = app.H - app.HUD_BOT - app.TERM_H
    log.info("canvas profile %s: %dx%d, HUD %d/%d, terminal %d, map %d",
             name, app.W, app.H, app.HUD_TOP, app.HUD_BOT, app.TERM_H, app.MAP_H)
    if name == "320x170":
        from . import ui320
        ui320.install()                     # compact HUD / terminal drawing


def canvas_size(name):
    values = PROFILES[name]
    return (640, 360) if values is None else (values["W"], values["H"])
