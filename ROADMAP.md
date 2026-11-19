# Roadmap — WatchDogsGo → CardputerZero port

Living tracking document. Update task checkboxes and the **Progress log**
at the bottom as work happens — this file, not `CLAUDE.md`, is the source
of truth for "where are we right now." `CLAUDE.md` holds the
why/architecture/risk context that doesn't change week to week.

**Status legend:** ⬜ not started · 🔵 in progress · ✅ done · ⛔ blocked

---

## Phase 0 — Hardware spike

**Status:** ⬜ not started
**Why first:** every later phase assumes answers to these. Cheap to test,
expensive to assume wrong.

| # | Task | Status | Notes |
|---|------|--------|-------|
| 0.0 | Get a shell on the device from the dev machine (ADB over the right USB-C in slave mode, or SSH over WiFi), then run `tools/phase0-probe.sh` (read-only inventory) | ⛔ | **Current blocker for every on-device item.** 2026-11-18: `adb devices` was empty and nothing matching in `lsusb`, so the device isn't connected to this machine yet |
| 0.1 | Get pyxel running at 320×170 **on-device** | 🔵 | Desktop findings: by default pyxel (2.9.9 and 3.0.2 both tested) needs an OpenGL window and panics on SDL's `dummy` driver; `pyxel.init(headless=True)` works with no display/GL and `pyxel.screen.data_ptr()` returns the 320×170 palette-index buffer. Candidate device path: headless pyxel + a small platform shim (evdev keyboard → `pyxel.set_btn`, buffer → RGB565 → the panel's fb/DRM node). Still unknown: which fb/DRM node drives the ST7789v3 panel and whether X/Wayland runs (probe section 2). Test with `tools/pyxel-smoke.py`, on the device with and without `--headless` |
| 0.2 | Confirm aarch64 availability of the Python deps on the shipped OS image | 🔵 | PyPI check (py3.11 and 3.13, manylinux_2_28 aarch64): wheels exist for `pyxel` 3.0.2, `pyserial`, `Pillow`, `scapy`, `bleak`, `LoRaRF`, `cryptography`, `PyNaCl`, `requests`. **No aarch64 wheel for `netifaces` or `dbus-python`** (sdist only) → use Debian's `python3-netifaces` / `python3-dbus` with a `--system-site-packages` venv, or compile (heavy on 512 MB). Not yet checked on the device itself (needs glibc ≥ 2.28). Upstream pins `pyxel>=2.0.0`, so the device would pull 3.x — the game itself is untested on pyxel 3 |
| 0.3 | Confirm which GPIO library works against BCM2837 (CM0) on this image — `python3-rpi-lgpio`, `RPi.GPIO`, `lgpio`, or raw `/dev/gpiochip*` | ⬜ | Upstream's `rpi-lgpio` targets Pi5/CM5 (BCM2711/2712), CM0 is BCM2837 — don't assume it works unchanged |
| 0.4 | Spike the non-root privilege model: minimal raw-socket test under a Linux capability (`cap_net_raw`/`cap_net_admin`) or udev-granted group, no `sudo` | ⬜ | Gates whether Phase 3 packaging is even possible as specified |
| 0.5 | Get ESP32 (projectZero) talking over a CardputerZero USB host port with **unmodified** `serial_manager.py` | ⬜ | Low risk — plain USB-serial |
| 0.6 | Verify NooElec NESDR SMART (RTL-SDR) through `dump1090`/`rtl_433`, including the `dvb_usb_rtl28xxu` kernel-module blacklist step | ⬜ | Low risk — plain USB, upstream already has `sdr_manager.py` for this device class |
| 0.7 | Measure/derive the Cap LoRa-1262 module's real CardputerZero GPIO pin numbers (schematic or continuity-test the Cap-Bus pins against the SoC) | ⬜ | Only the Cardputer-Adv mapping is public; CardputerZero's is a different SoC entirely |
| 0.8 | Decide which upstream ref to vendor from | ✅ | Decided 2026-11-18: `feat/aiov2-wifi-bt-fallback` @ `cad1e77` (4 commits ahead of `main` `7427fbf`) — it carries the internal-WiFi/BT bridge fallback the owner wants as an option. Unmerged, so record the SHA when vendoring |
| 0.9 | Probe the **internal** radio: which WiFi/BT chip and driver (`iw phy`, `dmesg \| grep -i brcm`), does `iw dev wlan0 scan` work non-root / under `CAP_NET_ADMIN`, is `hci0` present and does a `bleak` scan return devices, and (optional) is monitor mode available at all | ⬜ | Backs the "internal radio as a scan source" feature; expectation is scan-only (no deauth/handshake) |

