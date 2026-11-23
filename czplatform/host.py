"""Adapt the vendored game's uConsole assumptions to the CardputerZero — safely.

The vendored code was written for the uConsole + HackerGadgets AIO v2 board. On
the CardputerZero several of its hard-coded GPIO numbers mean something else
(measured, docs/hardware-notes.md):

    upstream use                   CardputerZero meaning of that GPIO
    ----------------------------   ------------------------------------------
    AIO "gps"  -> pinctrl GPIO 27  keyboard (TCA8418) interrupt
    AIO "usb"  -> pinctrl GPIO 23  LoRa DIO1 (an *input* from the chip)
    AIO "sdr"  -> pinctrl GPIO 7   SPI0 CS1 = LoRa NSS
    LoRa RST/BUSY/IRQ = 25/24/26   G25/G24 are the display's dc/enable lines
    LoRa on SPI bus 1, CS 0        the Cap is on SPI0 CS1 (/dev/spidev0.1)

Running that code unchanged would drive those pins. So, **without editing the
vendored files**, this module (1) turns ``AioManager`` into a no-op that never
spawns ``pinctrl``, (2) points the LoRa constants at the Cap's real pins, and
(3) defaults the GPS to ``/dev/ttyS0`` @ 115200. It also switches the Cap's 5 V
rail on (and restores it at exit), since that is what the AIO toggles did.
"""
from __future__ import annotations

import atexit
import logging
import os
from pathlib import Path

log = logging.getLogger("czplatform.host")

# Cap LoRa (confirmed on the device, docs/hardware-notes.md)
LORA_SPI_BUS = 0
LORA_SPI_CS = 1
LORA_PIN_RESET = 26
LORA_PIN_BUSY = 22
LORA_PIN_IRQ = 23                   # DIO1
GPS_DEVICE = "/dev/ttyS0"
GPS_BAUD = "115200"
CAP_RAIL = "/sys/class/leds/ext_5v_out"


def prepare_environment():
    """Defaults read by ``watchdogs.config`` at import time — call before it."""
    os.environ.setdefault("WDG_GPS_DEVICE", GPS_DEVICE)
    os.environ.setdefault("WDG_GPS_BAUD", GPS_BAUD)


def make_aio_inert():
    """Make HackerGadgets AIO v2 control a harmless no-op (see module doc)."""
    from watchdogs import aio_manager

    cls = aio_manager.AioManager
    cls.is_installed = staticmethod(lambda: False)
    cls.get_status = staticmethod(lambda: None)
    cls.toggle = staticmethod(lambda feature, on: False)

    def _install(callback):
        callback("AIO v2 control does not apply to the CardputerZero", "error")

    cls.install = staticmethod(_install)
    # belt and braces: nothing may reach pinctrl even through the helpers
    aio_manager._pinctrl_set = lambda pin, high: False
    aio_manager._pinctrl_get = lambda pin: False
    log.info("AIO v2 control disabled (its GPIOs are other things here)")


def point_lora_at_the_cap():
    """LoRaRF pins and SPI device of the Cap LoRa module."""
    from watchdogs import lora_manager

    lora_manager.SPI_BUS = LORA_SPI_BUS
    lora_manager.SPI_CS = LORA_SPI_CS
    lora_manager.PIN_RESET = LORA_PIN_RESET
    lora_manager.PIN_BUSY = LORA_PIN_BUSY
    lora_manager.PIN_IRQ = LORA_PIN_IRQ
    log.info("LoRa -> SPI%d.%d RST=G%d BUSY=G%d IRQ=G%d", LORA_SPI_BUS,
             LORA_SPI_CS, LORA_PIN_RESET, LORA_PIN_BUSY, LORA_PIN_IRQ)


BATTERY_CAPACITY = "/sys/class/power_supply/bq27220-0/capacity"


def read_battery():
    """Battery percentage from the CardputerZero's BQ27220 gauge (-1 if absent).

    ``CZ_FAKE_BATTERY=NN`` overrides it, for previewing the HUD on a dev machine.
    """
    fake = os.environ.get("CZ_FAKE_BATTERY")
    if fake:
        return int(fake)
    try:
        with open(BATTERY_CAPACITY) as f:
            return int(f.read().strip())
    except (OSError, ValueError):
        return -1


