#!/usr/bin/env python3
"""Which Cap LoRa pin is BUSY and which is DIO1? (ROADMAP 0.7)

Run ON the CardputerZero with the Cap attached and M5's LoRa/GPS apps closed
(they hold the GPIO lines and the SPI device). RX-only: it never transmits.

Derived pin map (docs/hardware-notes.md): RST = G26 (output), and G22/G23 are
BUSY and DIO1 in some order. The probe:
  1. powers the Cap rail (ext_5v_out) if it is off,
  2. pulses RST and records edges on G22/G23 (BUSY goes high while the chip
     restarts),
  3. reads the SX126x over /dev/spidev0.1: status, version string (SX1261 vs
     SX1262) and the default LoRa sync word,
  4. arms the RxTimeout IRQ on DIO1 and starts a ~10 ms receive, so DIO1 rises
     without any RF being sent; the pin that rises ~10 ms later and falls
     after ClearIrqStatus is DIO1,
  5. puts the chip to sleep and restores G26 / the rail to how it found them.

  .venv/bin/python tools/lora-pin-probe.py
"""
import sys
import time

import gpiod
import spidev
from gpiod.line import Direction, Edge, Value

CHIP = "/dev/gpiochip0"
PIN_RST = 26
CANDIDATES = (22, 23)
RAIL = "/sys/class/leds/ext_5v_out"


def rd(path):
    with open(path) as f:
        return f.read().strip()


def wr(path, value):
    with open(path, "w") as f:
        f.write(str(value))


def drain(lines, seconds):
    events, end = [], time.monotonic() + seconds
    while True:
        left = end - time.monotonic()
        if left <= 0:
            return events
        if lines.wait_edge_events(min(left, 0.01)):
            events.extend(lines.read_edge_events())


def show(title, events, ref_ns):
    print(f"  {title}: {len(events)} edge(s)")
    for e in events:
        kind = "rise" if e.event_type == e.Type.RISING_EDGE else "fall"
        print(f"    +{(e.timestamp_ns - ref_ns) / 1e6:8.3f} ms  "
              f"G{e.line_offset} {kind}")


def spi_cmd(spi, data):
    time.sleep(0.002)          # BUSY pin is not known yet: just wait
    return spi.xfer2(list(data))


