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


def adapt_game():
    """Apply every runtime adaptation. Call after importing, before constructing."""
    make_aio_inert()
    point_lora_at_the_cap()
    use_the_bq27220_gauge()
    free_sdr_usb_from_the_aio_gate()


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
