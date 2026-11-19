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
| 0.1 | Get pyxel drawing 320×170 **on-device** | ✅ | **Measured:** the panel is `/dev/fb0` (`panel-mipi-dbid`, 320×170, 16 bpp RGB565, stride 640 B) plus DRM `card1` (`SPI-1`, 320×170); no Xorg/Xwayland/weston/cage/sway process found; `fb0` is group `video` and the user is a member, so no root. pyxel by default needs an OpenGL window (fails without GL) but `headless=True` works and gives `pyxel.screen.data_ptr()` → plan: headless pyxel + RGB565 blit to fb0. The launcher (`APPLaunch.service`, a systemd *user* service) keeps `/dev/fb0` and `/dev/input/event3` open. **Done:** pyxel 3.0.2 installs in a venv on the device (`~/WatchDogsGo-CardPZero/.venv`, `--system-site-packages`) and `tools/pyxel-smoke.py --headless` passes there — init 320×170, both fonts, readable buffer, render byte-identical to the desktop one, peak RSS 26 MiB. Non-headless pyxel was deliberately not tried on the device (SDL could grab the DRM master and blank the panel). **fb0 blit verified:** `tools/fb-blit-test.py` renders with headless pyxel, converts the palette buffer to RGB565 (R5@11 G6@5 B5@0) and writes `/dev/fb0` — **30.0 fps sustained, ~4 ms per frame (draw 0.55 + convert 2.8 + write 0.7), ~16% of one core**; the previous screen is restored afterwards. **Next:** (a) read the keyboard from `event3` and inject it with `pyxel.set_btn` (the shim, 1.7); (b) **launcher handover — resolved by M5's guide** (`docs/launcher-guidelines.md`): for `Terminal=false` apps the launcher fork+execs them and pauses its own refresh while they run; our SSH-driven writes fought a launcher that wasn't paused (the first `write()` test showed nothing; with the launcher stopped, both `mmap` and `write()` persisted on read-back). `Sysplause` is only the "press any key" prompt of terminal apps. Kill path: long-press Home (fn+K) 5 s → SIGINT, +3 s → SIGKILL, so the game must exit on SIGINT; no long-press-ESC reliance. **To verify:** launch `tools/cz-demo.py` from the carousel (item 0.11) |
| 0.11 | Launcher-integration demo (new) | ✅ | `tools/cz-demo.py` (headless pyxel → `mmap` fb0, evdev keys shown on screen and logged, exits on ESC/timeout/SIGINT) and `tools/make-dev-entry.sh` (wrapper + `.desktop` generated in `~/WatchDogsGo-CardPZero/dev/` on the device) passed a 3 s SSH sanity run (30 fps). **Verified by the owner on 2026-11-18 (photo + log):** the entry registered with one `sudo install`, showed up in the carousel as "WDG Demo", launched from it and drew the animated 320×170 screen (≈30 fps over a 70 s run); the Spleen 5×8 font is crisp and legible at 1:1 on the real panel. Keyboard, from the log: with `fn` held, `fn+Z/X/C` arrive as real `KEY_LEFT/DOWN/RIGHT` (105/108/106) — the kernel translates the fn layer; **the `fn` key itself emits code 389** (down/up), which the game must ignore; an unmapped `fn+G` arrives as a plain `g`; ESC exits cleanly and the launcher resumes. Not yet exercised: `fn+F` (up), PgUp/PgDn/Home/End, and SIGINT via the Home long-press |
| 0.2 | Python deps on the shipped OS | 🔵 | Device: Python 3.13.5, pip 25.1.1, Debian 13. Already installed system-wide: `pyserial` 3.5, `Pillow` 11.1, `dbus-python` 1.4, `gi` 3.50, `cryptography` 43, `requests`, `lgpio`, `RPi.GPIO`, `gpiod` 2.2, `spidev`, `smbus2`. Missing: `pyxel`, `scapy`, `bleak`, `LoRaRF`, `PyNaCl`, `netifaces`. PyPI has aarch64 wheels (py3.13) for all of those except `netifaces` → `apt install python3-netifaces` (needs sudo) or drop it. Use a `--system-site-packages` venv to reuse the apt packages. Upstream pins `pyxel>=2.0.0` so the device pulls 3.x — the game is untested on pyxel 3 |
| 0.3 | GPIO/SPI library that works on the CM0 | ✅ | `lgpio`, `RPi.GPIO`, `gpiod` and `spidev` all import. Nodes `/dev/gpiochip0/1/2` (`gpiochip4` is an alias of `gpiochip0`, Pi5-style), `/dev/spidev0.1`, `/dev/i2c-*` belong to groups `gpio`/`spi`/`i2c`, and the user is in all three. Not yet exercised against real hardware. `gpiochip2` is `m5ioe1`, an I²C IO expander that switches the 5 V rails |
| 0.4 | Privilege model | 🔵 | **Measured:** device nodes need no root (groups gpio/spi/i2c/input/video/dialout/netdev/render), and the Cap's 5 V rail (`/sys/class/leds/ext_5v_out/brightness`) is group-writable via a udev rule shipped by M5's LoRa package. Still needs privilege: raw sockets (scapy, `CAP_NET_RAW`), triggering `iw` scans (`CAP_NET_ADMIN`, or NetworkManager over D-Bus via `netdev`). M5's own packages use two patterns: narrow udev rules, or `.desktop` `Exec=/usr/bin/sudo -n -- <bin>` plus a per-binary NOPASSWD `/etc/sudoers.d/<pkg>` shipped in the `.deb` (3 first-party apps). No per-app systemd service exists on the device. `tesso` is a normal sudoer (password). **Next:** raw-socket test once scapy is installed |
| 0.5 | ESP32 (projectZero) over a USB host port, unmodified `serial_manager.py` | ⬜ | Not plugged in yet. Host mode works: internal 4-port hub (Genesys 05e3:0610) is up with a USB LAN adapter on it; user is in `dialout` |
| 0.6 | NESDR SMART (RTL-SDR) via `dump1090`/`rtl_433` | ⬜ | Not plugged in yet; `rtl-sdr`, `rtl_433`, `dump1090` aren't installed (apt, needs sudo; `dump1090` is built from source upstream). Blacklist `dvb_usb_rtl28xxu` when it is |
| 0.7 | Cap LoRa real pin mapping | ✅ | M5's own `Cap-LoRa-1262` app (RadioLib) opens `/dev/spidev0.0`, `/dev/spidev0.1`, `/dev/gpiochip0`, `/dev/i2c-1` → SX1262 on **SPI0 (CLK G11, MOSI G10, MISO G9), NSS = CS1/G7 = `/dev/spidev0.1`** (CS0/G8 is the display). GPS app uses **`/dev/ttyS0`** = UART on G14/G15; kernel console is on `tty1`, so the port is free. Cap power = write `1` to `/sys/class/leds/ext_5v_out/brightness`. **Pins derived and mostly confirmed:** crossing M5's Cap-Bus table with the CardputerZero EXT table (the Cap-Bus is the same physical 14-pin header; the SPI pins line up one-to-one) gives **RST = G26, IRQ/DIO1 = G23, BUSY = G22**, NSS = G7 (CS1), SCK/MOSI/MISO = G11/G10/G9, I²C = G2/G3 (`/dev/i2c-1`), GPS = G14/G15. Measured with the Cap attached and M5's LoRa app open: `gpioinfo` shows G26 as an **output** and G22/G23 as inputs (consumer `pw_digital_io_linux`), the app holds `/dev/spidev0.1` and `/dev/i2c-1`, and the rail reads `ext_5v_out=255`. GPS verified: NMEA (GN/GP GGA/RMC/GSA/GSV…) at **115200** on `/dev/ttyS0` (9600 gives nothing), no fix indoors. **Confirmed by `tools/lora-pin-probe.py` (RX-only, nothing transmitted):** G26 = RST, **G22 = BUSY** (rises 0.09 ms after reset, falls 3.8 ms later) and **G23 = DIO1/IRQ** (rises at the RxTimeout, falls after ClearIrqStatus); the SX126x answers on `/dev/spidev0.1` (STBY_RC, default sync word 0x1424). **The module has a TCXO fed from DIO3**: without `SetDIO3AsTCXOCtrl` the chip reports `XOSC_START` and never enters RX; at 1.8 V it works (upstream already calls `setDio3TcxoCtrl(DIO3_OUTPUT_1_8, 10)`). The version register reads `SX1261 V2D 2D02`, but it can't tell SX1261 from SX1262 (Semtech forum), so trust the owner's label "LORA 868-932MHz SX1262". No PI4IOE5V6408 at 0x43/0x44 → consistent with the legacy Cap LoRa868 (no RF-switch expander). Real packet RX/TX belongs to 2.2 |
| 0.8 | Which upstream ref to vendor from | ✅ | Decided 2026-11-18: `feat/aiov2-wifi-bt-fallback` (carries the internal-radio bridge fallback). **Revised:** upstream `main` has moved to `8a2cb54` (v0.10.0+), 4 commits past our base `7427fbf`, so rebase the branch onto it first — see 1.1 and `docs/portal-rules.md` |
| 0.9 | Probe the internal radio | ✅ | **Measured:** `iw` is installed (`/usr/sbin`); `wlan0` managed, **supported modes IBSS / managed / AP / P2P — no monitor**, a single band (2.4 GHz), driver `brcmfmac` (+`brcmfmac_cyw`), firmware BCM43439-class. BT: `hci0` UP on the UART, HCI/LMP **5.2** (CYW4343A2). `wlan0` carries the default route (the SSH session rides on it). Conclusion: scan-only — WiFi wardriving (2.4 GHz) and BLE yes; deauth/handshake/sniffer/Evil Twin/SAE flood no. Remaining (moved into 2.7): `iw scan` without root, and a `bleak` scan |
| 0.10 | RAM budget (new) | 🔵 | ~353 MiB visible (`gpu_mem=128`, `cma-64`), **~145 MiB available** with launcher and services running, plus 352 MiB zram swap (zstd). Measure the game's RSS early; import `scapy` lazily. An idle headless pyxel process peaks at 26 MiB RSS. **The real game** (dry-run, 640×360 canvas, no hardware): 70 MiB after imports → **≈112–119 MiB** steady, flat over 100 s (the early growth is one-time loading) — fits next to the launcher (~131–153 MiB available) with little headroom; hardware managers will add some |