**Exit criteria:** 0.1–0.6 answered with a real yes/no (not an assumption);
0.7 has at least a working hypothesis to code against; 0.8 decided (done);
0.9 tells us what the internal radio can and can't do.

---

## Phase 1 — Minimal running build (menus + map, no radio hardware)

**Status:** ⬜ not started — blocked on Phase 0.1–0.4

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | Vendor `watchdogs/` package from the chosen upstream ref, commit records the exact source SHA | ⬜ | |
| 1.2 | Re-layout HUD/menu/terminal/map constants for 320×170 | ⬜ | Not a linear scale — 640/320=2.0 but 360/170≈2.12, aspect ratio differs (16:9 vs ~1.88:1); panels likely need to become toggle/overlay instead of always-on given less vertical room |
| 1.3 | Remap keyboard bindings to the Cardputer Zero's direct keys + `fn`-layer combos, verified against actual pyxel keycodes on-device | ⬜ | See `docs/hardware-notes.md` fn-layer table; docs are internally inconsistent about PgUp/PgDn, don't trust blindly |
| 1.4 | Stub out `aio_manager.py`'s `pinctrl`/`aiov2_ctl` rail toggles (uConsole/AIO-v2-only, doesn't apply here) | ⬜ | |
| 1.5 | Validate loot/XP persistence (`loot/loot_db.json`, `~/.watchdogs*`) on the microSD-backed home dir | ⬜ | |
| 1.6 | Game runs end-to-end with zero radio hardware attached (menus, map, terminal, plugins) | ⬜ | Upstream's fail-closed manager pattern should make this straightforward once 1.1–1.3 land |

**Exit criteria:** the game launches, renders correctly at 320×170, is
navigable with the Cardputer Zero's own keyboard, and persists state across
restarts — all with no ESP32/LoRa/GPS/SDR plugged in.

---

## Phase 2 — Radio hardware integration

**Status:** ⬜ not started — blocked on Phase 0.5–0.7 and Phase 1

| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | Wire up ESP32 projectZero link for real (WiFi/BLE scan, deauth, handshake capture, Evil Twin, BLE HID) | ⬜ | |
| 2.2 | Port `lora_manager.py` SPI bus/CS + GPIO (RST/BUSY/IRQ) constants to the real CardputerZero pin mapping from 0.7 | ⬜ | |
| 2.3 | Port `gps_manager.py` to the Cap module's GPS UART device path | ⬜ | Already generic via pyserial — mostly a device-path change |
| 2.4 | Re-verify MeshCore decode/encode + sniffer presets unchanged (protocol-level, should be hardware-agnostic) | ⬜ | |
| 2.5 | Wire up NESDR SMART for ADS-B (`dump1090`) and 433 MHz (`rtl_433`) for real, in-game | ⬜ | |
| 2.6 | Validate an external monitor-mode USB WiFi adapter (Alfa AWUS036ACH/ACM) for Dragon Drain/deauth — CardputerZero's onboard WiFi has no monitor-mode claim | ⬜ | Same requirement as uConsole, just now mandatory rather than optional |
| 2.7 | Run the upstream `wdg_wifi_bridge.py` against the internal `wlan0`/`hci0` (scan-only, no monitor mode) and confirm WiFi + BLE wardriving works through the unchanged serial protocol | ⬜ | Depends on 0.9; may need `--iface`/`--bt-iface` and path tweaks, and the bridge itself needs the same privilege decision as the game |
| 2.8 | Add an explicit scan-source setting (`auto` \| `esp32` \| `internal`) — env/`secrets.conf` + SYSTEM-menu entry — replacing the implicit "ESP32 if present, else bridge" fallback | ⬜ | Keep upstream identifiers; change only user-visible "AIO v2" strings. Using both sources at once is out of scope for now |

