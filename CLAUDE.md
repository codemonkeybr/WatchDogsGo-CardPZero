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
  WDGWars client parity", same as `origin/main`) and is currently on branch
  `feat/aiov2-wifi-bt-fallback` at `cad1e77`, **4 commits ahead of `main`**,
  clean. That branch exists only on the owner's fork (`fork/...`), not on
  `origin`.
- **Decided: vendor from `feat/aiov2-wifi-bt-fallback` @ `cad1e77`**, because
  it carries the game-side fallback that lets the game run on the host's own
  WiFi/BT through an ESP32-emulating bridge (see "Internal WiFi/BT" below) —
  the owner wants that as a selectable option on CardputerZero. Since it's
  unmerged work, always record the SHA when vendoring and re-check upstream
  `main` for drift before each sync.
- **Upstream has moved:** `origin/main` is now `8a2cb54` (v0.10.0+), four
  commits past `7427fbf` (portal UA platform detection + new fork rules,
  White Rabbit targets, uConsole detection). The feature branch sits on
  `7427fbf`, so rebase it onto upstream `main` before vendoring (ROADMAP 1.1)
  and read `docs/portal-rules.md`.
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
| Wireless | WiFi 2.4GHz 802.11 b/g/n only (no 5GHz, no monitor-mode claim found); BT 5.2 as reported by the device itself (`hciconfig`, CYW4343A2; docs and press say 4.2); 10/100M Ethernet via USB (SR9900A chip) |
| USB | 1× USB-A 2.0, 2× USB-C 2.0; **physical host/slave switch** on the left side. Host mode routes the CM0 through an internal GL852G hub → left USB-A, left USB-C, and Ethernet all become available. Slave mode instead connects the CM0 directly to the right USB-C port only (M5's docs use that port for ADB; we use SSH instead, so slave mode isn't needed for development) |
| Expansion | `EXT 2.54-14P` header (SPI0, UART, I2C1, USB4, GPIO — full pinout in `docs/hardware-notes.md`) **and** a separate Cap-Bus expansion slot for "Cap" modules. **Cap modules are not hot-swappable** — power off before inserting/removing one |
| OS | **Measured:** Debian 13 (trixie) on the Raspberry Pi kernel (6.18.x `+rpt`), aarch64, Python 3.13 — a stock Pi-class Linux box, reachable over plain SSH. Flashed to microSD via M5Stack's Image Flashing Guide |
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

### Internal WiFi/BT as a selectable scan source

The owner wants WiFi/BLE wardriving to be able to use the CardputerZero's
**own radio** instead of (or alongside) the ESP32. Upstream already has the
mechanism, which is why we vendor from the feature branch:

- `wdg_wifi_bridge.py` (repo root, community-contributed) opens a PTY and
  emulates an ESP32 projectZero over it: WiFi scans via `iw dev <iface>
  scan`, BLE scans via `bleak` on an `hci` adapter, plus Popen dispatch to
  optional helper scripts (`hs_capture.py` for handshakes). It rate-limits
  scans (`SCAN_COOLDOWN` = 5 s) and serves cached results on timeout.
- Game side (the 4 feature-branch commits): `serial_manager.py`'s
  `detect_aiov2_bridge_port()` returns `/tmp/aiov2-pty` when no real ESP32 is
  found, and `app.py` then runs the *same* serial protocol and parsing
  (`_via_aiov2_bridge` only suppresses firmware-version nagging and tweaks
  status text). WiFi and BT wardriving can run concurrently and be stopped
  independently.
- Today the choice is implicit ("ESP32 if present, else bridge"). The owner
  wants an explicit option, so add a scan-source setting (`auto` | `esp32` |
  `internal`; env/`secrets.conf` + a SYSTEM-menu entry) instead of relying
  on autodetect. Using both at once would mean two serial links merged in
  `app.py` — out of scope until the single-source path works.
- The "AIO v2" naming in upstream strings is uConsole-specific; in this
  fork, change only user-visible strings (to "internal WiFi/BT") and keep
  identifiers as-is where possible, to keep merges from upstream cheap.

Capability split (WiFi side **measured on the device, 2026-11-18**; the
BLE/scan path itself still has to be exercised — see ROADMAP 0.9 and 2.7):

| | Internal radio (managed-mode `iw scan` + BlueZ) | ESP32 (projectZero) |
|---|---|---|
| WiFi wardriving | yes, **2.4 GHz only** | yes; dual-band if the board is the ESP32-C5 upstream targets |
| BLE wardriving, AirTag scan, BT tracker | yes (BT 4.2-class: legacy advertising only) | yes |
| Deauth, handshake capture, sniffer, Evil Twin, SAE flood | **no** — needs monitor mode/injection, and the driver's supported modes are IBSS, managed, AP and P2P only | yes |

