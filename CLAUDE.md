# CLAUDE.md

Orientation for Claude Code (and humans) working in this repository. Keep it
**accurate**: when a measurement or a decision changes, fix the text here
instead of appending a correction. Task status lives in `ROADMAP.md`, not here.

## 1. The project

A port of **[WatchDogsGo](https://github.com/LOCOSP/WatchDogsGo)** — a `pyxel`
retro-game frontend (Watch-Dogs-style HUD, XP, world map) over *real*
WiFi/BLE/LoRa/SDR security tooling, built for the ClockworkPi uConsole (CM4) —
to the **M5Stack CardputerZero**, a pocket Linux handheld (Raspberry Pi CM0,
320×170 screen, 46-key keyboard).

Owner's goals: **maximum feasible feature parity**; run as a normal app that
the CardputerZero's own launcher starts from its carousel; stay **as faithful
to the original UI as the small screen allows**; offer **WiFi/BLE wardriving
from the device's own radio** as an option next to the ESP32; show it to the
WatchDogsGo community for feedback **before** any AppStore listing. Not in
scope now: publishing to the CardputerZero AppStore (`czdev publish`).

## 2. Map of the repository

| Path | What it is |
|---|---|
| `ROADMAP.md` | **Source of truth for status**: phases, tasks, measured results, progress log, pre-publication checklist. Update it at the end of every session. |
| `VENDORED.md` | Provenance of the vendored game code, the rebase recipe, how to re-sync with upstream. |
| `watchdogs/`, `plugins/`, `assets/`, `hs_capture.py`, `wdg_wifi_bridge.py`, `requirements.txt`, `secrets.conf.example`, `LICENSE` | **Vendored upstream code** (WatchDogsGo 0.10.0 + the internal-radio bridge). Unmodified at vendoring (commit `0603f22`); every later change is an ordinary commit — see §9. |
| `docs/hardware-notes.md` | Detailed measurements and pin tables, with sources. |
| `docs/launcher-guidelines.md` | How APPLaunch and M5's AppBuilder work, and what we adopt. |
| `docs/ui-adaptation.md` | Proposal for re-budgeting the UI from 640×360 to 320×170. |
| `docs/portal-rules.md` | Upstream's rules for forks that talk to the WDGWars portal. |
| `czplatform/` | **Our platform layer** (§5): runs the unmodified vendored game on the CardputerZero — `display.py` (RGB565 → `mmap` fb0), `keys.py` (evdev → `pyxel.set_btn`), `shim.py` (headless pyxel, main loop, SIGINT), `host.py` (**makes the uConsole GPIO code safe**, points LoRa/GPS at the Cap), `profile.py` + `ui320.py` (the 320×170 canvas and its compact HUD/terminal/menu drawing, installed at run time only in that profile — see `docs/ui-adaptation.md`), `__main__.py` (entry point: `python -m czplatform`). |
| `tests/` | Unit tests for `czplatform` (no hardware needed): `.venv/bin/python -m unittest discover -s tests -v`. They also pass on the device. |
| `tools/` | Device probes and test programs (§8). |
| `dev/` (gitignored) | Generated on the device only: wrapper script, `.desktop`, logs. |

## 3. State of play (2026-11-18)

**Proven on the real device:** SSH access; the display path (headless pyxel →
RGB565 → `mmap` of `/dev/fb0`, 30 fps at ~16% of a core); launching a pyxel app
from the carousel with a `.desktop` entry (the launcher pauses itself and the
screen is ours); keyboard events from evdev, including the fn layer; the Cap's
LoRa pins and its TCXO requirement; GPS NMEA over `/dev/ttyS0`; the internal
WiFi/BT characteristics; the packaging model.

**Done in the repo:** game code vendored unmodified; the platform layer
`czplatform/` (display, keyboard, signals, host safety) with 25 passing unit
tests; docs; probes/tools. **The 320×170 UI is under way** — top/bottom HUD,
the map/log split (ENTER switches between the map and a full-screen log) and the menu are done as a compact layer (`czplatform/ui320.py`,
`--canvas 320x170`; samples in `docs/screenshots/`), with ≈45–64 MiB RSS on the
CM0; the boot screen and the sub-screens still need work (ROADMAP 1.2).
**The real game now runs headless through it** —
on the dev machine (`--dry-run` renders the boot screen to a PNG) and on the
device without hardware attached: 30 fps, ≈112–119 MiB RSS, ≈2 s startup, 21–41%
of one core (ROADMAP 1.7, 0.10).

**Seen on the real panel (owner, 2026-11-18):** the game runs from the
carousel. Its log shows the keyboard, the Cap rail and the GPS port
(`/dev/ttyS0` @ 115200) working, 30 fps with the framebuffer write, and a clean
exit through the game's own quit path. **Not done yet — be honest about it:** it
still draws its 640×360 canvas, shown on the 320×170 panel only through the
interim `--view scale|crop`, i.e. illegible (the real re-layout is ROADMAP 1.2).
Unexercised on hardware: ESP32, NESDR/RTL-SDR, LoRa packets (RX/TX), a GPS *fix*,
WiFi/BLE scanning through the internal-radio bridge, raw sockets without root,
SIGINT through the Home long-press, typed text and the sym layer.

## 4. Hardware as measured

Sources: M5Stack docs + `tools/` probes on the owner's unit. Details and raw
numbers in `docs/hardware-notes.md`. The device shipped ~May 2026, so don't
trust remembered facts — measure.

### 4.1 Host: CardputerZero

| | |
|---|---|
| SoC / RAM | Raspberry Pi **CM0** (RP3A0/BCM2837), 4× Cortex-A53 @ 1 GHz, aarch64. **~353 MiB visible, ~145 MiB available** with the launcher running, plus 352 MiB zstd zram swap (`gpu_mem=128`, `cma-64`) |
| OS | **Debian 13 (trixie)**, Raspberry Pi kernel 6.18.x, Python 3.13, systemd 257 — a stock Pi-class Linux box. NetworkManager + wpa_supplicant + bluetooth + ssh. The login user needs a sudo password; ssh is key-based |
| Display | 1.9" 320×170 ST7789v3 over SPI via mipi-dbi → **`/dev/fb0`**: 16 bpp **RGB565** (R5@11 G6@5 B5@0), stride 640 B, group `video`. DRM `card1` (`SPI-1`); the vc4 GPU (`card0`) has HDMI only. **No X/Wayland** |
| Keyboard | TCA8418 matrix (5×10) on I²C 0x34 → **`/dev/input/event3`** (group `input`). The **kernel overlay does the layer translation** (3 keymaps: base, shift/sym, fn); the `fn` key itself emits **code 389** |
| Launcher | `APPLaunch` — a systemd *user* service (`M5CardputerZero-APPLaunch`, `Restart=always`). It **locks the screen after 30 s of keyboard inactivity** (a full-screen black overlay; the launcher also tries to dim the backlight, but **whether it really switches off on this unit is open**; Settings → Screen → DarkTime, TAB held 3 s locks; wake = any key, then TAB, ENTER) — but **not while an external app runs** (it calls `ui_screensaver_set_foreground(0)` on hand-off — owner-verified with the demo left open). Backlight: `/sys/class/backlight/backlight/brightness`, `root:video rw-rw-r--`, 0–100 |
| USB | host mode via the internal hub; 1× USB-A, 2× USB-C; physical host/slave switch (slave mode is only for M5's ADB) |
| Expansion | `EXT 2.54-14P` header = the Cap-Bus (not hot-swappable); 5 V rails switched through the `m5ioe1` I²C expander, exposed as LEDs in `/sys/class/leds/` |
| Power | TI BQ27220 gauge at `/sys/class/power_supply/bq27220-0` (source for the HUD battery) |
| Device nodes | `/dev/gpiochip0..2`, `/dev/spidev0.1`, `/dev/i2c-*`, `/dev/ttyS0`, `fb0`, `event3` — all reachable **without root** through the login user's groups (`gpio spi i2c input video dialout netdev render`) |

### 4.2 Owner's Cap: LoRa + GNSS (pins confirmed on the device)

Labelled "LORA 868-932MHz SX1262", with an 868 MHz-type RP-SMA antenna; the
sticker strip reads GNSS / LoRa. Most likely M5's legacy **Cap LoRa868**.

- **LoRa**: SX1262 on SPI0 **CS1 = `/dev/spidev0.1`** (CLK G11, MOSI G10, MISO
  G9, NSS G7); **RST = G26** (output), **BUSY = G22**, **DIO1/IRQ = G23**
  (measured by edge timing with `tools/lora-pin-probe.py`). The uConsole code
  uses SPI bus 1 / CS 0 and other pins — don't carry those over.
- **TCXO on DIO3**: without `SetDIO3AsTCXOCtrl` the chip reports `XOSC_START`
  and never enters RX; at 1.8 V it works. Upstream's `lora_manager.py` already
  calls `setDio3TcxoCtrl(DIO3_OUTPUT_1_8, 10)`. DIO2 is the RF switch there.
- The chip's version register reads `SX1261 V2D` — that register can't tell
  SX1261 from SX1262 (Semtech forum). Trust the label/M5 docs: SX1262, so
  `setTxPower(22, TX_POWER_SX1262)` is right (mind regional power limits).
- No PI4IOE5V6408 RF-switch expander answers at I²C 0x43/0x44 (the newer
  Cap LoRa-1262 has one) — consistent with the legacy LoRa868.
- **Power**: write `1` to `/sys/class/leds/ext_5v_out/brightness` (max is 1;
  group `gpio` can write it, via the udev rule M5's package ships). M5's own
  apps turn it off when they exit.
- **GPS**: ATGM336H, multi-constellation NMEA at **115200 baud on `/dev/ttyS0`**
  (G14/G15). The kernel console is on `tty1`, so the port is free. Upstream
  defaults to `/dev/ttyAMA0` @ 9600 — override (`WDG_GPS_DEVICE`,
  `WDG_GPS_BAUD`). Upstream's NMEA parser already accepts `GP*`/`GN*` GGA/RMC.
- How the pins were found: M5's pages document the **Cap-Bus** pins and the
  CardputerZero page documents the **EXT header**; the two are the same
  physical 14-pin connector, so crossing the tables by position gives the map
  (table in `docs/hardware-notes.md`).

### 4.3 Other radios

- **ESP32 (projectZero firmware)**: unchanged from the uConsole — USB serial
  at 115200, `serial_manager.py`. Should work on the host-mode USB ports; not
  yet tried.
- **Internal WiFi/BT as a scan source**: `wlan0` (brcmfmac, **2.4 GHz only,
  no monitor mode** — supported modes IBSS/managed/AP/P2P) and `hci0` (BT UART,
  HCI 5.2). Good for WiFi/BLE *wardriving*, not for deauth/handshake/sniffer/
  Evil Twin/SAE flood — those still need the ESP32 or an external monitor-mode
  adapter. `wlan0` is also the only uplink (the SSH session rides on it), and
  triggering `iw` scans needs `CAP_NET_ADMIN`. Upstream already has the
  mechanism: `wdg_wifi_bridge.py` emulates an ESP32 over a PTY (`iw scan` +
  `bleak`), and `serial_manager.detect_aiov2_bridge_port()` falls back to it.
  Planned: an explicit setting `auto | esp32 | internal` (ROADMAP 2.8); keep
  upstream identifiers and change only user-visible "AIO v2" strings.
- **SDR**: NooElec NESDR SMART (RTL-SDR) through upstream's `sdr_manager.py`
  (`dump1090`, `rtl_433` subprocesses) — pure USB, no pins. Needs `rtl-sdr`,
  `rtl-433`, `dump1090` installed and `dvb_usb_rtl28xxu` blacklisted.

## 5. Runtime design on the device

**Implemented in `czplatform/`, without editing the vendored code.** Before the
game is constructed, `shim.Runtime.install()` replaces `pyxel.init` (→ headless,
tells the panel the canvas size), `pyxel.run` (→ wrapped `update`/`draw`),
`pyxel.fullscreen` and `pyxel.mouse` (→ no-ops); `host.adapt_game()` patches
the uConsole-specific modules (§6); `__main__` replaces upstream's entry point.
The diagram below is what it does.

```
APPLaunch carousel ──(.desktop, Terminal=false, Exec=wrapper script)──▶ python
                                                                          │
  /dev/input/event3 ──evdev──▶ key map ──▶ pyxel.set_btn ──▶  game (watchdogs/app.py)
                                                                          │ headless pyxel, 320×170
  /dev/fb0  ◀── mmap ◀── RGB565 ◀── pyxel.screen.data_ptr() ◀─────────────┘
```

- **Rendering**: `pyxel.init(320, 170, headless=True)` (default pyxel needs an
  OpenGL window and panics without GL). Convert the palette-index buffer
  (`bytes(pyxel.screen.data_ptr())`) to RGB565 with two `bytes.translate`
  tables (low/high byte planes) and assign it into an `mmap` of `/dev/fb0`.
  Measured: ~4 ms/frame total.
- **Input**: read evdev from the TCA8418 node, ignore code 389 (`fn`), map
  evdev codes to pyxel keys with `pyxel.set_btn()`. Note pyxel's `KEY_*`
  constants are SDL keycodes, not evdev codes — a translation table is needed.
- **Launcher contract** (`docs/launcher-guidelines.md`): `Terminal=false` apps
  are fork+exec'd and the launcher pauses its own refresh until they exit;
  **long-pressing Home (fn+K) for 5 s sends SIGINT, SIGKILL 3 s later** → exit
  cleanly on SIGINT. `Exec` must be a plain executable path (no shell
  metacharacters), so use a wrapper script. stdout is lost — log to a file.
- **Privilege**: prefer **non-root** (device nodes are group-accessible). Needing
  more (raw sockets for scapy, `iw` scan triggers) → `CAP_NET_RAW/ADMIN` or
  M5's pattern: `Exec=/usr/bin/sudo -n -- <wrapper>` plus a per-binary
  NOPASSWD sudoers drop-in shipped in the `.deb` (the wrapper and what it runs
  must then be root-owned; no arguments allowed). Undecided: ROADMAP 3.1.
- **Packaging**: M5's conventions — a `.deb` under `/usr/share/APPLaunch/`
  (`applications/<pkg>.desktop`, `bin/`, `share/images/` icon), built from
  AppBuilder-style `packaging/{meta.env,stage.sh,postinst}` with
  `scripts/pack-deb.sh`; apt `Depends:` for system libs; **bundle pyxel** (not
  in Debian). No systemd service, no LVGL, no store publishing yet.
- **Views and controls (320×170 profile)**: the map is the home view and its
  last line is a one-line ticker of the newest log entry; **ENTER** (OK) toggles a
  full-screen log, where the arrows (`fn`+F/X/Z/C), PgUp/PgDn (`fn`+L/M),
  Home/End (`fn`+K/N) scroll, **ESC** returns and **TAB** opens the menu. The
  scroll keys are consumed by `ui320.input_filter` (set on `KeyInjector.filter`)
  before the game sees them — pyxel cannot un-press a key within a frame
  (`set_btn(k, False)` only clears a key held from an earlier frame).
- **Screen policy**: no auto-lock while we're the foreground app, so the screen
  stays on by itself; for long wardriving sessions decide our own dim/blank +
  wake-on-key policy (the backlight is writable without root) — ROADMAP 1.8.
- **Memory**: budget the whole game under ~100 MiB RSS. Idle headless pyxel
  is ~26 MiB. Keep heavy modules (scapy, cryptography…) lazily imported.

## 6. What we are porting (upstream architecture)

Upstream's own `CLAUDE.md` is *not* vendored (it describes their repo and
their uConsole workflow). In short:

- **Engine**: `pyxel`, canvas `W, H = 640, 360` at 30 FPS in `watchdogs/app.py`
  (~7.9k lines, `WatchDogsGame`, ~40 `_draw_*` methods, ~380 `pyxel.text` calls
  with absolute coordinates). `pyxel.init(..., display_scale=2)` +
  `pyxel.fullscreen(True)`, `pyxel.text` monkey-patched to use Spleen 5×8.
- **Menu dispatch**: `MENU_CATS` entries are `(hotkey, label, command,
  category, extra)`. Plain strings go over ESP32 serial (`CMD_*` in
  `config.py`); `_`-prefixed commands run Python-native features (MITM, Dragon
  Drain, BlueDucky, RACE, MeshCore, Flipper, SDR) through a long `if cmd ==`
  chain.
- **Manager pattern**: `lora_`, `serial_`, `gps_`, `flipper_`, `sdr_`, `aio_`,
  `watch_manager.py` — each a background thread + `Queue` + `_emit()` +
  `stop()`; `app.py` drains one queue per manager each frame. **They fail
  closed** (return `None`/`False`, log) when hardware is absent, so menus, map,
  terminal and plugins run with nothing attached.
- **State**: `LootManager` → `loot/<timestamp>/` + `loot/loot_db.json` (XP,
  badges, dedup sets); `~/.watchdogs_meshcore*.json`; logs in
  `~/.watchdogs/last_run.log`. Run from a read-only install dir and these paths
  must be redirected.
- **Map**: `tile_manager.py` (Stadia raster tiles, needs `STADIA_API_KEY`,
  quantized to pyxel's 16 colours) and `coastline.py` (procedural fallback).
- **Plugins**: `plugins/*.py`, `PluginBase` lifecycle hooks;
  `wardrive_upload.py` is the WDGWars portal client — see `docs/portal-rules.md`.
- **Dependencies**: only **`pyxel` and `pyserial`** are imported at module
  level; `scapy`, `cryptography`, `dbus`, `bleak`, `LoRaRF`, `requests`,
  `netifaces`, `gi`, `nacl`, `lgpio`/`RPi.GPIO`, `PIL` are imported lazily
  inside the functions that need them.
- **Entry point**: upstream's `watchdogs/__main__.py` runs a `preflight()`
  that calls `setup.sh` (not vendored, uConsole-specific) when anything is
  missing — ours is `python -m czplatform` (which also sets up the same
  logging and serial-port detection).
- **uConsole GPIO hazard — never run the vendored game on the device without
  `czplatform`.** `aio_manager.py` (HackerGadgets AIO v2) runs `pinctrl set`
  on GPIO 27 ("gps"), 23 ("usb"), 7 ("sdr"), 16 ("lora"), and
  `AioManager.is_installed()` is just `which pinctrl` — true here. On this
  device GPIO 27 is the **keyboard interrupt**, 23 the **LoRa DIO1** (an input
  from the chip) and 7 the **LoRa chip-select**; `lora_manager.py` also
  hard-codes RST/BUSY/IRQ = 25/24/26 on SPI bus 1 (G25/G24 are the display's
  `dc`/`enable`). `czplatform/host.py` makes `AioManager` a no-op that never
  spawns `pinctrl` and re-points the LoRa constants at the Cap (SPI0 CS1,
  RST=G26, BUSY=G22, IRQ=G23); `tests/test_host.py` guards it. The Cap's rail
  is switched by `host.CapRail` (`ext_5v_out`) instead.
- **Startup work to know about**: the constructor re-converts the hi-res
  `hacker.png`/`radio.png` with Pillow on every start (≈1.8 s on the CM0,
  writes into `assets/`), and imports `cryptography` for the MeshCore identity
  (ROADMAP 1.9, 1.10).
- **Keys**: TAB=menu, SPACE(hold)=hack, arrows=pan/navigate, `=`/`]` `-`/`[`
  `0`=zoom, S=stop, ESC=quit, PgUp/PgDn=terminal scroll, backtick=loot, full
  A–Z/0–9 input dialogs; ~45 `pyxel.KEY_*` constants in `app.py`.

## 7. Decisions and open risks

| Topic | Decision / finding | Where |
|---|---|---|
| Rendering | Headless pyxel → RGB565 → `mmap` fb0. Proven with a demo launched from the carousel | ROADMAP 0.1 ✅, 1.7 |
| Launcher/packaging | Follow M5's guidelines (`.desktop` + `.deb`); keep Python/pyxel; no LVGL, no service | `docs/launcher-guidelines.md`, 3.x |
| UI | Keep palette, fonts, widgets, per-tab art; re-budget layout only; display profiles in code | `docs/ui-adaptation.md`, 1.2 |
| Vendoring | Copy upstream unmodified, then small localized edits; record SHAs | `VENDORED.md`, 1.1 ✅ |
| Wardriving source | Internal radio *and* ESP32, selectable | 2.7, 2.8 |
| Privilege | Non-root by default; open for raw sockets / `iw` scans | 0.4, 3.1 |
| Portal | Follow upstream's fork rules (UA `Fork/` tag, honest platform, limits, pairing) | `docs/portal-rules.md`, 4.2, 4.5 |
| **Risk: RAM** | ~145 MiB free; the real game measures ≈112–119 MiB RSS (flat over 100 s) — fits, little headroom; hardware managers add some | 0.10 |
| **Hazard: uConsole GPIO code** | Unadapted AIO v2 code would drive the keyboard IRQ, LoRa DIO1/NSS and display lines — neutralized at runtime in `czplatform/host.py` | 1.4 ✅, `tests/test_host.py` |
| **Risk: layout effort** | ~40 draw methods with absolute pixel coordinates | 1.2 |
| **Risk: non-root raw sockets** | scapy features may need capabilities | 0.4 |
| Upstream drift | Upstream moves fast; delta must stay small | `VENDORED.md` |

## 8. Working on this repo

### Environments

- Dev machine: `.venv/` at the repo root (gitignored) with `pyxel` + `Pillow`
  — enough for headless renders and the tools. Python 3.12 here.
- Device: project dir `~/WatchDogsGo-CardPZero/` with `.venv` (created
  `--system-site-packages` to reuse apt's `dbus`/`gi`/`serial`/`PIL`/…),
  `assets/` (fonts), `tools/`, `dev/`.
- **Device access** is by SSH with key auth. The host and user are deliberately
  **not recorded in this repo** (it will be public) — they live in the
  private Claude memory. Reads and probes are fine; ask the owner before
  anything that needs `sudo` or changes system state (apt, `/etc`, `/boot`).
  The ssh login prints a harmless "valid user has been set up" banner.

### Tools (`tools/`)

| Tool | Purpose / notes |
|---|---|
| `phase0-probe.sh` | Read-only device inventory → text report (MACs masked; keep reports out of git). Run **on** the device |
| `pyxel-smoke.py` | pyxel init/fonts/buffer/PNG check, desktop and device; prints peak RSS |
| `fb-blit-test.py` | headless pyxel → fb0 write benchmark. Run over SSH it fights the launcher (see gotchas) |
| `lora-pin-probe.py` | RX-only SX126x pin/TCXO probe, on the device. **Close M5's LoRa/GPS apps first** (they hold the GPIO lines/SPI). `--tcxo` enables the DIO3 supply |
| `cz-demo.py` + `make-dev-entry.sh` | launcher-integration demo (draws, logs evdev keys) and the generator of the wrapper + `.desktop` |
| `ui-tour.sh` | **the UI review loop, no hardware**: runs the real game headless with the demo loot DB (`tests/fixtures/demo-data`), a fake 82 % battery and a scripted key tour, writing one PNG per screen (boot, main, each menu tab). `tools/ui-tour.sh [outdir] [320x170\|640x360]` |
| `make-sprites.py` | generates the half-size (85×128) menu sprites and the small radio icon into `assets/cz/` from the hi-res art, with the game's own palette pipeline |
| `fb-screenshot.py` | screenshot of the panel by reading fb0 over SSH. Reads a **single colour when the launcher has locked the screen** (30 s after an app exits or after idle) — press a key on the device and retry |

### Running the game

```bash
# dev machine: the REAL game, headless, no hardware — saves the panel view and the full canvas
.venv/bin/python -m czplatform --dry-run --frames 150      # -> czplatform-dryrun.png, czplatform-dryrun-canvas.png
tools/ui-tour.sh ./ui-tour 320x170                          # one PNG per screen (boot, main, each menu tab)
.venv/bin/python -m unittest discover -s tests -v          # 25 tests, no hardware
# device: from the carousel — the wrapper dev/wdg-game.sh runs `python -m czplatform --canvas 320x170`
```

Dev flags for UI work: `--canvas 640x360|320x170`, `--seed DIR` (a loot DB
fixture copied into the dry-run data dir), `--script 'wait:N,key:NAME,png:PATH,quit'`
(a scripted keyboard; `CZ_FAKE_BATTERY=NN` fakes the battery).

`--dry-run` uses a throw-away HOME and data dir, so nothing lands in `~/.watchdogs*`
or in the repo (`loot/` and `maps/` are gitignored anyway). Dev needs `pyxel`,
`Pillow`, `pyserial` and `cryptography` in `.venv`. Useful flags: `--view
scale|crop` (interim 640×360 → 320×170), `--png/--frames` (capture after N
frames), `--no-fb`, `--no-input`, `--cap-power on|off|auto`, `--verbose` (fps/RSS
lines on stderr), `--data-dir`, `--serial`.

### Dev loop on the device

1. Edit on the dev machine, `scp` the files to `~/WatchDogsGo-CardPZero/`.
2. Run non-visual checks over SSH.
3. For anything that draws: launch from the carousel. A bare `.desktop`
   (`tools/make-dev-entry.sh` prints the single `sudo install` line) is enough
   — the launcher rescans every ~3 s. Remove with `sudo rm
   /usr/share/APPLaunch/applications/wdg-demo.desktop`.
4. Read results from the log file the app writes (`dev/…`), or take a
   screenshot.

### Gotchas (learned the hard way)

- **pyxel `chdir`s to the script's folder on init**, and `pyxel.Font` doesn't
  find relative paths: resolve every path **before** `import pyxel`.
- `pyxel.quit()` exits the process immediately — nothing after `pyxel.run()`
  executes (`atexit` handlers *do* run, which is how `CapRail` restores the
  rail and how a `cProfile` dump works); print/log/restore *before* calling it.
- The vendored game's `update`/`draw` are bound methods, so `czplatform` finds
  the game instance with `update.__self__` to call its `_cleanup()`.
- **Never run the vendored game on the device without `czplatform`** (§6, uConsole
  GPIO hazard).
- **Compact-UI drift**: `ui320.py` replaces whole methods of `WatchDogsGame`
  (`_draw_hud_top`, `_draw_hud_bottom`, `_draw_terminal`, `_draw_menu`,
  `_draw_menu_hacker`, `_load_hacker_sprite`, plus wrappers on `_draw_messages`, `_draw_radar` and `update`) at
  run time. After every upstream sync, diff those methods against upstream — new
  HUD items or menu behaviour won't appear in the 320×170 layout until mirrored —
  and re-run `tools/ui-tour.sh`.
- Default pyxel needs OpenGL → always `headless=True` here.
- **Never draw on `/dev/fb0` from an SSH shell while the launcher is active**:
  it keeps repainting its own frame and wipes yours. If you must, stop it
  (`XDG_RUNTIME_DIR=/run/user/$UID systemctl --user stop APPLaunch.service`)
  with a `trap` that starts it again. Otherwise launch via the carousel.
- `iw`, `rfkill`, `swapon`, `ldconfig` live in `/usr/sbin`, which non-login SSH
  shells lack — add it to `PATH`.
- libgpiod **v2** `gpioinfo` takes line names, not chip names; use plain
  `gpioinfo` or `gpioinfo -c gpiochip0`.
- GitHub's compare API lists commits **oldest first** (I misread it once).
- The `fn` key emits code 389 — filter it. Unmapped fn combos arrive as the
  plain key.
- The Cap is **not hot-swappable**; test LoRa **RX-only**; mind regional power
  and band limits before any TX.
- Don't let a probe leave the hardware changed: restore G26 to input and the
  rail to its previous value (the probes do).

## 9. Conventions

- **Language**: talk to the owner in **Portuguese**; docs, code comments and
  commit messages in **English**.
- **Docs are living**: `ROADMAP.md` (status + progress log, updated every
  session), this file (stable orientation), `docs/*` (details). No duplicated
  truth — link instead.
- **Commits**: `<type>: <summary>` (`feat fix docs refactor chore perf test
  vendor tools`), body explains *why*. Use the normal Claude Code attribution
  trailers (upstream's "no AI attribution / don't commit CLAUDE.md" rule is
  their policy for their repo, not ours). The author is the owner's configured
  git identity.
- **Vendored code**: the vendoring commit stays pure upstream bytes;
  modifications go in later commits and stay small and localized (display
  profile constants, the runtime shim, stubs). Record upstream SHAs in
  `VENDORED.md`. Prefer changing user-visible strings over renaming
  identifiers, so merges stay cheap.
- **UI fidelity first**: same 16-colour palette, Spleen 5×8 at native size,
  same widgets and per-tab art; only the layout budget changes.
- **Privacy**: never commit the device host/IP/user, raw probe reports, API
  keys or `secrets.conf`. Scan with `git grep` before a push.
- **WDGWars portal traffic** must follow `docs/portal-rules.md`.
- **License**: vendored code is MIT © LOCOSP (`LICENSE` stays); the license
  for new code and the publication checklist are in `ROADMAP.md`.

## 10. Open questions for the owner

- Create the rebased branch in the fork (`feat/aiov2-wifi-bt-fallback` on top of
  upstream `8a2cb54`)? Vendoring didn't need it; it would make a clean PR.
- Default LoRa region/frequency plan for the MeshCore presets on this unit
  (the antenna looks like an 868 MHz one; the module covers 868–932 MHz).
- License for the new code (MIT keeps it simple).
- **Left open by the owner:** does the launcher's lock screen only paint black
  or really switch the backlight off? (sysfs is inconclusive; settle later by
  comparing the BQ27220 `current_now` awake vs locked — ROADMAP 1.8.)
- A photo of the Cap would confirm the legacy LoRa868 (no HY2.0/Grove port).
- CardputerZero or CardputerZero-Lite (camera/IMU/bundled SD) — minor.