**Exit criteria:** 0.1, 0.2, 0.4 answered on the device (not assumed);
0.5/0.6 verified with the real peripherals; 0.7 pins confirmed; 0.10 has a
first RSS measurement.

---

## Phase 1 — Minimal running build (menus + map, no radio hardware)

**Status:** 🔵 in progress — 1.1 (vendoring) done; next: the runtime shim and
entry point (1.7) and the 320×170 layout (1.2)

| # | Task | Status | Notes |
|---|------|--------|-------|
| 1.1 | Rebase `feat/aiov2-wifi-bt-fallback` onto upstream `main` (`8a2cb54`, v0.10.0+) in a **new** branch of the owner's fork (no force-push), then vendor `watchdogs/` from it; the vendoring commit records the exact source SHA | ✅ | Upstream changed the portal client (UA platform detection, rabbits/game-state) — see `docs/portal-rules.md`. **Trial in a throwaway clone (2026-11-18): the 4 branch commits replay onto `8a2cb54` with no conflicts** — only `watchdogs/app.py` is touched by both sides, in different regions — and the result compiles. **Done 2026-11-18, commit `0603f22`:** vendored from the throwaway-clone rebase (tip `4bed612`) rather than a branch in the owner's fork, so nothing in the fork was touched (the owner can still create that branch later). Provenance, the reproduction recipe and re-sync steps are in `VENDORED.md`. Hard module-level dependencies of the game are only `pyxel` and `pyserial`; everything else (scapy, cryptography, dbus, bleak, LoRaRF, requests, netifaces, gi, nacl…) is imported lazily inside functions. Keep the upstream `LICENSE` (MIT, © LOCOSP) with the vendored code |
| 1.2 | Re-layout HUD/menu/terminal/map for 320×170 | 🔵 | **Approach (2026-11-18):** no edits to the vendored `app.py` — `czplatform/profile.py` resizes the game's canvas globals at run time (`--canvas 320x170`) and `czplatform/ui320.py` swaps in compact draw methods only in that profile (the 640×360 layout stays intact). **Done:** top HUD, bottom HUD, the **map/log split** (the map gets the screen and its last line is a ticker with the newest log entry; **ENTER** switches to a full-screen log, where arrows/PgUp/PgDn/Home/End scroll and ESC returns — keys consumed by an input filter on the injector; owner's idea), menu (tabs, scrolling list with scroll bar, per-tab character at half scale + speech bubble) and the half-size sprites (`assets/cz/`, `tools/make-sprites.py`) — samples in `docs/screenshots/320x170-*.png`. **Remaining:** the boot screen (logo cut off, check list overflows), every sub-screen (loot, MeshCore chat, MITM, Flipper, flasher, pickers, whitelist, dialogs — not yet toured), a help overlay for the key hints removed from the bottom bar (`fn+H`), an optional full-screen terminal view, the radio icon, and the literals still assuming 640×360 (`p.draw(0, 0, 640, 360)`, panels of 340/320/300 px…). Measured on the CM0 (dry-run): **RSS ≈45–64 MiB** (was ≈112–119 MiB at 640×360), 30 fps, game `draw` 2–10 ms, 14–39% of a core. Tour with `tools/ui-tour.sh`. Original notes: | Proposal in `docs/ui-adaptation.md`; can be developed and reviewed entirely off-device with headless pyxel |
| 1.3 | Remap keyboard bindings | ⬜ | **Measured:** the keyboard is a TCA8418 (I²C 0x34, 5×10 matrix) on `/dev/input/event3` (alias `/dev/input/cardputer-zero-internal`, group `input`), and the kernel overlay defines three keymaps (base, shift/sym, fn). Decoded by eye from the overlay, the fn layer emits real `KEY_UP/DOWN/LEFT/RIGHT`, F1–F12, PageUp/PageDown, Home/End, Insert/Delete and media keys — so no raw-matrix handling is needed. **Verified live** for the arrows with `tools/cz-demo.py` (0.11): they arrive as real `KEY_*` codes, and the `fn` key's own code 389 must be ignored. Still to check live: PgUp/PgDn/Home/End and the sym layer. pyxel's `KEY_*` constants are SDL keycodes, not evdev codes, so the shim (1.7) needs an evdev → `pyxel.KEY_*` table |
| 1.4 | Stub out `aio_manager.py`'s `pinctrl`/`aiov2_ctl` rail toggles (uConsole/AIO-v2-only) | ✅ | **Safety-critical, done at runtime in `czplatform/host.py`** (no vendored edit): `AioManager` is a no-op that never spawns `pinctrl`. Unadapted, its `GPIO_MAP` would drive GPIO 27 (keyboard interrupt), 23 (LoRa DIO1) and 7 (LoRa NSS) on this device, and `is_installed()` is just `which pinctrl`, which exists here. Covered by `tests/test_host.py`. The Cap's rail is switched by `CapRail` (`ext_5v_out`) instead |
| 1.5 | Validate loot/XP persistence on the microSD-backed home dir | ⬜ | |
| 1.6 | Game runs end-to-end with zero radio hardware attached | ⬜ | Upstream's fail-closed manager pattern should make this straightforward once 1.1–1.3 land |
| 1.8 | Screen policy for long sessions | ⬜ | **No auto-lock while our app is in the foreground** — APPLaunch calls `ui_screensaver_set_foreground(0)` before handing off to an external app (default idle lock is 30 s, Settings → Screen → DarkTime; TAB hold 3 s locks) and restarts the idle timer when we exit. For wardriving that means the screen stays on (battery); decide an own dim/blank + wake-on-key policy. The backlight is writable without root: `/sys/class/backlight/backlight/brightness` (root:video `rw-rw-r--`, max 100). **Open (the owner chose to leave it):** does the lock only paint black, or really switch the backlight off? The launcher source paints a black overlay *and* dims the backlight, but sysfs read 100 while the screen was black — settle by comparing the BQ27220 `current_now` awake vs locked. A locked/blank screen reads as one colour in `tools/fb-screenshot.py` |
| 1.7 | Platform layer + entry point: headless pyxel, evdev → `pyxel.set_btn`, frame → RGB565 → `/dev/fb0`, SIGINT → the game's own `_cleanup()` | 🔵 | **Implemented in `czplatform/`** (`display.py`, `keys.py`, `shim.py`, `host.py`, `__main__.py`; run with `python -m czplatform`) **without editing the vendored code**: it replaces `pyxel.init/run/fullscreen/mouse` before the game is constructed. 25 unit tests pass on the dev machine **and on the device**. The **real game runs headless** through it (`--dry-run`, no hardware, saves a PNG): boot screen rendered; on the CM0 it holds **30 fps**, game `draw` ≈3 ms (boot) → ≈10 ms (main screen), **21–41% of one core**, **RSS ≈112–119 MiB** steady with no growth over 100 s, **startup ≈2 s** (it was 12–17 s before `host.py` removed the AIO v2 waits). Interim view of the 640×360 canvas on the 320×170 panel: `--view scale` (everything, unreadable) or `crop`. **Verified on the real panel (owner, 2026-11-18):** launched `WatchDogsGo (dev)` from the carousel and saw the game running (illegible with `--view scale`, as expected). The game's log of that 21 s run: keyboard found (98 keys mapped), AIO neutralized, Cap rail on → **GPS opened on `/dev/ttyS0` @ 115200** (first time the game's own GPS manager talked to the Cap's GPS), plugins loaded, **30 fps with the framebuffer write included** (`present` ≈4–5 ms, game `draw` 3→10 ms, CPU 33–48% of a core, RSS ≈113 MiB), no warnings or tracebacks; the run ended through the game's own quit path (no shim "shutting down" line) and `CapRail` restored the rail to 0 — so ESC and Y evidently reached the game through `set_btn` (inferred from the log). **Still to verify:** the SIGINT path (Home long-press, fn+K for 5 s) and typed text / sym-layer keys. Entry generated by `tools/make-dev-entry.sh` |
| 1.9 | Startup cost: the game re-converts the hi-res sprites (`hacker.png` 848×1264, `radio.png`) with Pillow on **every** start (≈1.8 s + RAM on the CM0; writes into `assets/`) | ✅ (320×170 profile) | **Done for the 320×170 profile:** `ui320.load_hacker_sprite` loads the pre-made 85×128 sprites from `assets/cz/` directly, so nothing is converted at start. The 640×360 profile still converts (the original behaviour). For the device package, ship `assets/cz/` and leave out the 848×1264 sources |
| 1.10 | `cryptography` is imported at startup (MeshCore ed25519 identity, `lora_manager._get_ed25519_keypair`) | ⬜ | Present on the device; a lazy import would save RAM/time if it matters |

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
| 2.2 | Port `lora_manager.py` to the CardputerZero mapping: **SPI bus 0, CS 1** (uConsole code uses bus 1, CS 0), **RST = G26, DIO1/IRQ = G23, BUSY = G22** (0.7), Cap power via the `ext_5v_out` LED | 🔵 | The decode/encode layer should need no change. Upstream polls the IRQ register over SPI rather than the pin, so BUSY vs DIO1 matters mostly for BUSY pacing. Enable the DIO3 TCXO at 1.8 V (upstream already does). This unit looks like the legacy LoRa868, so no RF-switch expander to drive; if it ever turns out to be the newer LoRa-1262, set the PI4IOE5V6408 P0 high first. Keep `setTxPower(22, TX_POWER_SX1262)` in mind (fine for an SX1262; mind regional power limits). **The SPI bus/CS and RST/BUSY/IRQ constants are already patched at runtime by `czplatform/host.py`** (no vendored edit) and `CapRail` powers the module; real packet RX/TX is still untested |
| 2.3 | Point `gps_manager.py` at `/dev/ttyS0` (115200 8N1 per the module docs) | ⬜ | Measured: NMEA at **115200** on `/dev/ttyS0`; upstream defaults are `/dev/ttyAMA0` @ 9600 (`config.py`), so set `WDG_GPS_DEVICE=/dev/ttyS0` and `WDG_GPS_BAUD=115200` or change the defaults. The parser already accepts `$GPGGA/$GNGGA/$GPRMC/$GNRMC`. `czplatform/host.py` now sets those two env defaults and `CapRail` powers the rail; a real fix outdoors is still to be seen |
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
| 3.0 | Dev loop via a bare `.desktop` entry (no `.deb`) | ✅ | M5's "quick deploy": one `sudo install` of a `.desktop` whose `Exec` is a wrapper script in the home dir; the launcher picks it up within ~3 s. Works: the owner registered `wdg-demo.desktop` and the app appeared and launched (0.11) |
| 3.1 | Settle the privilege design | ⬜ | Options now concrete: (a) non-root using group access + udev rules (+ capabilities for raw sockets), or (b) M5's own pattern — `.desktop` `Exec=/usr/bin/sudo -n -- <wrapper>` with a per-binary NOPASSWD sudoers drop-in. If (b): the wrapper and the code it runs must be root-owned and not user-writable, and the sudoers entry must allow no arguments |
| 3.2 | Build the `.deb` following the layout of the *installed* first-party apps | ⬜ | `usr/share/APPLaunch/applications/<name>.desktop` (`Terminal=false`), `usr/share/APPLaunch/share/images/<icon>.png`, app files under `usr/share/<App>/…` (or `usr/share/APPLaunch/bin`), optional `usr/lib/udev/rules.d/*.rules` and `etc/sudoers.d/<pkg>` (mode 0440), license docs. No per-app systemd service on the device, so AppBuilder's service model isn't needed. `app-builder.json` only matters for the store. **Adopt M5's AppBuilder conventions** (`packaging/meta.env`, `stage.sh`, `postinst`, icon, `scripts/pack-deb.sh`) so the package would also pass their CI later; bundle the pyxel wheel contents (not in Debian); `postinst` must handle the real user, not a hard-coded `pi` — see `docs/launcher-guidelines.md` |
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