Practical caveats: `wlan0` is probably also the device's only uplink
(WDGWars upload, map tiles, ssh), so scanning while associated may briefly
hurt throughput; triggering an `iw` scan normally needs `CAP_NET_ADMIN`
(reading cached results does not), which feeds into the privilege-model
decision below. Measured: `wlan0` is indeed the default-route interface
(this very SSH session rides on it), and `hci0` is up (BT UART, HCI 5.2).

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
  product token. Upstream publishes rules every fork must follow (UA format
  plus a `Fork/<name>` tag, honest platform string, rate limits, key
  handling) — see `docs/portal-rules.md` before touching this plugin.
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
they'll bite. (Several were refined by on-device measurements — see
"Measured on the device" after this list; where they disagree, that section
wins.)

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
   root-requiring operations. A fourth option is probably the cleanest if
   the installer allows it: keep the service non-root (`User=`) and grant
   only what's needed with systemd `AmbientCapabilities=CAP_NET_RAW
   CAP_NET_ADMIN` (scoped to the unit, not to the interpreter) — whether the
   CardputerZero tooling accepts that is unverified. Needs resolving before
   Phase 3 packaging, and ideally validated on hardware in Phase 0.
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
   *Desktop findings (2026-11-18):* by default `pyxel` (2.9.9 and 3.0.2 both
   tested) creates an **OpenGL** window and panics on SDL's `dummy` driver,
   so it can't start on a bare framebuffer/SPI panel without GL. But
   `pyxel.init(..., headless=True)` works with no display and no GL:
   `pyxel.screen.data_ptr()` yields the 320×170 palette-index buffer
   (a ctypes `c_uint8` array) and the BDF fonts/text render normally.
   Candidate device architecture, pending the probe results: run the game
   headless plus a small platform shim — evdev keyboard → `pyxel.set_btn()`,
   screen buffer → RGB565 → the panel's fb/DRM node. Upstream currently calls
   `pyxel.init(..., display_scale=2)` + `pyxel.fullscreen(True)` and
   monkey-patches `pyxel.text`, so a headless switch is a contained change
   (whether `fullscreen()` is harmless when headless is still to be checked).
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

## Measured on the device (2026-11-18)

From read-only probes of the owner's unit (details in
`docs/hardware-notes.md`, task status in `ROADMAP.md`).

1. **It's a stock Debian 13 / Raspberry Pi kernel box.** SSH is the way in;
   M5's ADB exists but isn't needed.
2. **Display = `/dev/fb0`**: 320×170, RGB565, an SPI panel driven through
   mipi-dbi (DRM `card1`), group `video`, no X/Wayland. So: headless pyxel +
   an RGB565 blit to fb0 (delta 3), no root. The launcher holds fb0 and the
   keyboard node open; per M5's APPLaunch guide it starts `Terminal=false`
   apps with fork+execlp and **pauses its own refresh while they run**, and
   long-pressing Home (fn+K) for 5 s sends them SIGINT (SIGKILL 3 s later) — my
   early SSH tests clashed with it because the launcher didn't know about
   them (`docs/launcher-guidelines.md`). Headless pyxel 3.0.2 already runs on the
   device (26 MiB peak RSS), and `tools/fb-blit-test.py` shows a 320×170
   RGB565 blit to fb0 sustaining 30 fps at ~16% of one core.
3. **RAM is the tightest resource**: ~353 MiB visible, ~145 MiB free with the
   launcher running, plus a 352 MiB zram swap. Budget the game's RSS early and
   import heavy modules (scapy) lazily.
4. **Non-root is largely feasible.** Group membership (gpio, spi, i2c, input,
   video, dialout, netdev) covers every device node, and the Cap's 5 V rail
   (`/sys/class/leds/ext_5v_out`) is group-writable. Only raw sockets and
   privileged WiFi operations need more. M5's own apps use narrow udev rules,
   or `.desktop` `Exec=/usr/bin/sudo -n -- <bin>` with a per-binary NOPASSWD
   sudoers drop-in shipped in the `.deb`; there is **no per-app systemd
   service** on the device, so AppBuilder's service model isn't what installed
   apps do (delta 1's "root services are rejected" applies to that store
   tooling, not necessarily to a sideloaded `.deb`).
5. **Keyboard**: the kernel overlay does the layer translation — the fn layer
   emits real `KEY_UP/DOWN/LEFT/RIGHT`, F-keys, PageUp/PageDown, Home/End on
   `/dev/input/event3` (verify live; decoded by eye so far).
6. **Internal radio**: no monitor mode (IBSS/managed/AP/P2P only), 2.4 GHz
   only, `iw` present, `hci0` up with BT 5.2 → scan-only source.
7. **Cap LoRa pins — confirmed on the device.** Derived by crossing M5's
   Cap-Bus table with the CardputerZero EXT table, then verified with
   `tools/lora-pin-probe.py` (RX-only): SX1262 on SPI0 **CS1**
   (`/dev/spidev0.1`; the uConsole code uses bus 1 CS 0), **RST = G26**,
   **BUSY = G22**, **DIO1/IRQ = G23**, rail via `ext_5v_out` (group-writable).
   **The module has a TCXO fed from DIO3** — without
   `SetDIO3AsTCXOCtrl` the chip reports `XOSC_START` and never enters RX; at
   1.8 V it works, and upstream's `lora_manager.py` already does
   `setDio3TcxoCtrl(DIO3_OUTPUT_1_8, 10)`. No PI4IOE5V6408 RF-switch expander
   answers at I²C 0x43/0x44, consistent with the legacy Cap LoRa868. GPS on
   **`/dev/ttyS0` @ 115200** (G14/G15; console is on `tty1`; NMEA verified, no
   fix indoors). Real packet RX/TX is still to be exercised (ROADMAP 2.2).
8. **Python**: system 3.13.5 already has pyserial, Pillow, dbus, gi,
   cryptography, requests, lgpio, RPi.GPIO, gpiod, spidev, smbus2. Missing:
   pyxel, scapy, bleak, LoRaRF, PyNaCl, netifaces (wheels exist for all but
   netifaces), and the radio tools (tcpdump, aircrack-ng, rtl-sdr, dump1090).
9. **Follow M5's own guidelines for integration and packaging** (decision
   2026-11-18, suggested by the owner; `docs/launcher-guidelines.md`): a
   `.desktop` entry in `/usr/share/APPLaunch/applications/` with
   `Terminal=false` and a plain-path `Exec` (a wrapper script — shell
   metacharacters are rejected), and a `.deb` laid out per AppBuilder's
   `packaging/` convention (`meta.env`, `stage.sh`, `postinst`, icon,
   `scripts/pack-deb.sh`). M5's own Python example renders exactly like our
   plan (Pillow → RGB565 → `mmap` of `/dev/fb0`, evdev keys), so the game stays
   Python/pyxel — no LVGL rewrite, no systemd service, no store publishing yet.
   A `.desktop` alone is enough for the dev loop (no `.deb` needed). The game
   must exit cleanly on SIGINT (the launcher's kill path).

## Phased plan

See **[`ROADMAP.md`](ROADMAP.md)** — the living tracking document with
per-task status checkboxes and a progress log. That file is the source of
truth for "where are we right now"; update it (not this section) as work
happens. In short: **Phase 0** hardware spike → **Phase 1** minimal build at
320×170 with no radio hardware → **Phase 2** LoRa/GPS/SDR/ESP32 integration
→ **Phase 3** package + sideload as an installed app → **Phase 4**
feature-parity pass + community feedback (no App Store submission yet).

## Open questions for the owner

- (Resolved 2026-11-18) LoRa chip: the owner's Cap is labelled "LORA
  868-932MHz SX1262" (so not SX1261 as first thought); the chip's version
  register reads `SX1261 V2D`, but that register can't tell the two apart.
  Still nice to have: a photo of the Cap, to confirm it is the legacy Cap
  LoRa868 (no HY2.0/Grove port) rather than the newer LoRa-1262.
- Is the CardputerZero or CardputerZero-Lite variant in hand (affects
  camera/IMU/bundled-SD assumptions, though none of those matter much to
  this port)?

## Working agreements

- `ROADMAP.md` is the source of truth for status. At the end of each work
  session, update the task checkboxes/status and append a line to its
  progress log, so the next session can resume from the file alone.
- Device access: SSH is the default way into the CardputerZero (M5's ADB is
  optional). The host and user are deliberately **not** recorded in this repo
  (it will be published); they live in the private Claude memory.
- Dev environments: `.venv/` at the repo root (gitignored; pyxel + Pillow) for
  headless renders on the dev machine, and a matching venv on the device at
  `~/WatchDogsGo-CardPZero/.venv` (`--system-site-packages`).
- Talk to the owner in Portuguese; keep repo docs, code comments and
  commit messages in English.
- UI fidelity to the original is a priority — keep palette, fonts, widget
  styles and the per-tab character art; only re-budget layout for 320×170.
  Details live in `docs/ui-adaptation.md`.

## Commit conventions for this repo

No upstream-inherited restriction here (the "never commit CLAUDE.md, never
AI-attribute commits" rule in `/home/tesso/dev/WatchDogsGo/CLAUDE.md` is that
*upstream* project's own policy for *their* repo — it does not apply to this
independent fork). Use normal Claude Code attribution on commits/PRs here
unless the owner says otherwise.
