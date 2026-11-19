#!/usr/bin/env bash
# Phase 0 inventory for the WatchDogsGo -> CardputerZero port.
#
# READ-ONLY: changes nothing on the device. Collects the facts Phase 0 of
# ROADMAP.md needs (graphics path, privilege model, GPIO/SPI/UART, USB,
# internal WiFi/BT, launcher packaging, Python deps) into one text report.
#
# Run it ON the CardputerZero (adb shell or ssh), then pull/paste the report:
#   adb push tools/phase0-probe.sh /tmp/
#   adb shell bash /tmp/phase0-probe.sh /tmp/phase0-report.txt
#   adb pull /tmp/phase0-report.txt .
#
# Usage: bash phase0-probe.sh [report-path]      (default ./phase0-report.txt)
#   PROBE_ACTIVE=1 bash phase0-probe.sh ...      also triggers ONE WiFi scan
#
# Privacy: MAC addresses are masked, the CPU serial is dropped, and nearby
# networks are only counted, never listed — reasonably safe to share.

# Non-login shells (ssh/adb) often lack the sbin dirs, where Debian puts iw,
# rfkill, swapon, ldconfig, tcpdump, wpa_cli... — don't report those missing.
export PATH="$PATH:/usr/local/sbin:/usr/sbin:/sbin"

OUT="${1:-./phase0-report.txt}"
: >"$OUT" 2>/dev/null || { echo "cannot write $OUT" >&2; exit 1; }

hdr() { printf '\n==================== %s ====================\n' "$1" >>"$OUT"; }

# probe "<label>" '<bash snippet>' — run the snippet, record output + exit
# code, never abort the script.
probe() {
  printf '\n$ %s\n' "$1" >>"$OUT"
  timeout 25 bash -c "$2" >>"$OUT" 2>&1
  local rc=$?
  [ $rc -eq 0 ] || printf '[exit %s]\n' "$rc" >>"$OUT"
}

hdr "1. System"
probe "uname -a" 'uname -a'
probe "os-release" 'cat /etc/os-release'
probe "device-tree model" 'tr -d "\0" </proc/device-tree/model; echo'
probe "cpu" 'grep -m1 "model name" /proc/cpuinfo; grep -m1 -i "^hardware" /proc/cpuinfo; echo "cores: $(nproc)"; cat /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq 2>/dev/null'
probe "memory / swap / disk" 'free -m; swapon --show; df -h / /home 2>/dev/null'
probe "user / privileges" 'id; echo -n "passwordless sudo: "; sudo -n true 2>/dev/null && echo yes || echo no'
probe "python / pip / systemd" 'python3 --version; python3 -m pip --version; systemctl --version | head -1'
probe "temperature / throttling" 'vcgencmd measure_temp; vcgencmd get_throttled'

hdr "2. Graphics path (ROADMAP 0.1)"
probe "framebuffer / DRM nodes" 'ls -l /dev/fb* /dev/dri/* 2>&1'
probe "fb0 info" 'for f in name virtual_size bits_per_pixel stride; do printf "%s: " $f; cat /sys/class/graphics/fb0/$f 2>&1; done'
probe "DRM connectors" 'for c in /sys/class/drm/*/; do echo "$c $(cat $c/status 2>/dev/null) $(head -1 $c/modes 2>/dev/null)"; done'
probe "session type" 'echo "XDG_SESSION_TYPE=$XDG_SESSION_TYPE DISPLAY=$DISPLAY WAYLAND_DISPLAY=$WAYLAND_DISPLAY"'
probe "display-server / launcher processes" "ps -eo pid,user,args | grep -iE 'Xorg|Xwayland|weston|cage|sway|APPLaunch|launcher|lvgl|cardputer|m5' | grep -v grep"
probe "graphics libs" "ldconfig -p | grep -E 'libSDL2|libEGL|libGLES|libdrm|libgbm|libts'"

hdr "3. Launcher / app packaging (ROADMAP 3.x)"
probe "APPLaunch tree" 'ls -laR /usr/share/APPLaunch 2>&1 | head -80'
probe "installed .desktop entries (first 5)" 'for f in $(ls /usr/share/APPLaunch/applications/*.desktop 2>/dev/null | head -5); do echo "--- $f"; cat "$f"; done'
probe "units mentioning APPLaunch/cardputer/m5stack" 'grep -rlsiE "APPLaunch|cardputer|m5stack" /lib/systemd/system /etc/systemd/system 2>/dev/null | head -10'
probe "first matching unit" 'u=$(grep -rlsiE "APPLaunch|cardputer|m5stack" /lib/systemd/system /etc/systemd/system 2>/dev/null | head -1); [ -n "$u" ] && { echo "--- $u"; cat "$u"; }'
probe "running services (filtered)" 'systemctl list-units --type=service --state=running --no-pager | grep -iE "launch|cardputer|m5|app|display|ssh|adb|bluetooth|network|wpa"'
probe "m5 / cardputer packages" 'dpkg -l 2>/dev/null | grep -iE "m5|cardputer|applaunch|czdev|lvgl"'
probe "adbd" 'ps -eo pid,user,args | grep -i adbd | grep -v grep'