**Exit criteria:** WiFi/BLE scanning, LoRa/MeshCore, GPS fix, ADS-B, and 433
MHz decoding all work from in-game menus with the real hardware attached.

---

## Phase 3 — Package as an installed CardputerZero app

**Status:** ⬜ not started — blocked on Phase 0.4's privilege-model answer

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Resolve the privilege model for real (capabilities / udev rules / helper daemon) — not a spike, the shipped design | ⬜ | Gates whether a systemd-service package works at all |
| 3.2 | Build the `.deb`: `DEBIAN/{control,postinst,prerm}`, systemd unit, `.desktop` under `usr/share/APPLaunch/applications/`, `app-builder.json` manifest (needs a 320×170 screenshot) | ⬜ | Reuse the AppBuilder packaging *shape*, not its LVGL/CMake build step — this project is Python/pyxel |
| 3.3 | Sideload via `scp` + `sudo dpkg -i`, confirm it appears on and launches from the home screen | ⬜ | No `czdev publish` / store submission — explicitly out of scope right now |
| 3.4 | Write a short install doc for community testers (parallel to upstream's `curl \| sudo bash` quick-install, adapted for sideload) | ⬜ | |

**Exit criteria:** a `.deb` that a tester can `scp`+`dpkg -i` onto their own
CardputerZero and launch from the home screen like any other installed app.

---

## Phase 4 — Feature-parity pass + community feedback

**Status:** ⬜ not started — blocked on Phase 3

| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | Flipper Zero USB integration (VID:PID detection) | ⬜ | Should be unchanged from upstream |
| 4.2 | Decide how CardputerZero-build WDGWars portal traffic is tagged/routed | ⬜ | Don't silently break the `WatchDogsGo/` User-Agent token classification upstream relies on — coordinate before shipping |
| 4.3 | Share the sideload build with the WatchDogsGo community, collect feedback | ⬜ | Explicit owner goal — do this *before* any App Store conversation |
| 4.4 | Triage feedback into a follow-up list (bugs vs. "won't fit this hardware" vs. "worth a store listing later") | ⬜ | |

**Exit criteria:** community has a build they can actually install and
play, and feedback has been collected and triaged.

---

## Progress log

Append newest entries at the top. One line per session/milestone is enough
— the task tables above carry the detail.

- **2026-11-18 (Phase 0 started)** — Decided to vendor from
  `feat/aiov2-wifi-bt-fallback` (the internal-radio bridge fallback lives
  there); added 0.9 and 2.7/2.8 for the internal radio as a selectable scan
  source. Desktop-side results: aarch64 wheels exist for every dependency
  except `netifaces`/`dbus-python`; pyxel needs OpenGL unless
  `headless=True`, which works and exposes the frame buffer — this shapes
  the on-device rendering plan (0.1). Wrote `tools/phase0-probe.sh`
  (read-only device inventory) and `tools/pyxel-smoke.py`. **Blocked on
  device access (0.0):** not visible via adb/lsusb from this machine, so all
  on-device spikes (0.1, 0.3–0.7, 0.9) wait on it. Also wrote
  `docs/ui-adaptation.md` (proposal for the 320×170 re-layout).
- **2026-11-18** — Repo created. `CLAUDE.md` and `docs/hardware-notes.md`
  written (device/expansion-board specs, upstream architecture, platform
  risk list). Corrected an early misread: the "ADB Scan (Radar)" USB
  peripheral is actually a NooElec NESDR SMART (RTL-SDR) — downgraded from
  an open question to a Phase 0/1 verify-only item, since upstream already
  has `sdr_manager.py` for that device class. This `ROADMAP.md` created to
  track phase-by-phase status going forward. No code ported yet — still
  entirely in Phase 0.
