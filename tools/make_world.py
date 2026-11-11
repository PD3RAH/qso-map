#!/usr/bin/env python3
"""Convert world-atlas TopoJSON (Natural Earth, public domain) to a compact world.json for QSO Map.
Usage: python3 tools/make_world.py countries-50m.json src/world.json"""
import json, sys, math

def decode(topo):
    sc, tr = topo["transform"]["scale"], topo["transform"]["translate"]
    arcs = []
    for a in topo["arcs"]:
        x = y = 0; pts = []
        for dx, dy in a:
            x += dx; y += dy
            pts.append((x * sc[0] + tr[0], y * sc[1] + tr[1]))
        arcs.append(pts)
    def ring(idx):
        out = []
        for i in idx:
            p = arcs[i] if i >= 0 else arcs[~i][::-1]
            out.extend(p if not out else p[1:])
        return out
    return ring

def dp(pts, eps):
    if len(pts) < 4: return pts
    keep = [False] * len(pts); keep[0] = keep[-1] = True
    st = [(0, len(pts) - 1)]
    while st:
        a, b = st.pop()
        ax, ay = pts[a]; bx, by = pts[b]
        dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy) or 1e-12
        best, bi = -1, None
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs(dy * (px - ax) - dx * (py - ay)) / L if (dx or dy) else math.hypot(px - ax, py - ay)
            if d > best: best, bi = d, i
        if bi is not None and best > eps:
            keep[bi] = True; st += [(a, bi), (bi, b)]
    return [p for p, k in zip(pts, keep) if k]

def _clip(ring, keep_west):
    """Sutherland-Hodgman: deel van een (ontvouwen) ring links (lon <= 180) of rechts (lon >= 180) van 180 graden."""
    def inside(p):
        return p[0] <= 180.0 if keep_west else p[0] >= 180.0
    out = []
    n = len(ring)
    for i in range(n):
        cur, prev = ring[i], ring[i - 1]
        if inside(cur):
            if not inside(prev):
                t = (180.0 - prev[0]) / (cur[0] - prev[0])
                out.append((180.0, prev[1] + t * (cur[1] - prev[1])))
            out.append(cur)
        elif inside(prev):
            t = (180.0 - prev[0]) / (cur[0] - prev[0])
            out.append((180.0, prev[1] + t * (cur[1] - prev[1])))
    return out


def split_antimeridian(ring):
    """Ringen die de datumgrens kruisen (Rusland, Fiji) in twee gesloten ringen knippen,
    zodat elk deel op de platte kaart als gevuld vlak getekend kan worden."""
    lons = [p[0] for p in ring]
    if not any(abs(a - b) > 180 for a, b in zip(lons, lons[1:] + lons[:1])):
        return [ring]
    un, off = [ring[0]], 0.0
    for (x0, _), (x1, y1) in zip(ring, ring[1:]):
        if x1 - x0 > 180:
            off -= 360
        elif x0 - x1 > 180:
            off += 360
        un.append((x1 + off, y1))
    if sum(p[0] for p in un) / len(un) < 0:           # zorg dat de ring rond +180 ligt
        un = [(x + 360, y) for x, y in un]
    west = _clip(un, True)
    east = [(x - 360, y) for x, y in _clip(un, False)]
    return [r for r in (west, east) if len(r) >= 4]


def main(src, dst, eps=0.06):
    topo = json.load(open(src))
    ring = decode(topo)
    out, npts = [], 0
    for g in topo["objects"]["countries"]["geometries"]:
        name = g.get("properties", {}).get("name", "")
        polys = g["arcs"] if g["type"] == "MultiPolygon" else ([g["arcs"]] if g["type"] == "Polygon" else [])
        rings = []
        for poly in polys:
            for part in split_antimeridian(ring(poly[0])):     # buitenring; gaten (meren) weggelaten
                r = dp(part, eps)
                if len(r) >= 4:
                    flat = []
                    for x, y in r: flat += [round(x, 2), round(y, 2)]
                    rings.append(flat); npts += len(r)
        if rings: out.append({"n": name, "r": rings})
    json.dump({"src": "Natural Earth 1:50m via world-atlas (public domain)", "c": out}, open(dst, "w"), separators=(",", ":"))
    print(len(out), "countries", npts, "points")

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 0.06)
