"""Auto-start the internal-radio WiFi/BT bridge when no ESP32 is plugged in.

``wdg_wifi_bridge.py`` (vendored) already emulates an ESP32 projectZero
device over a PTY using the host's own WiFi (wlan0) and Bluetooth (hci0) —
upstream wrote it for the uConsole's second WiFi adapter, but on the
CardputerZero there's only the one internal radio, no monitor mode, and
(after the nmcli/root fix in wdg_wifi_bridge.py) no sudo requirement either.
This module is the glue: `maybe_start()` checks for a real ESP32 first (it
always wins when plugged in) and only then spawns the bridge, matching
``serial_manager.detect_aiov2_bridge_port()``'s expected PTY path so the
vendored game code needs no changes at all.
"""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path

log = logging.getLogger(__name__)

_ROOT = Path(__file__).resolve().parent.parent
_WIFI_IFACE = "wlan0"
_BT_IFACE = "hci0"
_START_TIMEOUT = 8.0

_proc: subprocess.Popen | None = None


def maybe_start(log_dir: str | None = None) -> str | None:
    """Start the internal-radio bridge if there's no ESP32 and wlan0 exists.

    Returns the PTY path to pass as the game's serial port, or None (no
    ESP32 *and* no usable internal radio, or the bridge failed to come up —
    the game's managers fail closed either way, same as upstream).
    """
    global _proc
    from watchdogs.serial_manager import detect_esp32_port, AIOV2_BRIDGE_PTY

    if detect_esp32_port():
        return None  # a real ESP32 always wins
    if not os.path.exists(f"/sys/class/net/{_WIFI_IFACE}"):
        log.info("internal radio: no ESP32 and no %s — nothing to fall back to",
                  _WIFI_IFACE)
        return None

    try:
        os.remove(AIOV2_BRIDGE_PTY)
    except FileNotFoundError:
        pass

    log_dir = log_dir or os.path.expanduser("~/.watchdogs")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "internal-radio-bridge.log")
    logf = open(log_path, "a")
    _proc = subprocess.Popen(
        [sys.executable, str(_ROOT / "wdg_wifi_bridge.py"),
         "--iface", _WIFI_IFACE, "--bt-iface", _BT_IFACE,
         "--no-monitor", "--pty", AIOV2_BRIDGE_PTY],
        stdout=logf, stderr=subprocess.STDOUT, start_new_session=True,
    )
    log.info("internal radio: starting bridge on %s/%s (pid %d), log: %s",
              _WIFI_IFACE, _BT_IFACE, _proc.pid, log_path)

    deadline = time.time() + _START_TIMEOUT
    while time.time() < deadline:
        if os.path.exists(AIOV2_BRIDGE_PTY):
            log.info("internal radio: bridge up at %s", AIOV2_BRIDGE_PTY)
            return AIOV2_BRIDGE_PTY
        if _proc.poll() is not None:
            log.warning("internal radio: bridge exited early (code %s) — see %s",
                        _proc.returncode, log_path)
            return None
        time.sleep(0.2)
    log.warning("internal radio: bridge did not come up within %.0fs", _START_TIMEOUT)
    return None


def stop() -> None:
    """Stop a bridge started by this process, if any. Safe to call anytime."""
    global _proc
    if _proc is not None and _proc.poll() is None:
        _proc.terminate()
        try:
            _proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _proc.kill()
    _proc = None
