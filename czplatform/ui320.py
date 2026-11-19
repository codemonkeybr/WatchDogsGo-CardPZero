"""Compact drawing for the 320x170 panel (ROADMAP 1.2, docs/ui-adaptation.md).

Replacement draw methods for ``watchdogs.app.WatchDogsGame``, installed by
``install()`` only when the 320x170 canvas profile is used; the vendored file
stays untouched and the original 640x360 layout keeps working. Each method reads
the same game state as the original — same palette, same Spleen 5x8 font at its
native size, same widgets — and only re-budgets the space:

* HUD top    10 px  level / XP bar / hat / earned badges ... zoom / battery
* HUD bottom 10 px  loot counters ... tools / LoRa / GPS (key hints moved to help)
* terminal   10 px  a one-line ticker with the newest log entry; ENTER switches
                    to a full-screen log (and back)

Widths are computed from the actual strings (5 px per glyph) so nothing overlaps.
"""
from __future__ import annotations

import logging
import struct
from pathlib import Path

import pyxel

log = logging.getLogger("czplatform.ui")

CW = 5                      # Spleen 5x8 glyph advance


def _app():
    from watchdogs import app
    return app


# ---------------------------------------------------------------------------
# HUD top
# ---------------------------------------------------------------------------

_BADGE_HUD = (
    ("flipper", "FLP", "C_WARNING"), ("wardriver", "WDR", "C_SUCCESS"),
    ("meshcore", "MSH", 2), ("handshake_hunter", "HS", "C_ERROR"),
    ("wpasec_uploader", "WPA", 12), ("evil_twin", "ET", 8),
    ("skywatch", "ADB", "C_HACK_CYAN"), ("iot_hunter", "433", 12),
)


