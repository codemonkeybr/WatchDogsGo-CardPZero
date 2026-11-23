# Internal WiFi monitor mode — why we don't have it, and what might change that

Status: **not available today**, open to revisit later (see `ROADMAP.md` 2.8
for the related "explicit radio-source override" task). Written 2026-11-20
after the owner asked why their Pwnagotchi (Raspberry Pi Zero 2 W) gets
monitor mode on its internal WiFi but the CardputerZero doesn't, despite both
boards using Broadcom/Cypress chips on similar Raspberry Pi compute silicon.

## The chip, not the SoC, is the limiting factor

`docs/hardware-notes.md` already measured the CardputerZero's internal radio:

```
wlan0 managed on phy#0, driver brcmfmac + brcmfmac_cyw,
firmware brcmfmac43439-sdio (BCM43439/5, v7.95.75)
iw phy supported modes: IBSS, managed, AP, P2P-client, P2P-GO, P2P-device
— no monitor — single band (2.4 GHz)
```

The CardputerZero's compute module (CM0, RP3A0/BCM2837) is the same lineage
of silicon as a Raspberry Pi Zero 2 W — but the WiFi radio is a separate chip
wired to it, and it's not the same part:

| Board | WiFi chip | nexmon support for Linux (`brcmfmac`) |
|---|---|---|
| Raspberry Pi Zero 2 W (the Pwnagotchi's board) | **bcm43436b0** | ✅ monitor mode + radiotap + injection, firmware `9_88_4_65`, Raspberry Pi OS kernel 5.10 |
| Raspberry Pi 3 / Zero W (1st gen) | bcm43430a1 | ✅ |
| Raspberry Pi 3B+ / 4 | bcm43455c0 | ✅ |
| **CardputerZero** | **bcm43439** | ❌ for Linux — nexmon's only `bcm43439a0` entry (firmware `7_95_49`) targets the **Raspberry Pi Pico W's own SDK** (a microcontroller build, not `brcmfmac`/Raspberry Pi OS at all) |

Source: the official supported-devices table in
[seemoo-lab/nexmon's README](https://github.com/seemoo-lab/nexmon) (fetched
2026-11-20). Pwnagotchi's internal-WiFi monitor mode on a Pi Zero 2 W works
*because* nexmon ships a driver-level patch for that exact chip revision,
not because the Zero 2 W's CPU is special. The CardputerZero happens to carry
a newer/different chip revision (`43439` vs `43436b0`) that nobody has
published a Raspberry Pi OS nexmon patch for yet.

## What this means for us

- This is **not** a CM0/RP3A0 hardware ceiling — it's a firmware-patch
  availability gap for one specific Broadcom/Cypress part.
- The internal `wlan0`'s `iw phy` capability list (`IBSS, managed, AP,
  P2P-*` — no `monitor`) reflects the *stock* firmware blob. A nexmon-style
  patch replaces that blob with one that adds real 802.11 monitor-mode
  frames + radiotap + (on fully-supported chips) injection — it isn't
  something `iw`/`cfg80211` can be talked into doing against the unpatched
  firmware.
- Today, wardriving/deauth-class features on this device that need monitor
  mode or injection have to come from the ESP32 or an external
  monitor-capable USB adapter — the internal
  radio stays managed-mode-only (WiFi/BLE *wardriving*, no sniffer/deauth/
  Evil Twin/SAE flood).

## Possible future directions (not started)

- Check whether `bcm43439` ever gets an upstream nexmon patch (watch
  [seemoo-lab/nexmon](https://github.com/seemoo-lab/nexmon) releases/issues).
- See whether the CardputerZero's board uses the exact same silicon stepping
  as a chip nexmon *does* support under a different firmware filename (some
  Broadcom parts are relabeled across board revisions) — would need pulling
  the chip's exact part marking/datasheet, not just the SDIO firmware name
  Linux loads.
- Porting/writing a new nexmon patch ourselves is plausible in principle
  (nexmon is an open framework precisely for this) but is a real reverse-
  engineering project on someone else's firmware blob, not a quick port —
  scope it properly before committing to it.
- In the meantime, an external USB WiFi adapter with known monitor-mode
  support (same family of adapters already used on uConsole-style setups)
  remains the practical path if real monitor-mode/injection features are
  wanted on this device.
