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
- 433 MHz scanning (`rtl_433`) and ADS-B (`readsb`, bundled with RTL-SDR
  support — see §3) with a NooElec NESDR SMART or similar RTL-SDR dongle
  plugged in (`rtl-sdr`/`rtl-433` are `Recommends:`, not `Depends:`, since
  the dongle is optional hardware).
- WDGWars portal sync/pairing (see `docs/portal-rules.md`).

## 3. ADS-B (dump1090)

Works out of the box — no manual step. Debian's own `readsb` package ships
without RTL-SDR support, so the package bundles its own build of `readsb`
(compiled with RTL-SDR enabled, `vendor/readsb/README.md`) and wires it onto
`PATH` as `dump1090` automatically (`packaging/postinst`), which is what
`watchdogs/sdr_manager.py` looks for. Plug in an RTL-SDR dongle (a NooElec
NESDR SMART or similar) and the ADS-B Radar screen just works.

## 4. If something looks wrong

- The game logs to `~/.watchdogs/last_run.log` on the device — `tail -f` it
  while reproducing an issue.
- `~/.watchdogs/secrets.conf` holds your own WDGWars pairing key / Stadia
  tiles API key, seeded empty from `secrets.conf.example` on first run — fill
  it in yourself; the package never ships anyone else's keys.
- Please report issues against this fork
  (`https://github.com/LOCOSP/WatchDogsGo` for upstream behaviour, this
  repository for anything CardputerZero-specific).