def use_the_bq27220_gauge():
    """The game reads the uConsole's AXP20x PMIC; here it is a BQ27220."""
    from watchdogs import app

    app.WatchDogsGame._read_battery = staticmethod(read_battery)


def free_sdr_usb_from_the_aio_gate():
    """``_toggle_sdr``/``_toggle_usb`` hard-require ``AioManager.toggle()`` to
    succeed before doing anything — on the uConsole those GPIOs gate the USB
    port's own power. ``make_aio_inert()`` already makes ``AioManager`` a
    no-op (correctly: AIO v2 isn't installed here, and those GPIOs are other
    things, see the module docstring), which as an upstream side effect means
    the *original* ``_toggle_sdr``/``_toggle_usb`` could never turn on at all
    on this device — found live, trying to use ADS-B Radar with the SDR
    plugged in: "[SDR] AIO v2 not available", forever. The CardputerZero's USB
    host ports are always-on (no such gate exists here), so this makes both
    toggles software-only, the same shape ``_toggle_gps``/``_toggle_lora``
    already use when AIO v2 is absent.
    """
    from watchdogs import app

    def _toggle_sdr(self):
        new_state = not self._sdr_enabled
        self._sdr_enabled = new_state
        if new_state:
            self.msg("[SDR] ON", app.C_SUCCESS)
            self._term_add("[SYS] SDR enabled", raw=True)
        else:
            self._sdr.stop()
            self.msg("[SDR] OFF", app.C_WARNING)
            self._term_add("[SYS] SDR disabled", raw=True)
        self.glitch_timer = 2

    def _toggle_usb(self):
        new_state = not self._usb_enabled
        self._usb_enabled = new_state
        if new_state:
            self.msg("[USB] ON", app.C_SUCCESS)
            self._term_add("[SYS] USB enabled", raw=True)
        else:
            self.msg("[USB] OFF", app.C_WARNING)
            self._term_add("[SYS] USB disabled", raw=True)
        self.glitch_timer = 2

    app.WatchDogsGame._toggle_sdr = _toggle_sdr
    app.WatchDogsGame._toggle_usb = _toggle_usb
    log.info("SDR/USB toggles freed from the AIO v2 gate (always-on USB host ports here)")


def tag_portal_user_agent():
    """Append our fork tag to the WDGWars User-Agent (``docs/portal-rules.md``:
    forks must identify themselves, e.g. ``Fork/CardputerZero-0.1.0``). The
    platform/hwid part is already honest — ``wardrive_upload.py``'s own
    ``/proc/device-tree/model`` check reports ``RPi-XXXXXX`` here, not
    ``uConsole`` — only the fork tag itself was missing. ``USER_AGENT`` is a
    plain module-level string read by ``_open()`` at call time, so patching
    it once here (before any request is made) is enough; a later import by
    ``discover_plugins()`` reuses the same cached module object.
    """
    from plugins import wardrive_upload
    from czplatform import __version__ as _cz_version

    wardrive_upload.USER_AGENT += f" Fork/CardputerZero-{_cz_version}"
    log.info("WDGWars User-Agent: %s", wardrive_upload.USER_AGENT)


