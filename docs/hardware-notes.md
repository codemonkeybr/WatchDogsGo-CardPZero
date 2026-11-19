# Hardware reference notes

Research dump backing `CLAUDE.md`'s hardware section. Gathered 2026-11-18 via
web search (the device shipped ~May 2026, after this assistant's knowledge
cutoff, so none of this was prior knowledge — it's all sourced below).
Treat anything not confirmed against the physical hardware as provisional.

## CardputerZero — full EXT 2.54-14P pinout

Source: docs.m5stack.com/en/CardputerZero

| Left Pin | Function | Right Pin | Function |
|---|---|---|---|
| 1 | HAT_P0 (USB4_D_P / G26) | 2 | 5VIN |
| 3 | HAT_P1 (USB4_D_N / G23) | 4 | GND |
| 5 | G22 | 6 | 5VOUT |
| 7 | G11, SPI0_CLK | 8 | G2, I2C1_SDA |
| 9 | G10, SPI0_MOSI | 10 | G3, I2C1_SCL |
| 11 | G9, SPI0_MISO | 12 | G15, UART_RXD |
| 13 | G7, SPI0_CS1 | 14 | G14, UART_TXD |

`HAT_P0`/`HAT_P1` switch between GPIO (default) and USB Hub `USB4` via
`PYG1_HAT_SW`.

Other on-board GPIO assignments (not on the EXT header, internal):
- Display (ST7789v3): MOSI=G10, SCLK=G11, DC=G25, CS=G8, TE=G5
- Audio (I2S/I2C): G18–G21 (I2S), G2/G3 (I2C1 — shared with EXT pins 8/10
  above), G24 (speaker amp enable), G17 (headphone detect)
- IR: TX=G12, RX=G13
- Keyboard controller (TCA8418) interrupt: G27

## Cap LoRa-1262 / "Cap LoRa868" (SKU U201) — Cap-Bus pinout

Source: docs.m5stack.com/en/products/sku/U201, and the retail listing
`shop.m5stack.com/products/cap-lora-1262-for-cardputer-adv-sx1262-atgm336h`
(titled "for Cardputer-Adv"; the docs page separately lists CardputerZero as
a compatible host too — not reconciled, both kept here).

- LoRa chip: **SX1262** on a Stamp LoRa-1262 module. SPI interface.
  868–923 MHz, up to +20 dBm TX, -147 dBm sensitivity (low data rate mode).
  External RP-SMA antenna (rubber duck included).
- GPS chip: **ATGM336H-6N** (AT6668 solution). UART @ 115200 8N1, NMEA 0183
  4.1. Built-in ceramic antenna.
- Cap-Bus pinout (14 pins):
  - Left: GPS_TX(1), GPS_RX(2), SCL(3), SDA(4), 5V_OUT(5), GND(6), 5V_IN(7)
  - Right: LoRa_NSS(14), LoRa_MISO(13), LoRa_MOSI(12), LoRa_SCK(11),
    LoRa_BUSY(10), LoRa_IRQ(9), LoRa_RST(8)
- **Cardputer-Adv** GPIO mapping behind that Cap-Bus (given by the docs
  page — NOT necessarily the same on CardputerZero, which has a different
  SoC/GPIO map entirely):
  - LoRa: RST=G3, IRQ=G4, BUSY=G6, SCK=G40, MOSI=G14, MISO=G39, NSS=G5
  - GPS: RX=G13, TX=G15
  - SCL/SDA routing not stated.
- Vendor software references: Arduino `RadioLib` (LoRa) + M5Stack's
  `TinyGPSPlus` fork (GPS), and UiFlow2 MicroPython docs. **No Linux kernel
  module or driver referenced** — this is an ESP32/Arduino-world module by
  default; on CardputerZero (a Linux CM0 host) it'll need to go through
  userspace `spidev`/GPIO chardev + a Linux SPI SX1262 driver, same general
  shape as the uConsole AIO v2 board's `LoRaRF`-based approach in
  `lora_manager.py`.
- For comparison, uConsole's AIO v2 SX1262 wiring (what `lora_manager.py`
  currently targets): SPI bus 1, CS 0, 7.8 MHz; RESET=GPIO25, BUSY=GPIO24,
  IRQ=GPIO26 (BCM numbering). These are **uConsole/CM4 GPIO numbers, not
  transferable to CardputerZero's CM0** — kept here only as the pattern to
  replicate once CardputerZero's real numbers are known.

## CardputerZero keyboard (confirmed layer map)

Source: docs.m5stack.com/en/compute/cardputerzero/usage

