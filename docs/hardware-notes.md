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

## Measured on the device (2026-11-18)

From `tools/phase0-probe.sh` plus follow-up read-only commands over SSH on the
owner's unit. Raw reports aren't committed (hostnames/usernames). Where this
section disagrees with the press/docs material above, this section wins.

**System.** Hostname `CardputerZero`; Debian 13.7 *trixie*; kernel
`6.18.39+rpt-rpi-v8` aarch64; device-tree model "Raspberry Pi Compute Module 0
Rev 1.0"; 4 cores @ 1 GHz; Python 3.13.5; systemd 257; 29 GB SD (22 GB free).
NetworkManager, wpa_supplicant, bluetooth and ssh run; `lightdm.service` is
active but no Xorg/Xwayland/weston/cage/sway process was found. The login user
is in `adm dialout cdrom sudo audio video plugdev games users netdev lpadmin
gpio i2c spi render input`; sudo needs a password except for three M5 apps.

**Memory.** `MemTotal` 361,392 kB (~353 MiB; `gpu_mem=128`,
`dtoverlay=vc4-kms-v3d,cma-64`), `MemAvailable` ~145 MB with the launcher and
services running, plus a 352 MiB zstd zram swap (~94 MB stored in ~16 MB).

**Display.** `/dev/fb0` (alias `/dev/fb_lcd`): name `panel-mipi-dbid`, 320×170,
16 bpp (RGB565), stride 640 B, group `video`. DRM: `card1` = `SPI-1` connected
320×170 (alias `/dev/dri/cardputer-zero-internal`, platform
`3f204000.spi-cs-0`); `card0` + `renderD128` = the vc4 GPU, HDMI disconnected.

**Launcher / apps.** `/usr/share/APPLaunch/bin/M5CardputerZero-APPLaunch` runs as
the login user from the systemd *user* unit `/usr/lib/systemd/user/APPLaunch.service`
(`Restart=always`, `WorkingDirectory=/usr/share/APPLaunch`) and holds
`/dev/fb0` and `/dev/input/event3` open. Apps are `.desktop` files in
`/usr/share/APPLaunch/applications/` (`Terminal=false`, icons under
`/usr/share/APPLaunch/share/images/`). Installed: Camera, Files, Music, Piano,
Recorder, Compass, IR Chat/Remote, Keyboard Guide, ZClaw, Calculator, the
AppStore, LaunchWizard, and Cap apps for LoRa-1262, LoRa-1262 GPS, CC1101 NFC
and CC1101 Sub-GHz chat. `preinstalled-desktop-apps.tsv` has the columns
`filename, Name, Icon, Exec, Terminal, Sysplause` — the last hints at a
pause-the-launcher flag (unresolved). M5's ADB support is a USB-gadget script
set in `/usr/share/APPLaunch/adb/`.

**Packaging precedent.** `dpkg -L` of the Cap packages: the LoRa package ships
`/usr/lib/udev/rules.d/70-cap-lora-1262.rules` (chgrp `gpio` + `g+w` on
`/sys/class/leds/ext_5v_out/brightness`), the `.desktop`, an icon and an app
under `/usr/share/Cap-LoRa-1262/bin/`; the GPS package ships
`/etc/sudoers.d/m5cardputerzero-cap-lora-1262-gps` (mode 0440) and its
`.desktop` uses `Exec=/usr/bin/sudo -n -- /usr/share/APPLaunch/bin/<App>`; the
sudoers lines for the three Cap apps are `(root) NOPASSWD: <exact binary> ""`
(no arguments). No per-app systemd service.

**Input.** `tca8418c` at I²C `0x34` (i2c-1), IRQ GPIO27, 5 rows × 10 columns,
node `/dev/input/event3` (alias `/dev/input/cardputer-zero-internal`, group
`input`). The `cardputerzero-v5-overlay` defines three keymaps
(`linux,keymap`, `linux,keymap1`, `linux,keymap2`) and the sym/fn/shift button
codes `0x43/0x42/0x41`; decoded by eye, the fn keymap yields `KEY_UP(103)`,
`KEY_DOWN(108)`, `KEY_LEFT(105)`, `KEY_RIGHT(106)`, F1–F12, PageUp(104),
PageDown(109), Home(102), End(107), Insert(110), Delete(111), PrintScreen(99)
and media/volume keys — i.e. the kernel does the fn-layer translation. Verify
with a live capture.

**GPIO / buses.** `gpiochip0` (bcm2835, 54 lines; `gpiochip4` is an alias),
`gpiochip1` (`gpio-spi-cs`), `gpiochip2` (`m5ioe1`, 14 lines — an I²C IO
expander at `0x4f` driving the 5 V rails and a USB mux; consumers
`ext_usb_gpio_fun`, `grove_5v_out`, `ext_5v_out`). Pin states: G9/G10/G11 =
SPI0 (alt0), G14/G15 = TXD1/RXD1 (alt5 → `/dev/ttyS0`, `/dev/serial0`), G2/G3 =
I²C1, G4 = `grove_fun`, G6 = `irq` (power-fail), G7/G8 = SPI0 CS1/CS0, G12/G13
= IR TX/RX, G17 = headphone detect, G24 = `enable`, G25 = `dc` (display),
**G22/G23/G26 unclaimed**. `/dev/spidev0.1` exists (CS0 belongs to the display
driver). LEDs for the rails: `/sys/class/leds/{ext_5v_out,grove_5v_out,ext_usb_gpio_fun,grove_fun}`.
Boot config: `dtparam=spi=on`, `i2c_arm=on`, `i2s=on`, `enable_uart=1`,
overlays `cardputerzero-v5-overlay`, `bq27220_v5`, `bmi270_bmm150_overlay`,
`gpio-ir`, `gpio-ir-tx`, `imx219`, `dwc2`; kernel `console=tty1` (the UART is
free) and `cfg80211.ieee80211_regdom=AE`.