def redirect_user_state(state_dir: Path | None = None):
    """Point secrets.conf/plugin state at a writable per-user directory
    instead of the vendored code's hardcoded "next to the installed files"
    paths (``Path(__file__).resolve().parent.parent / "secrets.conf"`` in
    ``watchdogs/config.py``, ``watchdogs/tile_manager.py`` and
    ``plugins/wardrive_upload.py``; ``Path(__file__).parent /
    ".wardrive_state.json"`` likewise). Harmless for a git checkout (where
    that directory is the owner's own home dir), but wrong for a `.deb`
    install under the read-only ``/usr/share/APPLaunch/apps/<pkg>/``: the
    WDGWars pairing screen's own ``adopt_api_key()`` *writes* a freshly
    paired key back to that path, and that write would silently fail there
    (found while packaging, ROADMAP Phase 3).

    Reuses ``~/.watchdogs/``, the directory the game's own logging already
    creates (``last_run.log``), seeding a fresh ``secrets.conf`` there from
    the installed ``secrets.conf.example`` on first run so there is an
    obvious place to put ``STADIA_API_KEY`` etc. (never auto-filled with
    anyone's real key).
    """
    state_dir = state_dir or (Path.home() / ".watchdogs")
    state_dir.mkdir(parents=True, exist_ok=True)
    secrets_path = state_dir / "secrets.conf"

    if not secrets_path.is_file():
        example = Path(__file__).resolve().parent.parent / "secrets.conf.example"
        if example.is_file():
            secrets_path.write_text(example.read_text(encoding="utf-8"))
            log.info("seeded %s from secrets.conf.example", secrets_path)

    def _read_secrets() -> dict:
        result = {}
        if secrets_path.is_file():
            try:
                for line in secrets_path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    result[k.strip()] = v.strip()
            except OSError:
                pass
        return result

    # watchdogs/config.py's _secrets dict and the three constants derived
    # from it run at *import* time (module-level `_secrets = _load_secrets()`),
    # so patching the function afterwards wouldn't change already-baked
    # values — overwrite the data directly instead.
    from watchdogs import config as wdg_config

    fresh = _read_secrets()
    wdg_config._secrets = fresh
    wdg_config.WIGLE_API_NAME = fresh.get("WDG_WIGLE_NAME") or fresh.get("JANOS_WIGLE_NAME", "")
    wdg_config.WIGLE_API_TOKEN = fresh.get("WDG_WIGLE_TOKEN") or fresh.get("JANOS_WIGLE_TOKEN", "")
    wdg_config.WPASEC_KEY = fresh.get("WDG_WPASEC_KEY") or fresh.get("JANOS_WPASEC_KEY", "")

    # Everything else reads lazily at call time — safe to replace the
    # functions/methods outright.
    from watchdogs import tile_manager
    tile_manager._load_stadia_key = lambda: _read_secrets().get("STADIA_API_KEY", "")

    from plugins import wardrive_upload

    wardrive_upload._load_secrets_conf = _read_secrets

    def _state_file(self):
        return state_dir / "wardrive_state.json"

    def _save_secret(self, key: str, value: str):
        lines = secrets_path.read_text().splitlines() if secrets_path.is_file() else []
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = f"{key}={value}"
                break
        else:
            lines.append(f"{key}={value}")
        secrets_path.write_text("\n".join(lines) + "\n")

    wardrive_upload.WardriveUpload._state_file = _state_file
    wardrive_upload.WardriveUpload._save_secret = _save_secret

    try:
        from plugins import janos_import
        janos_import.JanosImport._wdg_loot_path = (
            lambda self: Path(self.app.loot._base) if self.app and self.app.loot
            else state_dir / "loot"
        )
    except ImportError:
        pass

    log.info("user state redirected to %s", state_dir)


def auto_start_lora_like_aio_left_on():
    """Mirror upstream's own "AIO v2 already powered on" auto-start
    (``watchdogs/app.py`` ~838-847: if ``self._lora_enabled`` is already True
    when ``__init__`` reaches that point, it starts MeshCore and sends the
    boot advert right away) — real only when ``_aio_available`` is True,
    which is never the case here (``make_aio_inert()``), so ``_lora_enabled``
    starts out hard-coded False on this device and that block never fires.

    The CardputerZero has no AIO switch to remember "the owner left it on
    last time", but the Cap plays the same role: if it's physically attached,
    try LoRa/MeshCore on every boot, same as upstream already does for AIO.
    Owner's explicit call (2026-11-20): full parity, including the real boot
    advert — not just marking the HUD as on.

    First attempt wrapped ``__init__`` and ran this *after* calling the
    original — that code is unreachable: ``__init__``'s own last line is
    ``pyxel.run(self.update, self.draw)`` (``watchdogs/app.py:853``), which
    through ``czplatform.shim.Runtime.run`` ends up blocking inside the real
    pyxel loop for the rest of the game's life, same as the documented
    ``pyxel.quit()`` gotcha — confirmed live (``WatchDogsGame.__init__`` was
    provably our wrapper at construction time, yet the line placed after the
    original call never logged). Wrapping ``update`` instead — a bound
    method actually called every frame once the game is running, the same
    proven pattern as ``_toggle_sdr``/``_toggle_usb`` — and firing this once
    on the first frame reaches the exact same "game is fully built, hasn't
    started its main loop yet" moment, just one frame later than upstream's.

    Safe if the Cap isn't actually there: ``start_meshcore()`` only sets
    ``running = True`` synchronously — the real SPI/GPIO init runs in
    ``LoRaManager``'s background thread and fails closed (``running`` flips
    back to False, logged) the same way GPS/SDR already do when their
    hardware is absent; the HUD already renders that as ``LoRa:IDLE``, not a
    false ``LoRa:ON`` (``watchdogs/app.py`` ~5076-5080).
    """
    from watchdogs import app

    _orig_update = app.WatchDogsGame.update

    def _update_with_lora_autostart(self):
        if not getattr(self, "_cz_lora_autostart_done", False):
            self._cz_lora_autostart_done = True
            log.info("LoRa auto-start (frame 1): _lora_enabled=%s",
                     self._lora_enabled)
            if not self._lora_enabled:
                self._lora_enabled = True
                try:
                    self._lora.set_mc_channels(self._mc_channels_list)
                    self._lora.start_meshcore(self._mc_region)
                    log.info("start_meshcore() called, running=%s",
                             self._lora.running)
                    self._term_add("[SYS] LoRa Cap — MeshCore auto-started",
                                    raw=True)
                    lat = self.player_lat if self.gps_fix else 0.0
                    lon = self.player_lon if self.gps_fix else 0.0
                    self._lora.send_meshcore_advert(self._mc_node_name, lat, lon)
                    log.info("send_meshcore_advert() called")
                except Exception:
                    log.exception("LoRa/MeshCore auto-start failed")
        _orig_update(self)

    app.WatchDogsGame.update = _update_with_lora_autostart
    log.info("LoRa/MeshCore auto-start wired (mirrors AIO-left-on behavior)")