- Modifiers: `sym` (blue symbols), `shift` (uppercase), `fn` (orange
  shortcuts). Each can be held, tapped-once (next key only), or
  double-tapped (locked until pressed again).
- `fn` layer:

  | Combo | Function |
  |---|---|
  | `fn`+`1`–`9` | F1–F9 |
  | `fn`+`0`/`O`/`P` | F10/F11/F12 |
  | `fn`+`Backspace` | Delete (forward) |
  | `fn`+`F`/`X` | Up / Down arrow |
  | `fn`+`Z`/`C` | Left / Right arrow |
  | `fn`+`K`/`N` | Home / End |
  | `fn`+`L`/`M` | Page Up / Page Down |
  | `fn`+`B` | Insert |
  | `fn`+`J` | Print Screen |
  | `fn`+`H` | Show/hide app help |
  | `fn`+`Q`/`W`/`E` | Play-pause / Prev / Next track |
  | `fn`+`A`/`S`/`D` | Mute / Vol down / Vol up |
  | `fn`+`U`/`I` | Brightness down / up |

- Direct keys: `TAB` (context-dependent: hold on HOME = lock screen),
  `ENTER`/`OK` (confirm), `ESC` (hold = exit to HOME, short press = back/
  cancel), `4`–`8` (context action keys in some apps).
- Not resolved by the docs: whether a held `fn` makes pyxel (or any app
  reading raw keycodes) see a distinct arrow keycode, or the base letter
  key plus a separate modifier state — needs testing on-device. The docs
  themselves are internally inconsistent about PgUp/PgDn in the CLI/Python
  sections (`shift+fn+L/M` there vs plain `fn+L/M` in the main shortcut
  table) — verify by testing on hardware, don't trust either table blindly.

## App packaging shape (CardputerZero-AppBuilder / `czdev`)

Source: `github.wyh1030873310.workers.dev/m5stack/CardputerZero-AppBuilder` (a worker-proxied
mirror reachable by this assistant's fetch tool; the canonical repo is
presumably `github.com/m5stack/CardputerZero-AppBuilder`).

- `czdev` is a pure-Python CLI (needs Python 3, git, `dpkg-deb`).
  `czdev new NAME` scaffolds from `CardputerZero/Template` (LVGL+CMake by
  default, with an SDL2 desktop preview build and a device framebuffer
  build). `NAME` must be a valid Debian package name.
- CI cross-compiles x86_64→aarch64 (`aarch64-linux-gnu-` toolchain); no
  local ARM toolchain required if building through the repo's GitHub
  Actions workflow.
- `.deb` layout:
  - `DEBIAN/control`, `DEBIAN/postinst` (enable+start the systemd service),
    `DEBIAN/prerm` (stop+disable it).
  - `lib/systemd/system/<package>.service` — **apps must run as a
    non-root user; root services are rejected by the tooling.**
  - `usr/share/APPLaunch/applications/<package>.desktop` — this is what the
    launcher actually discovers (exact scan mechanism not documented).
  - `usr/share/APPLaunch/{bin,lib,share}/` — executable, libs, fonts/images.
- Manifest `app-builder.json` carries the App Store listing metadata
  (title, summary, screenshots — at least one must be 320×170 — categories).
  Full schema is in the repo's `docs/APP_BUILDER_JSON.md` (not fetched yet).
- Sideload path (what this project will use, per the owner's "don't publish
  to the store yet" instruction):
  ```bash
  scp <package>_arm64.deb pi@<device-ip>:/tmp/
  ssh pi@<device-ip> "sudo dpkg -i /tmp/<package>_arm64.deb"
  ```
  `postinst` then enables/starts the service automatically.
- Publishing (`czdev login/publish/...`) exists but is **out of scope**
  for this project right now.

## Sources

- https://docs.m5stack.com/en/CardputerZero
- https://docs.m5stack.com/en/products/sku/U201
- https://docs.m5stack.com/en/compute/cardputerzero/usage
- https://docs.m5stack.com/en/guide/linux/cardputerzero/adb
- https://shop.m5stack.com/products/cap-lora-1262-for-cardputer-adv-sx1262-atgm336h
  (linked by the project owner; fetch was rate-limited at research time,
  not yet re-confirmed — the `docs.m5stack.com/.../sku/U201` fetch above is
  the primary source for this module's specs)
- https://github.wyh1030873310.workers.dev/m5stack/CardputerZero-AppBuilder
- https://www.cnx-software.com/2026/05/25/cardputerzero-a-raspberry-pi-cm0-pocket-computer-for-makers/
- https://liliputing.com/cardputerzero-pocket-computer-combines-the-brains-of-a-raspberry-pi-zero-2w-with-a-tiny-display-keyboard-and-battery/
