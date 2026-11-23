# Installing WatchDogsGo on the CardputerZero

A quick-install guide for testers sideloading the `.deb`, adapted from
upstream's own quick-install flow for this device. See `ROADMAP.md` for the
full porting status.

## 1. Install the package

```bash
scp watchdogsgo-cardputerzero_<version>_arm64.deb you@your-cardputerzero:/tmp/
ssh you@your-cardputerzero
sudo dpkg -i /tmp/watchdogsgo-cardputerzero_*.deb
sudo apt-get install -f -y   # pulls in any missing apt dependency
```

`apt-get install -f` is the step that actually resolves `Depends:` from the
Debian repos — a plain `dpkg -i` will report "dependency problems" and leave
the package unconfigured; that's expected, `apt-get install -f` fixes it in
place without reinstalling anything.

`"WatchDogsGo (beta)"` then appears on the launcher's carousel (same `(beta)`
suffix convention as the dev entry's `"WatchDogsGo (dev)"`, so testers can
tell this apart from anything else on their device). Log back out of SSH
and use the device's own keyboard from here — the game owns the keyboard and
screen while it runs (long-press Home, `fn`+K, for 5 s to quit back to the
launcher).

## 2. What works out of the box

Everything the `Depends:`/`Recommends:` list in `packaging/meta.env` covers,
all plain Debian packages:

- GPS (`/dev/ttyS0`), the keyboard, the display, the battery HUD.
- LoRa / MeshCore, if you have a Cap with an SX1262 LoRa module (`LoRaRF` is
  bundled in the package since it isn't in Debian; see `docs/hardware-notes.md`).
- WiFi/BLE wardriving from the device's own radio (no monitor mode — see
  `docs/wifi-monitor-mode.md` — but SSID/BLE scanning works unprivileged).
- 433 MHz scanning (`rtl_433`) with a NooElec NESDR SMART or similar RTL-SDR
  dongle plugged in (`rtl-sdr`/`rtl-433` are `Recommends:`, not `Depends:`,
  since the dongle is optional hardware).
- WDGWars portal sync/pairing (see `docs/portal-rules.md`).

## 3. ADS-B (dump1090) — manual step, not in the package

The ADS-B Radar needs `dump1090`, and Debian 13 (trixie) doesn't package
`dump1090` at all. Debian does package `readsb` (the maintained successor),
but **its Debian build ships without RTL-SDR support** (`RTLSDR` is off by
default upstream), so a stock `apt install readsb` can't open the dongle.

There's no way to fix this from the `.deb` alone — it needs compiling
`readsb` locally with RTL-SDR support turned on. If you want ADS-B:

```bash
sudo apt install -y --no-install-recommends \
    devscripts dpkg-dev debhelper \
    libusb-1.0-0-dev libncurses-dev zlib1g-dev zlib1g pkg-config \
    libzstd-dev libzstd1 librtlsdr0 librtlsdr-dev rtl-sdr rtl-433
sudo systemctl disable --now readsb   # its own daemon would hold the dongle
sudo systemctl mask readsb
mkdir -p /tmp/readsb-build && cd /tmp/readsb-build
dget -u https://deb.debian.org/debian/pool/main/r/readsb/readsb_3.14.1630+git20240609.adc080d-1.dsc
cd readsb-3.14.1630+git20240609.adc080d
DEB_BUILD_OPTIONS=noddebs dpkg-buildpackage -b -Prtlsdr -ui -uc -us
cd .. && sudo dpkg -i readsb_3.14.1630+git20240609.adc080d-1_arm64.deb
sudo install -m 755 /usr/share/APPLaunch/apps/watchdogsgo-cardputerzero/tools/dump1090-readsb-shim.sh /usr/local/bin/dump1090
```

Without this step: 433 MHz scanning still works; ADS-B Radar will report
"dump1090 not installed" and stay off. This is a known, documented
limitation — see `ROADMAP.md`, "SDR unlock" — not a bug in the package.

## 4. If something looks wrong

- The game logs to `~/.watchdogs/last_run.log` on the device — `tail -f` it
  while reproducing an issue.
- `~/.watchdogs/secrets.conf` holds your own WDGWars pairing key / Stadia
  tiles API key, seeded empty from `secrets.conf.example` on first run — fill
  it in yourself; the package never ships anyone else's keys.
- Please report issues against this fork
  (`https://github.com/LOCOSP/WatchDogsGo` for upstream behaviour, this
  repository for anything CardputerZero-specific).
