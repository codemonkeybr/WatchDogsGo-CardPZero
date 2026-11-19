# Roadmap — WatchDogsGo → CardputerZero port

Living tracking document. Update task checkboxes and the **Progress log**
at the bottom as work happens — this file, not `CLAUDE.md`, is the source
of truth for "where are we right now." `CLAUDE.md` holds the
why/architecture/risk context that doesn't change week to week.

**Status legend:** ⬜ not started · 🔵 in progress · ✅ done · ⛔ blocked

---

## Phase 0 — Hardware spike

**Status:** 🔵 in progress — device reachable over SSH, first two read-only
probes done (2026-11-18). Raw probe reports are kept out of git (hostnames,
usernames); the findings are summarized here and in `docs/hardware-notes.md`.
**Why first:** every later phase assumes answers to these. Cheap to test,
expensive to assume wrong.

| # | Task | Status | Notes |
|---|------|--------|-------|
| 0.0 | Shell on the device from the dev machine | ✅ | SSH with key auth works (default path; M5's ADB also exists but isn't needed — it's a stock Debian box). `tools/phase0-probe.sh` is the read-only inventory. Host/user are not recorded in the repo (it will be public) |
| 0.1 | Get pyxel drawing 320×170 **on-device** | 🔵 | **Measured:** the panel is `/dev/fb0` (`panel-mipi-dbid`, 320×170, 16 bpp RGB565, stride 640 B) plus DRM `card1` (`SPI-1`, 320×170); no Xorg/Xwayland/weston/cage/sway process found; `fb0` is group `video` and the user is a member, so no root. pyxel by default needs an OpenGL window (fails without GL) but `headless=True` works and gives `pyxel.screen.data_ptr()` → plan: headless pyxel + RGB565 blit to fb0. The launcher (`APPLaunch.service`, a systemd *user* service) keeps `/dev/fb0` and `/dev/input/event3` open. **Done:** pyxel 3.0.2 installs in a venv on the device (`~/WatchDogsGo-CardPZero/.venv`, `--system-site-packages`) and `tools/pyxel-smoke.py --headless` passes there — init 320×170, both fonts, readable buffer, render byte-identical to the desktop one, peak RSS 26 MiB. Non-headless pyxel was deliberately not tried on the device (SDL could grab the DRM master and blank the panel). **Next:** (a) fb0 blit test (will scribble over the launcher UI — ask the owner first); (b) launcher handover: with M5's LoRa app running, the launcher is *not* stopped (state `S`) and still holds fb0 and `event3`, and the app is spawned as `sh -c <Exec>` and opens fb0/event3 itself — so both can read the keyboard; how the launcher stays out of the way, and the "Sysplause" column in `preinstalled-desktop-apps.tsv`, are still unknown. M5's docs say long-pressing ESC exits to HOME, probably the launcher watching the key — don't rely on a long-press ESC in the game |
| 0.2 | Python deps on the shipped OS | 🔵 | Device: Python 3.13.5, pip 25.1.1, Debian 13. Already installed system-wide: `pyserial` 3.5, `Pillow` 11.1, `dbus-python` 1.4, `gi` 3.50, `cryptography` 43, `requests`, `lgpio`, `RPi.GPIO`, `gpiod` 2.2, `spidev`, `smbus2`. Missing: `pyxel`, `scapy`, `bleak`, `LoRaRF`, `PyNaCl`, `netifaces`. PyPI has aarch64 wheels (py3.13) for all of those except `netifaces` → `apt install python3-netifaces` (needs sudo) or drop it. Use a `--system-site-packages` venv to reuse the apt packages. Upstream pins `pyxel>=2.0.0` so the device pulls 3.x — the game is untested on pyxel 3 |
| 0.3 | GPIO/SPI library that works on the CM0 | ✅ | `lgpio`, `RPi.GPIO`, `gpiod` and `spidev` all import. Nodes `/dev/gpiochip0/1/2` (`gpiochip4` is an alias of `gpiochip0`, Pi5-style), `/dev/spidev0.1`, `/dev/i2c-*` belong to groups `gpio`/`spi`/`i2c`, and the user is in all three. Not yet exercised against real hardware. `gpiochip2` is `m5ioe1`, an I²C IO expander that switches the 5 V rails |
| 0.4 | Privilege model | 🔵 | **Measured:** device nodes need no root (groups gpio/spi/i2c/input/video/dialout/netdev/render), and the Cap's 5 V rail (`/sys/class/leds/ext_5v_out/brightness`) is group-writable via a udev rule shipped by M5's LoRa package. Still needs privilege: raw sockets (scapy, `CAP_NET_RAW`), triggering `iw` scans (`CAP_NET_ADMIN`, or NetworkManager over D-Bus via `netdev`). M5's own packages use two patterns: narrow udev rules, or `.desktop` `Exec=/usr/bin/sudo -n -- <bin>` plus a per-binary NOPASSWD `/etc/sudoers.d/<pkg>` shipped in the `.deb` (3 first-party apps). No per-app systemd service exists on the device. `tesso` is a normal sudoer (password). **Next:** raw-socket test once scapy is installed |
| 0.5 | ESP32 (projectZero) over a USB host port, unmodified `serial_manager.py` | ⬜ | Not plugged in yet. Host mode works: internal 4-port hub (Genesys 05e3:0610) is up with a USB LAN adapter on it; user is in `dialout` |
| 0.6 | NESDR SMART (RTL-SDR) via `dump1090`/`rtl_433` | ⬜ | Not plugged in yet; `rtl-sdr`, `rtl_433`, `dump1090` aren't installed (apt, needs sudo; `dump1090` is built from source upstream). Blacklist `dvb_usb_rtl28xxu` when it is |
| 0.7 | Cap LoRa-1262 real pin mapping | 🔵 | M5's own `Cap-LoRa-1262` app (RadioLib) opens `/dev/spidev0.0`, `/dev/spidev0.1`, `/dev/gpiochip0`, `/dev/i2c-1` → SX1262 on **SPI0 (CLK G11, MOSI G10, MISO G9), NSS = CS1/G7 = `/dev/spidev0.1`** (CS0/G8 is the display). GPS app uses **`/dev/ttyS0`** = UART on G14/G15; kernel console is on `tty1`, so the port is free. Cap power = write `1` to `/sys/class/leds/ext_5v_out/brightness`. **Pins derived and mostly confirmed:** crossing M5's Cap-Bus table with the CardputerZero EXT table (the Cap-Bus is the same physical 14-pin header; the SPI pins line up one-to-one) gives **RST = G26, IRQ/DIO1 = G23, BUSY = G22**, NSS = G7 (CS1), SCK/MOSI/MISO = G11/G10/G9, I²C = G2/G3 (`/dev/i2c-1`), GPS = G14/G15. Measured with the Cap attached and M5's LoRa app open: `gpioinfo` shows G26 as an **output** and G22/G23 as inputs (consumer `pw_digital_io_linux`), the app holds `/dev/spidev0.1` and `/dev/i2c-1`, and the rail reads `ext_5v_out=255`. GPS verified: NMEA (GN/GP GGA/RMC/GSA/GSV…) at **115200** on `/dev/ttyS0` (9600 gives nothing), no fix indoors. **Still open:** (1) which of G22/G23 is BUSY and which is DIO1 rests on the pin-order derivation — settle it with an SPI/GPIO test after the owner closes M5's app (reset pulse on G26, `SetRx` with a short timeout so DIO1 rises without transmitting, watch both lines); (2) the newer Cap LoRa-1262 has a PI4IOE5V6408 expander whose P0 must be set high to enable the RF antenna switch — nothing answered at I²C 0x43/0x44, so this unit may be the legacy Cap LoRa868 (no expander): confirm the module model |
| 0.8 | Which upstream ref to vendor from | ✅ | Decided 2026-11-18: `feat/aiov2-wifi-bt-fallback` (carries the internal-radio bridge fallback). **Revised:** upstream `main` has moved to `72441cb` (v0.10.0), 4 commits past our base `7427fbf`, so rebase the branch onto it first — see 1.1 and `docs/portal-rules.md` |
| 0.9 | Probe the internal radio | ✅ | **Measured:** `iw` is installed (`/usr/sbin`); `wlan0` managed, **supported modes IBSS / managed / AP / P2P — no monitor**, a single band (2.4 GHz), driver `brcmfmac` (+`brcmfmac_cyw`), firmware BCM43439-class. BT: `hci0` UP on the UART, HCI/LMP **5.2** (CYW4343A2). `wlan0` carries the default route (the SSH session rides on it). Conclusion: scan-only — WiFi wardriving (2.4 GHz) and BLE yes; deauth/handshake/sniffer/Evil Twin/SAE flood no. Remaining (moved into 2.7): `iw scan` without root, and a `bleak` scan |
| 0.10 | RAM budget (new) | 🔵 | ~353 MiB visible (`gpu_mem=128`, `cma-64`), **~145 MiB available** with launcher and services running, plus 352 MiB zram swap (zstd). Measure the game's RSS early; import `scapy` lazily. First data point: an idle headless pyxel process peaks at 26 MiB RSS |

**Exit criteria:** 0.1, 0.2, 0.4 answered on the device (not assumed);
0.5/0.6 verified with the real peripherals; 0.7 pins confirmed; 0.10 has a
first RSS measurement.

---

## Phase 1 — Minimal running build (menus + map, no radio hardware)

**Status:** ⬜ not started — blocked on 0.1 (pyxel on the device) and the
vendoring rebase

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | Rebase `feat/aiov2-wifi-bt-fallback` onto upstream `main` (`72441cb`, v0.10.0) in the owner's fork, then vendor `watchdogs/` from it; the vendoring commit records the exact source SHA | ⬜ | Upstream changed the portal client (UA platform detection, rabbits/game-state) — see `docs/portal-rules.md`. Keep the upstream `LICENSE` (MIT, © LOCOSP) with the vendored code |
| 1.2 | Re-layout HUD/menu/terminal/map for 320×170 | ⬜ | Proposal in `docs/ui-adaptation.md`; can be developed and reviewed entirely off-device with headless pyxel |
| 1.3 | Remap keyboard bindings | ⬜ | **Measured:** the keyboard is a TCA8418 (I²C 0x34, 5×10 matrix) on `/dev/input/event3` (alias `/dev/input/cardputer-zero-internal`, group `input`), and the kernel overlay defines three keymaps (base, shift/sym, fn). Decoded by eye from the overlay, the fn layer emits real `KEY_UP/DOWN/LEFT/RIGHT`, F1–F12, PageUp/PageDown, Home/End, Insert/Delete and media keys — so no raw-matrix handling is needed. Verify with a live capture (`evtest` isn't installed; python `evdev` or `cat` works) |
| 1.4 | Stub out `aio_manager.py`'s `pinctrl`/`aiov2_ctl` rail toggles (uConsole/AIO-v2-only) | ⬜ | The Cap's 5 V rail is `/sys/class/leds/ext_5v_out` here — a candidate replacement for the "GPS/LoRa power" toggles |
| 1.5 | Validate loot/XP persistence on the microSD-backed home dir | ⬜ | |
| 1.6 | Game runs end-to-end with zero radio hardware attached | ⬜ | Upstream's fail-closed manager pattern should make this straightforward once 1.1–1.3 land |
| 1.7 | Headless-pyxel platform shim: evdev → `pyxel.set_btn`, buffer → RGB565 → `/dev/fb0`, plus the launcher handover | ⬜ | Depends on the 0.1 on-device results |

**Exit criteria:** the game launches, renders correctly at 320×170, is
navigable with the CardputerZero's own keyboard, persists state across
restarts, and stays within the RAM budget — all with no ESP32/LoRa/GPS/SDR
plugged in.

---

## Phase 2 — Radio hardware integration

**Status:** ⬜ not started — blocked on Phase 0.5–0.7 and Phase 1

| # | Task | Status | Notes |
|---|------|--------|-------|
| 2.1 | Wire up the ESP32 projectZero link for real (WiFi/BLE scan, deauth, handshake capture, Evil Twin, BLE HID) | ⬜ | |
| 2.2 | Port `lora_manager.py` to the CardputerZero mapping: **SPI bus 0, CS 1** (uConsole code uses bus 1, CS 0), **RST = G26, DIO1/IRQ = G23, BUSY = G22** (0.7), Cap power via the `ext_5v_out` LED | ⬜ | The decode/encode layer should need no change. Upstream polls the IRQ register over SPI rather than the pin, so BUSY vs DIO1 matters mostly for BUSY pacing. If the Cap turns out to be the LoRa-1262 with the PI4IOE5V6408, set its P0 high first (RF switch) |
| 2.3 | Point `gps_manager.py` at `/dev/ttyS0` (115200 8N1 per the module docs) | ⬜ | Measured: NMEA at **115200** on `/dev/ttyS0`; upstream defaults are `/dev/ttyAMA0` @ 9600 (`config.py`), so set `WDG_GPS_DEVICE=/dev/ttyS0` and `WDG_GPS_BAUD=115200` or change the defaults. The parser already accepts `$GPGGA/$GNGGA/$GPRMC/$GNRMC`. Power the rail first |
| 2.4 | Re-verify MeshCore decode/encode + sniffer presets unchanged | ⬜ | Protocol-level, should be hardware-agnostic |
| 2.5 | NESDR SMART for ADS-B (`dump1090`) and 433 MHz (`rtl_433`) in-game | ⬜ | |
| 2.6 | Validate an external monitor-mode USB WiFi adapter (Alfa AWUS036ACH/ACM) for Dragon Drain/deauth | ⬜ | Now confirmed mandatory: the internal radio has no monitor mode (0.9) |
| 2.7 | Run `wdg_wifi_bridge.py` against the internal `wlan0`/`hci0` (scan-only, no monitor mode) and confirm WiFi + BLE wardriving through the unchanged serial protocol | ⬜ | `iw` and `hci0` are present. Needs `bleak` installed, a privilege answer for `iw scan`, and SSID comma-quoting checked in the bridge's CSV output |
| 2.8 | Explicit scan-source setting (`auto` \| `esp32` \| `internal`) — env/`secrets.conf` + SYSTEM-menu entry — replacing "ESP32 if present, else bridge" | ⬜ | Keep upstream identifiers; change only user-visible "AIO v2" strings. Using both sources at once is out of scope for now |

**Exit criteria:** WiFi/BLE scanning, LoRa/MeshCore, GPS fix, ADS-B, and 433
MHz decoding all work from in-game menus with the real hardware attached.

---

## Phase 3 — Package as an installed CardputerZero app

**Status:** ⬜ not started — blocked on the 0.4 privilege answer and 0.1

| # | Task | Status | Notes |
|---|------|--------|-------|
| 3.1 | Settle the privilege design | ⬜ | Options now concrete: (a) non-root using group access + udev rules (+ capabilities for raw sockets), or (b) M5's own pattern — `.desktop` `Exec=/usr/bin/sudo -n -- <wrapper>` with a per-binary NOPASSWD sudoers drop-in. If (b): the wrapper and the code it runs must be root-owned and not user-writable, and the sudoers entry must allow no arguments |
| 3.2 | Build the `.deb` following the layout of the *installed* first-party apps | ⬜ | `usr/share/APPLaunch/applications/<name>.desktop` (`Terminal=false`), `usr/share/APPLaunch/share/images/<icon>.png`, app files under `usr/share/<App>/…` (or `usr/share/APPLaunch/bin`), optional `usr/lib/udev/rules.d/*.rules` and `etc/sudoers.d/<pkg>` (mode 0440), license docs. No per-app systemd service on the device, so AppBuilder's service model isn't needed. `app-builder.json` only matters for the store |
| 3.3 | Sideload (`scp` + `sudo dpkg -i` or `apt install ./x.deb`) and confirm it appears on and launches from the home screen | ⬜ | Needs the owner's sudo password. No `czdev publish` / store submission |
| 3.4 | Short install doc for community testers | ⬜ | Adapted from upstream's quick-install |

**Exit criteria:** a `.deb` that a tester can install on their own
CardputerZero and launch from the home screen like any other app.

---

## Phase 4 — Feature-parity pass + community feedback

**Status:** ⬜ not started — blocked on Phase 3

| # | Task | Status | Notes |
|---|------|--------|-------|
| 4.1 | Flipper Zero USB integration (VID:PID detection) | ⬜ | Should be unchanged from upstream |
| 4.2 | Make the portal client conform to upstream's fork rules | ⬜ | See `docs/portal-rules.md`: `Fork/CardputerZero-<ver>` UA tag, honest platform string, rate limits + `Retry-After`, no double uploads |
| 4.3 | Share the sideload build with the WatchDogsGo community, collect feedback | ⬜ | Explicit owner goal — before any App Store conversation |
| 4.4 | Triage feedback (bugs vs. "won't fit this hardware" vs. "worth a store listing later") | ⬜ | |
| 4.5 | Screen for `/api/device-pair` code pairing | ⬜ | A 64-char key on a 46-key keyboard is painful; upstream's pairing exists at the API level but has no UI yet |
| 4.6 | Consider the Cap CC1101 modules | ⬜ | M5 ships NFC and Sub-GHz-chat apps for them, so they exist for this device; possible Flipper-style features later |

**Exit criteria:** community has a build they can install and play, and
feedback has been collected and triaged.

---

## Before publishing the repo on GitHub

- [ ] `LICENSE`: upstream is MIT (© LOCOSP). Keep that notice with any vendored
      code and choose the license for new code (MIT keeps it simple).
- [ ] Credit upstream `LOCOSP/WatchDogsGo` and the community contributors
      (e.g. the bridge's authors) in the README.
- [ ] Scrub local absolute paths (`/home/...`) and anything device-specific
      (host, IP, username) from the docs — `git grep` before the first push.
- [ ] Portal rules satisfied (`docs/portal-rules.md`).
- [ ] Community README: sideload install steps, 320×170 screenshots.
- [ ] Commits authored with the owner's configured git identity; default
      branch `main`.
- [ ] `secrets.conf` and raw probe reports stay untracked (already in
      `.gitignore`).

---

## Progress log

Append newest entries at the top. One line per session/milestone is enough
— the task tables above carry the detail.

- **2026-11-18 (on-device tests)** — Created dev venvs (repo `.venv` and
  `~/WatchDogsGo-CardPZero/.venv` on the device). pyxel 3.0.2 runs headless on
  the device (26 MiB RSS, render identical to desktop). With the Cap attached
  and M5's LoRa app open: G26 is an output, G22/G23 inputs, `spidev0.1` held,
  rail on; GPS NMEA flows at 115200 on `/dev/ttyS0` (no fix indoors). Owner
  pointed out the pins are documented on M5's site — right: crossing the Cap-Bus
  table with the CardputerZero EXT table yields RST=G26, IRQ=G23, BUSY=G22,
  consistent with the measurements (`docs/hardware-notes.md`). No answer from
  the PI4IOE5V6408 RF-switch expander → possibly the legacy Cap LoRa868.
  Launcher is not paused while an app runs.
- **2026-11-18 (device measured)** — Owner gave SSH access (reserved IP);
  noted privately, not in the repo. Ran the read-only probe twice. Big
  findings: stock Debian 13 on a Pi CM0 (SSH, not ADB); display is a plain
  `/dev/fb0` 320×170 RGB565 with no X/Wayland (headless pyxel + fb blit is
  viable and needs no root); RAM is the tight resource (~145 MiB free);
  internal WiFi has **no monitor mode** (scan-only, 2.4 GHz) while `hci0`
  works (BT 5.2); non-root access to GPIO/SPI/I²C/input/fb works through
  group membership; M5's packaging precedent is `.desktop` + sudoers/udev, not
  per-app services; Cap LoRa on SPI0 CS1 with GPS on `/dev/ttyS0`, BUSY/IRQ/RST
  ∈ {G22, G23, G26}. Upstream `main` moved to v0.10.0 and added fork rules for
  the portal → `docs/portal-rules.md`, and the vendoring base must be rebased
  (1.1). Added "before publishing" checklist; git default branch → `main`.
- **2026-11-18 (Phase 0 started)** — Decided to vendor from
  `feat/aiov2-wifi-bt-fallback` (internal-radio bridge fallback); added 0.9
  and 2.7/2.8. Desktop-side: aarch64 wheels exist for every dependency except
  `netifaces`/`dbus-python`; pyxel needs OpenGL unless `headless=True`, which
  works and exposes the frame buffer. Wrote `tools/phase0-probe.sh`,
  `tools/pyxel-smoke.py`, `docs/ui-adaptation.md`.
- **2026-11-18** — Repo created. `CLAUDE.md` and `docs/hardware-notes.md`
  written (device/expansion-board specs, upstream architecture, platform
  risk list). Corrected an early misread: the "ADB Scan (Radar)" USB
  peripheral is actually a NooElec NESDR SMART (RTL-SDR). `ROADMAP.md`
  created to track phase-by-phase status.