def preload_lgpio():
    """Import ``lgpio`` now, while the cwd is still whatever the launcher
    wrapper set (writable), not after pyxel.init() has chdir'd into the
    read-only install tree.

    ``lgpio`` opens a notify pipe, ``.lgd-nfy<N>``, at a path relative to the
    process's cwd **the first time the module is imported** (RPi.GPIO's
    ``lgpio.py:562`` runs ``_notify_thread = _callback_thread()`` at module
    scope). Under a `.deb` install, ``WatchDogsGame.__init__`` calls
    ``pyxel.init()`` before ``_build_boot_checks()`` imports ``LoRaRF`` (→
    ``RPi.GPIO`` → ``lgpio``), and pyxel chdirs to the directory holding the
    running script on init — here, the root-owned, read-only
    ``.../apps/<pkg>/czplatform/`` — so that later import crashes
    (``FileNotFoundError: .lgd-nfy-3``, confirmed live on the device). Doing
    the import here, before anything calls ``pyxel.init()``, makes the pipe
    once while cwd is still writable; Python caches the module, so the later
    ``import LoRaRF`` just reuses it.
    """
    try:
        import lgpio  # noqa: F401
    except Exception:
        log.debug("lgpio preload failed (no LoRa hardware expected?)", exc_info=True)


def adapt_game():
    """Apply every runtime adaptation. Call after importing, before constructing."""
    make_aio_inert()
    point_lora_at_the_cap()
    use_the_bq27220_gauge()
    tag_portal_user_agent()
    free_sdr_usb_from_the_aio_gate()
    auto_start_lora_like_aio_left_on()
    redirect_user_state()
    preload_lgpio()


class CapRail:
    """The Cap's 5 V rail (``ext_5v_out``): on while the game runs.

    Writable without root through group ``gpio`` (M5's udev rule). The previous
    value is restored at exit, like M5's own Cap apps do.
    """

    def __init__(self, path=CAP_RAIL):
        self.path = path
        self._previous = None

    def available(self):
        return os.access(os.path.join(self.path, "brightness"), os.W_OK)

    def _read(self, name):
        with open(os.path.join(self.path, name)) as f:
            return int(f.read().strip())

    def _write(self, value):
        with open(os.path.join(self.path, "brightness"), "w") as f:
            f.write(str(value))

    def on(self):
        if not self.available():
            log.info("Cap rail not available here (%s)", self.path)
            return False
        self._previous = self._read("brightness")
        self._write(self._read("max_brightness"))
        atexit.register(self.restore)
        log.info("Cap rail on (was %d)", self._previous)
        return True

    def restore(self):
        if self._previous is None:
            return
        try:
            self._write(self._previous)
            log.info("Cap rail restored to %d", self._previous)
        except OSError as exc:
            log.warning("could not restore the Cap rail: %s", exc)
        self._previous = None