**Internal radio.** `wlan0` managed on `phy#0` (also a P2P-device), driver
`brcmfmac` + `brcmfmac_cyw`, firmware `brcmfmac43439-sdio` (BCM43439/5, v7.95.75);
`iw phy` supported modes: IBSS, managed, AP, P2P-client, P2P-GO, P2P-device —
**no monitor** — and a single band (2.4 GHz). `wlan0` holds the default route.
Bluetooth: `hci0`, bus UART, UP RUNNING, HCI/LMP 5.2, manufacturer Cypress
(CYW4343A2, Murata Type-1YN), firmware
`BCM4343A2.raspberrypi,0-compute-module.hcd`.

**USB.** Host mode (dwc2): root hub → Genesys `05e3:0610` 4-port hub → USB LAN
`0fe6:9900` (`eth0`, down). No ttyUSB/ttyACM devices present; the RTL-SDR
kernel module isn't loaded.

**Battery.** `/sys/class/power_supply/bq27220-0` (TI BQ27220): status,
voltage, current, capacity, temperature, design capacity 1750 mAh — the source
for the HUD's battery readout.

**Not installed** (as of the probe): `pyxel`, `scapy`, `bleak`, `LoRaRF`,
`PyNaCl`, `netifaces`, `tcpdump`, `aircrack-ng`, `evtest`, `rtl_test`,
`rtl_433`, `dump1090`, `esptool`. Present: `iw`, `rfkill`, `wpa_cli`, `nmcli`,
`pinctrl`, `gpioinfo`, `hciconfig`, `bluetoothctl`, `dtc`, `strings`.

## Cap LoRa-1262 pins on the CardputerZero (derived, 2026-11-18)

M5's Cap pages (`…/products/sku/U201` "Cap LoRa868", `…/products/sku/U214` and
`…/cap/Cap_LoRa-1262` "Cap LoRa-1262") document the pins as a **Cap-Bus** table
plus the **Cardputer-Adv** GPIOs — they have no CardputerZero GPIO column.
The CardputerZero page documents its 14-pin **EXT header**. The Cap-Bus is that
same physical header, so crossing the two tables by position gives the mapping:

| Cap-Bus pin | Function | EXT pin | CardputerZero GPIO |
|---|---|---|---|
| 8 | LoRa RST | 1 (HAT_P0) | **G26** |
| 9 | LoRa IRQ (DIO1) | 3 (HAT_P1) | **G23** |
| 10 | LoRa BUSY | 5 | **G22** |
| 11 | LoRa SCK | 7 | G11 (SPI0_CLK) |
| 12 | LoRa MOSI | 9 | G10 (SPI0_MOSI) |
| 13 | LoRa MISO | 11 | G9 (SPI0_MISO) |
| 14 | LoRa NSS | 13 | G7 (SPI0_CS1 → `/dev/spidev0.1`) |
| 4 / 3 | SDA / SCL | 8 / 10 | G2 / G3 (I²C1 → `/dev/i2c-1`) |
| 2 / 1 | GPS RX / TX (host perspective) | 12 / 14 | G15 / G14 (`/dev/ttyS0`) |
| 5 / 6 / 7 | 5V_OUT / GND / 5V_IN | 6 / 4 / 2 | 5 V rails (`ext_5v_out`) |

(Cap-Bus right column top→bottom lines up with the EXT left column top→bottom,
and the SPI pins match one-to-one, which is what validates the crossing. The
GPS labels are from the host's perspective: the Adv table pairs "GPS-RX" with the
host's RX pin.)

**Evidence on the device** (Cap attached, M5's LoRa app open): `gpioinfo`
shows G26 as an **output** and G22/G23 as inputs, all with consumer
`pw_digital_io_linux`; the app holds `/dev/spidev0.1`, `/dev/i2c-1` and
`/dev/gpiochip0`; `ext_5v_out` reads 255. The GPS answers on `/dev/ttyS0` at
**115200** baud (multi-constellation NMEA, `GNRMC status=V` / `GNGGA quality=0`
indoors); 9600 returns nothing.

**Not yet confirmed:** which of G22/G23 is BUSY vs DIO1 (it rests on the
position argument above), and the RF switch. The Cap LoRa-1262 (not the older
LoRa868) carries a PI4IOE5V6408 I/O expander on I²C whose **P0 must be driven
high to enable the RF antenna switch** (`FM8625H`, `SX_ANT_SW`); M5's comparison
table lists "RF Switch Control: None" for the LoRa868. A read of I²C `0x43` and
`0x44` on `/dev/i2c-1` returned `EIO` (nothing there), so this unit may be the
LoRa868 or the expander sits at another address.

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