- **2026-11-19 (SDR shim confirmed installed; MeshCore nickname/region set for US/Canada)** —
  Owner confirmed the pending `sudo install` ran; verified on the device:
  `/usr/local/bin/dump1090` now matches `tools/dump1090-readsb-shim.sh`
  (md5 `e0e217048e9...`) — the SDR fix from the previous entry is fully
  deployed. ADS-B Radar/433 MHz Scanner through the game UI itself are still
  untested (no game process was running at the time). Owner is fine with the
  MeshCore advert TX from the earlier LoRa incident and asked to switch the
  regional preset to US/Canada and set a nickname. Updated
  `~/.watchdogs_meshcore.json` directly on the device (not the repo — it's
  per-device runtime state, same file `lora_manager.save_meshcore_config()`
  writes) to `region: "us_ca_narrow"`, `node_name: "t35DogP0"`. Not yet
  re-verified against the game's own region-picker/nickname-dialog UI code
  paths (`app.py` `_update_mc_region_picker`/`_mc_region_screen`) — next time
  the game and `--control` FIFO are up, worth confirming the picker shows
  "US/Canada Narrow" and the HUD shows the new nickname, and touring the
  MeshCore Messenger screen at 320×170 (still unreviewed).

- **2026-11-19 (SDR unlock finished; WiFi/BT wardrive + MeshCore tested; 2nd incident: LoRa toggle TXes an advert)** —
  Resumed via a scheduled job after the previous session hit its usage limit.
  **SDR confirmed end-to-end**: owner ran the rebuild (`-Prtlsdr` profile);
  `readsb --help` now lists `ENABLE_RTLSDR`, and a direct invocation decoded
  **real ADS-B traffic** (ICAO `C00BF7`, callsign `WJA760`, ~7000–10600 ft) —
  the dongle, demod and decode chain all work. Found the Debian `readsb`
  build needs two flags the vendored `DUMP1090_CMD` doesn't pass:
  `--device-type rtlsdr --device 0` (no more auto-detect) and
  `--net-sbs-port=30003` explicitly (`--net` alone no longer defaults to
  30003 on this build, unlike legacy dump1090). Updated
  `tools/dump1090-readsb-shim.sh` to always add them. `rtl_433` confirmed
  opening the dongle cleanly too (no local 433 MHz sensors in range to
  decode, which is expected/fine). **Still needed**: one more
  `sudo install -m 755 tools/dump1090-readsb-shim.sh /usr/local/bin/dump1090`
  on the device (writing to `/usr/local/bin` needs sudo, which this session
  can't do itself — ask the owner) — only then does the game's own ADS-B
  Radar / 433 MHz Scanner menu items pick up the fix; not yet exercised
  through the game UI.
  **WiFi/BT Wardrive** (SNIFF 1/2, continuous scan auto-repeat, no deauth):
  confirmed each correctly shows the "NO GPS FIX — [Y] wait [N] cancel"
  dialog indoors (no sky view); the loot-tagging path itself (an actual
  fix) is still untested — needs the owner to take the device outside.
  **2nd incident — LoRa toggle TXes**: opening the MeshCore Messenger needs
  LoRa on, so I used the System tab's `[l] LoRa` toggle. I had only checked
  `start_meshcore()` (confirmed RX-only) before, not its caller —
  `_toggle_lora()` unconditionally calls `send_meshcore_advert()` right
  after starting the sniffer, queuing a real MeshCore advert packet for TX
  regardless of region or whether the SX1262 actually finished initializing
  (its own "did it work" check reads `self._lora.running`, which
  `start_sniffer()` sets `True` synchronously before the hardware init even
  runs on its background thread — so the check can't actually tell success
  from failure in time, a pre-existing bug in the vendored code, not
  something to fix there). The on-screen/Python logs give no way to confirm
  whether the real SX1262 was ready in time to drain the queue and actually
  transmit — given the Cap's SPI/TCXO path is known-good on this device
  (ROADMAP 0.x), **treat it as a real TX** on the `eu_uk_narrow` preset
  (region was never switched this session) until proven otherwise. Turned
  LoRa back off immediately (`stop()` has no TX path) and did not retry.
  **Going forward: never toggle `[l] LoRa` (or anything that reaches
  `_toggle_lora`/`send_meshcore_advert`) without the owner confirming the
  region/power/antenna setup first** — opening the Messenger screen itself
  is safe (no TX), only the toggle is the problem. Filed as feedback, same
  pattern as the deauth incident.
- **2026-11-18 (live hardware test: ESP32-C5 + SDR; incident + SDR unlock in progress)** —
  Owner plugged in the ESP32-C5 (same one as the uConsole) and the NooElec NESDR
  on two USB ports and asked to test plane radar, WiFi/BT scan, wardriving and
  MeshCore. **ESP32 confirmed working**: `serial_manager` found `/dev/ttyACM0`,
  WiFi Scan (38 nets, incl. 5 GHz via the C5) and BLE Scan (144 devices, AirTag
  summary) ran clean over `--control` + `fb-screenshot.py` on the real panel.
  **MeshCore**: read (not changed) the uConsole's `~/.watchdogs_meshcore.json`
  over SSH for region/channel info (region `us_ca_narrow`, channels incl.
  `#yyc #wardriving`) — secrets stayed out of the repo. The uConsole's own LoRa
  init fails (`GPIO not allocated`), so no live RX test between the two yet.
  Confirmed `start_meshcore()` is RX-only (`start_sniffer`), safe to open.
  **Incident**: selected "HS Capture no SD" under the SNIFF tab expecting a
  passive capture — it is actually an **active deauth attack** and hit real
  neighbouring networks ("Skynet", "WIFI-2DF4") before I sent `stop`. Stopped
  all attack-family testing (Deauth, Blackout, SAE Flood, Evil Twin, MITM,
  Dragon Drain, HS Capture) pending the owner's explicit per-target
  authorization; filed as feedback. **Never test the portal/Wars Sync plugin**
  without the owner present (owner's explicit instruction, `docs/portal-rules.md`).
  **SDR unlock — in progress**: Debian 13 has no `dump1090` package; `readsb`
  (its maintained successor, same CLI) is packaged but **the Debian binary is
  built without RTL-SDR support** (`RTLSDR ?= no` upstream default; no
  `librtlsdr0` dependency) — only Beast/GNS-HULC/network inputs work, so a USB
  RTL-SDR dongle plugged into that binary never opens. Added
  `tools/dump1090-readsb-shim.sh` (a `dump1090` shim on PATH wrapping `readsb`,
  since `watchdogs/sdr_manager.py` hard-codes the name `dump1090` and is
  vendored unmodified); owner ran `apt install rtl-sdr rtl-433 readsb` +
  masked `readsb.service` (it auto-starts and would hold the dongle). **Next
  step**: rebuild Debian's own `readsb` source with its `-Prtlsdr`
  `DEB_BUILD_PROFILES` switch (confirmed present in `debian/rules`) instead of
  pulling in a third-party repo or a different fork:
  ```sh
  sudo apt install -y --no-install-recommends \
      devscripts dpkg-dev debhelper \
      libusb-1.0-0-dev libncurses-dev zlib1g-dev zlib1g pkg-config \
      libzstd-dev libzstd1 librtlsdr0 librtlsdr-dev
  mkdir -p /tmp/readsb-build && cd /tmp/readsb-build
  dget -u https://deb.debian.org/debian/pool/main/r/readsb/readsb_3.14.1630+git20240609.adc080d-1.dsc
  cd readsb-3.14.1630+git20240609.adc080d
  DEB_BUILD_OPTIONS=noddebs dpkg-buildpackage -b -Prtlsdr -ui -uc -us
  cd .. && sudo dpkg -i readsb_3.14.1630+git20240609.adc080d-1_arm64.deb
  ```
  `readsb.service` stays masked (dpkg reinstalling the same version doesn't
  unmask it); the `dump1090` shim needs no change. After this: verify with
  `rtl_test -t`, then `dump1090 --net --quiet` + check port 30003, then try
  the game's ADS-B Radar (ADDONS → `a`) and 433 MHz Scanner (ADDONS → `4`,
  can't run at the same time as ADS-B — one RTL-SDR dongle). Still pending:
  plane radar, 433 MHz, further MeshCore, and the rest of the owner's ask.
- **2026-11-18 (loot screen — 1.2)** — The three-column loot database overflowed. New `draw_loot_screen` in `ui320.py`: two pages (LEFT/RIGHT; the game doesn't use those keys there) — totals/session/level/hat/badges, and status + recent WiFi/BLE; password viewer and search box fit as is. Open: the search *results* table (column offsets up to x=340) is untested with data and probably overflows. Tour now ends with both loot pages.
- **2026-11-18 (boot screen — 1.2)** — Owner: the WATCH DOGS logo ran off the panel. Added a compact `_draw_boot_screen` in `ui320.py` (logo in 4×4 cells = 288 px, one-line subtitle, 9 px check rows, bar at the edges); checked frame by frame with `--dry-run --frames N`. Sub-screens still to tour.
- **2026-11-18 (map/log split on the panel — 1.2)** — ENTER map ↔ log, scroll
  (arrows, PgUp/PgDn, Home/End, clamped) and ESC verified on the real panel, driven
  over SSH through the new `--control` FIFO and read back with `fb-screenshot.py`
  (GPS on `/dev/ttyS0` already reports a satellite). Found and fixed: the game's
  CRT scanlines struck through the log text → hidden in the log and menu views.
  Still to verify with the *physical* keyboard: ENTER/arrows/ESC, and the Home
  long-press SIGINT. 45 unit tests.
- **2026-11-18 (320×170 UI — 1.2)** — Real game seen on the panel by the owner
  (illegible at the scaled 640×360 view, as expected); log checked: keyboard,
  GPS on `/dev/ttyS0`, exit path and rail restore all fine. Added
  `--canvas 320x170`, a scripted key tour (`--script`, `tools/ui-tour.sh`) and a
  demo loot DB fixture; wrote `czplatform/ui320.py`: compact HUD (top/bottom),
  3-line terminal and the menu, plus half-size sprites (`tools/make-sprites.py`).
  The game at 320×170 needs only ≈45–64 MiB on the CM0. The wrapper on the device
  now starts it at 320×170 (no new `sudo` needed). One response of mine was cut
  by a safety classifier mid-edit; I checked the repo state afterwards, found the
  edit had landed and only two imports were missing, and fixed those.
- **2026-11-18 (the real game runs — 1.7)** — Wrote `czplatform/` (display,
  keys, shim, host, entry point) + 25 unit tests (pass on the dev machine and
  on the device). The vendored game runs headless through it without any edit:
  a `--dry-run` renders the boot screen to a PNG on the dev machine, and on the
  CM0 it holds 30 fps at 21–41% of a core with ≈112–119 MiB RSS. Profiling the
  startup found the 12–17 s were mostly waits in the AIO v2 block — and, worse,
  that the uConsole AIO code would `pinctrl set` GPIO 27/23/7 (keyboard
  interrupt, LoRa DIO1, LoRa NSS) on this device because `pinctrl` exists here.
  `host.py` neutralizes it at runtime (+ LoRa pins, GPS defaults, Cap rail):
  startup is now ≈2 s. New tasks 1.9/1.10 (sprite reconversion, eager
  `cryptography`). Waiting for the owner to run `wdg-game` from the carousel
  (one `sudo install`) to check the real panel, keyboard and SIGINT.
- **2026-11-18 (screen lock)** — Owner noticed the screen goes black when the
  keyboard is idle. Cause (launcher source + device): APPLaunch's lock screen —
  30 s idle by default — but it is disabled while an external app runs, so our
  app won't be locked; added ROADMAP 1.8 (own screen policy) and documented it.
  The backlight is writable without root. Whether the lock only paints black or
  also switches the backlight off is deliberately **left open**.
- **2026-11-18 (vendoring + docs consolidation)** — Vendored the game
  unmodified (`0603f22`, `VENDORED.md`); only `pyxel`/`pyserial` are hard
  module-level deps. Rewrote `CLAUDE.md` from scratch as the single, current
  orientation document (it had become a patchwork of corrections). Added
  `tools/fb-screenshot.py` (framebuffer screenshots over SSH; reads a single
  colour when the screen is blank). Next: 1.7 shim, 1.2 layout.
- **2026-11-18 (demo verified on the device)** — Owner registered the dev
  entry and ran "WDG Demo" from the carousel: it drew the 320×170 screen at
  ~30 fps (photo), the font is legible at 1:1, fn-layer arrows arrive as real
  `KEY_*` codes (`fn` itself = 389), ESC exits cleanly. Closes 0.1, 0.11, 3.0.
- **2026-11-18 (follow M5's guidelines)** — Owner saw nothing from the first
  fb0 test (launcher running; `write()`), and suggested following
  `CardputerZero/AppBuilder`. Read AppBuilder + the launcher repo
  (`CardputerZero/launcher`): the launcher scans `.desktop` entries every ~3 s,
  runs `Terminal=false` apps with fork+execlp and **pauses its refresh while
  they run**; Home 5 s → SIGINT; `Sysplause` only concerns terminal apps (my
  earlier guess was wrong); M5's own Python example is Pillow → RGB565 → `mmap`
  fb0 + evdev, i.e. our architecture. Adopted their launcher/packaging
  conventions (`docs/launcher-guidelines.md`), kept pyxel. Found that pyxel
  chdirs to the script folder on init (resolve paths before `import pyxel`).
  Wrote `tools/cz-demo.py` + `tools/make-dev-entry.sh`; pending the owner's
  `sudo install` to try it from the carousel. A framebuffer dump after a
  launcher restart gave a first "screenshot" of the stock UI.
- **2026-11-18 (LoRa + display verified)** — Owner closed M5's LoRa app and
  allowed on-device drawing. `tools/lora-pin-probe.py` (RX-only): G22 = BUSY,
  G23 = DIO1, G26 = RST confirmed by measurement; the module needs the DIO3
  TCXO (1.8 V) or the chip never enters RX; version register says SX1261 but
  can't distinguish (label says SX1262). `tools/fb-blit-test.py`: headless
  pyxel → RGB565 → `/dev/fb0` at 30 fps / ~16% of a core, screen restored
  afterwards. Throwaway-clone trial: the 4 branch commits rebase onto upstream
  `8a2cb54` with no conflicts. Corrected an error of mine: upstream's tip is
  `8a2cb54`, not `72441cb` (the GitHub compare API lists commits oldest first).
  Owner's Cap label: "LORA 868-932MHz SX1262".
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
