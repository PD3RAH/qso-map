#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
QSO Map  -  shows the contacts in an ADIF log on a world map, with distance and bearing
QSO Map  -  toont de verbindingen uit een ADIF-log op de wereldkaart, met afstand en richting

Copyright (c) 2026 Richard A. Hendriksen (PD3RAH)
Licensed under the MIT License - see LICENSE.
Map data: Natural Earth (public domain) via world-atlas (ISC License).

Requires / Vereist:  Python 3.10+ with tkinter (no other packages)
Run / Start:         python qso_map.py [logbook.adi]
"""

import csv
import datetime as dtm
import json
import math
import queue
import os
import re
import sys
import threading
import tkinter as tk
import urllib.request
import webbrowser
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont

import prefixes

# ----------------------------------------------------------------- settings / instellingen
APP_NAME = "QSO Map"
APP_VERSION = "1.2.0"
REPO_URL = "https://github.com/PD3RAH/qso-map"
RELEASE_API = "https://api.github.com/repos/PD3RAH/qso-map/releases/latest"
DOWNLOAD_PREFIX = "https://github.com/PD3RAH/qso-map/releases/download/"
SURVEY_URL = "https://www.pd3rah.nl/qsomap/enquete.php"
APP_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "QSOMap")
CONFIG_FILE = os.path.join(DATA_DIR, "settings.json")
CORR_FILE = os.path.join(DATA_DIR, "corrections.json")     # aangepaste locators, per logbestand
CWSTATION_LOG = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "CWStation", "logbook.adi")
WORLD_FILE = os.path.join(APP_DIR, "world.json")
EARTH_R = 6371.0
HALF_CIRC = math.pi * EARTH_R
DEFAULT_CONFIG = {
    "lang": "nl",
    "theme": "Amber",
    "mycall": "",
    "mygrid": "",
    "use_file_grid": True,
    "units": "km",
    "projection": "azi",
    "lines": True,
    "rings": True,
    "grayline": True,
    "labels": False,
    "reopen_last": True,
    "last_file": "",
    "check_updates": True,
    "auto_install": False,
    "map_style": "bright",
    "starts": 0,
    "survey_asked": False,
}

BAND_ORDER = ["2190m", "630m", "160m", "80m", "60m", "40m", "30m", "20m", "17m", "15m", "12m", "10m",
              "6m", "4m", "2m", "1.25m", "70cm", "23cm", "13cm", "SAT", "?"]
BAND_EDGES = [(0.1357, 0.1378, "2190m"), (0.472, 0.479, "630m"), (1.8, 2.0, "160m"), (3.5, 4.0, "80m"),
              (5.06, 5.45, "60m"), (7.0, 7.3, "40m"), (10.1, 10.15, "30m"), (14.0, 14.35, "20m"),
              (18.068, 18.168, "17m"), (21.0, 21.45, "15m"), (24.89, 24.99, "12m"), (28.0, 29.7, "10m"),
              (50.0, 54.0, "6m"), (70.0, 71.0, "4m"), (144.0, 148.0, "2m"), (222.0, 225.0, "1.25m"),
              (420.0, 450.0, "70cm"), (1240.0, 1300.0, "23cm"), (2300.0, 2450.0, "13cm")]
BAND_COL = {"2190m": "#8f7bff", "630m": "#8f7bff", "160m": "#9b6bff", "80m": "#5b8cff", "60m": "#43b7ff",
            "40m": "#2ee6d6", "30m": "#4be38a", "20m": "#ffd23f", "17m": "#ffb02e", "15m": "#ff8a4c",
            "12m": "#ff5d73", "10m": "#ff4dc4", "6m": "#d98cff", "4m": "#c3a6ff", "2m": "#f2f6f8",
            "1.25m": "#b8c7d1", "70cm": "#9fe7ff", "23cm": "#9fffd0", "13cm": "#fff0a0", "SAT": "#ffffff",
            "?": "#8aa0b0"}
DIST_BINS = [0, 500, 1000, 2000, 3000, 5000, 8000, 12000, 1e9]


# ----------------------------------------------------------------- geo helpers
def grid_to_latlon(g):
    """Maidenhead-locator (2/4/6/8 tekens) -> midden van het vak (lat, lon), of None."""
    g = (g or "").strip().upper()
    if len(g) < 2 or len(g) % 2 or not re.fullmatch(r"[A-R]{2}([0-9]{2}([A-X]{2}([0-9]{2})?)?)?", g):
        return None
    lon, lat = -180.0, -90.0
    lon += (ord(g[0]) - 65) * 20
    lat += (ord(g[1]) - 65) * 10
    dlon, dlat = 20.0, 10.0
    if len(g) >= 4:
        lon += int(g[2]) * 2
        lat += int(g[3]) * 1
        dlon, dlat = 2.0, 1.0
    if len(g) >= 6:
        lon += (ord(g[4]) - 65) * (5 / 60)
        lat += (ord(g[5]) - 65) * (2.5 / 60)
        dlon, dlat = 5 / 60, 2.5 / 60
    if len(g) >= 8:
        lon += int(g[6]) * (0.5 / 60)
        lat += int(g[7]) * (0.25 / 60)
        dlon, dlat = 0.5 / 60, 0.25 / 60
    return lat + dlat / 2, lon + dlon / 2


def latlon_to_grid(lat, lon, n=6):
    lon = (lon + 180) % 360
    lat = min(max(lat + 90, 0), 179.9999)
    s = chr(65 + int(lon // 20)) + chr(65 + int(lat // 10))
    lon, lat = lon % 20, lat % 10
    s += str(int(lon // 2)) + str(int(lat // 1))
    if n >= 6:
        lon, lat = lon % 2, lat % 1
        s += chr(97 + int(lon * 12)) + chr(97 + int(lat * 24))
    return s


def adif_latlon(v):
    """ADIF-formaat 'N052 30.000' -> graden."""
    m = re.fullmatch(r"\s*([NSEWnsew])\s*(\d{1,3})\s+(\d{1,2}(?:\.\d+)?)\s*", v or "")
    if not m:
        return None
    d = int(m.group(2)) + float(m.group(3)) / 60
    return -d if m.group(1).upper() in "SW" else d


def dist_brg(la1, lo1, la2, lo2):
    """Grootcirkel-afstand (km) en beginrichting (graden) van punt 1 naar punt 2."""
    p1, p2 = math.radians(la1), math.radians(la2)
    dl = math.radians(lo2 - lo1)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    d = 2 * EARTH_R * math.asin(min(1.0, math.sqrt(a)))
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return d, (math.degrees(math.atan2(y, x)) + 360) % 360


def destination(lat, lon, brg, dist_km):
    p1, l1 = math.radians(lat), math.radians(lon)
    b, dr = math.radians(brg), dist_km / EARTH_R
    p2 = math.asin(math.sin(p1) * math.cos(dr) + math.cos(p1) * math.sin(dr) * math.cos(b))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(dr) * math.cos(p1), math.cos(dr) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180


def gc_points(la1, lo1, la2, lo2, n):
    """n+1 punten langs de grootcirkel."""
    p1, l1, p2, l2 = map(math.radians, (la1, lo1, la2, lo2))
    v1 = (math.cos(p1) * math.cos(l1), math.cos(p1) * math.sin(l1), math.sin(p1))
    v2 = (math.cos(p2) * math.cos(l2), math.cos(p2) * math.sin(l2), math.sin(p2))
    dot = max(-1.0, min(1.0, sum(a * b for a, b in zip(v1, v2))))
    om = math.acos(dot)
    if om < 1e-9:
        return [(la1, lo1), (la2, lo2)]
    so = math.sin(om)
    out = []
    for i in range(n + 1):
        f = i / n
        a, b = math.sin((1 - f) * om) / so, math.sin(f * om) / so
        x, y, z = (a * v1[k] + b * v2[k] for k in range(3))
        out.append((math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x))))
    return out


def subsolar(now=None):
    """Punt waar de zon loodrecht staat (lat, lon), benadering ~0.1 graad."""
    now = now or dtm.datetime.now(dtm.timezone.utc)
    jd = now.timestamp() / 86400.0 + 2440587.5
    n = jd - 2451545.0
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)
    lam = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    eps = math.radians(23.439 - 0.0000004 * n)
    dec = math.asin(math.sin(eps) * math.sin(lam))
    ra = math.degrees(math.atan2(math.cos(eps) * math.sin(lam), math.cos(lam)))
    gmst = (18.697374558 + 24.06570982441908 * n) % 24
    lon = (ra - gmst * 15 + 540) % 360 - 180
    return math.degrees(dec), lon


def band_of(rec):
    b = (rec.get("BAND") or "").strip().lower()
    if b:
        b = b.replace(" ", "")
        for k in BAND_ORDER:
            if k.lower() == b:
                return k
        return b
    try:
        f = float(rec.get("FREQ") or 0)
    except ValueError:
        f = 0
    for lo, hi, name in BAND_EDGES:
        if lo <= f <= hi:
            return name
    return "?"


# ----------------------------------------------------------------- internet (updates)
def _winhttp_get(url, timeout=15, headers="", progress=None):
    """HTTP(S) GET via Windows WinHTTP (TLS en proxy van Windows; de meegeleverde Python heeft geen OpenSSL).
    Volgt doorverwijzingen (GitHub-downloads). progress(gelezen, totaal) wordt tijdens het lezen aangeroepen."""
    import ctypes
    from ctypes import wintypes
    from urllib.parse import urlsplit
    w = ctypes.WinDLL("winhttp")
    H = ctypes.c_void_p
    w.WinHttpOpen.restype = H
    w.WinHttpOpen.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    w.WinHttpConnect.restype = H
    w.WinHttpConnect.argtypes = [H, wintypes.LPCWSTR, wintypes.WORD, wintypes.DWORD]
    w.WinHttpOpenRequest.restype = H
    w.WinHttpOpenRequest.argtypes = [H, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.LPCWSTR,
                                     ctypes.c_void_p, wintypes.DWORD]
    w.WinHttpSendRequest.argtypes = [H, wintypes.LPCWSTR, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                     wintypes.DWORD, ctypes.c_size_t]
    w.WinHttpReceiveResponse.argtypes = [H, ctypes.c_void_p]
    w.WinHttpQueryDataAvailable.argtypes = [H, ctypes.POINTER(wintypes.DWORD)]
    w.WinHttpReadData.argtypes = [H, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    w.WinHttpQueryHeaders.argtypes = [H, wintypes.DWORD, wintypes.LPCWSTR, ctypes.c_void_p,
                                      ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD)]
    w.WinHttpSetTimeouts.argtypes = [H, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int]
    w.WinHttpCloseHandle.argtypes = [H]
    u = urlsplit(url)
    secure = u.scheme == "https"
    port = u.port or (443 if secure else 80)
    path = (u.path or "/") + (("?" + u.query) if u.query else "")
    agent = f"QSOMap/{APP_VERSION}"
    hs = w.WinHttpOpen(agent, 4, None, None, 0) or w.WinHttpOpen(agent, 0, None, None, 0)
    hc = hr = None
    try:
        if not hs:
            raise OSError("WinHttpOpen failed")
        ms = int(timeout * 1000)
        w.WinHttpSetTimeouts(hs, ms, ms, ms, ms)
        hc = w.WinHttpConnect(hs, u.hostname, port, 0)
        hr = w.WinHttpOpenRequest(hc, "GET", path, None, None, None, 0x00800000 if secure else 0)
        if not hr:
            raise OSError("WinHttpOpenRequest failed")
        if not w.WinHttpSendRequest(hr, headers or None, 0xFFFFFFFF if headers else 0, None, 0, 0, 0):
            raise OSError(f"WinHttpSendRequest failed ({ctypes.GetLastError()})")
        if not w.WinHttpReceiveResponse(hr, None):
            raise OSError(f"WinHttpReceiveResponse failed ({ctypes.GetLastError()})")
        code, size = wintypes.DWORD(0), wintypes.DWORD(4)
        w.WinHttpQueryHeaders(hr, 19 | 0x20000000, None, ctypes.byref(code), ctypes.byref(size), None)
        total, size = wintypes.DWORD(0), wintypes.DWORD(4)
        w.WinHttpQueryHeaders(hr, 5 | 0x20000000, None, ctypes.byref(total), ctypes.byref(size), None)
        chunks, got_all = [], 0
        while True:
            n = wintypes.DWORD(0)
            if not w.WinHttpQueryDataAvailable(hr, ctypes.byref(n)) or n.value == 0:
                break
            buf = ctypes.create_string_buffer(n.value)
            got = wintypes.DWORD(0)
            w.WinHttpReadData(hr, buf, n.value, ctypes.byref(got))
            chunks.append(buf.raw[:got.value])
            got_all += got.value
            if progress:
                progress(got_all, total.value)
        if code.value and code.value >= 400:
            raise OSError(f"HTTP {code.value}")
        return b"".join(chunks)
    finally:
        for hnd in (hr, hc, hs):
            if hnd:
                w.WinHttpCloseHandle(hnd)


def http_get(url, timeout=15, progress=None):
    try:
        import ssl  # noqa: F401  (niet aanwezig in de meegeleverde Windows-runtime)
    except ImportError:
        return _winhttp_get(url, timeout, "Accept: application/vnd.github+json\r\n", progress)
    req = urllib.request.Request(url, headers={"User-Agent": f"QSOMap/{APP_VERSION}",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        total = int(r.headers.get("Content-Length") or 0)
        chunks, n = [], 0
        while True:
            b = r.read(65536)
            if not b:
                break
            chunks.append(b)
            n += len(b)
            if progress:
                progress(n, total)
        return b"".join(chunks)


def version_tuple(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


# ----------------------------------------------------------------- ADIF
def read_adif(path):
    """ADIF (.adi) inlezen. Geeft (header, records). Lengtes worden als bytes geteld (ADIF-norm);
    klopt dat niet (UTF-8), dan wordt tot de volgende tag gelezen."""
    with open(path, "rb") as f:
        data = f.read()
    head = {}
    up = data.upper()
    i = up.find(b"<EOH>")
    tag = re.compile(rb"<([A-Za-z0-9_]+)(?::(\d+))?(?::([A-Za-z]))?>")
    if i >= 0 or not data.lstrip().startswith(b"<"):
        hdr, data = (data[:i], data[i + 5:]) if i >= 0 else (b"", data)
        for m in tag.finditer(hdr):
            if m.group(2):
                head[m.group(1).decode().upper()] = hdr[m.end():m.end() + int(m.group(2))].decode("utf-8", "replace")

    def dec(b):
        try:
            return b.decode("utf-8")
        except UnicodeDecodeError:
            return b.decode("latin-1")
    out, rec, pos = [], {}, 0
    while True:
        m = tag.search(data, pos)
        if not m:
            break
        name = m.group(1).decode().upper()
        if name == "EOR":
            if rec:
                out.append(rec)
            rec, pos = {}, m.end()
            continue
        if name == "EOH":
            rec, pos = {}, m.end()
            continue
        n = int(m.group(2) or 0)
        val = data[m.end():m.end() + n]
        rec[name] = dec(val).strip()
        pos = m.end() + n
    return head, out


def adif_field(k, v):
    v = str(v)
    return f"<{k}:{len(v.encode('utf-8'))}>{v} "


def write_adif(path, recs):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{APP_NAME} export\n" + adif_field("ADIF_VER", "3.1.4") + adif_field("PROGRAMID", "QSOMap") +
                adif_field("PROGRAMVERSION", APP_VERSION) + "<EOH>\n")
        for r in recs:
            f.write("".join(adif_field(k, v) for k, v in r.items() if v != "") + "<EOR>\n")


# ----------------------------------------------------------------- thema & widgets (zoals CW Station)
C = dict(bg="#07121b", panel="#0c1d2b", panel2="#10283b", border="#1a3d55", btn="#132e45",
         btnhi="#1b4160", acc="#ffb02e", acc2="#5cc8ff", text="#d8edf6", dim="#6f93a8",
         red="#ff4d5e", amber="#ff9f43", green="#4be38a", scr="#030a10")
THEMES = {
    "Amber":     dict(acc="#ffb02e", acc2="#5cc8ff"),
    "Turquoise": dict(acc="#2ee6d6", acc2="#ffb43c"),
    "Green":     dict(acc="#63e68a", acc2="#ffb43c"),
    "Ice blue":  dict(acc="#5cb8ff", acc2="#ffb43c"),
    "Copper":    dict(acc="#ff8a4c", acc2="#7fd6ff"),
    "Purple":    dict(acc="#b78cff", acc2="#ffc35c"),
}
THEME_NL = {"Amber": "Amber", "Turquoise": "Turquoise", "Green": "Groen", "Ice blue": "IJsblauw",
            "Copper": "Koper", "Purple": "Paars"}
# Kaartkleuren: "bright" = heldere kaart (standaard), "dark" = donker zoals de rest van het scherm
MAP_STYLES = {
    "bright": dict(sea="#1b5a85", sea_rim="#123f60", land="#4f8068", edge="#9cc9b0", grat="#3a78a3",
                   ring=0.55, line=0.85, night="gray12", night_sea=0.38, spoke="#3d7ba5", border="#5fa0c8"),
    "dark":   dict(sea="#030a10", sea_rim="#030a10", land="#13324a", edge="#2f6b8c", grat="#102638",
                   ring=0.30, line=0.55, night="gray12", night_sea=0.0, spoke="#14334a", border="#1a3d55"),
}
M = dict(MAP_STYLES["bright"])
UI = "Segoe UI"
MONO = "Consolas"
DIGIT = "Bahnschrift"
SCALE = 1.0


def S(v):
    return max(1, int(round(v * SCALE)))


def scale_for(w, h):
    return round(min(max(min(w / 1560.0, h / 1000.0), 0.66), 1.7), 2)


def _mix(c1, c2, f):
    f = min(max(f, 0.0), 1.0)
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{int(x + (y - x) * f):02x}" for x, y in zip(a, b))


def trace(widget, var, cb):
    tid = var.trace_add("write", lambda *a: cb())

    def _rm(ev):
        if ev.widget is widget:
            try:
                var.trace_remove("write", tid)
            except tk.TclError:
                pass
    widget.bind("<Destroy>", _rm, add="+")


def panel(parent, title=None):
    f = tk.Frame(parent, bg=C["panel"], highlightthickness=1, highlightbackground=C["border"])
    head = None
    if title is not None:
        head = tk.Frame(f, bg=C["panel"])
        head.pack(fill="x", padx=12, pady=(8, 0))
        tk.Frame(head, bg=C["acc"], width=3, height=12).pack(side="left", padx=(0, 7))
        lbl = tk.Label(head, text=title, bg=C["panel"], fg=C["dim"], font=(UI, S(9), "bold"))
        lbl.pack(side="left")
        head.title = lbl
    body = tk.Frame(f, bg=C["panel"])
    body.pack(fill="both", expand=True, padx=12, pady=6)
    return f, body, head


def label(parent, text="", fg=None, font=None, bg=None, **kw):
    return tk.Label(parent, text=text, bg=bg or parent.cget("bg"), fg=fg or C["dim"],
                    font=font or (UI, S(9)), **kw)


def entry(parent, var, width=8, font=None):
    return tk.Entry(parent, textvariable=var, width=width, bg=C["panel2"], fg=C["text"],
                    insertbackground=C["acc"], relief="flat", font=font or (UI, S(10)),
                    highlightthickness=1, highlightbackground=C["border"], highlightcolor=C["acc"])


class FlatButton(tk.Canvas):
    """Afgeronde knop (canvas). Optioneel gekoppeld aan een BooleanVar (toggle)."""

    def __init__(self, parent, text, command=None, var=None, width=None, font=None,
                 accent=None, padx=12, pady=5, radius=8):
        self.font = tkfont.Font(font=font or (UI, S(10), "bold"))
        self._text = text
        self.padx, self.pady, self.radius = padx, pady, radius
        self.minw = (width or 0) * self.font.measure("0")
        w, h = self._size()
        super().__init__(parent, width=w, height=h, bg=parent.cget("bg"),
                         highlightthickness=0, cursor="hand2")
        self.command = command
        self.var = var
        self.accent = accent or C["acc"]
        self.active = False
        self.hover = False
        self.fg_override = None
        self.bind("<Enter>", lambda e: self._h(True))
        self.bind("<Leave>", lambda e: self._h(False))
        self.bind("<Button-1>", self._click)
        self.bind("<Configure>", lambda e: self._paint())
        if var is not None:
            trace(self, var, lambda: self.set_active(bool(var.get())))
            self.active = bool(var.get())
        self._paint()

    def _size(self):
        return (max(self.font.measure(self._text) + 2 * self.padx, self.minw),
                self.font.metrics("linespace") + 2 * self.pady)

    def config(self, cnf=None, **kw):
        if "text" in kw:
            self._text = kw.pop("text")
            w, h = self._size()
            kw.setdefault("width", w)
        if "fg" in kw:
            self.fg_override = kw.pop("fg")
        if kw:
            super().config(cnf, **kw)
        self._paint()
    configure = config

    def _h(self, on):
        self.hover = on
        self._paint()

    def _click(self, ev):
        if self.var is not None:
            self.var.set(not self.var.get())
        if self.command:
            self.command()

    def set_active(self, on, accent=None):
        self.active = bool(on)
        if accent:
            self.accent = accent
        self._paint()

    def _paint(self):
        try:
            w, h = self.winfo_width(), self.winfo_height()
        except tk.TclError:
            return
        if w <= 1:
            w, h = self._size()
        self.delete("all")
        r = min(self.radius, h / 2)
        if self.active:
            bg, fg, ol = self.accent, "#03131b", self.accent
        else:
            bg = C["btnhi"] if self.hover else C["btn"]
            fg = self.fg_override or C["text"]
            ol = _mix(C["border"], C["acc"], 0.35) if self.hover else C["border"]
        x1, y1, x2, y2 = 1, 1, w - 1, h - 1
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
               x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        self.create_polygon(pts, smooth=True, fill=bg, outline=ol)
        self.create_text(w / 2, h / 2, text=self._text, fill=fg, font=self.font)


class Slider(tk.Canvas):
    def __init__(self, parent, var, lo, hi, command=None, width=200, height=22):
        super().__init__(parent, width=width, height=height, bg=parent.cget("bg"),
                         highlightthickness=0, cursor="hand2")
        self.var, self.lo, self.hi, self.command = var, lo, hi, command
        self.w, self.h = width, height
        self.bind("<Button-1>", self._set)
        self.bind("<B1-Motion>", self._set)
        self.bind("<ButtonRelease-1>", lambda e: self.command and self.command(True))
        self.bind("<MouseWheel>", lambda e: self._step(1 if e.delta > 0 else -1))
        self.bind("<Configure>", lambda e: self._resize(e.width))
        trace(self, var, self.draw)
        self.draw()

    def set_range(self, lo, hi):
        self.lo, self.hi = lo, max(hi, lo + 1e-9)
        self.draw()

    def _resize(self, w):
        self.w = w
        self.draw()

    def _set(self, ev):
        f = min(max((ev.x - 8) / max(self.w - 16, 1), 0), 1)
        self.var.set(round(self.lo + f * (self.hi - self.lo), 2))
        if self.command:
            self.command(False)

    def _step(self, d):
        v = self.var.get() + d * (self.hi - self.lo) / 50
        self.var.set(round(min(max(v, self.lo), self.hi), 2))
        if self.command:
            self.command(True)

    def draw(self):
        self.delete("all")
        try:
            v = float(self.var.get())
        except (ValueError, tk.TclError):
            return
        f = (v - self.lo) / (self.hi - self.lo) if self.hi > self.lo else 1
        y = self.h // 2
        x = 8 + f * (self.w - 16)
        k = max(5, int(self.h * 0.33))
        lw = max(3, int(self.h * 0.18))
        self.create_line(8, y, self.w - 8, y, fill=C["btn"], width=lw, capstyle="round")
        self.create_line(8, y, x, y, fill=C["acc"], width=lw, capstyle="round")
        self.create_oval(x - k, y - k, x + k, y + k, fill=C["text"], outline=C["acc"], width=2)


# ----------------------------------------------------------------- kaart
class MapView(tk.Canvas):
    """Wereldkaart: 'eq' = platte kaart (lengte/breedte), 'azi' = azimutaal equidistant rond het eigen QTH
    (afstanden en richtingen vanaf huis zijn daar exact: een rechte lijn is de grootcirkel)."""

    def __init__(self, parent, app):
        super().__init__(parent, bg=C["panel"], highlightthickness=0, cursor="fleur")
        self.app = app
        self.proj = app.cfg.get("projection", "azi")
        self.k = None
        self.cu = self.cv = 0.0
        self._cache = {}
        self._drag = None
        self._redraw_job = None
        self._items = {}            # canvas-id -> qso-index
        self._hover_id = None
        self.pending_view = None
        self.bind("<Configure>", lambda e: self._on_resize())
        self.bind("<ButtonPress-1>", self._press)
        self.bind("<B1-Motion>", self._move)
        self.bind("<ButtonRelease-1>", self._release)
        self.bind("<MouseWheel>", self._wheel)
        self.bind("<Button-4>", lambda e: self._zoom_at(e.x, e.y, 1.25))
        self.bind("<Button-5>", lambda e: self._zoom_at(e.x, e.y, 0.8))
        self.bind("<Double-Button-1>", lambda e: self._zoom_at(e.x, e.y, 2.0))
        self.bind("<Motion>", self._hover)
        self.bind("<Leave>", lambda e: self.delete("tip"))

    # ---------- projectie
    def project(self, lat, lon):
        if self.proj == "eq":
            return lon, -lat
        h = self.app.home
        p0, l0 = math.radians(h[0]), math.radians(h[1])
        p, l = math.radians(lat), math.radians(lon)
        cc = math.sin(p0) * math.sin(p) + math.cos(p0) * math.cos(p) * math.cos(l - l0)
        c = math.acos(max(-1.0, min(1.0, cc)))
        if c > math.radians(179.3):
            return None
        kk = EARTH_R * (c / math.sin(c) if c > 1e-9 else 1.0)
        x = kk * math.cos(p) * math.sin(l - l0)
        y = kk * (math.cos(p0) * math.sin(p) - math.sin(p0) * math.cos(p) * math.cos(l - l0))
        return x, -y

    def _jump(self):
        return 180.0 if self.proj == "eq" else 6000.0

    def project_path(self, pts):
        """Lijst (lat,lon) -> lijst van segmenten in kaarteenheden, gesplitst bij sprongen (datumgrens/antipode)."""
        segs, cur, last = [], [], None
        lim = self._jump()
        for la, lo in pts:
            q = self.project(la, lo)
            if q is None:
                if len(cur) >= 4:
                    segs.append(cur)
                cur, last = [], None
                continue
            if last is not None and (abs(q[0] - last[0]) > lim or abs(q[1] - last[1]) > lim):
                if len(cur) >= 4:
                    segs.append(cur)
                cur = []
            cur += [q[0], q[1]]
            last = q
        if len(cur) >= 4:
            segs.append(cur)
        return segs

    def _land(self):
        key = (self.proj, self.app.home if self.proj == "azi" else None)
        if key in self._cache:
            return self._cache[key]
        polys, lines = [], []
        for ctry in self.app.world:
            for ring in ctry["r"]:
                pts = list(zip(ring[1::2], ring[0::2]))
                segs = self.project_path(pts)
                if len(segs) == 1 and len(segs[0]) >= 6:
                    polys.append(segs[0])
                else:
                    lines.extend(segs)
        self._cache = {key: (polys, lines)}
        return polys, lines

    # ---------- beeld
    def fit_world(self):
        w, h = max(self.winfo_width(), 50), max(self.winfo_height(), 50)
        if self.proj == "eq":
            self.k = min(w / 360.0, h / 170.0)
            self.cu, self.cv = 0.0, -5.0                    # 85 N .. 75 S, de hele breedte
        else:
            self.k = (min(w, h) / 2 - S(30)) / HALF_CIRC     # ruimte voor de windroos-labels
            self.cu = self.cv = 0.0
        self.redraw()

    def fit_data(self):
        pts = [self.project(q["lat"], q["lon"]) for q in self.app.visible()]
        pts = [p for p in pts if p] + [self.project(*self.app.home)]
        pts = [p for p in pts if p]
        if len(pts) < 2:
            return self.fit_world()
        us, vs = [p[0] for p in pts], [p[1] for p in pts]
        w, h = max(self.winfo_width(), 50), max(self.winfo_height(), 50)
        du, dv = max(max(us) - min(us), 1e-3), max(max(vs) - min(vs), 1e-3)
        self.k = min(w / du, h / dv) * 0.86
        self.k = min(self.k, self._kmax())
        self.cu, self.cv = (max(us) + min(us)) / 2, (max(vs) + min(vs)) / 2
        self.redraw()

    def _kmin(self):
        w, h = max(self.winfo_width(), 50), max(self.winfo_height(), 50)
        return (min(w / 360.0, h / 170.0) if self.proj == "eq" else (min(w, h) / 2 - S(30)) / HALF_CIRC) * 0.6

    def _kmax(self):
        return self._kmin() * 120

    def set_projection(self, p):
        self.proj = p
        self.k = None
        self.fit_world()

    def X(self, u):
        return self.winfo_width() / 2 + (u - self.cu) * self.k

    def Y(self, v):
        return self.winfo_height() / 2 + (v - self.cv) * self.k

    def tx(self, flat):
        w2, h2, k, cu, cv = self.winfo_width() / 2, self.winfo_height() / 2, self.k, self.cu, self.cv
        out = flat[:]
        out[0::2] = [w2 + (u - cu) * k for u in flat[0::2]]
        out[1::2] = [h2 + (v - cv) * k for v in flat[1::2]]
        return out

    def _on_resize(self):
        if self.k is None and self.pending_view:
            self.k, self.cu, self.cv = self.pending_view
            self.pending_view = None
            self.schedule_redraw()
        elif self.k is None:
            self.after(30, self.fit_world)
        else:
            self.schedule_redraw()

    def schedule_redraw(self, ms=40):
        if self._redraw_job:
            self.after_cancel(self._redraw_job)
        self._redraw_job = self.after(ms, self.redraw)

    def redraw(self):
        self._redraw_job = None
        if self.k is None:
            return
        self.delete("all")
        self._items = {}
        w, h = self.winfo_width(), self.winfo_height()
        land_c, edge_c = M["land"], M["edge"]
        # achtergrond (oceaan)
        self.create_rectangle(0, 0, w, h, fill=C["panel"], outline="")
        if self.proj == "eq":
            self.create_rectangle(self.X(-180), self.Y(-90), self.X(180), self.Y(90), fill=M["sea"],
                                  outline=M["border"], width=2)
        else:
            r = HALF_CIRC * self.k
            cx, cy = self.X(0), self.Y(0)
            n = 7                                           # zachte overgang naar de rand (diepte)
            for i in range(n):
                rr = r * (1 - i / n * 0.55)
                self.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, outline="",
                                 fill=_mix(M["sea_rim"], M["sea"], i / (n - 1)))
            self.create_oval(cx - r, cy - r, cx + r, cy + r, outline=M["border"], width=2)
        # graticule
        grat = M["grat"]
        if self.proj == "eq":
            for lon in range(-180, 181, 30):
                self.create_line(self.X(lon), self.Y(-90), self.X(lon), self.Y(90), fill=grat)
            for lat in range(-60, 91, 30):
                self.create_line(self.X(-180), self.Y(-lat), self.X(180), self.Y(-lat), fill=grat,
                                 dash=(2, 3) if lat == 0 else None)
        # nacht (platte kaart): donkerder zee onder het land
        if self.proj == "eq" and self.app.grayline_var.get():
            self.create_polygon(self.tx(self._night_poly()), fill=_mix(M["sea"], "#000000", M["night_sea"]), outline="")
        # land
        polys, lines = self._land()
        for p in polys:
            self.create_polygon(self.tx(p), fill=land_c, outline=edge_c)
        for ln in lines:
            self.create_line(self.tx(ln), fill=edge_c)
        # grijslijn
        if self.app.grayline_var.get():
            self._draw_grayline()
        # afstandsringen + windroos
        if self.app.rings_var.get():
            self._draw_rings()
        # verbindingen
        vis = self.app.visible()
        if self.app.lines_var.get():
            done = set()
            for q in vis:
                key = (round(q["lat"], 3), round(q["lon"], 3))
                if key in done:
                    continue
                done.add(key)
                for seg in self.app.path_for(q, self):
                    self.create_line(self.tx(seg), fill=_mix(M["sea"], BAND_COL.get(q["band"], "#8aa0b0"), M["line"]),
                                     width=1, tags="line")
        self._draw_dots(vis)
        self._draw_home()
        self._draw_selection()
        self._draw_legend(vis)

    def _draw_dots(self, vis):
        rr = S(3.2)
        odx = self.app.odx()
        show_lbl = self.app.labels_var.get() and len(vis) <= 600
        lf = (UI, S(8))
        for q in vis:
            p = self.project(q["lat"], q["lon"])
            if not p:
                continue
            x, y = self.X(p[0]), self.Y(p[1])
            col = BAND_COL.get(q["band"], "#8aa0b0")
            if q["src"] == "pfx":
                iid = self.create_rectangle(x - rr + 1, y - rr + 1, x + rr - 1, y + rr - 1, fill=M["sea"],
                                            outline=col, width=1.5, tags="dot")
            else:
                iid = self.create_oval(x - rr, y - rr, x + rr, y + rr, fill=col, outline="#03131b", tags="dot")
            self._items[iid] = q["i"]
            if show_lbl:
                self.create_text(x + rr + 3, y, text=q["call"], anchor="w", fill=_mix(col, C["text"], 0.5),
                                 font=lf, tags="lbl")
        if odx is not None and odx["i"] != self.app.sel:
            p = self.project(odx["lat"], odx["lon"])
            if p:
                x, y = self.X(p[0]), self.Y(p[1])
                r = S(9)
                self.create_oval(x - r, y - r, x + r, y + r, outline=C["acc"], width=2)
                self.create_text(x, y - r - S(8), text="ODX " + odx["call"], fill=C["acc"],
                                 font=(UI, S(8), "bold"))

    def _draw_home(self):
        p = self.project(*self.app.home)
        if not p:
            return
        x, y = self.X(p[0]), self.Y(p[1])
        r = S(6)
        self.create_oval(x - r * 2, y - r * 2, x + r * 2, y + r * 2, outline=_mix(M["sea"], C["acc"], 0.6), width=1)
        self.create_oval(x - r, y - r, x + r, y + r, fill=C["acc"], outline="#03131b", width=2)
        self.create_text(x, y + r * 2 + S(6), text=self.app.home_label(), fill=C["acc"], font=(UI, S(8), "bold"))

    def _draw_selection(self):
        q = self.app.selected_qso()
        if not q:
            return
        p = self.project(q["lat"], q["lon"])
        if not p:
            return
        for seg in self.app.path_for(q, self):
            self.create_line(self.tx(seg), fill=C["acc2"], width=2)
        x, y = self.X(p[0]), self.Y(p[1])
        r = S(8)
        self.create_oval(x - r, y - r, x + r, y + r, outline=C["acc2"], width=2)
        txt = f"{q['call']}  ·  {self.app.fmt_dist(q['dist'])}  ·  {q['brg']:.0f}°"
        f = (UI, S(9), "bold")
        tid = self.create_text(x + r + 6, y - r - 4, text=txt, anchor="sw", fill="#03131b", font=f)
        b = self.bbox(tid)
        bg = self.create_rectangle(b[0] - 5, b[1] - 2, b[2] + 5, b[3] + 2, fill=C["acc2"], outline="")
        self.tag_lower(bg, tid)

    def _draw_rings(self):
        h = self.app.home
        span_km = (self.winfo_width() / self.k) * (111.0 if self.proj == "eq" else 1.0)
        step = next((s for s in (100, 250, 500, 1000, 2500, 5000) if span_km / s <= 9), 5000)
        col = _mix(M["sea"], C["acc"], M["ring"])
        tcol = _mix(M["sea"], C["acc"], 0.9)
        d = step
        f = (UI, S(8))
        while d < 20000:
            pts = [destination(h[0], h[1], b, d) for b in range(0, 361, 3)]
            for seg in self.project_path(pts):
                self.create_line(self.tx(seg), fill=col, dash=(3, 4))
            if d % (step * 2 if step < 5000 else step) == 0 or step >= 2500:
                la, lo = destination(h[0], h[1], 135, d)
                p = self.project(la, lo)
                if p:
                    self.create_text(self.X(p[0]) + 3, self.Y(p[1]), text=self.app.fmt_dist(d, 0), anchor="w",
                                     fill=tcol, font=f)
            d += step
        if self.proj == "azi":
            r = HALF_CIRC * self.k
            cx, cy = self.X(0), self.Y(0)
            names = self.app.t(["N", "NO", "O", "ZO", "Z", "ZW", "W", "NW"], ["N", "NE", "E", "SE", "S", "SW", "W", "NW"])
            for i, b in enumerate(range(0, 360, 30)):
                a = math.radians(b)
                self.create_line(cx, cy, cx + r * math.sin(a), cy - r * math.cos(a), fill=M["spoke"])
                tx_, ty_ = cx + (r + S(12)) * math.sin(a), cy - (r + S(12)) * math.cos(a)
                lbl = names[b // 45] if b % 45 == 0 else f"{b}°"
                self.create_text(tx_, ty_, text=lbl, fill=C["acc"] if b % 90 == 0 else C["dim"],
                                 font=(UI, S(9), "bold") if b % 90 == 0 else f)
            for b in (45, 135, 225, 315):
                a = math.radians(b)
                tx_, ty_ = cx + (r + S(12)) * math.sin(a), cy - (r + S(12)) * math.cos(a)
                self.create_text(tx_, ty_, text=names[b // 45], fill=C["dim"], font=(UI, S(9), "bold"))

    def _night_poly(self):
        dec, slon = subsolar()
        td = math.tan(math.radians(dec)) or 1e-6
        line = []
        for lon in range(-180, 181, 2):
            lat = math.degrees(math.atan(-math.cos(math.radians(lon - slon)) / td))
            line += [lon, -lat]
        pole = 90 if dec < 0 else -90               # nacht rond de pool die van de zon af staat
        return line + [180, -pole, -180, -pole]

    def _draw_grayline(self):
        dec, slon = subsolar()
        pts = [destination(dec, slon, b, HALF_CIRC / 2) for b in range(0, 361, 2)]
        if self.proj == "eq":
            poly = self._night_poly()
            line = poly[:-4]
            if M["night"]:                           # lichte schaduw over het land
                self.create_polygon(self.tx(poly), fill="#000000", stipple=M["night"], outline="")
            self.create_line(self.tx(line), fill="#ffe08a", width=1, dash=(6, 4))
        else:
            for seg in self.project_path(pts):
                self.create_line(self.tx(seg), fill="#ffe08a", width=1, dash=(6, 4))
        p = self.project(dec, slon)
        if p:
            x, y = self.X(p[0]), self.Y(p[1])
            r = S(7)
            self.create_oval(x - r, y - r, x + r, y + r, fill="#ffd23f", outline="#ff9f43", width=2)
            for a in range(0, 360, 45):
                ra = math.radians(a)
                self.create_line(x + r * 1.4 * math.cos(ra), y + r * 1.4 * math.sin(ra),
                                 x + r * 2.0 * math.cos(ra), y + r * 2.0 * math.sin(ra), fill="#ffd23f", width=2)

    def _draw_legend(self, vis):
        bands = sorted({q["band"] for q in vis}, key=lambda b: BAND_ORDER.index(b) if b in BAND_ORDER else 99)
        if not bands:
            return
        x, y = S(12), S(14)
        f = (UI, S(8), "bold")
        for b in bands:                      # verticale legenda linksboven
            col = BAND_COL.get(b, "#8aa0b0")
            self.create_oval(x, y - S(4), x + S(8), y + S(4), fill=col, outline="", tags="leg")
            self.create_text(x + S(13), y, text=b, anchor="w", fill=C["text"], font=f, tags="leg")
            y += S(16)
        self.create_rectangle(x + 1, y - S(3), x + S(7), y + S(3), outline=C["dim"], width=1.5, tags="leg")
        self.create_text(x + S(13), y, anchor="w", fill=C["dim"], font=(UI, S(8)), tags="leg",
                         text=self.app.t("= positie uit prefix (benadering)", "= position from prefix (approx.)"))
        bb = self.bbox("leg")
        if bb:
            bg = self.create_rectangle(bb[0] - S(8), bb[1] - S(6), bb[2] + S(8), bb[3] + S(6),
                                       fill=C["panel"], outline=C["border"])
            self.tag_lower(bg, "leg")

    # ---------- muis
    def _press(self, ev):
        self._drag = (ev.x, ev.y, self.cu, self.cv, False)

    def _move(self, ev):
        if not self._drag or self.k is None:
            return
        x0, y0, cu, cv, moved = self._drag
        dx, dy = ev.x - x0, ev.y - y0
        if not moved and abs(dx) + abs(dy) < 4:
            return
        nu, nv = cu - dx / self.k, cv - dy / self.k
        self.move("all", (self.cu - nu) * self.k, (self.cv - nv) * self.k)
        self.cu, self.cv = nu, nv
        self._drag = (x0, y0, cu, cv, True)

    def _release(self, ev):
        if not self._drag:
            return
        moved = self._drag[4]
        self._drag = None
        if moved:
            self.schedule_redraw(10)
            return
        hit = self._hit(ev.x, ev.y)
        if hit is not None:
            self.app.select(hit, from_map=True)

    def _hit(self, x, y):
        r = S(6)
        best = None
        for iid in self.find_overlapping(x - r, y - r, x + r, y + r):
            if iid in self._items:
                best = self._items[iid]
        return best

    def _hover(self, ev):
        if self._drag:
            return
        hit = self._hit(ev.x, ev.y)
        self.delete("tip")
        if hit is None:
            self.config(cursor="fleur")
            return
        self.config(cursor="hand2")
        q = self.app.qsos[hit]
        others = self.app.at_same_place(q)
        txt = f"{q['call']}  {q['band']} {q['mode']}  ·  {self.app.fmt_dist(q['dist'])}"
        if len(others) > 1:
            txt += self.app.t(f"  (+{len(others) - 1} op deze plek)", f"  (+{len(others) - 1} at this spot)")
        t = self.create_text(ev.x + 14, ev.y + 16, text=txt, anchor="nw", fill=C["text"],
                             font=(UI, S(9), "bold"), tags="tip")
        b = self.bbox(t)
        bg = self.create_rectangle(b[0] - 6, b[1] - 3, b[2] + 6, b[3] + 3, fill=C["panel2"],
                                   outline=C["acc"], tags="tip")
        self.tag_lower(bg, t)

    def _wheel(self, ev):
        self._zoom_at(ev.x, ev.y, 1.25 if ev.delta > 0 else 0.8)

    def _zoom_at(self, x, y, f):
        if self.k is None:
            return
        nk = min(max(self.k * f, self._kmin()), self._kmax())
        w2, h2 = self.winfo_width() / 2, self.winfo_height() / 2
        u = self.cu + (x - w2) / self.k
        v = self.cv + (y - h2) / self.k
        self.k = nk
        self.cu = u - (x - w2) / nk
        self.cv = v - (y - h2) / nk
        self.schedule_redraw(15)

    def zoom(self, f):
        self._zoom_at(self.winfo_width() / 2, self.winfo_height() / 2, f)

    def center_on(self, q, zoom_in=True):
        p = self.project(q["lat"], q["lon"])
        if not p:
            return
        if zoom_in:
            self.k = min(max(self.k, self._kmin() * 6), self._kmax())
        self.cu, self.cv = p
        self.redraw()


# ----------------------------------------------------------------- kleine grafieken
class BarChart(tk.Canvas):
    """Horizontale staafjes: [(label, waarde, kleur)]."""

    def __init__(self, parent, height):
        super().__init__(parent, bg=C["panel"], height=height, highlightthickness=0)
        self.rows = []
        self.bind("<Configure>", lambda e: self.draw())

    def set(self, rows):
        self.rows = rows
        self.draw()

    def draw(self):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 20 or not self.rows:
            self.create_text(w / 2, h / 2, text="—", fill=C["dim"], font=(UI, S(10)))
            return
        n = len(self.rows)
        rh = min(h / n, S(20))
        mx = max(v for _, v, _ in self.rows) or 1
        lw, vw = S(64), S(44)
        f = (UI, S(8), "bold")
        for i, (lbl, v, col) in enumerate(self.rows):
            y = i * rh + rh / 2
            self.create_text(0, y, text=lbl, anchor="w", fill=C["dim"], font=f)
            bw = (w - lw - vw) * v / mx
            self.create_rectangle(lw, y - rh * 0.32, w - vw, y + rh * 0.32, fill=C["panel2"], outline="")
            if v:
                self.create_rectangle(lw, y - rh * 0.32, lw + max(bw, 2), y + rh * 0.32, fill=col, outline="")
            self.create_text(w, y, text=str(v), anchor="e", fill=C["text"], font=f)


# ----------------------------------------------------------------- hoofdapplicatie
class App:
    SPEEDS = (("1×", 4), ("5×", 20), ("25×", 100), ("100×", 400))     # QSO's per seconde

    def __init__(self, root, path=None):
        self.root = root
        self.cfg = self._load_cfg()
        self.lang = self.cfg.get("lang", "nl")
        C.update(THEMES.get(self.cfg.get("theme", "Amber"), THEMES["Amber"]))
        M.update(MAP_STYLES.get(self.cfg.get("map_style", "bright"), MAP_STYLES["bright"]))
        try:
            with open(WORLD_FILE, encoding="utf-8") as f:
                self.world = json.load(f)["c"]
        except Exception:
            self.world = []
        self.qsos = []
        self.nopos = []
        self.file_path = ""
        self.file_home = None
        self.file_call = ""
        self.home = (52.6, 5.0)          # wordt overschreven door instellingen/ADIF
        self.home_src = ""
        self.sel = None
        self.band_filter = set()
        self.mode_filter = set()
        self.search = ""
        self.period_mode = None          # None = alles, "Y" jaar, "M" maand, "D" dag
        self.period_val = ""             # bijv. "2024", "202406", "20240610"
        self.cursor = None               # tijdlijn: aantal QSO's (chronologisch) zichtbaar, None = alles
        self.playing = False
        self.speed_i = 1
        self.update_info = None
        self._paths = {}
        self._vis_cache = None
        self._sort = ("dt", True)
        self.gq = queue.Queue()
        self.corr = self._load_corr()
        self._init_vars()
        self._resolve_home()
        global SCALE
        try:
            SCALE = scale_for(root.winfo_screenwidth() * 0.98, root.winfo_screenheight() * 0.90)
        except tk.TclError:
            pass
        self._style()
        self._build()
        self._resize_job = None
        root.bind("<Configure>", self._on_root_configure, add="+")
        root.after(500, self._clock)
        root.after(150, self._poll)
        root.after(60000, self._grayline_tick)
        root.protocol("WM_DELETE_WINDOW", self._quit)
        start = path or (self.cfg.get("last_file") if self.cfg.get("reopen_last") else "")
        if start and os.path.exists(start):
            root.after(200, lambda: self.load(start))

    def t(self, nl, en):
        return nl if self.lang == "nl" else en

    # ---------- config
    def _load_cfg(self):
        cfg = dict(DEFAULT_CONFIG)
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, encoding="utf-8") as f:
                    cfg.update(json.load(f))
        except Exception as e:
            print("config:", e)
        if cfg.get("theme") not in THEMES:
            cfg["theme"] = "Amber"
        return cfg

    def _save_cfg(self):
        try:
            self.cfg.update(lang=self.lang, projection=self.map.proj if hasattr(self, "map") else self.cfg["projection"],
                            lines=bool(self.lines_var.get()), rings=bool(self.rings_var.get()),
                            grayline=bool(self.grayline_var.get()), labels=bool(self.labels_var.get()))
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print("config save:", e)

    def _init_vars(self):
        self.lines_var = tk.BooleanVar(value=bool(self.cfg.get("lines", True)))
        self.rings_var = tk.BooleanVar(value=bool(self.cfg.get("rings", True)))
        self.grayline_var = tk.BooleanVar(value=bool(self.cfg.get("grayline", True)))
        self.labels_var = tk.BooleanVar(value=bool(self.cfg.get("labels", False)))
        self.time_var = tk.DoubleVar(value=0)
        self.search_var = tk.StringVar()
        self.upd_var = tk.BooleanVar(value=bool(self.cfg.get("check_updates", True)))

    def _style(self):
        r = self.root
        r.configure(bg=C["bg"])
        st = ttk.Style()
        try:
            st.theme_use("clam")
        except Exception:
            pass
        st.configure("TCombobox", fieldbackground=C["panel2"], background=C["btn"], foreground=C["text"],
                     arrowcolor=C["acc"], bordercolor=C["border"], lightcolor=C["panel2"],
                     darkcolor=C["panel2"], selectbackground=C["panel2"], selectforeground=C["text"])
        st.map("TCombobox", fieldbackground=[("readonly", C["panel2"])], foreground=[("readonly", C["text"])])
        st.configure("Vertical.TScrollbar", background=C["btn"], troughcolor=C["panel"],
                     bordercolor=C["panel"], arrowcolor=C["acc"])
        st.configure("Treeview", background=C["scr"], fieldbackground=C["scr"], foreground=C["text"],
                     rowheight=S(22), borderwidth=0, font=(UI, S(9)))
        st.map("Treeview", background=[("selected", C["btnhi"])], foreground=[("selected", C["acc"])])
        st.configure("Treeview.Heading", background=C["panel2"], foreground=C["dim"], borderwidth=0,
                     font=(UI, S(9), "bold"), relief="flat")
        st.map("Treeview.Heading", background=[("active", C["btn"])])
        r.option_add("*TCombobox*Listbox.background", C["panel2"])
        r.option_add("*TCombobox*Listbox.foreground", C["text"])
        r.option_add("*TCombobox*Listbox.selectBackground", C["acc"])
        r.option_add("*TCombobox*Listbox.selectForeground", "#03141c")

    # ---------- QTH
    def _resolve_home(self):
        g = grid_to_latlon(self.cfg.get("mygrid", ""))
        if self.cfg.get("use_file_grid", True) and self.file_home:
            self.home, self.home_src = self.file_home[:2], self.file_home[2]
        elif g:
            self.home, self.home_src = g, self.cfg["mygrid"].upper()
        elif self.file_home:
            self.home, self.home_src = self.file_home[:2], self.file_home[2]
        else:
            self.home, self.home_src = (52.6, 5.0), ""

    def home_label(self):
        call = self.cfg.get("mycall") or self.file_call
        return (call or self.t("Thuis", "Home")).upper()

    def fmt_dist(self, km, dec=None):
        if km is None:
            return "—"
        if self.cfg.get("units") == "mi":
            v, u = km * 0.621371, "mi"
        else:
            v, u = km, "km"
        if dec == 0 or v >= 100:
            return f"{v:,.0f} {u}".replace(",", "." if self.lang == "nl" else ",")
        return f"{v:.1f} {u}".replace(".", "," if self.lang == "nl" else ".")

    # ---------- UI
    def _build(self):
        r = self.root
        t = self.t
        r.title(f"{APP_NAME}" + (f" - {os.path.basename(self.file_path)}" if self.file_path else ""))

        # ===== kopbalk
        hdr = tk.Frame(r, bg=C["bg"])
        hdr.pack(fill="x", padx=14, pady=(10, 6))
        logo = tk.Canvas(hdr, width=S(54), height=S(54), bg=C["bg"], highlightthickness=0)
        logo.pack(side="left")
        logo.create_oval(S(2), S(2), S(52), S(52), outline=C["acc"], width=2, fill=C["panel"])
        logo.create_oval(S(12), S(12), S(42), S(42), outline=C["acc2"], width=1)
        logo.create_line(S(27), S(4), S(27), S(50), fill=_mix(C["panel"], C["acc2"], 0.6))
        logo.create_line(S(4), S(27), S(50), S(27), fill=_mix(C["panel"], C["acc2"], 0.6))
        logo.create_line(S(27), S(27), S(42), S(15), fill=C["acc"], width=2)
        logo.create_oval(S(24), S(24), S(30), S(30), fill=C["acc"], outline="")
        logo.create_oval(S(39), S(12), S(45), S(18), fill=C["acc2"], outline="")
        tt = tk.Frame(hdr, bg=C["bg"])
        tt.pack(side="left", padx=10)
        tk.Label(tt, text=APP_NAME, bg=C["bg"], fg=C["text"], font=(UI, S(22), "bold")).pack(anchor="w")
        sub = t("ADIF-logboek op de wereldkaart  ·  afstand & richting", "ADIF logbook on the world map  ·  distance & bearing")
        if self.cfg.get("mycall"):
            sub += "  ·  " + self.cfg["mycall"].upper()
        tk.Label(tt, text=sub, bg=C["bg"], fg=C["dim"], font=(UI, S(10))).pack(anchor="w")
        srow = tk.Frame(tt, bg=C["bg"])
        srow.pack(anchor="w")
        last = getattr(self, "_status_last", ("", None))
        self.status = label(srow, last[0], fg=last[1] or C["amber"], font=(UI, S(9)), bg=C["bg"])
        self.status.pack(side="left")
        self.upd_btn = FlatButton(srow, "", command=self._open_update, padx=10, pady=1,
                                  font=(UI, S(9), "bold"), accent=C["acc2"])
        if self.update_info:
            self._show_update_button()

        con = tk.Frame(hdr, bg=C["bg"])
        con.pack(side="right")
        row = tk.Frame(con, bg=C["bg"])
        row.pack(anchor="e")
        self.btn_open = FlatButton(row, t("ADIF openen", "Open ADIF"), command=self.open_dialog, padx=16, pady=6,
                                   accent=C["green"])
        self.btn_open.pack(side="left")
        self.btn_open.set_active(True, C["green"])
        if os.path.exists(CWSTATION_LOG):
            FlatButton(row, t("CW Station-logboek", "CW Station logbook"), command=lambda: self.load(CWSTATION_LOG),
                       padx=12, pady=6).pack(side="left", padx=(8, 0))
        FlatButton(row, t("Herladen", "Reload"), command=self.reload, padx=12, pady=6).pack(side="left", padx=(8, 0))
        row2 = tk.Frame(con, bg=C["bg"])
        row2.pack(anchor="e", pady=(6, 0))
        FlatButton(row2, t("Exporteren", "Export"), command=self.export_menu, padx=12, pady=4).pack(side="left")
        FlatButton(row2, t("Handleiding", "Manual"), command=self.open_manual, padx=12, pady=4).pack(side="left", padx=(6, 0))
        FlatButton(row2, t("Enquête", "Survey"), command=self.open_survey, padx=12, pady=4).pack(side="left", padx=(6, 0))
        FlatButton(row2, "⚙ " + t("Instellingen", "Settings"), command=self.show_settings,
                   padx=12, pady=4).pack(side="left", padx=(6, 0))
        clk = tk.Frame(hdr, bg=C["bg"])
        clk.pack(side="left", padx=(30, 0))
        for name, attr in ((t("LOKAAL", "LOCAL"), "clk_loc"), ("UTC", "clk_utc")):
            col = tk.Frame(clk, bg=C["bg"])
            col.pack(side="left", padx=10)
            label(col, name, fg=C["acc"], font=(UI, S(8), "bold")).pack()
            lb = tk.Label(col, text="--:--:--", bg=C["bg"], fg=C["text"], font=(MONO, S(17), "bold"), width=8)
            lb.pack()
            setattr(self, attr, lb)

        # ===== hoofdgedeelte
        main = tk.Frame(r, bg=C["bg"])
        main.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        left = tk.Frame(main, bg=C["bg"], width=S(330))
        left.pack(side="left", fill="y")
        left.pack_propagate(False)
        right = tk.Frame(main, bg=C["bg"])
        right.pack(side="left", fill="both", expand=True, padx=(10, 0))

        # --- ODX / thuis
        f, b, _ = panel(left)
        f.pack(fill="x")
        top = tk.Frame(b, bg=C["panel"])
        top.pack(fill="x")
        label(top, "ODX", fg=C["acc"], font=(UI, S(13), "bold")).pack(side="left")
        self.odx_call = label(top, "", fg=C["dim"], font=(UI, S(11)))
        self.odx_call.pack(side="right")
        self.odx_lbl = tk.Label(b, text="—", bg=C["panel"], fg=C["text"], font=(DIGIT, S(30), "bold"))
        self.odx_lbl.pack(anchor="center")
        hr = tk.Frame(b, bg=C["panel"])
        hr.pack(fill="x", pady=(2, 0))
        label(hr, t("Thuis", "Home"), font=(UI, S(9))).pack(side="left")
        self.home_lbl = label(hr, "", fg=C["acc"], font=(UI, S(10), "bold"))
        self.home_lbl.pack(side="left", padx=(6, 0))
        FlatButton(hr, t("Wijzig", "Change"), command=self.show_settings, padx=8, pady=1,
                   font=(UI, S(8), "bold")).pack(side="right")

        # --- statistiek
        f, b, _ = panel(left, t("STATISTIEK", "STATISTICS"))
        f.pack(fill="x", pady=(8, 0))
        self.stat_lbls = {}
        rows = [("qso", t("QSO's", "QSOs")), ("calls", t("Unieke calls", "Unique calls")),
                ("ctry", t("Landen", "Countries")), ("grids", t("Locatorvelden", "Grid squares")),
                ("avg", t("Gemiddelde afstand", "Average distance")), ("med", t("Mediaan", "Median")),
                ("tot", t("Totaal", "Total")), ("earth", t("Keer rond de aarde", "Times around the earth")),
                ("pfx", t("Positie uit prefix", "Position from prefix")), ("nopos", t("Zonder positie", "No position"))]
        g = tk.Frame(b, bg=C["panel"])
        g.pack(fill="x")
        for i, (k, txt) in enumerate(rows):
            label(g, txt, font=(UI, S(9))).grid(row=i, column=0, sticky="w")
            v = label(g, "—", fg=C["text"], font=(UI, S(10), "bold"))
            v.grid(row=i, column=1, sticky="e")
            self.stat_lbls[k] = v
        g.columnconfigure(1, weight=1)

        # --- afstandsverdeling
        f, b, _ = panel(left, t("AFSTANDSVERDELING", "DISTANCE DISTRIBUTION"))
        f.pack(fill="x", pady=(8, 0))
        self.dist_chart = BarChart(b, S(132))
        self.dist_chart.pack(fill="x")

        # --- per band
        # --- filter (banden + modes), onderaan links zoals de band/mode-knoppen in CW Station
        f, b, h = panel(left, "FILTER")
        f.pack(side="bottom", fill="x", pady=(8, 0))
        FlatButton(h, t("Alles", "All"), command=self.clear_filters, padx=8, pady=1,
                   font=(UI, S(8), "bold")).pack(side="right")
        self.band_box = tk.Frame(b, bg=C["panel"])
        self.band_box.pack(fill="x")
        self.mode_box = tk.Frame(b, bg=C["panel"])
        self.mode_box.pack(fill="x", pady=(6, 0))

        f, b, _ = panel(left, t("PER BAND", "BY BAND"))
        f.pack(fill="both", expand=True, pady=(8, 0))
        self.band_chart = BarChart(b, S(60))
        self.band_chart.pack(fill="both", expand=True)

        # --- kaart
        f, b, h = panel(right, t("WERELDKAART", "WORLD MAP"))
        f.pack(fill="both", expand=True)
        self.map_head = h
        self.map_info = label(h, "", fg=C["dim"], font=(UI, S(9), "bold"))
        self.map_info.pack(side="left", padx=(8, 0))
        bar = tk.Frame(h, bg=C["panel"])
        bar.pack(side="right")
        fb = (UI, S(9), "bold")
        self.btn_azi = FlatButton(bar, t("Azimutaal", "Azimuthal"), command=lambda: self.set_proj("azi"), padx=9, pady=2, font=fb)
        self.btn_eq = FlatButton(bar, t("Wereld", "World"), command=lambda: self.set_proj("eq"), padx=9, pady=2, font=fb)
        self.btn_azi.pack(side="left", padx=2)
        self.btn_eq.pack(side="left", padx=(2, 12))
        for txt, var in ((t("Lijnen", "Lines"), self.lines_var), (t("Ringen", "Rings"), self.rings_var),
                         (t("Grijslijn", "Grey line"), self.grayline_var), (t("Calls", "Calls"), self.labels_var)):
            FlatButton(bar, txt, var=var, command=self._layers_changed, padx=9, pady=2, font=fb).pack(side="left", padx=2)
        FlatButton(bar, "−", command=lambda: self.map.zoom(0.8), padx=9, pady=2, font=fb).pack(side="left", padx=(12, 2))
        FlatButton(bar, "+", command=lambda: self.map.zoom(1.25), padx=9, pady=2, font=fb).pack(side="left", padx=2)
        FlatButton(bar, t("Wereld passend", "Fit world"), command=lambda: self.map.fit_world(), padx=9, pady=2, font=fb).pack(side="left", padx=2)
        FlatButton(bar, t("QSO's passend", "Fit QSOs"), command=lambda: self.map.fit_data(), padx=9, pady=2, font=fb).pack(side="left", padx=2)
        self.map = MapView(b, self)
        self.map.pack(fill="both", expand=True)
        self._proj_buttons()

        # tijdlijn
        tl = tk.Frame(b, bg=C["panel"])
        tl.pack(fill="x", pady=(8, 0))
        label(tl, t("TIJDLIJN", "TIMELINE"), fg=C["acc"], font=(UI, S(9), "bold")).pack(side="left")
        self.play_btn = FlatButton(tl, "▶ " + t("Afspelen", "Play"), command=self.toggle_play, padx=10, pady=2, font=fb)
        self.play_btn.pack(side="left", padx=(10, 4))
        self.speed_btns = []
        for i, (txt, _) in enumerate(self.SPEEDS):
            bt = FlatButton(tl, txt, command=lambda i=i: self._set_speed(i), padx=7, pady=2, font=(UI, S(8), "bold"))
            bt.pack(side="left", padx=1)
            self.speed_btns.append(bt)
        self._set_speed(self.speed_i)
        FlatButton(tl, t("Alles tonen", "Show all"), command=self.show_all_time, padx=9, pady=2,
                   font=fb).pack(side="right", padx=(6, 0))
        self.time_lbl = label(tl, "", fg=C["text"], font=(MONO, S(10), "bold"), width=30, anchor="e")
        self.time_lbl.pack(side="right")
        self.slider = Slider(tl, self.time_var, 0, 1, command=self._slider_moved, width=S(300), height=S(20))
        self.slider.pack(side="left", fill="x", expand=True, padx=10)

        # periode: alles / jaar / maand / dag
        pr = tk.Frame(b, bg=C["panel"])
        pr.pack(fill="x", pady=(6, 0))
        label(pr, t("PERIODE", "PERIOD"), fg=C["acc"], font=(UI, S(9), "bold")).pack(side="left")
        self.period_btns = {}
        for m, txt in ((None, t("Alles", "All")), ("Y", t("Jaar", "Year")), ("M", t("Maand", "Month")), ("D", t("Dag", "Day"))):
            bt = FlatButton(pr, txt, command=lambda m=m: self.set_period_mode(m), padx=9, pady=2, font=fb)
            bt.pack(side="left", padx=(10 if m is None else 2, 0))
            self.period_btns[m] = bt
        FlatButton(pr, "◀", command=lambda: self.step_period(-1), padx=8, pady=2, font=fb).pack(side="left", padx=(14, 2))
        self.period_combo = ttk.Combobox(pr, state="disabled", width=26, font=(UI, S(10)))
        self.period_combo.pack(side="left", padx=2)
        self.period_combo.bind("<<ComboboxSelected>>", self._period_pick)
        FlatButton(pr, "▶", command=lambda: self.step_period(1), padx=8, pady=2, font=fb).pack(side="left", padx=2)
        self.period_info = label(pr, "", fg=C["dim"], font=(UI, S(9), "bold"))
        self.period_info.pack(side="left", padx=(12, 0))
        self._period_widgets()

        # --- onderste rij: tabel + geselecteerde station
        bottom = tk.Frame(right, bg=C["bg"], height=S(270))
        bottom.pack(fill="x", pady=(10, 0))
        bottom.pack_propagate(False)
        f, b, h = panel(bottom, t("VERBINDINGEN", "CONTACTS"))
        f.pack(side="left", fill="both", expand=True)
        self.tbl_info = label(h, "", font=(UI, S(9), "bold"))
        self.tbl_info.pack(side="left", padx=(8, 0))
        se = entry(h, self.search_var, 14)
        se.pack(side="right")
        label(h, t("Zoek call", "Find call"), font=(UI, S(9))).pack(side="right", padx=(0, 6))
        trace(se, self.search_var, self._search_changed)
        cols = [("date", t("Datum", "Date"), 84), ("time", "UTC", 50), ("call", "Call", 92), ("band", "Band", 54),
                ("mode", "Mode", 58), ("grid", t("Locator", "Locator"), 70), ("dist", t("Afstand", "Distance"), 84),
                ("brg", t("Richting", "Bearing"), 64), ("ctry", t("Land", "Country"), 150)]
        tf = tk.Frame(b, bg=C["panel"])
        tf.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(tf, columns=[c[0] for c in cols], show="headings", selectmode="browse")
        for key, txt, wd in cols:
            self.tree.heading(key, text=txt, command=lambda k=key: self._sort_by(k))
            self.tree.column(key, width=S(wd), anchor="e" if key in ("dist", "brg") else "w",
                             stretch=key == "ctry")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._tree_select)
        self.tree.bind("<Double-1>", lambda e: self.sel is not None and self.map.center_on(self.qsos[self.sel]))
        self.tree.tag_configure("pfx", foreground=C["dim"])
        self.tree.bind("<Button-3>", self._tree_right)

        f, b, h = panel(bottom, "STATION")
        f.pack(side="left", fill="y", padx=(10, 0))
        f.configure(width=S(330))
        f.pack_propagate(False)
        self.st_call = tk.Label(b, text="—", bg=C["panel"], fg=C["acc"], font=(UI, S(20), "bold"), anchor="w")
        self.st_call.pack(fill="x")
        self.st_ctry = label(b, "", fg=C["text"], font=(UI, S(10)), anchor="w")
        self.st_ctry.pack(fill="x")
        dr = tk.Frame(b, bg=C["panel"])
        dr.pack(fill="x", pady=(4, 2))
        self.st_dist = tk.Label(dr, text="", bg=C["panel"], fg=C["text"], font=(DIGIT, S(18), "bold"))
        self.st_dist.pack(side="left")
        self.st_brg = label(dr, "", fg=C["acc2"], font=(UI, S(10), "bold"))
        self.st_brg.pack(side="right")
        g = tk.Frame(b, bg=C["panel"])
        g.pack(fill="x")
        self.st_rows = {}
        for i, (k, txt) in enumerate((("when", t("Datum/tijd", "Date/time")), ("bm", "Band / mode"),
                                      ("rst", "RST s / r"), ("grid", "Locator"), ("name", t("Naam / QTH", "Name / QTH")))):
            label(g, txt, font=(UI, S(8))).grid(row=i, column=0, sticky="w")
            v = label(g, "", fg=C["text"], font=(UI, S(9), "bold"), anchor="e")
            v.grid(row=i, column=1, sticky="e")
            self.st_rows[k] = v
            if k == "grid":
                FlatButton(g, "✎", command=self.edit_grid, padx=6, pady=0,
                           font=(UI, S(8), "bold")).grid(row=i, column=2, sticky="e", padx=(4, 0))
        g.columnconfigure(1, weight=1)
        br = tk.Frame(b, bg=C["panel"])
        br.pack(fill="x", side="bottom")
        FlatButton(br, "QRZ.com", command=self.qrz, padx=9, pady=2, font=fb).pack(side="left")
        FlatButton(br, t("Toon op kaart", "Show on map"), command=lambda: self.sel is not None and self.map.center_on(self.qsos[self.sel]),
                   padx=9, pady=2, font=fb).pack(side="left", padx=6)

        r.bind("<Control-o>", lambda e: self.open_dialog())
        r.bind("<Control-O>", lambda e: self.open_dialog())
        r.bind("<F5>", lambda e: self.reload())
        r.bind("<space>", lambda e: None if isinstance(e.widget, tk.Entry) else self.toggle_play())
        if self.qsos:
            self._rebuild_filters()
        self._refresh_all(redraw=False)
        if not self.qsos:
            self._set_status(t("open een ADIF-bestand (.adi) om je verbindingen te zien", "open an ADIF file (.adi) to see your contacts"), C["amber"])

    def _proj_buttons(self):
        self.btn_azi.set_active(self.map.proj == "azi")
        self.btn_eq.set_active(self.map.proj == "eq")

    def set_proj(self, p):
        self.map.set_projection(p)
        self._proj_buttons()
        self._paths = {}
        self._save_cfg()

    def _layers_changed(self):
        self.map.redraw()
        self._save_cfg()

    def _set_status(self, txt, color=None):
        self._status_last = (txt, color)               # blijft staan na opnieuw opbouwen (schaal/thema)
        if self.status:
            self.status.config(text=txt, fg=color or C["dim"])

    def _clock(self):
        now = dtm.datetime.now()
        try:
            self.clk_loc.config(text=now.strftime("%H:%M:%S"))
            self.clk_utc.config(text=dtm.datetime.now(dtm.timezone.utc).strftime("%H:%M:%S"))
        except tk.TclError:
            pass
        self.root.after(1000 - now.microsecond // 1000 + 5, self._clock)

    def _grayline_tick(self):
        if self.grayline_var.get() and not self.playing:
            self.map.redraw()
        self.root.after(60000, self._grayline_tick)

    def _on_root_configure(self, ev):
        if ev.widget is not self.root:
            return
        if self._resize_job:
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(500, self._apply_scale)

    def _apply_scale(self):
        global SCALE
        self._resize_job = None
        w, h = self.root.winfo_width(), self.root.winfo_height()
        if w < 200 or h < 200:
            return
        new = scale_for(w, h)
        if abs(new - SCALE) >= 0.08:
            SCALE = new
            self.rebuild()

    def rebuild(self):
        view = (self.map.proj, self.map.k, self.map.cu, self.map.cv) if hasattr(self, "map") else None
        for w in self.root.winfo_children():
            if not isinstance(w, tk.Toplevel):
                w.destroy()
        C.update(THEMES.get(self.cfg.get("theme", "Amber"), THEMES["Amber"]))
        M.update(MAP_STYLES.get(self.cfg.get("map_style", "bright"), MAP_STYLES["bright"]))
        self.status = None
        self._paths = {}
        self._style()
        self._build()
        if view and view[0] == self.map.proj and view[1] is not None:
            self.map.pending_view = view[1:]
        if self.selected_qso() and self.tree.exists(str(self.sel)):
            self.root.after(100, lambda: self.select(self.sel))

    # ---------- laden
    def open_dialog(self):
        d = os.path.dirname(self.file_path) if self.file_path else os.path.expanduser("~")
        p = filedialog.askopenfilename(parent=self.root, initialdir=d, title=self.t("ADIF-bestand openen", "Open ADIF file"),
                                       filetypes=[("ADIF", "*.adi *.adif *.ADI *.ADIF"), (self.t("Alle bestanden", "All files"), "*.*")])
        if p:
            self.load(p)

    def reload(self):
        if self.file_path:
            self.load(self.file_path)

    def load(self, path, quiet=False):
        t = self.t
        if path.lower().endswith(".adx"):
            messagebox.showwarning(APP_NAME, t("ADX (XML) wordt niet ondersteund. Exporteer je log als .adi.",
                                                "ADX (XML) is not supported. Export your log as .adi."), parent=self.root)
            return
        try:
            head, recs = read_adif(path)
        except Exception as e:
            messagebox.showerror(APP_NAME, f"{t('Kan bestand niet lezen', 'Cannot read file')}:\n{e}", parent=self.root)
            return
        self.file_path = path
        self.cfg["last_file"] = path
        self.file_home, self.file_call = None, ""
        qsos, nopos = [], []
        for rec in recs:
            call = (rec.get("CALL") or "").upper().strip()
            if not call:
                continue
            if not self.file_home:
                la, lo = adif_latlon(rec.get("MY_LAT")), adif_latlon(rec.get("MY_LON"))
                if la is not None and lo is not None:
                    self.file_home = (la, lo, latlon_to_grid(la, lo))
                else:
                    g = grid_to_latlon(rec.get("MY_GRIDSQUARE"))
                    if g:
                        self.file_home = (g[0], g[1], rec["MY_GRIDSQUARE"].upper())
            if not self.file_call:
                self.file_call = (rec.get("STATION_CALLSIGN") or rec.get("OPERATOR") or "").upper()
            q = self._make_qso(rec, call)
            (qsos if q["lat"] is not None else nopos).append(q)
        qsos.sort(key=lambda q: q["sortkey"])
        for i, q in enumerate(qsos):
            q["i"] = i
        self.qsos, self.nopos = qsos, nopos
        self._resolve_home()
        self._compute_dist()
        self.sel = None
        self.cursor = None
        self.playing = False
        if not quiet:
            self.period_mode, self.period_val = None, ""
        self._paths = {}
        self.map._cache = {}
        self._vis_cache = None
        self._save_cfg()
        self.root.title(f"{APP_NAME} - {os.path.basename(path)}")
        self._rebuild_filters()
        self._period_widgets()
        self._refresh_all(redraw=False)
        if quiet:
            return
        self.map.fit_world()
        n_pfx = sum(1 for q in qsos if q["src"] == "pfx")
        n_ed = sum(1 for q in qsos if q.get("edited"))
        msg = t(f"{os.path.basename(path)}: {len(qsos) + len(nopos)} QSO's geladen", f"{os.path.basename(path)}: {len(qsos) + len(nopos)} QSOs loaded")
        if n_pfx:
            msg += t(f"  ·  {n_pfx} zonder locator (positie uit prefix)", f"  ·  {n_pfx} without locator (position from prefix)")
        if n_ed:
            msg += t(f"  ·  {n_ed} aangepaste locator(s)", f"  ·  {n_ed} edited locator(s)")
        if not self.home_src:
            msg += t("  ·  stel je eigen locator in bij Instellingen!", "  ·  set your own locator in Settings!")
        self._set_status(msg, C["green"] if self.home_src else C["amber"])
        if not self.home_src:
            self.root.after(300, self.show_settings)

    def _make_qso(self, rec, call):
        date, tm = (rec.get("QSO_DATE") or "")[:8], (rec.get("TIME_ON") or "")[:6]
        try:
            dt = dtm.datetime.strptime(date + tm.ljust(6, "0"), "%Y%m%d%H%M%S")
        except ValueError:
            dt = None
        lat = lon = None
        src = None
        edited = False
        fix = self._corr_map().get(self._qkey(call, date, tm))
        if fix and grid_to_latlon(fix):
            rec = dict(rec)
            rec["GRIDSQUARE"] = fix
            rec.pop("LAT", None)
            rec.pop("LON", None)
            edited = True
        la, lo = adif_latlon(rec.get("LAT")), adif_latlon(rec.get("LON"))
        grid = (rec.get("GRIDSQUARE") or "").strip()
        if la is not None and lo is not None:
            lat, lon, src = la, lo, "ll"
        else:
            g = grid_to_latlon(grid) or grid_to_latlon((rec.get("VUCC_GRIDS") or "").split(",")[0])
            if g:
                lat, lon, src = g[0], g[1], "grid"
        pf = prefixes.lookup(call)
        if lat is None and pf:
            lat, lon, src = pf[1], pf[2], "pfx"
        ctry = (rec.get("COUNTRY") or "").strip().title() or (pf[0] if pf else "")
        return dict(call=call, date=date, time=tm, dt=dt, sortkey=(date, tm, call),
                    band=band_of(rec), mode=(rec.get("SUBMODE") or rec.get("MODE") or "?").upper(),
                    grid=grid.upper()[:4] + grid.lower()[4:6] + grid[6:8], lat=lat, lon=lon, src=src, ctry=ctry,
                    rst_s=rec.get("RST_SENT", ""), rst_r=rec.get("RST_RCVD", ""), name=rec.get("NAME", ""),
                    qth=rec.get("QTH", ""), rec=rec, dist=None, brg=None, i=-1, edited=edited)

    def _compute_dist(self):
        h = self.home
        for q in self.qsos:
            q["dist"], q["brg"] = dist_brg(h[0], h[1], q["lat"], q["lon"])

    # ---------- selectie / filter
    def visible(self):
        if self._vis_cache is not None:
            return self._vis_cache
        s = self.search
        out = []
        lo, hi = self.span()
        lim = self.cursor if self.cursor is not None else hi
        for q in self.qsos[lo:lim]:
            if self.band_filter and q["band"] not in self.band_filter:
                continue
            if self.mode_filter and q["mode"] not in self.mode_filter:
                continue
            if s and not q["call"].startswith(s):
                continue
            out.append(q)
        self._vis_cache = out
        return out

    def _invalidate(self):
        self._vis_cache = None

    # ---------- periode (jaar / maand / dag)
    MONTHS_NL = ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"]
    MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    MONTHS_NL_LONG = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september",
                      "oktober", "november", "december"]
    MONTHS_EN_LONG = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                      "October", "November", "December"]

    def span(self):
        """Indexbereik (lo, hi) van de QSO's in de gekozen periode. De QSO's zijn op datum gesorteerd,
        dus een periode is altijd een aaneengesloten stuk."""
        n = len(self.qsos)
        if not self.period_mode or not self.period_val:
            return 0, n
        import bisect
        if getattr(self, "_dates_for", None) is not self.qsos:
            self._dates = [q["date"] for q in self.qsos]
            self._dates_for = self.qsos
        k = self.period_val
        return bisect.bisect_left(self._dates, k), bisect.bisect_right(self._dates, k + "99999999"[:8 - len(k)])

    def periods(self, mode):
        """Beschikbare periodes in de log: [(sleutel, aantal QSO's)], oud naar nieuw."""
        ln = {"Y": 4, "M": 6, "D": 8}[mode]
        cnt = {}
        for q in self.qsos:
            if len(q["date"]) >= ln:
                k = q["date"][:ln]
                cnt[k] = cnt.get(k, 0) + 1
        return sorted(cnt.items())

    def period_name(self, k, long=False):
        nl = self.lang == "nl"
        if len(k) == 4:
            return k
        m = int(k[4:6]) - 1
        if not 0 <= m < 12:
            return k
        if len(k) == 6:
            names = (self.MONTHS_NL_LONG if nl else self.MONTHS_EN_LONG) if long else (self.MONTHS_NL if nl else self.MONTHS_EN)
            return f"{names[m]} {k[:4]}"
        try:
            wd = dtm.date(int(k[:4]), m + 1, int(k[6:8])).weekday()
        except ValueError:
            return k
        days = ["ma", "di", "wo", "do", "vr", "za", "zo"] if nl else ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return f"{days[wd]} {int(k[6:8])} {(self.MONTHS_NL if nl else self.MONTHS_EN)[m]} {k[:4]}"

    def set_period_mode(self, mode):
        if mode == self.period_mode:
            return
        old = self.period_val
        self.period_mode = mode
        if mode:
            avail = [k for k, _ in self.periods(mode)]
            if not avail:
                self.period_mode, self.period_val = None, ""
            else:
                # sluit aan bij de vorige keuze (bijv. jaar 2024 -> eerste maand van 2024), anders de nieuwste
                q = self.selected_qso()
                ref = old or (q["date"] if q else "")
                ln = {"Y": 4, "M": 6, "D": 8}[mode]
                hit = [k for k in avail if ref and (k.startswith(ref[:ln]) or ref.startswith(k))]
                self.period_val = hit[-1] if hit and len(ref) >= ln else (hit[0] if hit else avail[-1])
        else:
            self.period_val = ""
        self._period_changed()

    def step_period(self, d):
        if not self.period_mode:
            self.set_period_mode("Y")
            return
        avail = [k for k, _ in self.periods(self.period_mode)]
        if not avail:
            return
        i = avail.index(self.period_val) if self.period_val in avail else len(avail) - 1
        self.period_val = avail[min(max(i + d, 0), len(avail) - 1)]
        self._period_changed()

    def _period_pick(self, ev=None):
        i = self.period_combo.current()
        if self.period_mode and i >= 0:
            self.period_val = self._period_keys[i]
            self._period_changed()

    def _period_changed(self):
        self.playing = False
        self.cursor = None
        try:
            self.play_btn.config(text="▶ " + self.t("Afspelen", "Play"))
        except tk.TclError:
            pass
        self._period_widgets()
        self._refresh_all()

    def _period_widgets(self):
        if not hasattr(self, "period_btns"):
            return
        for m, b in self.period_btns.items():
            b.set_active(m == self.period_mode)
        if self.period_mode:
            items = self.periods(self.period_mode)
            self._period_keys = [k for k, _ in items]
            self.period_combo.config(values=[f"{self.period_name(k, True)}   ({n})" for k, n in items], state="readonly")
            if self.period_val in self._period_keys:
                self.period_combo.current(self._period_keys.index(self.period_val))
        else:
            self._period_keys = []
            self.period_combo.set("")
            self.period_combo.config(values=[], state="disabled")

    def odx(self):
        vis = self.visible()
        return max(vis, key=lambda q: q["dist"]) if vis else None

    def at_same_place(self, q):
        return [o for o in self.visible() if abs(o["lat"] - q["lat"]) < 1e-6 and abs(o["lon"] - q["lon"]) < 1e-6]

    def path_for(self, q, mv):
        key = (round(q["lat"], 3), round(q["lon"], 3))
        if key not in self._paths:
            h = self.home
            if mv.proj == "azi":
                a, b = mv.project(*h), mv.project(q["lat"], q["lon"])
                self._paths[key] = [[a[0], a[1], b[0], b[1]]] if a and b else []
            else:
                n = max(6, int((q["dist"] or 0) / 300))
                self._paths[key] = mv.project_path(gc_points(h[0], h[1], q["lat"], q["lon"], n))
        return self._paths[key]

    def selected_qso(self):
        return self.qsos[self.sel] if self.sel is not None and self.sel < len(self.qsos) else None

    def select(self, i, from_map=False):
        self.sel = i
        q = self.qsos[i]
        t = self.t
        self.st_call.config(text=q["call"])
        self.st_ctry.config(text=(q["ctry"] or "—") + ("  ≈" if q["src"] == "pfx" else ""))
        self.st_dist.config(text=self.fmt_dist(q["dist"]))
        lp = (q["brg"] + 180) % 360
        self.st_brg.config(text=t(f"kort {q['brg']:.0f}°  ·  lang {lp:.0f}°", f"SP {q['brg']:.0f}°  ·  LP {lp:.0f}°"))
        when = f"{q['date'][:4]}-{q['date'][4:6]}-{q['date'][6:8]}  {q['time'][:2]}:{q['time'][2:4]}" if q["date"] else "—"
        self.st_rows["when"].config(text=when)
        self.st_rows["bm"].config(text=f"{q['band']} / {q['mode']}")
        self.st_rows["rst"].config(text=f"{q['rst_s'] or '—'} / {q['rst_r'] or '—'}")
        src = {"ll": "LAT/LON", "grid": "", "pfx": t("prefix ≈", "prefix ≈")}.get(q["src"], "")
        if q.get("edited"):
            src = t("aangepast", "edited")
        self.st_rows["grid"].config(text=(q["grid"] or latlon_to_grid(q["lat"], q["lon"], 4)) + (f"  ({src})" if src else ""))
        nq = " / ".join(x for x in (q["name"], q["qth"]) if x)
        self.st_rows["name"].config(text=nq[:34] or "—")
        if from_map or not self.tree.selection() or self.tree.selection()[0] != str(i):
            if self.tree.exists(str(i)):
                self.tree.selection_set(str(i))
                self.tree.see(str(i))
        self.map.redraw()

    def _tree_right(self, ev):
        """Rechtsklik op een regel: selecteren en locator aanpassen."""
        iid = self.tree.identify_row(ev.y)
        if iid:
            self.select(int(iid))
            self.edit_grid()

    def _tree_select(self, ev):
        s = self.tree.selection()
        if s and (self.sel is None or s[0] != str(self.sel)):
            self.select(int(s[0]))

    def _search_changed(self):
        self.search = self.search_var.get().strip().upper()
        self._invalidate()
        self._refresh_all()

    def _rebuild_filters(self):
        for box in (self.band_box, self.mode_box):
            for w in box.winfo_children():
                w.destroy()
        bands = sorted({q["band"] for q in self.qsos}, key=lambda b: BAND_ORDER.index(b) if b in BAND_ORDER else 99)
        modes = sorted({q["mode"] for q in self.qsos})
        self.band_filter &= set(bands)
        self.mode_filter &= set(modes)
        self.band_btns, self.mode_btns = {}, {}
        f = (UI, S(9), "bold")
        for box, items, store, flt in ((self.band_box, bands, self.band_btns, "band"),
                                       (self.mode_box, modes, self.mode_btns, "mode")):
            rowf = None
            for i, it in enumerate(items):
                if i % 5 == 0:
                    rowf = tk.Frame(box, bg=C["panel"])
                    rowf.pack(fill="x", pady=1)
                bt = FlatButton(rowf, it.replace("m", "") if flt == "band" and it.endswith("m") and it[:-1].replace(".", "").isdigit() else it,
                                command=lambda it=it, flt=flt: self._toggle_filter(flt, it), width=4, padx=6, pady=3, font=f,
                                accent=BAND_COL.get(it, C["acc"]) if flt == "band" else C["acc"])
                bt.pack(side="left", padx=1)
                store[it] = bt
        self._filter_buttons()

    def _filter_buttons(self):
        for it, bt in getattr(self, "band_btns", {}).items():
            bt.set_active(it in self.band_filter)
        for it, bt in getattr(self, "mode_btns", {}).items():
            bt.set_active(it in self.mode_filter)

    def _toggle_filter(self, kind, it):
        s = self.band_filter if kind == "band" else self.mode_filter
        s.symmetric_difference_update({it})
        self._filter_buttons()
        self._invalidate()
        self._refresh_all()

    def clear_filters(self):
        self.band_filter.clear()
        self.mode_filter.clear()
        self.search_var.set("")
        self._filter_buttons()
        self._invalidate()
        self._refresh_all()

    # ---------- verversen
    def _refresh_all(self, redraw=True):
        self._invalidate()
        self._update_stats()
        self._fill_table()
        self._update_timeline_label()
        try:
            self.home_lbl.config(text=f"{(self.home_src or self.t('niet ingesteld', 'not set'))}  ·  {self.home_label()}")
        except tk.TclError:
            pass
        if redraw:
            self.map.redraw()

    def _update_stats(self):
        vis = self.visible()
        if hasattr(self, "period_info"):
            if self.period_mode and self.period_val:
                lo, hi = self.span()
                days = len({q["date"] for q in self.qsos[lo:hi]})
                self.period_info.config(text=self.t(f"{hi - lo} QSO's op {days} dag(en)", f"{hi - lo} QSOs on {days} day(s)"))
            else:
                self.period_info.config(text=self.t("hele log", "whole log"))
        t = self.t
        L = self.stat_lbls
        n_nopos = len(self.nopos)
        if not vis:
            for k, v in L.items():
                v.config(text="—")
            L["nopos"].config(text=str(n_nopos) if n_nopos else "—")
            self.odx_lbl.config(text="—")
            self.odx_call.config(text="")
            self.dist_chart.set([])
            self.band_chart.set([])
            self.map_info.config(text="")
            return
        ds = sorted(q["dist"] for q in vis)
        tot = sum(ds)
        o = max(vis, key=lambda q: q["dist"])
        nl = self.lang == "nl"
        fmt_n = (lambda v: f"{v:,}".replace(",", ".")) if nl else (lambda v: f"{v:,}")
        L["qso"].config(text=fmt_n(len(vis)))
        L["calls"].config(text=fmt_n(len({q["call"] for q in vis})))
        L["ctry"].config(text=str(len({q["ctry"] for q in vis if q["ctry"]})))
        L["grids"].config(text=str(len({q["grid"][:4] for q in vis if len(q["grid"]) >= 4})))
        L["avg"].config(text=self.fmt_dist(tot / len(vis)))
        L["med"].config(text=self.fmt_dist(ds[len(ds) // 2]))
        L["tot"].config(text=self.fmt_dist(tot, 0))
        L["earth"].config(text=(f"{tot / 40075.0:.1f}".replace(".", ",") if nl else f"{tot / 40075.0:.1f}") + "×")
        L["pfx"].config(text=str(sum(1 for q in vis if q["src"] == "pfx")))
        L["nopos"].config(text=str(n_nopos))
        self.odx_lbl.config(text=self.fmt_dist(o["dist"], 0))
        self.odx_call.config(text=f"{o['call']}  ·  {o['band']}")
        bins = [0] * (len(DIST_BINS) - 1)
        for d in ds:
            for j in range(len(bins)):
                if DIST_BINS[j] <= d < DIST_BINS[j + 1]:
                    bins[j] += 1
                    break
        mi = self.cfg.get("units") == "mi"

        def bl(a, b):
            f = 0.621371 if mi else 1.0
            fk = lambda v: f"{v * f / 1000:.1f}".rstrip("0").rstrip(".").replace(".", "," if nl else ".") + "k" if v * f >= 1000 else f"{v * f:.0f}"
            return f"{fk(a)}+" if b > 1e8 else f"{fk(a)}–{fk(b)}"
        rows = [(bl(DIST_BINS[j], DIST_BINS[j + 1]), bins[j], _mix(C["acc"], C["acc2"], j / (len(bins) - 1)))
                for j in range(len(bins))]
        self.dist_chart.set(rows)
        cnt = {}
        for q in vis:
            cnt[q["band"]] = cnt.get(q["band"], 0) + 1
        bands = sorted(cnt, key=lambda b: BAND_ORDER.index(b) if b in BAND_ORDER else 99)
        self.band_chart.set([(b, cnt[b], BAND_COL.get(b, "#8aa0b0")) for b in bands])
        per = f"  ·  {self.period_name(self.period_val, True)}" if self.period_mode and self.period_val else ""
        self.map_info.config(text=f"·  {fmt_n(len(vis))} {self.t("QSO's", "QSOs")}{per}  ·  {self.t('thuis', 'home')} {self.home_src or '?'}")

    def _fill_table(self):
        tr = self.tree
        tr.delete(*tr.get_children())
        vis = list(self.visible())
        key, rev = self._sort
        kf = {"dt": lambda q: q["sortkey"], "date": lambda q: q["sortkey"], "time": lambda q: q["time"],
              "call": lambda q: q["call"], "band": lambda q: BAND_ORDER.index(q["band"]) if q["band"] in BAND_ORDER else 99,
              "mode": lambda q: q["mode"], "grid": lambda q: q["grid"], "dist": lambda q: q["dist"],
              "brg": lambda q: q["brg"], "ctry": lambda q: q["ctry"]}[key]
        vis.sort(key=kf, reverse=rev)
        for q in vis:
            d = q["date"]
            tr.insert("", "end", iid=str(q["i"]), tags=("pfx",) if q["src"] == "pfx" else (),
                      values=(f"{d[:4]}-{d[4:6]}-{d[6:8]}" if d else "", f"{q['time'][:2]}:{q['time'][2:4]}" if q["time"] else "",
                              q["call"], q["band"], q["mode"],
                              ("✎ " + q["grid"]) if q.get("edited") else (q["grid"] or ("≈ " + latlon_to_grid(q["lat"], q["lon"], 4))),
                              self.fmt_dist(q["dist"], 0), f"{q['brg']:.0f}°", q["ctry"]))
        self.tbl_info.config(text=f"·  {len(vis)}" + (self.t(f"  ·  {len(self.nopos)} zonder positie", f"  ·  {len(self.nopos)} without position") if self.nopos else ""))
        if self.sel is not None and tr.exists(str(self.sel)):
            tr.selection_set(str(self.sel))

    def _sort_by(self, key):
        k, rev = self._sort
        self._sort = (key, not rev if k == key else key in ("dist", "date", "dt"))
        self._fill_table()

    # ---------- tijdlijn
    def _set_speed(self, i):
        self.speed_i = i
        for j, b in enumerate(self.speed_btns):
            b.set_active(j == i)

    def _update_timeline_label(self):
        lo, hi = self.span()
        self.slider.set_range(lo, max(hi, lo + 1))
        c = hi if self.cursor is None else self.cursor
        self.time_var.set(c)
        if hi <= lo:
            self.time_lbl.config(text="")
            return
        q = self.qsos[max(c - 1, lo)]
        d = q["date"]
        ds = f"{d[:4]}-{d[4:6]}-{d[6:8]}" if d else "????-??-??"
        self.time_lbl.config(text=f"{ds}   {c - lo}/{hi - lo}")

    def _slider_moved(self, final):
        lo, hi = self.span()
        c = int(round(self.time_var.get()))
        self.cursor = None if c >= hi else max(c, lo)
        if final:
            self._refresh_all()
        else:
            self._invalidate()
            self._update_timeline_label()
            self.map.schedule_redraw(60)

    def show_all_time(self):
        self.playing = False
        self.play_btn.config(text="▶ " + self.t("Afspelen", "Play"))
        self.cursor = None
        self._refresh_all()

    def toggle_play(self):
        if not self.qsos:
            return
        self.playing = not self.playing
        self.play_btn.config(text=("⏸ " + self.t("Pauze", "Pause")) if self.playing else ("▶ " + self.t("Afspelen", "Play")))
        if self.playing:
            if self.cursor is None:
                self.cursor = self.span()[0]
                self._refresh_all()
            self._play_t0 = None
            self._play_frac = 0.0
            self.root.after(40, self._play_tick)
        else:
            self._refresh_all()

    def _play_tick(self):
        if not self.playing:
            return
        n = self.span()[1]
        self._play_frac += self.SPEEDS[self.speed_i][1] * 0.05
        step = int(self._play_frac)
        self._play_frac -= step
        if step:
            old = self.cursor if self.cursor is not None else self.span()[0]
            self.cursor = min(old + step, n)
            self._invalidate()
            self._draw_new(range(old, self.cursor))
            self._update_timeline_label()
            if self.cursor % 10 < step or self.cursor >= n:
                self._update_stats()
        if self.cursor is not None and self.cursor >= n:
            self.playing = False
            self.cursor = None
            self.play_btn.config(text="▶ " + self.t("Afspelen", "Play"))
            self._refresh_all()
            return
        self.root.after(50, self._play_tick)

    def _draw_new(self, idx):
        """Tijdens afspelen: alleen nieuwe verbindingen tekenen (snel) met een korte 'flits'."""
        mv = self.map
        rr = S(3.2)
        for i in idx:
            q = self.qsos[i]
            if self.band_filter and q["band"] not in self.band_filter:
                continue
            if self.mode_filter and q["mode"] not in self.mode_filter:
                continue
            if self.search and not q["call"].startswith(self.search):
                continue
            col = BAND_COL.get(q["band"], "#8aa0b0")
            if self.lines_var.get():
                for seg in self.path_for(q, mv):
                    mv.create_line(mv.tx(seg), fill=_mix(M["sea"], col, M["line"]))
            p = mv.project(q["lat"], q["lon"])
            if not p:
                continue
            x, y = mv.X(p[0]), mv.Y(p[1])
            iid = mv.create_oval(x - rr, y - rr, x + rr, y + rr, fill=col, outline="#03131b")
            mv._items[iid] = q["i"]
            fl = mv.create_oval(x - rr * 4, y - rr * 4, x + rr * 4, y + rr * 4, outline=col, width=2)
            mv.after(350, lambda fl=fl: mv.delete(fl))

    # ---------- export
    def export_menu(self):
        if not self.qsos:
            self._set_status(self.t("geen gegevens om te exporteren", "no data to export"), C["amber"])
            return
        m = tk.Menu(self.root, tearoff=0, bg=C["panel2"], fg=C["text"], activebackground=C["acc"],
                    activeforeground="#03131b", font=(UI, S(10)))
        m.add_command(label=self.t("ADIF met afstand (DISTANCE) en locator…", "ADIF with distance (DISTANCE) and grid…"),
                      command=self.export_adif)
        m.add_command(label=self.t("CSV voor Excel…", "CSV for Excel…"), command=self.export_csv)
        m.add_command(label=self.t("Kaart als PostScript (.eps)…", "Map as PostScript (.eps)…"), command=self.export_eps)
        x, y = self.root.winfo_pointerx(), self.root.winfo_pointery()
        m.tk_popup(x, y)

    def _ask_save(self, ext, desc):
        base = os.path.splitext(os.path.basename(self.file_path or "qsomap"))[0]
        return filedialog.asksaveasfilename(parent=self.root, defaultextension=ext, initialfile=f"{base}_qsomap{ext}",
                                            filetypes=[(desc, "*" + ext)])

    def export_adif(self):
        p = self._ask_save(".adi", "ADIF")
        if not p:
            return
        recs = []
        for q in self.visible():
            r = dict(q["rec"])
            r["DISTANCE"] = f"{q['dist']:.0f}"
            if not r.get("GRIDSQUARE") and q["src"] != "pfx":
                r["GRIDSQUARE"] = latlon_to_grid(q["lat"], q["lon"])
            if not r.get("MY_GRIDSQUARE") and self.home_src:
                r["MY_GRIDSQUARE"] = latlon_to_grid(*self.home)
            recs.append(r)
        write_adif(p, recs)
        self._set_status(self.t(f"{len(recs)} QSO's opgeslagen in {os.path.basename(p)}", f"{len(recs)} QSOs saved to {os.path.basename(p)}"), C["green"])

    def export_csv(self):
        p = self._ask_save(".csv", "CSV")
        if not p:
            return
        sep = ";" if self.lang == "nl" else ","
        with open(p, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=sep)
            w.writerow(["date", "time_utc", "call", "band", "mode", "gridsquare", "lat", "lon", "position_source",
                        "distance_km", "bearing_deg", "long_path_deg", "country", "rst_sent", "rst_rcvd", "name", "qth"])
            for q in self.visible():
                num = (lambda v: f"{v}".replace(".", ",")) if sep == ";" else str
                w.writerow([q["date"], q["time"], q["call"], q["band"], q["mode"], q["grid"], num(round(q["lat"], 4)),
                            num(round(q["lon"], 4)), q["src"], num(round(q["dist"], 1)), num(round(q["brg"], 1)),
                            num(round((q["brg"] + 180) % 360, 1)), q["ctry"], q["rst_s"], q["rst_r"], q["name"], q["qth"]])
        self._set_status(self.t(f"CSV opgeslagen: {os.path.basename(p)}", f"CSV saved: {os.path.basename(p)}"), C["green"])

    def export_eps(self):
        p = self._ask_save(".eps", "PostScript")
        if not p:
            return
        self.map.postscript(file=p, colormode="color")
        self._set_status(self.t(f"Kaart opgeslagen: {os.path.basename(p)}", f"Map saved: {os.path.basename(p)}"), C["green"])

    # ---------- diversen
    # ---------- locator aanpassen
    def _load_corr(self):
        try:
            with open(CORR_FILE, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_corr(self):
        try:
            os.makedirs(DATA_DIR, exist_ok=True)
            with open(CORR_FILE, "w", encoding="utf-8") as f:
                json.dump(self.corr, f, indent=1, ensure_ascii=False)
        except Exception as e:
            print("corrections save:", e)

    @staticmethod
    def _qkey(call, date, tm):
        return f"{call}|{date}|{tm[:4]}"

    def _corr_map(self):
        return self.corr.get(os.path.abspath(self.file_path), {}) if self.file_path else {}

    def edit_grid(self):
        """Locator van de geselecteerde verbinding aanpassen. Het logbestand zelf blijft ongewijzigd;
        de correctie wordt onthouden en gaat mee bij Exporteren -> ADIF."""
        q = self.selected_qso()
        t = self.t
        if not q:
            self._set_status(t("selecteer eerst een verbinding in de tabel of op de kaart", "select a contact in the table or on the map first"), C["amber"])
            return
        same = [o for o in self.qsos if o["call"] == q["call"]]
        w = tk.Toplevel(self.root)
        w.title(t("Locator aanpassen", "Edit locator"))
        w.configure(bg=C["bg"])
        w.transient(self.root)
        w.resizable(False, False)
        f, b, _ = panel(w, t("LOCATOR AANPASSEN", "EDIT LOCATOR"))
        f.pack(fill="x", padx=12, pady=(12, 6))
        d = q["date"]
        label(b, f"{q['call']}   {d[:4]}-{d[4:6]}-{d[6:8]}  {q['time'][:2]}:{q['time'][2:4]} UTC   {q['band']} {q['mode']}",
              fg=C["acc"], font=(UI, S(11), "bold")).pack(anchor="w")
        cur = q["grid"] or ("≈ " + latlon_to_grid(q["lat"], q["lon"], 4) + t(" (uit prefix)", " (from prefix)"))
        label(b, t(f"Huidige locator: {cur}", f"Current locator: {cur}"), font=(UI, S(9))).pack(anchor="w", pady=(4, 8))
        row = tk.Frame(b, bg=C["panel"])
        row.pack(anchor="w")
        label(row, t("Nieuwe locator", "New locator"), font=(UI, S(10))).pack(side="left", padx=(0, 8))
        gv = tk.StringVar(value=q["grid"])
        e = entry(row, gv, 10, font=(MONO, S(13), "bold"))
        e.pack(side="left")
        prev = label(row, "", fg=C["text"], font=(UI, S(9), "bold"))
        prev.pack(side="left", padx=(10, 0))
        allv = tk.BooleanVar(value=False)
        if len(same) > 1:
            FlatButton(b, t(f"Ook voor de andere {len(same) - 1} QSO's met {q['call']}",
                            f"Also for the other {len(same) - 1} QSOs with {q['call']}"),
                       var=allv, padx=8, pady=2, font=(UI, S(9), "bold")).pack(anchor="w", pady=(10, 0))
        label(b, t("Je logbestand wordt niet gewijzigd. De aanpassing wordt onthouden;\n"
                   "met Exporteren → ADIF maak je een gecorrigeerd logbestand.",
                   "Your log file is not changed. The correction is remembered;\n"
                   "use Export → ADIF to create a corrected log file."),
              font=(UI, S(8)), justify="left").pack(anchor="w", pady=(10, 0))
        msg = label(w, "", fg=C["red"], font=(UI, S(9)), bg=C["bg"])
        msg.pack(fill="x", padx=12)

        def norm(g):
            g = g.strip().replace(" ", "")
            return g[:2].upper() + g[2:4] + g[4:6].lower() + g[6:8]

        def preview():
            g = norm(gv.get())
            p = grid_to_latlon(g)
            if p:
                dd, bb = dist_brg(self.home[0], self.home[1], p[0], p[1])
                prev.config(text=f"→ {self.fmt_dist(dd)}  ·  {bb:.0f}°", fg=C["green"])
            else:
                prev.config(text=t("ongeldig", "invalid") if g else "", fg=C["red"])
        trace(e, gv, preview)
        preview()

        def apply(new):
            targets = same if allv.get() else [q]
            fmap = self.corr.setdefault(os.path.abspath(self.file_path), {})
            for o in targets:
                k = self._qkey(o["call"], o["date"], o["time"])
                if new is None:                              # terugzetten naar het origineel
                    fmap.pop(k, None)
                else:
                    fmap[k] = new
            if not fmap:
                self.corr.pop(os.path.abspath(self.file_path), None)
            self._save_corr()
            w.destroy()
            keep = self._qkey(q["call"], q["date"], q["time"])
            view = (self.map.k, self.map.cu, self.map.cv)
            self.load(self.file_path, quiet=True)
            self.map.k, self.map.cu, self.map.cv = view
            hit = next((o for o in self.qsos if self._qkey(o["call"], o["date"], o["time"]) == keep), None)
            if hit:
                self.select(hit["i"])
            else:
                self.map.redraw()
            n = len(targets)
            self._set_status(t(f"locator aangepast voor {n} QSO('s)" if new else f"originele locator teruggezet ({n} QSO('s))",
                               f"locator changed for {n} QSO(s)" if new else f"original locator restored ({n} QSO(s))"), C["green"])

        def save():
            g = norm(gv.get())
            if not grid_to_latlon(g) or len(g) < 4:
                msg.config(text=t("Ongeldige locator. Gebruik 4, 6 of 8 tekens, bijv. JO22 of JO22mp.",
                                  "Invalid locator. Use 4, 6 or 8 characters, e.g. JO22 or JO22mp."))
                return
            apply(g)
        bar = tk.Frame(w, bg=C["bg"])
        bar.pack(fill="x", padx=12, pady=(6, 12))
        FlatButton(bar, t("Opslaan", "Save"), command=save).pack(side="right")
        FlatButton(bar, t("Annuleren", "Cancel"), command=w.destroy).pack(side="right", padx=6)
        if any(o.get("edited") for o in same):
            FlatButton(bar, t("Origineel terugzetten", "Restore original"), command=lambda: apply(None)).pack(side="left")
        e.bind("<Return>", lambda ev: save())
        w.bind("<Escape>", lambda ev: w.destroy())
        w.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - w.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - w.winfo_height()) // 3
        w.geometry(f"+{max(x, 0)}+{max(y, 0)}")
        e.focus_set()
        e.select_range(0, "end")
        w.grab_set()

    def qrz(self):
        q = self.selected_qso()
        if q:
            call = max(q["call"].split("/"), key=len)       # PA/DL1ABC/P -> DL1ABC
            webbrowser.open("https://www.qrz.com/db/" + call)

    def open_manual(self):
        name = "HANDLEIDING.html" if self.lang == "nl" else "MANUAL.html"
        for p in (os.path.join(APP_DIR, "docs", name), os.path.join(APP_DIR, "..", "docs", name.replace(".html", ".md"))):
            if os.path.exists(p):
                try:
                    os.startfile(os.path.abspath(p))
                except AttributeError:
                    webbrowser.open("file://" + os.path.abspath(p))
                return
        webbrowser.open(REPO_URL + "/blob/main/docs/" + name.replace(".html", ".md"))

    # ---------- automatische update
    def _poll(self):
        """Berichten van achtergrond-threads verwerken (tkinter alleen vanuit de hoofdthread)."""
        try:
            while True:
                fn = self.gq.get_nowait()
                fn()
        except queue.Empty:
            pass
        except Exception as e:
            print("poll:", e)
        self.root.after(150, self._poll)

    def check_update_async(self, manual=False):
        """Controleert op GitHub of er een nieuwere versie is. Bij een update-bestand in de release
        kan het programma zichzelf bijwerken (downloaden, stil installeren, opnieuw starten)."""
        if not manual and not self.cfg.get("check_updates", True):
            return

        def work():
            try:
                info = json.loads(http_get(RELEASE_API).decode("utf-8"))
                tag = (info.get("tag_name") or "").lstrip("vV")
                if not tag or version_tuple(tag) <= version_tuple(APP_VERSION):
                    if manual:
                        self.gq.put(lambda: messagebox.showinfo(APP_NAME, self.t(
                            f"Je hebt de nieuwste versie ({APP_VERSION}).", f"You have the latest version ({APP_VERSION})."),
                            parent=self.root))
                    return
                asset = None
                for pat in (r"QSOMap-Update-[\d.]+\.exe$", r"QSOMap-Setup-[\d.]+\.exe$"):
                    for a in info.get("assets", []):
                        url = a.get("browser_download_url") or ""
                        if re.search(pat, a.get("name", "")) and url.startswith(DOWNLOAD_PREFIX):
                            asset = dict(name=a["name"], url=url, size=int(a.get("size") or 0),
                                         sha256=(a.get("digest") or "").split("sha256:")[-1] if
                                         (a.get("digest") or "").startswith("sha256:") else "")
                            break
                    if asset:
                        break
                upd = dict(version=tag, page=info.get("html_url") or REPO_URL + "/releases/latest", asset=asset,
                           notes=(info.get("body") or "").strip())
                self.gq.put(lambda: self._update_found(upd, manual))
            except Exception as e:
                print("update-check:", e)
                if manual:
                    self.gq.put(lambda: messagebox.showwarning(APP_NAME, self.t(
                        f"Controleren op updates is mislukt:\n{e}", f"Checking for updates failed:\n{e}"), parent=self.root))
        threading.Thread(target=work, daemon=True).start()

    def _update_found(self, upd, manual):
        self.update_info = upd
        self._show_update_button()
        v = upd["version"]
        if self.cfg.get("auto_install") and upd["asset"] and os.name == "nt" and not manual:
            self.install_update()
            return
        if not manual and self.cfg.get("update_asked") == v:
            return
        self.cfg["update_asked"] = v
        self._save_cfg()
        notes = upd["notes"][:600] + ("…" if len(upd["notes"]) > 600 else "")
        if upd["asset"] and os.name == "nt":
            q = self.t(f"Er is een nieuwe versie van QSO Map: {v}  (jij hebt {APP_VERSION}).\n\n{notes}\n\n"
                       "Nu automatisch bijwerken? Het programma sluit even af en start daarna vanzelf opnieuw.",
                       f"A new version of QSO Map is available: {v}  (you have {APP_VERSION}).\n\n{notes}\n\n"
                       "Update automatically now? The program closes briefly and then restarts by itself.")
            if messagebox.askyesno(self.t("Update beschikbaar", "Update available"), q, parent=self.root):
                self.install_update()
        else:
            if messagebox.askyesno(self.t("Update beschikbaar", "Update available"), self.t(
                    f"Er is een nieuwe versie van QSO Map: {v}  (jij hebt {APP_VERSION}).\n\nDe downloadpagina openen?",
                    f"A new version of QSO Map is available: {v}  (you have {APP_VERSION}).\n\nOpen the download page?"),
                    parent=self.root):
                webbrowser.open(upd["page"])

    def _show_update_button(self):
        if self.update_info and self.upd_btn.winfo_exists():
            self.upd_btn.config(text="⬆ " + self.t(f"Nieuwe versie {self.update_info['version']} – bijwerken",
                                                  f"New version {self.update_info['version']} – update"))
            self.upd_btn.set_active(True, C["acc2"])
            self.upd_btn.pack(side="left", padx=(10, 0))

    def _open_update(self):
        if not self.update_info:
            return
        if self.update_info["asset"] and os.name == "nt":
            self.install_update()
        else:
            webbrowser.open(self.update_info["page"])

    def install_update(self):
        """Update downloaden, controleren (grootte + SHA-256), stil installeren en het programma opnieuw starten."""
        upd = self.update_info
        if not upd or not upd["asset"] or getattr(self, "_updating", False):
            return
        self._updating = True
        a = upd["asset"]
        t = self.t
        self._set_status(t(f"update {upd['version']} downloaden…", f"downloading update {upd['version']}…"), C["acc2"])

        def prog(n, total):
            total = total or a["size"]
            if total:
                pct = int(n * 100 / total)
                if pct != getattr(self, "_last_pct", -1):
                    self._last_pct = pct
                    self.gq.put(lambda p=pct: self._set_status(
                        t(f"update {upd['version']} downloaden… {p}%", f"downloading update {upd['version']}… {p}%"), C["acc2"]))

        def work():
            try:
                import hashlib
                import tempfile
                data = http_get(a["url"], timeout=60, progress=prog)
                if a["size"] and len(data) != a["size"]:
                    raise OSError(t("download onvolledig", "download incomplete"))
                if a["sha256"] and hashlib.sha256(data).hexdigest().lower() != a["sha256"].lower():
                    raise OSError(t("controlegetal (SHA-256) klopt niet", "checksum (SHA-256) mismatch"))
                if data[:2] != b"MZ":
                    raise OSError(t("geen geldig installatiebestand", "not a valid installer"))
                path = os.path.join(tempfile.gettempdir(), a["name"])
                with open(path, "wb") as f:
                    f.write(data)
                self.gq.put(lambda: self._run_installer(path))
            except Exception as e:
                def fail(e=e):
                    self._updating = False
                    self._set_status(t(f"update mislukt: {e}", f"update failed: {e}"), C["red"])
                    if messagebox.askyesno(APP_NAME, t(f"Automatisch bijwerken is mislukt:\n{e}\n\nDe downloadpagina openen?",
                                                         f"Automatic update failed:\n{e}\n\nOpen the download page?"),
                                           parent=self.root):
                        webbrowser.open(upd["page"])
                self.gq.put(fail)
        threading.Thread(target=work, daemon=True).start()

    def _run_installer(self, path):
        import subprocess
        self._set_status(self.t("update installeren… QSO Map start zo opnieuw", "installing update… QSO Map will restart"), C["acc2"])
        self._save_cfg()
        try:
            subprocess.Popen([path, "/S"], close_fds=True,
                             creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
        except OSError as e:
            self._updating = False
            self._set_status(self.t(f"update starten mislukt: {e}", f"could not start update: {e}"), C["red"])
            return
        self.root.after(300, self._quit)

    # ---------- enquête
    def open_survey(self):
        self.cfg["survey_asked"] = True
        self._save_cfg()
        webbrowser.open(f"{SURVEY_URL}?lang={self.lang}&v={APP_VERSION}")

    def maybe_ask_survey(self):
        """Na de 5e start één keer vriendelijk vragen om de enquête in te vullen."""
        self.cfg["starts"] = int(self.cfg.get("starts", 0)) + 1
        self._save_cfg()
        if self.cfg["starts"] >= 5 and not self.cfg.get("survey_asked"):
            self.cfg["survey_asked"] = True
            self._save_cfg()
            if messagebox.askyesno(self.t("Enquête", "Survey"), self.t(
                    "Je gebruikt QSO Map nu een tijdje. Wil je een korte enquête invullen (ca. 2 minuten)?\n\n"
                    "Je bevindingen helpen om het programma te verbeteren. Later kan het ook via de knop 'Enquête'.",
                    "You have been using QSO Map for a while. Would you like to fill in a short survey (about 2 minutes)?\n\n"
                    "Your findings help to improve the program. You can also use the 'Survey' button later."),
                    parent=self.root):
                self.open_survey()

    # ---------- instellingen
    def show_settings(self):
        t = self.t
        w = tk.Toplevel(self.root)
        w.title(t("Instellingen", "Settings"))
        w.configure(bg=C["bg"])
        w.transient(self.root)
        f, b, _ = panel(w, t("ALGEMEEN", "GENERAL"))
        f.pack(fill="x", padx=12, pady=(12, 6))
        lang_v = tk.StringVar(value="Nederlands" if self.lang == "nl" else "English")
        tname = (lambda k: THEME_NL[k]) if self.lang == "nl" else (lambda k: k)
        theme_v = tk.StringVar(value=tname(self.cfg.get("theme", "Amber")))
        call_v = tk.StringVar(value=self.cfg.get("mycall", ""))
        grid_v = tk.StringVar(value=self.cfg.get("mygrid", ""))
        unit_v = tk.StringVar(value="km" if self.cfg.get("units") != "mi" else "mi")
        filegrid_v = tk.BooleanVar(value=bool(self.cfg.get("use_file_grid", True)))
        reopen_v = tk.BooleanVar(value=bool(self.cfg.get("reopen_last", True)))
        auto_v = tk.BooleanVar(value=bool(self.cfg.get("auto_install", False)))
        styles = [("bright", t("Helder", "Bright")), ("dark", t("Donker", "Dark"))]
        style_v = tk.StringVar(value=dict(styles).get(self.cfg.get("map_style", "bright"), styles[0][1]))
        fb = (UI, S(9), "bold")
        grid = [(t("Taal", "Language"), ttk.Combobox(b, textvariable=lang_v, state="readonly", width=14,
                                                    values=["Nederlands", "English"])),
                (t("Kleur", "Colour"), ttk.Combobox(b, textvariable=theme_v, state="readonly", width=14,
                                                   values=[tname(k) for k in THEMES])),
                (t("Mijn call", "My call"), entry(b, call_v, 14)),
                (t("Mijn locator", "My locator"), entry(b, grid_v, 14)),
                (t("Eenheid", "Units"), ttk.Combobox(b, textvariable=unit_v, state="readonly", width=14, values=["km", "mi"])),
                (t("Kaart", "Map"), ttk.Combobox(b, textvariable=style_v, state="readonly", width=14,
                                                 values=[x[1] for x in styles])),
                ("", label(b, t("locator bijv. JO22mp (4, 6 of 8 tekens)", "locator e.g. JO22mp (4, 6 or 8 characters)"), font=(UI, S(8))))]
        for i, (txt_, wd) in enumerate(grid):
            label(b, txt_, font=(UI, S(10))).grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 8), pady=4)
            wd.grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w", padx=(0, 24), pady=4)
        opts = tk.Frame(b, bg=C["panel"])
        opts.grid(row=4, column=0, columnspan=4, sticky="w", pady=(8, 2))
        FlatButton(opts, t("Locator uit ADIF (MY_GRIDSQUARE) voorrang geven", "Prefer locator from ADIF (MY_GRIDSQUARE)"),
                   var=filegrid_v, padx=8, pady=2, font=fb).pack(anchor="w", pady=2)
        FlatButton(opts, t("Laatste bestand openen bij starten", "Open last file at start-up"),
                   var=reopen_v, padx=8, pady=2, font=fb).pack(anchor="w", pady=2)
        ur = tk.Frame(opts, bg=C["panel"])
        ur.pack(anchor="w", pady=2)
        FlatButton(ur, t("Automatisch op updates controleren", "Check for updates automatically"),
                   var=self.upd_var, padx=8, pady=2, font=fb).pack(side="left")
        FlatButton(ur, t("Nu controleren", "Check now"), command=lambda: self.check_update_async(manual=True),
                   padx=8, pady=2, font=fb).pack(side="left", padx=(8, 0))
        FlatButton(opts, t("Updates zonder vragen installeren (programma herstart vanzelf)",
                           "Install updates without asking (program restarts by itself)"),
                   var=auto_v, padx=8, pady=2, font=fb).pack(anchor="w", pady=2)
        msg = label(w, "", fg=C["red"], font=(UI, S(9)), bg=C["bg"])
        msg.pack(fill="x", padx=12)
        bar = tk.Frame(w, bg=C["bg"])
        bar.pack(fill="x", padx=12, pady=(6, 12))

        def save():
            g = grid_v.get().strip()
            if g and not grid_to_latlon(g):
                msg.config(text=t("Ongeldige locator. Gebruik bijv. JO22 of JO22mp.", "Invalid locator. Use e.g. JO22 or JO22mp."))
                return
            self.lang = "nl" if lang_v.get() == "Nederlands" else "en"
            theme = next((k for k in THEMES if tname(k) == theme_v.get()), "Amber")
            self.cfg.update(theme=theme, mycall=call_v.get().strip().upper(), mygrid=g[:2].upper() + g[2:4] + g[4:6].lower() + g[6:8],
                            units=unit_v.get(), use_file_grid=bool(filegrid_v.get()), reopen_last=bool(reopen_v.get()),
                            check_updates=bool(self.upd_var.get()), lang=self.lang, auto_install=bool(auto_v.get()),
                            map_style=next((k for k, v in styles if v == style_v.get()), "bright"))
            old_home = self.home
            self._resolve_home()
            if self.home != old_home:
                self._compute_dist()
                self.map._cache = {}
            self._save_cfg()
            w.destroy()
            self.rebuild()
            if self.qsos:
                self._set_status(self.t(f"thuis-QTH: {self.home_src or '?'}", f"home QTH: {self.home_src or '?'}"), C["green"])
        FlatButton(bar, t("Opslaan", "Save"), command=save, accent=C["acc"]).pack(side="right")
        FlatButton(bar, t("Annuleren", "Cancel"), command=w.destroy).pack(side="right", padx=6)
        label(bar, f"{APP_NAME} {APP_VERSION}  ·  PD3RAH  ·  MIT License  ·  " +
              t("kaart: Natural Earth (publiek domein)  ·  geleverd zoals het is, zonder garantie",
                "map: Natural Earth (public domain)  ·  provided as is, without warranty"),
              font=(UI, S(8)), bg=C["bg"]).pack(side="left")
        w.grab_set()

    def _quit(self):
        self.playing = False
        self._save_cfg()
        self.root.destroy()


def main():
    root = tk.Tk()
    root.geometry("1560x1000")
    try:
        root.state("zoomed")
    except tk.TclError:
        pass
    root.minsize(1000, 640)
    path = next((a for a in sys.argv[1:] if os.path.isfile(a)), None)
    app = App(root, path)
    if not app.cfg.get("mygrid") and not path and not app.cfg.get("last_file"):
        root.after(600, app.show_settings)
    root.after(3000, app.check_update_async)
    root.after(4000, app.maybe_ask_survey)
    root.mainloop()


if __name__ == "__main__":
    main()