def main() -> int:
    orig_rail = int(rd(f"{RAIL}/brightness"))
    max_rail = int(rd(f"{RAIL}/max_brightness"))
    print(f"rail ext_5v_out initially {orig_rail} (max {max_rail})")
    if orig_rail == 0:
        wr(f"{RAIL}/brightness", max_rail)
        time.sleep(0.3)

    out = ins = spi = None
    try:
        out = gpiod.request_lines(CHIP, consumer="wdg-lora-probe", config={
            PIN_RST: gpiod.LineSettings(direction=Direction.OUTPUT,
                                        output_value=Value.ACTIVE)})
        ins = gpiod.request_lines(CHIP, consumer="wdg-lora-probe", config={
            p: gpiod.LineSettings(direction=Direction.INPUT,
                                  edge_detection=Edge.BOTH)
            for p in CANDIDATES})
        idle = {p: int(ins.get_value(p) == Value.ACTIVE) for p in CANDIDATES}
        print(f"idle levels: {idle}")

        spi = spidev.SpiDev()
        spi.open(0, 1)                      # /dev/spidev0.1 (CS1)
        spi.max_speed_hz = 1_000_000
        spi.mode = 0

        drain(ins, 0.01)                    # discard stale events
        print("reset pulse on G26:")
        ref = time.monotonic_ns()
        out.set_value(PIN_RST, Value.INACTIVE)
        time.sleep(0.002)
        out.set_value(PIN_RST, Value.ACTIVE)
        show("after reset", drain(ins, 0.05), ref)

        status = spi_cmd(spi, [0xC0, 0x00])[1]
        print(f"GetStatus: 0x{status:02x} (chip mode {(status >> 4) & 7}, "
              f"cmd status {(status >> 1) & 7}; mode 2 = STBY_RC)")
        ver = bytes(spi_cmd(spi, [0x1D, 0x03, 0x20, 0x00] + [0] * 16)[4:])
        print("version string:", ver.decode("ascii", "replace").strip("\x00 "))
        sync = spi_cmd(spi, [0x1D, 0x07, 0x40, 0x00, 0x00, 0x00])[4:]
        print("LoRa sync word:", "".join(f"{b:02x}" for b in sync),
              "(default 1424)")

        if "--tcxo" in sys.argv:
            # Only if the module has a TCXO fed from DIO3: 1.8 V, 5 ms
            # start-up, then recalibrate. Off by default.
            print("enabling DIO3 TCXO supply at 1.8 V (--tcxo)")
            for data in ([0x80, 0x00], [0x97, 0x02, 0x00, 0x01, 0x40],
                         [0x07, 0x00, 0x00], [0x89, 0x7F]):
                spi_cmd(spi, data)
            time.sleep(0.05)
        for data in (
            [0x80, 0x00],                                   # SetStandby RC
            [0x8A, 0x01],                                   # SetPacketType LoRa
            [0x86, 0x36, 0x40, 0x00, 0x00],                 # 868.0 MHz
            [0x8B, 0x07, 0x04, 0x01, 0x00],                 # SF7 BW125 CR4/5
            [0x8C, 0x00, 0x08, 0x00, 0xFF, 0x01, 0x00],     # packet params
            [0x08, 0x02, 0x00, 0x02, 0x00, 0, 0, 0, 0],     # IRQ: Timeout -> DIO1
            [0x02, 0xFF, 0xFF],                             # ClearIrqStatus
        ):
            spi_cmd(spi, data)
        drain(ins, 0.01)

        print("SetRx with a ~10 ms timeout (no transmission):")
        ref2 = time.monotonic_ns()
        spi_cmd(spi, [0x82, 0x00, 0x02, 0x80])
        ev_rx = drain(ins, 0.05)
        show("during/after RX window", ev_rx, ref2)
        st_after = spi_cmd(spi, [0xC0, 0x00])[1]
        errs = spi_cmd(spi, [0x17, 0x00, 0x00, 0x00])
        err_word = (errs[2] << 8) | errs[3]
        names = {0: "RC64K_CALIB", 1: "RC13M_CALIB", 2: "PLL_CALIB",
                 3: "ADC_CALIB", 4: "IMG_CALIB", 5: "XOSC_START",
                 6: "PLL_LOCK", 8: "PA_RAMP"}
        flags = [n for b, n in names.items() if err_word & (1 << b)] or ["none"]
        print(f"after SetRx: status 0x{st_after:02x} (chip mode "
              f"{(st_after >> 4) & 7}; 5 = RX, 2 = STBY_RC), device errors "
              f"0x{err_word:04x}: {', '.join(flags)}")
        irq = spi_cmd(spi, [0x12, 0x00, 0x00, 0x00])
        print(f"GetIrqStatus: 0x{irq[2]:02x}{irq[3]:02x} (0x0200 = RxTimeout)")
        ref3 = time.monotonic_ns()
        spi_cmd(spi, [0x02, 0xFF, 0xFF])
        ev_clear = drain(ins, 0.02)
        show("after ClearIrqStatus", ev_clear, ref3)

        verdict = None
        for p in CANDIDATES:
            rises = [(e.timestamp_ns - ref2) / 1e6 for e in ev_rx
                     if e.line_offset == p and e.event_type == e.Type.RISING_EDGE]
            falls = [e for e in ev_clear
                     if e.line_offset == p and e.event_type == e.Type.FALLING_EDGE]
            if any(5.0 <= r <= 25.0 for r in rises) and falls:
                verdict = p
        if verdict is None:
            print("VERDICT: inconclusive — read the edge lists above")
        else:
            other = [p for p in CANDIDATES if p != verdict][0]
            print(f"VERDICT: DIO1/IRQ = G{verdict}, BUSY = G{other}")
        spi_cmd(spi, [0x80, 0x00])
        spi_cmd(spi, [0x84, 0x00])          # SetSleep
        return 0
    finally:
        if spi is not None:
            spi.close()
        if ins is not None:
            ins.release()
        if out is not None:
            out.release()
        try:                                # G26 was an input before M5's app
            gpiod.request_lines(CHIP, consumer="wdg-lora-probe", config={
                PIN_RST: gpiod.LineSettings(direction=Direction.INPUT)
            }).release()
        except OSError as exc:
            print("WARN: could not return G26 to input:", exc)
        if orig_rail == 0:
            wr(f"{RAIL}/brightness", 0)
            print("rail restored to 0")


if __name__ == "__main__":
    sys.exit(main())
