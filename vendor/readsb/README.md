# Vendored `readsb` (RTL-SDR build)

`readsb-arm64` is `readsb` 3.14.1630+git20240609.adc080d-1 built from
**Debian's own source package** (`apt source readsb`, Debian trixie) with its
`-Prtlsdr` build profile, exactly the recipe that used to be `docs/install.md`'s
manual step:

```bash
sudo apt install -y --no-install-recommends \
    devscripts dpkg-dev debhelper \
    libusb-1.0-0-dev libncurses-dev zlib1g-dev pkg-config \
    libzstd-dev librtlsdr-dev
mkdir -p /tmp/readsb-build && cd /tmp/readsb-build
dget -u https://deb.debian.org/debian/pool/main/r/readsb/readsb_3.14.1630+git20240609.adc080d-1.dsc
cd readsb-3.14.1630+git20240609.adc080d
DEB_BUILD_OPTIONS=noddebs dpkg-buildpackage -b -Prtlsdr -ui -uc -us
```

Stock Debian omits `-Prtlsdr` (`RTLSDR` is off by default upstream), so a
plain `apt install readsb` can't open an RTL-SDR dongle — see
`docs/hardware-notes.md` / `ROADMAP.md` ("SDR unlock") for the full story.
This binary is the result of that build, stripped and copied out of the
`.deb` `dpkg-buildpackage` produces — we ship the arm64 binary directly
instead of making every install compile it (`packaging/stage.sh`).

`LICENSE` is Debian's `readsb` package's own `copyright` file (GPLv2, per
upstream https://github.com/wiedehopf/readsb). No source changes — same
build-from-source-package relationship as `pyxel`/`LoRaRF` elsewhere under
`vendor/` (bundled because Debian doesn't ship a working build, not because
we modified anything).

Re-run the recipe above (on an arm64 Debian trixie box, or the device
itself) to refresh this binary after a Debian `readsb` source update; replace
`readsb-arm64` with the new build's `/usr/bin/readsb`.