def draw_hud_top(self):
    A = _app()
    ty = 1
    pyxel.rect(0, 0, A.W, A.HUD_TOP, A.C_HUD_BG)
    pyxel.line(0, A.HUD_TOP - 1, A.W - 1, A.HUD_TOP - 1, A.C_HUD_LINE)

    # right side first, so the left side knows how much room it has
    zoom = f"Z:{self.proj.label}"
    bat = self._battery_pct
    right_w = len(zoom) * CW + 3
    bat_txt, bat_col = "", A.C_DIM
    if bat >= 0:
        bat_txt = f"BAT:{bat}%"
        bat_col = A.C_SUCCESS if bat > 25 else (A.C_WARNING if bat > 10 else A.C_ERROR)
        right_w += len(bat_txt) * CW + 5
    right_x = A.W - right_w
    pyxel.text(right_x, ty, zoom, A.C_DIM)
    if bat_txt:
        pyxel.text(right_x + len(zoom) * CW + 5, ty, bat_txt, bat_col)

    limit = right_x - 4
    x = 3
    lv = f"LV:{self.level}"
    pyxel.text(x, ty, lv, A.C_SUCCESS)
    x += len(lv) * CW + 4
    title = self.level_title
    pyxel.text(x, ty, title, A.C_SUCCESS)
    x += len(title) * CW + 4

    xw = 30                                         # XP bar
    nxt, cur = self.xp_for_next_level, self.xp_in_current_level
    xf = int(xw * cur / nxt) if nxt > 0 else xw
    pyxel.rect(x, ty + 1, xw, 6, A.C_GRID)
    pyxel.rect(x, ty + 1, xf, 6, A.C_HACK_CYAN)
    pyxel.rectb(x, ty + 1, xw, 6, A.C_COAST)
    x += xw + 3
    xp = f"{self.xp}"
    pyxel.text(x, ty, xp, A.C_DIM)
    x += len(xp) * CW + 4

    hat_name, hat_color = self._get_hat_profile()   # hat badge
    if x + 9 + len(hat_name) * CW < limit:
        pyxel.circ(x + 3, A.HUD_TOP // 2, 3, 7)
        pyxel.circ(x + 3, A.HUD_TOP // 2, 2, hat_color)
        x += 9
        pyxel.text(x, ty, hat_name, A.C_DIM)
        x += len(hat_name) * CW + 3

    for badge_id, label, color in _BADGE_HUD:      # earned badges, if they fit
        if badge_id not in self._badges:
            continue
        col = getattr(A, color) if isinstance(color, str) else color
        lw = len(label) * CW + 3
        if x + lw > limit:
            break
        pyxel.rectb(x, 0, lw, A.HUD_TOP - 1, col)
        pyxel.text(x + 2, ty, label, col)
        x += lw + 2


# ---------------------------------------------------------------------------
# HUD bottom
# ---------------------------------------------------------------------------

def draw_hud_bottom(self):
    A = _app()
    y = A.H - A.HUD_BOT + 1
    pyxel.rect(0, A.H - A.HUD_BOT, A.W, A.HUD_BOT, A.C_HUD_BG)
    pyxel.line(0, A.H - A.HUD_BOT, A.W - 1, A.H - A.HUD_BOT, A.C_HUD_LINE)

    t_bt = self._loot_totals.get("bt", 0) + len(self.ble_devices)
    t_wifi = self._loot_totals.get("wifi", 0) + len(self.wifi_networks)
    t_hs = (self._loot_totals.get("hs", 0)
            + sum(1 for m in self.markers if m.type == "handshake"))
    n_pwn = (sum(1 for d in self.ble_devices if d.hacked)
             + sum(1 for n in self.wifi_networks if n.hacked))
    t_pwd = (self._loot_totals.get("passwords", 0)
             + self._loot_totals.get("et_captures", 0)
             + self.state.submitted_forms
             + len(self.state.evil_twin_captured_data))

    # right side: GPS, LoRa, active tools — built right to left
    if self.gps_fix:
        gps, gcol = "GPS:OK", A.C_SUCCESS
    elif self.gps.available:
        if self.gps_sats_vis > 0:
            gps, gcol = f"GPS:{self.gps_sats_vis}sat", A.C_WARNING
        else:
            gps, gcol = "GPS:...", A.C_ERROR
    else:
        gps, gcol = "GPS:--", A.C_DIM
    right = [(gps, gcol)]
    if self._lora.running:
        right.append((f"LoRa:{self._lora.packets_received}", A.C_SUCCESS))
    elif self._lora_enabled:
        right.append(("LoRa:idle", A.C_WARNING))
    tools = []
    if self.wifi_scanning:
        tools.append("WiFi")
    if self.ble_scanning:
        tools.append("BT")
    if self.sniffing:
        tools.append("SNF")
    if self.capturing_hs:
        tools.append("HS")
    if self.state.portal_running:
        tools.append("EP")
    if self.state.evil_twin_running:
        tools.append("ET")
    if self._sdr.running and "adsb" in self._sdr.mode:
        n_pos = sum(1 for a in self._sdr.aircraft.values() if a.has_position)
        tools.append(f"ADS-B:{n_pos}/{len(self._sdr.aircraft)}")
    if self._sdr.running and "433" in self._sdr.mode:
        tools.append(f"433:{self._sdr.total_sensors_seen}")
    if tools:
        right.append((" ".join(tools) + "." * ((pyxel.frame_count // 10) % 4), 12))

    # left side: loot counters, shortened only if the right side needs the room
    counters = ((f"BLE:{t_bt}", A.C_HACK_CYAN), (f"WiFi:{t_wifi}", A.C_WARNING),
                (f"HS:{t_hs}", A.C_ERROR), (f"PWD:{t_pwd}", 12),
                (f"PWN:{n_pwn}", A.C_SUCCESS))
    left_w = sum(len(t) * CW for t, _ in counters) + 5 * (len(counters) - 1) + 4
    x_right = A.W - 3
    drawn = []
    for text, col in right:                         # most important first
        w = len(text) * CW
        if x_right - w - 5 < left_w:
            break
        x_right -= w
        drawn.append((x_right, text, col))
        x_right -= 5
    for xr, text, col in drawn:
        pyxel.text(xr, y, text, col)

    x = 3
    for text, col in counters:
        pyxel.text(x, y, text, col)
        x += len(text) * CW + 5


# ---------------------------------------------------------------------------
# Terminal: a 3-line ticker
# ---------------------------------------------------------------------------

def _tool_name(self):
    if self.capturing_hs:
        return "HANDSHAKE"
    if self.wifi_scanning or self._wifi_scan_only:
        return "WiFi SCAN"
    if self.ble_scanning or self._ble_scan_only:
        return "BT SCAN"
    if self._bt_airtag:
        return "TAG SCAN"
    if self._bt_tracking:
        return "BT TRACK"
    if self.sniffing:
        return "SNIFFER"
    if self._mitm.running:
        return f"MITM [{self._mitm.packets}pkt]"
    if self._dragon_drain.running:
        return "DRAGON DRAIN"
    if self.state.portal_running:
        return f"EVIL PORTAL [{self.state.submitted_forms}cap]"
    if self.state.evil_twin_running:
        return f"EVIL TWIN [{len(self.state.evil_twin_captured_data)}cap]"
    return ""


# The map gets (almost) the whole screen and its last line is a ticker showing
# the newest log entry. ENTER (OK) switches to a full-screen log and back; the
# switch only happens while the map is what is on screen.

LOG_LINE_H = 9
_GAME = [None]                  # the running game instance, for input_filter


def log_rows(h, hud_top, hud_bot):
    """How many log lines fit in the full-screen view (under a title row)."""
    return max(1, (h - hud_bot - (hud_top + 12) - 1) // LOG_LINE_H)


def clamp_scroll(scroll, total, rows):
    return max(0, min(scroll, max(0, total - rows)))


def log_window(total, scroll, rows):
    """[start, end) of the lines to show, newest at the bottom; ``scroll`` is
    how many lines the view is scrolled up from the newest one."""
    scroll = clamp_scroll(scroll, total, rows)
    end = total - scroll
    return max(0, end - rows), end


def _line_color(self, lines, colors, i, default):
    return colors[i] if len(colors) == len(lines) else default


def _draw_ticker(self):
    A = _app()
    pyxel.rect(0, A.TERM_Y, A.W, A.TERM_H, 0)
    pyxel.line(0, A.TERM_Y, A.W - 1, A.TERM_Y, A.C_MENU_BORDER)
    with self._term_lock:
        lines = list(self.terminal_lines[-1:])
        colors = list(self._terminal_colors[-1:])
    if lines:
        pyxel.text(4, A.TERM_Y + 1, lines[0][:(A.W - 8) // CW],
                   colors[0] if colors else A.C_TEXT)


def _draw_log(self):
    A = _app()
    top = A.HUD_TOP
    pyxel.rect(0, top, A.W, A.H - A.HUD_BOT - top, 0)
    with self._term_lock:
        lines = list(self.terminal_lines)
        colors = list(self._terminal_colors)
    total = len(lines)
    rows = log_rows(A.H, A.HUD_TOP, A.HUD_BOT)

    pyxel.text(4, top + 1, "> OUTPUT", A.C_HACK_CYAN)
    right = f"L:{total}"
    pyxel.text(A.W - len(right) * CW - 4, top + 1, right, A.C_DIM)
    status = (f"SCROLL +{self.term_scroll}" if self.term_scroll > 0
              else _tool_name(self))
    if status:
        pyxel.text(A.W - (len(right) + len(status) + 2) * CW - 4, top + 1, status,
                   A.C_DIM if self.term_scroll > 0 else A.C_WARNING)
    pyxel.line(0, top + 10, A.W - 1, top + 10, A.C_MENU_BORDER)

    start, end = log_window(total, self.term_scroll, rows)
    y = top + 12
    for i in range(start, end):
        pyxel.text(4, y, lines[i][:(A.W - 8) // CW],
                   _line_color(self, lines, colors, i, A.C_TEXT))
        y += LOG_LINE_H
    if self.term_scroll == 0 and pyxel.frame_count % 30 < 20:
        pyxel.text(4, min(y, A.H - A.HUD_BOT - LOG_LINE_H), "_", A.C_HACK_CYAN)


def draw_terminal(self):
    self._cz_map_frame = pyxel.frame_count      # the map branch is on screen
    if getattr(self, "_cz_view", "map") == "log":
        _draw_log(self)
    else:
        _draw_ticker(self)


def _map_is_idle(self):
    """True when the map is the active screen and nothing modal is open."""
    on_screen = getattr(self, "_cz_map_frame", -99) >= pyxel.frame_count - 2
    return bool(on_screen and not self.menu_open
                and not getattr(self, "input_mode", False)
                and not getattr(self, "confirm_quit", False)
                and not getattr(self, "_boot_phase", False)
                and not getattr(self, "_attack_mode", "")
                and not getattr(self, "_gps_wait_dialog", False))


def _update_view(self):
    """Run before the game's own update: ENTER toggles map <-> log."""
    _GAME[0] = self
    view = getattr(self, "_cz_view", "map")
    idle = _map_is_idle(self)
    if view == "log" and not idle:
        view = "map"                              # the menu or another screen took over
    if idle and pyxel.btnp(pyxel.KEY_RETURN):
        view = "log" if view == "map" else "map"
        if view == "map":
            self.term_scroll = 0                  # the ticker shows the newest
    if view != getattr(self, "_cz_view", "map"):
        log.info("view: %s -> %s", getattr(self, "_cz_view", "map"), view)
    self._cz_view = view


def scroll_log(game, code):
    """Handle one scroll key in the log view; returns True if it was one."""
    A = _app()
    rows = log_rows(A.H, A.HUD_TOP, A.HUD_BOT)
    with game._term_lock:
        total = len(game.terminal_lines)
    s = game.term_scroll
    if code == 103:                               # UP
        s += 1
    elif code == 108:                             # DOWN
        s -= 1
    elif code == 104:                             # PAGEUP
        s += rows - 1
    elif code == 109:                             # PAGEDOWN
        s -= rows - 1
    elif code == 107:                             # END: back to the newest
        s = 0
    elif code == 102:                             # HOME: the oldest
        s = total
    else:
        return False
    game.term_scroll = clamp_scroll(s, total, rows)
    return True


def input_filter(code, value):
    """Installed on the keyboard injector. In the log view the scroll keys, the
    arrows and ESC belong to the log, so they never reach the game (which would
    pan the map or ask to quit). Returns True when the event was consumed."""
    game = _GAME[0]
    if game is None or getattr(game, "_cz_view", "map") != "log":
        return False
    if code == 1:                                 # ESC: back to the map
        if value == 1:
            game._cz_view = "map"
            game.term_scroll = 0
        return True
    if code in (105, 106):                        # LEFT/RIGHT: swallow, no pan
        return True
    if code in (102, 103, 104, 107, 108, 109):
        if value in (1, 2):                       # press and auto-repeat
            scroll_log(game, code)
        return True
    return False


# ---------------------------------------------------------------------------
# Sprites: half-size art from assets/cz/ (tools/make-sprites.py)
# ---------------------------------------------------------------------------

def _png_size(path):
    with open(path, "rb") as f:
        head = f.read(24)
    return struct.unpack(">II", head[16:24])


def load_hacker_sprite(self):
    """Replacement for the game's loader: loads the pre-made 85x128 sprites
    (no Pillow conversion of the 848x1264 sources at every start)."""
    A = _app()
    art = Path(A.__file__).resolve().parent.parent / "assets" / "cz"
    self._hacker_sprite_ok = False
    main = art / "hacker_sprite.png"
    if main.exists():
        try:
            pyxel.images[1].load(0, 0, str(main))
            self._hacker_w, self._hacker_h = _png_size(main)
            self._hacker_sprite_ok = True
        except Exception:
            self._hacker_sprite_ok = False
    for tab, name in enumerate(("scan", "sniff", "attack", "addons", "hacker")):
        path = art / f"{name}_sprite.png"
        if path.exists():
            self._menu_sprites[tab] = str(path)
    self._current_menu_sprite = 4
    self._radio_sprite_ok = False
    self._radio_w, self._radio_h = 16, 24
    radio = art / "radio_sprite.png"
    if radio.exists():
        try:
            pyxel.images[2].load(0, 0, str(radio))
            self._radio_w, self._radio_h = _png_size(radio)
            self._radio_sprite_ok = True
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Menu: tabs + list on the left, the tab's character and a speech bubble on the right
# ---------------------------------------------------------------------------

MENU_PX, MENU_PW = 3, 214           # list panel: x and width
TAB_H, ROW_H = 11, 11

_NOT_AN_ATTACK = ("_stop_all", "_reboot", "_dl_map", "_gps_toggle",
                  "_lora_toggle", "_sdr_toggle", "_usb_toggle", "_wl_screen",
                  "_wpasec_up", "_wpasec_dl", "_flash_esp", "_bt_hid_wip",
                  "_bd_wip", "_race_wip")


def draw_menu(self):
    A = _app()
    for y in range(A.HUD_TOP, A.TERM_Y):            # dim the map behind the menu
        if y % 2 == 0:
            pyxel.line(0, y, A.W - 1, y, 0)

    px, pw = MENU_PX, MENU_PW
    tab_y = A.HUD_TOP + 2
    cat_w = pw // len(A.MENU_CATS)
    for i, (cat_name, _items) in enumerate(A.MENU_CATS):
        tx = px + i * cat_w
        if i == self.menu_cat:
            pyxel.rect(tx, tab_y - 1, cat_w - 1, TAB_H, A.C_HACK_CYAN)
            pyxel.text(tx + 3, tab_y + 1, cat_name[:6], 0)
        else:
            pyxel.rectb(tx, tab_y - 1, cat_w - 1, TAB_H, A.C_COAST)
            pyxel.text(tx + 3, tab_y + 1, cat_name[:6], A.C_DIM)

    _, items = A.MENU_CATS[self.menu_cat]
    iy = tab_y + TAB_H + 2
    hint_y = A.TERM_Y - 10
    max_vis = (hint_y - iy) // ROW_H
    first = 0 if self.menu_sel < max_vis else self.menu_sel - max_vis + 1
    for row, idx in enumerate(range(first, min(len(items), first + max_vis))):
        hotkey, label, cmd, state_key, input_type = items[idx]
        ty = iy + row * ROW_H
        sel = idx == self.menu_sel
        running = self._is_running(state_key)
        is_stop = state_key == "_stop_all"
        is_na = (cmd.startswith("_") and state_key not in _NOT_AN_ATTACK
                 and not state_key.startswith("_p_"))
        if sel:
            pyxel.rect(px, ty - 1, pw, ROW_H, A.C_ERROR if is_stop else A.C_HACK_CYAN)
            pyxel.rectb(px, ty - 1, pw, ROW_H, A.C_TEXT)
            tc = 0
        else:
            bc = A.C_ERROR if is_stop else (A.C_COAST if is_na else A.C_MENU_BORDER)
            pyxel.rectb(px, ty - 1, pw, ROW_H, bc)
            tc = A.C_ERROR if is_stop else (A.C_DIM if is_na else A.C_TEXT)
        pyxel.text(px + 4, ty + 1, f"[{hotkey}] {label}", tc)
        if state_key in A._NEEDS_EXT_WIFI:
            wx = px + pw - 32
            pyxel.tri(wx, ty + 8, wx + 4, ty, wx + 8, ty + 8, A.C_ERROR)
            pyxel.text(wx + 3, ty + 1, "!", 0)
        if running:
            pyxel.text(px + pw - 18, ty + 1, "ON", A.C_SUCCESS if not sel else 0)
        if input_type:
            pyxel.text(px + pw - 8, ty + 1, ">", A.C_DIM if not sel else 0)

    if len(items) > max_vis:                         # scroll bar
        track = max_vis * ROW_H
        thumb = max(4, track * max_vis // len(items))
        top = iy - 1 + (track - thumb) * first // (len(items) - max_vis)
        pyxel.rect(px + pw + 2, iy - 1, 2, track, A.C_GRID)
        pyxel.rect(px + pw + 2, top, 2, thumb, A.C_HACK_CYAN)

    if self.menu_sel < len(items) and items[self.menu_sel][3] in A._NEEDS_EXT_WIFI:
        pyxel.text(px + 1, hint_y, "! Needs an external WiFi adapter", A.C_WARNING)
    else:
        pyxel.text(px + 1, hint_y, "arrows(fn)  ENTER  TAB", A.C_DIM)

    sx = px + pw + 8                                 # status, top of the right column
    pyxel.text(sx, A.HUD_TOP + 2, "ESP32:", A.C_DIM)
    pyxel.text(sx + 6 * CW, A.HUD_TOP + 2, "OK" if self._esp32 else "OFFLINE",
               A.C_SUCCESS if self._esp32 else A.C_ERROR)
    pyxel.text(sx, A.HUD_TOP + 11, f"// {A.MENU_CATS[self.menu_cat][0]}",
               A.C_HACK_CYAN)


def draw_menu_hacker(self):
    """The tab's character at half scale + a speech bubble, over the dimmed menu."""
    A = _app()
    target = self.menu_cat
    if target != self._current_menu_sprite:          # swap the art with the tab
        path = self._menu_sprites.get(target) or self._menu_sprites.get(4)
        if path:
            try:
                pyxel.images[1].load(0, 0, path)
                self._current_menu_sprite = target if target in self._menu_sprites else 4
            except Exception:
                pass

    col_x = MENU_PX + MENU_PW + 6
    col_w = A.W - col_x - 3
    feet_y = A.H - A.HUD_BOT                         # stands on the bottom HUD
    if self._hacker_sprite_ok and self._hacker_w > 0:
        sx = col_x + (col_w - self._hacker_w) // 2
        sy = feet_y - self._hacker_h
        top = max(sy, A.HUD_TOP)
        pyxel.rect(sx, top, self._hacker_w, feet_y - top, 0)   # hide the scanlines
        pyxel.blt(sx, sy, 1, 0, 0, self._hacker_w, self._hacker_h, 0)
        cx, by = sx + self._hacker_w // 2, sy + self._hacker_h // 3
    else:
        cx, by = col_x + col_w // 2, feet_y - 70
        pyxel.rect(cx - 6, feet_y - 50, 12, 50, 1)
        pyxel.circ(cx, feet_y - 56, 6, 1)

    quips = A.HACKER_QUIPS[self.menu_cat % len(A.HACKER_QUIPS)]
    quip = quips[(pyxel.frame_count // 90) % len(quips)].upper()
    qw, qh = len(quip) * CW + 10, 14
    qx = max(col_x - 2, min(cx - qw // 2, A.W - qw - 2))
    qy = by
    pyxel.rect(qx + 2, qy, qw - 4, qh, 0)            # body, rounded corners
    pyxel.rect(qx, qy + 2, qw, qh - 4, 0)
    pyxel.rect(qx + 1, qy + 1, qw - 2, qh - 2, 0)
    c = A.C_HACK_CYAN
    pyxel.line(qx + 3, qy, qx + qw - 4, qy, c)
    pyxel.line(qx + 3, qy + qh - 1, qx + qw - 4, qy + qh - 1, c)
    pyxel.line(qx, qy + 3, qx, qy + qh - 4, c)
    pyxel.line(qx + qw - 1, qy + 3, qx + qw - 1, qy + qh - 4, c)
    for dx, dy in ((1, 1), (2, 1), (1, 2), (qw - 2, 1), (qw - 3, 1), (qw - 2, 2),
                   (1, qh - 2), (2, qh - 2), (1, qh - 3), (qw - 2, qh - 2),
                   (qw - 3, qh - 2), (qw - 2, qh - 3)):
        pyxel.pset(qx + dx, qy + dy, c)
    pyxel.line(cx - 3, qy, cx, qy - 4, c)            # tail, pointing up at the face
    pyxel.line(cx + 3, qy, cx, qy - 4, c)
    pyxel.text(qx + (qw - len(quip) * CW) // 2, qy + (qh - 8) // 2, quip, c)


def _in_log(game):
    return getattr(game, "_cz_view", "map") == "log"


def _hide_when(original, hide):
    """Wrap a draw method so it is skipped while ``hide(game)`` is true."""
    def wrapper(self):
        if not hide(self):
            original(self)
    return wrapper


def install():
    """Swap the compact drawing methods into the game class."""
    G = _app().WatchDogsGame
    G._draw_hud_top = draw_hud_top
    G._draw_hud_bottom = draw_hud_bottom
    G._draw_terminal = draw_terminal
    G._draw_menu = draw_menu
    G._draw_menu_hacker = draw_menu_hacker
    G._load_hacker_sprite = load_hacker_sprite

    # the map's toasts overlap the menu hint and the log; the radar is the map's
    G._draw_messages = _hide_when(G._draw_messages,
                                  lambda g: g.menu_open or _in_log(g))
    G._draw_radar = _hide_when(G._draw_radar, _in_log)
    # the CRT sweep lines cross the text on a 170 px screen: keep them on the map
    # only (legibility over ornament where there is something to read)
    G._draw_scanlines = _hide_when(G._draw_scanlines,
                                   lambda g: g.menu_open or _in_log(g))

    original_update = G.update                  # ENTER toggles map <-> log

    def update(self):
        _update_view(self)
        original_update(self)

    G.update = update
