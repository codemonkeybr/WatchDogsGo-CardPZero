# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this project is

A port of **[WatchDogsGo](https://github.com/LOCOSP/WatchDogsGo)** — a `pyxel`
retro-game frontend over real WiFi/BLE/LoRa security tooling, originally built
for the **ClockworkPi uConsole (CM4)** — to the **M5Stack CardputerZero
(Raspberry Pi CM0)**.

Goal, as stated by the project owner: port with **maximum feasible feature
parity**, ship it as a normal installed app the owner's CardputerZero can
launch from its home screen like any other app, and **show it to the
WatchDogsGo community for feedback before considering an official
cardputer.cc store listing**. Not in scope right now: publishing to the
CardputerZero App Store (`czdev publish`).

### Provenance

- The owner's working fork: `https://github.com/codemonkeybr/WatchDogsGo`,
  checked out locally at `/home/tesso/dev/WatchDogsGo`.
- Upstream: `https://github.com/LOCOSP/WatchDogsGo` (remote `origin` in that
  checkout; the fork is remote `fork`).
- As of 2026-11-18, that checkout has `main` at `7427fbf` ("feat(portal):
  WDGWars client parity") and is currently sitting on branch
  `feat/aiov2-wifi-bt-fallback` at `cad1e77`, 6 commits ahead of `main`,
  clean (no uncommitted changes).
- **Decide before Phase 1** which ref to vendor from — `main` for the
  conservative baseline, or the feature branch if the AIO v2 WiFi/BT fallback
  work should be in the CardputerZero port too (that specific feature is
  uConsole/AIO-v2-specific and likely gets stubbed out anyway, see below).
- This repo does not vendor that code yet. When it does, record the exact
  source commit hash in the commit that adds it, so drift from upstream stays
  traceable.

## Target hardware

### Host: M5Stack CardputerZero

Confirmed from M5Stack's own docs (docs.m5stack.com/en/CardputerZero) —
this device shipped/crowdfunded ~May 2026, after this model's knowledge
cutoff, so treat anything below *not* sourced from the docs fetch as
unverified until checked against the hardware in hand.

| | |
|---|---|
| SoC | Raspberry Pi **CM0**, RP3A0 (BCM2837), quad-core Cortex-A53 @ 1 GHz, aarch64 |
| RAM | 512 MB LPDDR2 |
| Storage | microSD (32 GB included on the standard SKU; CardputerZero-Lite needs one bought separately) |
| Display | **1.9" LCD, 320×170**, ST7789v3 controller |
| Keyboard | 46-key matrix, TCA8418 I2C controller; `sym`/`shift`/`fn` modifier layers (see Input section) |
| Sensors | BMI270 IMU, RX8130CE RTC (standard SKU); BMM150 magnetometer + IMX219 8MP CSI camera only on C154/C154-B/C154-V1 variants |
| Audio | ES8389 codec, MEMS mic, 1W/8Ω speaker, 3.5mm TRRS jack |
| IR | TX + RX |
| Battery | 3.7V 1750mAh Li-ion, BQ27220YZFR gauge, charges via USB-C2 (5V/2A) even when off |
| Wireless | WiFi 2.4GHz 802.11 b/g/n only (no 5GHz, no monitor-mode claim found); BT listed as 4.2 in most sources, disputed as possibly 5.0; 10/100M Ethernet via USB (SR9900A chip) |
| USB | 1× USB-A 2.0, 2× USB-C 2.0; **physical host/slave switch** on the left side. Host mode routes the CM0 through an internal GL852G hub → left USB-A, left USB-C, and Ethernet all become available. Slave mode instead connects the CM0 directly to the right USB-C port only (used for ADB, ADB = Android Debug Bridge terminology, even though this is a Linux device) |
| Expansion | `EXT 2.54-14P` header (SPI0, UART, I2C1, USB4, GPIO — full pinout in `docs/hardware-notes.md`) **and** a separate Cap-Bus expansion slot for "Cap" modules. **Cap modules are not hot-swappable** — power off before inserting/removing one |
| OS | Linux, aarch64. Flashed to microSD via M5Stack's Image Flashing Guide. No specific distro named in the docs; third-party coverage assumes a customized Raspberry Pi OS-like image |
| App ecosystem | CardputerZero-AppBuilder / `czdev` CLI → apps ship as `.deb` (systemd service + `.desktop` under `usr/share/APPLaunch/`), discovered by the APPLauncher home screen. Store front-end at cardputer.cc. Example app runtimes: C+LVGL, SDL2, Qt, Python, Rust |

### Expansion: LoRa + GPS Cap module

The owner's module is almost certainly M5Stack's **"Cap LoRa-1262"** (sold as
"for Cardputer-Adv", SKU appears as `U201`/`Cap LoRa868` in M5Stack's docs,
which separately list it as compatible with **both** Cardputer-Adv and
CardputerZero):

- LoRa radio: **SX1262** (not SX1261 — correct this if hardware labeling
  says otherwise once it's in hand), via a Stamp LoRa-1262 module, SPI
  interface, 868–923 MHz, up to +20 dBm TX, external RP-SMA antenna.
- GPS: **ATGM336H-6N** (AT6668 solution), UART @ 115200 8N1, NMEA 0183 4.1,
  built-in ceramic antenna.
- Cap-Bus pinout is published (14-pin: GPS TX/RX, SCL/SDA, 5V, GND on the
  left; LoRa NSS/MISO/MOSI/SCK/BUSY/IRQ/RST on the right) — but the
  **CardputerZero-side GPIO numbers behind that Cap-Bus are not published**.
  M5Stack's page only gives the *Cardputer-Adv* GPIO mapping (RST=G3,
  IRQ=G4, BUSY=G6, SCK=G40, MOSI=G14, MISO=G39, NSS=G5, GPS RX=G13 TX=G15).
  **This must be re-derived from the CardputerZero schematic or measured on
  hardware before `lora_manager.py`/`gps_manager.py` pins can be ported** —
  do not assume the Cardputer-Adv numbers carry over.
- Same chip family as the uConsole AIO v2 board's SX1262 (`lora_manager.py`
  already targets SX1262 via `LoRaRF`), so the *protocol/decode* layer
  (MeshCore advert/text decode, sniffer presets, balloon tracking) should
  need little or no change — only the SPI bus/CS index and the
  reset/busy/irq GPIO numbers are host-specific.

### ESP32 companion (projectZero firmware)

Unchanged from the uConsole setup: a USB-serial-attached ESP32 running
[projectZero](https://github.com/LOCOSP/projectZero) does the actual WiFi/BLE
radio work (scan, deauth, handshake capture, Evil Twin, BLE HID) and streams
line-based results back at 115200 baud. `serial_manager.py` talks to it over
`/dev/ttyUSB*`/`/dev/ttyACM*` — this should plug into the CardputerZero's
USB-A/USB-C **host**-mode ports with no protocol changes, only needs
re-verifying that `detect_esp32_port()`'s heuristics still find it.

### SDR: NooElec NESDR SMART (RTL-SDR)

Corrected by the owner — not "ADB Scan (Radar)", it's a **NooElec NESDR
SMART**, a standard USB RTL-SDR receiver (RTL2832U + R820T2 tuner family).
This is good news for the port: upstream **already has a manager for this
exact device class**, `sdr_manager.py` — it's a pure subprocess wrapper
around two standard CLI tools, `dump1090` (ADS-B aircraft tracking, built
from `flightaware/dump1090` per the upstream README) and `rtl_433` (433 MHz
ISM-band sensor decoding), talking to the dongle through the normal
`librtlsdr` userspace stack. No GPIO/SPI/special driver involved — it's
just a USB device.

Porting implications, all low-risk compared to the LoRa/GPS Cap module:
- Needs `rtl-sdr`/`librtlsdr` + `dump1090` + `rtl_433` to build/install for
  aarch64 on whatever OS image CardputerZero ships — all three have
  mainstream aarch64 support already (Debian packages `rtl-sdr`/`rtl-433`;
  `dump1090` is built from source upstream too, same as on the uConsole).
- Standard RTL-SDR gotcha, not Cardputer-specific: the kernel's own DVB
  driver (`dvb_usb_rtl28xxu`) grabs RTL2832U devices by default and has to
  be blacklisted (or the module unbound) before `librtlsdr` can open the
  device in userspace — same as on any other Linux box, just needs doing
  once on the device image.
- Plug into a CardputerZero USB **host**-mode port (internal hub, same as
  the ESP32 and any external WiFi adapter); power draw (~250–300 mA) should
  be within the hub's budget but hasn't been measured on this specific
  device yet.
- No pin/GPIO porting work needed at all here, unlike the LoRa/GPS module —
  this moves to Phase 0/1 as a "plug it in and verify" item, not a design
  question.

## Upstream architecture (what we're porting)

Summarized from `/home/tesso/dev/WatchDogsGo/CLAUDE.md` and direct reading of
`watchdogs/`; see that file for the authoritative version.

- **Engine**: `pyxel`, fixed canvas **640×360 @ 30 FPS**, single process,
  `pyxel.run(update, draw)` in `app.py`. Launched via `sudo ./run.sh` → `sudo
  -E .venv/bin/python3 -m watchdogs` — **sudo is required today** for
  GPIO/serial/scapy raw-socket access.
- **Menu dispatch**: every entry in `MENU_CATS` is `(hotkey, label, command,
  category, extra)`. Plain command strings go out over ESP32 serial
  (`CMD_*` in `config.py`); `_`-prefixed commands dispatch to a large
  `if cmd == "_xxx":` chain in `app.py` for uConsole-native, non-ESP32
  attacks (MITM/ARP spoofing, Dragon Drain, BlueDucky, RACE, MeshCore LoRa,
  Flipper Zero, SDR).
- **Manager pattern**: each hardware subsystem (`lora_manager.py`,
  `serial_manager.py`, `gps_manager.py`, `flipper_manager.py`,
  `sdr_manager.py`, `aio_manager.py`, `watch_manager.py`) is a background
  `threading.Thread` + thread-safe `Queue` + `_emit()` + `stop()`/
  `_stop_event`. `app.py`'s 30 FPS loop has one `_poll_*` per manager that
  drains the queue and updates game state. **Every manager fails closed**
  (`None`/`False` + log, never raises) when its hardware isn't present —
  this is exactly the property that makes incremental porting safe: menus,
  map, terminal and plugins already run with zero hardware attached.
- **State/persistence**: `loot_manager.py` owns `loot/<timestamp>/` session
  dirs + `loot/loot_db.json` (XP, badges, hacker-hat classification,
  MeshCore contacts, dedup sets). Two files live outside the repo in
  `$HOME`: `~/.watchdogs_meshcore.json`, `~/.watchdogs_meshcore_key`. Logs go
  to `~/.watchdogs/last_run.log`.
- **Map rendering**: `tile_manager.py` pulls Stadia Maps raster tiles
  (needs `STADIA_API_KEY`) and quantizes to pyxel's 16-color palette;
  `coastline.py` (864 lines) is a procedural Natural Earth coastline
  fallback for zoomed-out views with no tile backing.
- **Plugins**: `plugins/*.py` auto-discovered, any `PluginBase` subclass
  gets `on_load/on_unload/on_update/draw` lifecycle hooks and a PLUGINS tab
  entry. `plugins/wardrive_upload.py` is the WDGWars portal client — HMAC
  signed, routes/ranks traffic by matching the `WatchDogsGo/` User-Agent
  product token. **Don't rename that token** in anything derived from this
  fork without separately arranging it with the wdgwars.pl admin, or
  CardputerZero traffic silently stops being recognized upstream.
- **Keybindings** (full table in upstream README): TAB=menu, SPACE(hold)=hack,
  arrows=pan/navigate, `=`/`]` `-`/`[` `0`=zoom, S=stop, ESC=quit,
  PgUp/PgDn=scroll terminal (`Fn+U`/`Fn+K` on the uConsole keyboard),
  backtick=loot screen, plus a full alphanumeric input-dialog mode and extra
  bindings inside the MITM and Flipper sub-screens. ~45 distinct
  `pyxel.KEY_*` constants are read across `app.py`.
- **System deps** (Debian/apt): `libsdl2-dev`/`libsdl2-image-dev` (pyxel),
  `tcpdump`, `aircrack-ng`, `iw`, `rtl-433`, `dump1090` (built from source),
  `bluez`+`bluez-tools`, `python3-rpi-lgpio` (GPIO on Pi5/CM5 — **note: CM0
  is BCM2837, an older generation than the Pi5/CM5's BCM2712 that
  `rpi-lgpio` targets; verify this library, or fall back to classic
  `RPi.GPIO`/`lgpio`, actually works against BCM2837 before relying on it**),
  `python3-gi`/`gir1.2-glib-2.0` (BlueZ pairing agent).
- **Python deps**: `pyxel`, `pyserial`, `Pillow`, `scapy`, `netifaces`,
  `bleak`, `dbus-python`, `LoRaRF`, `cryptography`, `PyNaCl`, `requests`.

## Key platform deltas (uConsole/CM4 → CardputerZero/CM0)

These are the things that actually have to change, roughly in the order
they'll bite:

1. **Privilege model — biggest open risk.** Upstream runs the whole game as
   root via `sudo`. CardputerZero's own app-packaging docs state apps "must
   run as a non-root user" and that **root systemd services are rejected**
   by the installer. Raw sockets (scapy deauth/MITM), monitor-mode WiFi,
   GPIO/SPI (LoRa), and serial port access all currently assume root.
   Needs a real design decision: Linux capabilities (`setcap
   cap_net_raw,cap_net_admin+eip` on the python3 interpreter or a wrapper
   binary — imprecise since it'd grant it to *all* scripts run by that
   interpreter), udev rules granting group access to `/dev/ttyUSB*`,
   `/dev/spidev*`, GPIO chardev, or a small privileged helper
   process/socket that the unprivileged game talks to for just the
   root-requiring operations. Needs resolving before Phase 3 packaging, and
   ideally validated on hardware in Phase 0.
2. **Screen: 640×360 → 320×170.** Not a clean /2 scale on either axis
   (640/320=2.0, 360/170≈2.12) and the aspect ratio differs slightly
   (16:9 vs ~1.88:1). `app.py` hardcodes pixel-space layout throughout
   (HUD_TOP/HUD_BOT/TERM_H/MAP_H, sprite coordinates, menu geometry) — this
   needs a deliberate re-layout for the smaller canvas, not a naive scale
   factor. Expect panels (HUD, terminal, menu) to need to become
   toggle/overlay rather than always-on-screen simultaneously, given far
   less vertical room.
3. **Rendering backend unknown.** CardputerZero's own app template ships a
   "desktop SDL preview" for dev and a separate "device framebuffer build"
   for the actual device — unclear whether `pyxel`'s SDL2-based renderer
   runs as-is on-device, or whether there's no X11/Wayland and it needs a
   bare-KMS/fbdev target. **First thing to test once hardware is in hand.**
   Lower pixel count (320×170 vs 640×360, ~4× fewer pixels) should help
   performance either way given the CM0's modest CPU.
4. **Keyboard remap.** Confirmed from `docs.m5stack.com/.../usage`:
   modifiers are `sym` (blue symbols), `shift` (uppercase), `fn` (orange
   shortcuts, tap-once/tap-twice/hold). Relevant `fn` layer:
   `fn+F/X/Z/C`→Up/Down/Left/Right, `fn+L/M`→PgUp/PgDn, `fn+K/N`→Home/End,
   `fn+1-9/0/O/P`→F1–F12. `ESC` is a dedicated key (hold = exit app to
   HOME). `TAB`, `ENTER`/`OK`, `BACKSPACE` are direct physical keys. No
   dedicated arrow keys — everything upstream binds to `pyxel.KEY_UP` etc.
   needs to either also accept the `fn`-layer combo, or the keymap needs
   remapping at the pyxel-key level once it's confirmed which physical keys
   pyxel actually reports when `fn` is held (pyxel may see a distinct
   keycode, or may see the base key — needs on-device testing).
5. **GPIO/SPI pin numbers.** `lora_manager.py` hardcodes uConsole AIO v2
   pins (`PIN_RESET=25, PIN_BUSY=24, PIN_IRQ=26`, SPI bus 1 CS 0).
   `aio_manager.py`/the SYSTEM-menu GPS/LoRa/SDR/USB rail toggles use
   `pinctrl` + the HackerGadgets `aiov2_ctl` tool — **both are uConsole/AIO
   v2-specific and don't apply to CardputerZero at all**; that whole
   subsystem should be stubbed/disabled for this port rather than ported.
   The Cap LoRa-1262 module's real CardputerZero pin numbers still need
   sourcing (see hardware section above).
6. **WiFi monitor mode.** CardputerZero's onboard WiFi is 2.4GHz b/g/n with
   no monitor-mode capability mentioned anywhere. Upstream's Dragon Drain
   (WPA3 SAE flood) already requires an *external* monitor-mode USB WiFi
   adapter (Alfa AWUS036ACH/ACM) even on the uConsole — that requirement
   likely carries over unchanged (plug the same adapter into a
   CardputerZero USB host port), it's just now the *only* way to get
   monitor mode, not an upgrade over a half-working built-in option.
7. **App packaging.** Target shape per `CardputerZero-AppBuilder`: a `.deb`
   with `DEBIAN/{control,postinst,prerm}`, a systemd unit under
   `lib/systemd/system/`, a `.desktop` under
   `usr/share/APPLaunch/applications/`, and binaries/assets under
   `usr/share/APPLaunch/{bin,lib,share}`. Scaffolded with `czdev new` from
   the `CardputerZero/Template` repo (LVGL/CMake by default — this project
   is Python/pyxel instead, so the template's build step won't apply
   directly; only its packaging *shape* — DEBIAN scripts, `.desktop`,
   `app-builder.json` — is reusable). **Sideload only, per the owner's
   stated goal**: `scp *.deb` to the device + `sudo dpkg -i`, no
   `czdev publish`/store listing.

## Phased plan

**Phase 0 — hardware spike (do this first, before investing in the port):**
- [ ] Confirm `pyxel`/SDL2 actually renders on-device (or find the real
      on-device graphics path if not SDL2) and get a trivial 320×170 pyxel
      window on screen.
- [ ] Confirm aarch64 wheel/build availability for `pyxel`, `scapy`,
      `bleak`, `cryptography`, `PyNaCl`, `LoRaRF` on whatever OS image ships.
- [ ] Confirm which GPIO library actually works against BCM2837 on this
      image (`python3-rpi-lgpio`, `RPi.GPIO`, `lgpio`, or raw `/dev/gpiochip*`).
- [ ] Spike the privilege-model question (capabilities vs udev vs helper
      daemon) with a minimal non-root raw-socket test.
- [ ] Get the ESP32 projectZero link working over a CardputerZero USB host
      port with unmodified `serial_manager.py`.
- [ ] Measure the Cap LoRa-1262 module's real GPIO pin numbers on this
      device (or find them in M5Stack's schematic/source once published).
- [ ] Verify the NESDR SMART (RTL-SDR) works through `dump1090`/`rtl_433`
      on-device, including the `dvb_usb_rtl28xxu` blacklist step.

**Phase 1 — minimal running build (menus + map, no radio hardware):**
- Vendor the `watchdogs/` package (pinned to a specific upstream commit,
  recorded in the commit message) as the starting point.
- Re-layout HUD/menu/terminal/map for 320×170.
- Remap the keyboard (direct keys + `fn`-layer combos) and verify against
  the actual pyxel keycodes the device reports.
- Stub out uConsole/AIO-v2-only subsystems (`aio_manager.py`'s
  `pinctrl`/`aiov2_ctl` rail toggles) rather than porting them.
- Validate loot/XP persistence on the microSD-backed home dir.

**Phase 2 — radio hardware integration:**
- Port `lora_manager.py`/`gps_manager.py` SPI bus/CS and GPIO pin constants
  to the Cap LoRa-1262+GPS module's real CardputerZero mapping.
- Re-verify MeshCore decode/encode and sniffer presets unchanged
  (protocol-level code, should be hardware-agnostic already).

**Phase 3 — package as an installed CardputerZero app:**
- Resolve the privilege model for real (not a spike) — this gates whether
  a systemd-service packaging works at all, or whether the app needs to
  launch as a privileged process some other way the APPLauncher accepts.
- Build the `.deb` (DEBIAN scripts, `.desktop`, `app-builder.json` with a
  320×170 screenshot per the manifest's requirement), sideload via
  `scp` + `dpkg -i`, confirm it shows up and launches from the home screen.
- **No `czdev publish` / store submission** — sideload-only for now, per
  the owner's explicit preference to gather community feedback first.

**Phase 4 — feature-parity pass + community feedback:**
- Flipper Zero USB integration (VID:PID detection, should be unchanged).
- Decide how WDGWars portal traffic from CardputerZero builds should be
  tagged/routed (don't silently break the `WatchDogsGo/` UA token
  classification upstream relies on).
- Validate an external monitor-mode WiFi adapter end-to-end for
  Dragon Drain/deauth on CardputerZero's USB host ports.
- Gather community feedback before any App Store conversation.

## Open questions for the owner

- Which upstream ref to vendor from: `main` (`7427fbf`) or
  `feat/aiov2-wifi-bt-fallback` (`cad1e77`)?
- Confirm the LoRa+GPS module's exact part name/chip once it's visible on
  the hardware (SX1261 vs SX1262 — public docs for the closest matching
  M5Stack product say SX1262).
- Is the CardputerZero or CardputerZero-Lite variant in hand (affects
  camera/IMU/bundled-SD assumptions, though none of those matter much to
  this port)?

## Commit conventions for this repo

No upstream-inherited restriction here (the "never commit CLAUDE.md, never
AI-attribute commits" rule in `/home/tesso/dev/WatchDogsGo/CLAUDE.md` is that
*upstream* project's own policy for *their* repo — it does not apply to this
independent fork). Use normal Claude Code attribution on commits/PRs here
unless the owner says otherwise.