hdr "4. Input (ROADMAP 1.3)"
probe "input devices" 'cat /proc/bus/input/devices'
probe "input nodes" 'ls -l /dev/input/ 2>&1'

hdr "5. Internal WiFi / BT (ROADMAP 0.9)"
probe "net links (names + state only)" 'ip -br link | awk "{print \$1, \$2}"'
probe "wireless interfaces" 'iw dev | grep -vE "addr|ssid"'
probe "wiphy: bands + supported interface modes (is monitor listed?)" 'iw phy | sed -n "/Supported interface modes:/,/Band 1:/p" | head -25; iw phy | grep -E "^\s+Band [0-9]+:"'
probe "wifi/bt kernel modules" 'lsmod | grep -iE "brcm|cfg80211|bluetooth|hci|btbcm"'
probe "kernel log: wifi/bt (may need root)" 'dmesg 2>&1 | grep -iE "brcm|wlan|bluetooth|hci0|btbcm" | tail -30'
probe "brcm firmware files" 'ls /lib/firmware/brcm 2>/dev/null | head -30'
probe "bluetooth adapters" 'ls /sys/class/bluetooth 2>&1; hciconfig -a 2>&1 | grep -vE "BD Address"; bluetoothctl list 2>&1 | sed -E "s/Controller [0-9A-F:]+/Controller <mac>/"'
probe "rfkill" 'rfkill list 2>&1'
probe "network services" 'for s in NetworkManager wpa_supplicant bluetooth dhcpcd systemd-networkd; do printf "%s: " $s; systemctl is-active $s 2>&1; done'
probe "default-route interface" 'ip route show default | awk "{print \$5}"'
probe "cached WiFi scan, BSS count (no scan triggered)" 'iw dev wlan0 scan dump 2>&1 | grep -c "^BSS"'
if [ "${PROBE_ACTIVE:-0}" = "1" ]; then
  probe "ACTIVE: triggered WiFi scan (denied if non-root without CAP_NET_ADMIN)" "iw dev wlan0 scan 2>&1 | awk '/^BSS/{n++} /denied|not permitted|busy/{print} END{print \"BSS seen:\", n+0}'"
fi

hdr "6. GPIO / SPI / UART / I2C (ROADMAP 0.3, 0.7)"
probe "device nodes" 'ls -l /dev/gpiochip* /dev/spidev* /dev/i2c-* /dev/ttyAMA* /dev/ttyS* /dev/serial* 2>&1'
probe "group membership" 'id -nG'
probe "gpiod chips" 'gpiodetect 2>&1; gpioinfo 2>&1 | head -80'
probe "pinctrl (pin states: evidence for the Cap-Bus mapping)" 'pinctrl get 2>&1 | head -80'
probe "boot config (overlays, uart, spi)" 'for f in /boot/firmware/config.txt /boot/config.txt; do [ -f $f ] && { echo "--- $f"; grep -vE "^\s*(#|$)" $f; }; done'
probe "loaded dt overlays" 'dtoverlay -l 2>&1'
probe "python gpio/bus libs" 'for m in lgpio RPi.GPIO gpiod spidev serial smbus2; do if out=$(python3 -I -c "import $m;print(\"$m OK\", getattr($m,\"__version__\",\"\"))" 2>/dev/null); then echo "$out"; else echo "$m MISSING"; fi; done'

hdr "7. USB peripherals (ROADMAP 0.5, 0.6)"
probe "lsusb" 'lsusb 2>&1'
probe "lsusb tree" 'lsusb -t 2>&1'
probe "usb-serial nodes" 'ls -l /dev/ttyUSB* /dev/ttyACM* 2>&1'
probe "RTL-SDR kernel module bound? (dvb_usb_rtl28xxu must be blacklisted)" 'lsmod | grep -iE "dvb_usb_rtl28xxu|rtl2832|rtl2830|dvb_usb_v2"; ls /etc/modprobe.d/ 2>/dev/null | grep -i rtl'
probe "radio / network tools" 'for t in rtl_test rtl_433 dump1090 dump1090-fa iw tcpdump aircrack-ng nmcli wpa_cli esptool pinctrl gpioinfo hciconfig bluetoothctl; do printf "%-14s " $t; command -v $t || echo MISSING; done'

hdr "8. Python dependencies (ROADMAP 0.2)"
probe "imports" 'for m in pyxel serial PIL scapy netifaces bleak dbus gi LoRaRF cryptography nacl requests; do if out=$(python3 -I -c "import $m;print(\"$m OK\", getattr($m,\"__version__\",\"\"))" 2>/dev/null | tail -1); [ -n "$out" ]; then echo "$out"; else echo "$m MISSING"; fi; done'

hdr "9. Power"
probe "power supplies" 'for d in /sys/class/power_supply/*; do echo "--- $d"; grep -v SERIAL $d/uevent 2>/dev/null; done'

# Mask MAC addresses everywhere in the report.
sed -i -E 's/([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}/xx:xx:xx:xx:xx:xx/g' "$OUT"
echo "Report written to $OUT ($(wc -l <"$OUT") lines)"
