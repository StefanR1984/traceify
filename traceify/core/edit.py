"""Bearbeitungsfunktionen für Vektoren (ohne Oberfläche, daher gut testbar).

* close_corner     – zwei Linien bis zu ihrem Schnittpunkt verlängern/kürzen
* orthogonalize    – fast waagrechte/senkrechte Linien exakt ausrichten, Ecken bleiben verbunden
* snap_gaps        – Endpunkte innerhalb einer Distanz zusammenführen
* join_lines       – verbundene Linien zu Polylinien zusammenfassen
* explode          – Polylinien in Einzellinien auflösen
* translate        – Objekte verschieben (z. B. Bereichs-Ergebnisse an ihre Stelle)
* move_point       – einen Knoten verschieben, verbundene Nachbarn optional mitnehmen
"""
from __future__ import annotations

import copy
import math
from typing import List, Optional, Tuple

from .model import Arc, Circle, Insert, Line, Point, Polyline, Text, LAYER_POLY, LAYER_LINES


# ------------------------------------------------------------------ Geometrie
def _intersection(a1: Point, a2: Point, b1: Point, b2: Point) -> Optional[Point]:
    d1 = (a2[0] - a1[0], a2[1] - a1[1])
    d2 = (b2[0] - b1[0], b2[1] - b1[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-9:
        return None
    t = ((b1[0] - a1[0]) * d2[1] - (b1[1] - a1[1]) * d2[0]) / den
    return (a1[0] + t * d1[0], a1[1] + t * d1[1])


def close_corner(l1: Line, l2: Line) -> bool:
    """Verlängert/kürzt zwei Linien bis zum gemeinsamen Schnittpunkt (Ecke schließen).

    Es wird jeweils der Endpunkt bewegt, der dem Schnittpunkt näher liegt.
    Gibt False zurück, wenn die Linien parallel sind.
    """
    p = _intersection(l1.p1, l1.p2, l2.p1, l2.p2)
    if p is None:
        return False
    for ln in (l1, l2):
        if math.dist(ln.p1, p) < math.dist(ln.p2, p):
            ln.p1 = p
        else:
            ln.p2 = p
    return True


def _angle(l: Line) -> float:
    return math.degrees(math.atan2(l.p2[1] - l.p1[1], l.p2[0] - l.p1[0])) % 180


def _clusters(points: List[Tuple[object, int, Point]], tol: float):
    """Gruppiert Endpunkte, die näher als tol beieinander liegen (einfaches Union-Find)."""
    parent = list(range(len(points)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    cell = {}
    for i, (_, _, p) in enumerate(points):
        cell.setdefault((int(p[0] // tol), int(p[1] // tol)), []).append(i)
    for (cx, cy), idx in cell.items():
        near = [j for dx in (-1, 0, 1) for dy in (-1, 0, 1) for j in cell.get((cx + dx, cy + dy), [])]
        for i in idx:
            for j in near:
                if i < j and math.dist(points[i][2], points[j][2]) <= tol:
                    parent[find(i)] = find(j)
    groups = {}
    for i in range(len(points)):
        groups.setdefault(find(i), []).append(i)
    return [g for g in groups.values() if len(g) > 1]


def _endpoints(ents) -> List[Tuple[object, int, Point]]:
    out = []
    for e in ents:
        if isinstance(e, Line):
            out += [(e, 0, e.p1), (e, 1, e.p2)]
        elif isinstance(e, Polyline) and e.points and not e.closed:
            out += [(e, 0, e.points[0]), (e, len(e.points) - 1, e.points[-1])]
    return out


def _set_end(e, idx, p):
    if isinstance(e, Line):
        if idx == 0:
            e.p1 = p
        else:
            e.p2 = p
    else:
        e.points[idx] = p


def orthogonalize(ents: list, tol_deg: float = 3.0, join_tol: float = 2.0,
                  min_px: float = 0.0, max_deg: float = 20.0, max_shift: float = 0.0) -> int:
    """Richtet fast waagrechte/senkrechte Linien exakt aus. Gibt die Anzahl geänderter Linien zurück.

    Vorher verbundene Endpunkte bleiben verbunden (Ecke = x der Senkrechten, y der Waagrechten).
    min_px: kurze Linien, deren Enden höchstens so viele Pixel von der Achse abweichen, werden
    auch ausgerichtet (ihr Winkel ist im Scan unsicher) – bis höchstens max_deg.
    max_shift: wenn > 0, nur Linien ausrichten, deren Enden sich dabei insgesamt höchstens so
    viele Pixel quer verschieben (lange, merklich schräge Linien bleiben, wie sie sind).
    """
    lines = [e for e in ents if isinstance(e, Line)]
    pts = _endpoints(lines)
    groups = _clusters(pts, join_tol)
    kind = {}
    n = 0

    def near(dev: float, L: float) -> bool:
        if max_shift > 0 and L * math.sin(math.radians(dev)) > max_shift:
            return False          # Enden würden zu weit von der Tinte wandern
        if dev <= tol_deg:
            return True
        return min_px > 0 and dev <= max_deg and L * math.sin(math.radians(dev)) <= min_px
    for l in lines:
        a = _angle(l)
        L = math.dist(l.p1, l.p2)
        if near(min(a, 180 - a), L) and min(a, 180 - a) <= abs(a - 90):
            y = (l.p1[1] + l.p2[1]) / 2
            l.p1, l.p2 = (l.p1[0], y), (l.p2[0], y)
            kind[id(l)] = "h"
            n += 1
        elif near(abs(a - 90), L):
            x = (l.p1[0] + l.p2[0]) / 2
            l.p1, l.p2 = (x, l.p1[1]), (x, l.p2[1])
            kind[id(l)] = "v"
            n += 1
    for g in groups:
        members = [pts[i] for i in g]
        xs = [(e.p1 if idx == 0 else e.p2)[0] for e, idx, _ in members if kind.get(id(e)) == "v"]
        ys = [(e.p1 if idx == 0 else e.p2)[1] for e, idx, _ in members if kind.get(id(e)) == "h"]
        cur = [(e.p1 if idx == 0 else e.p2) for e, idx, _ in members]
        x = sum(xs) / len(xs) if xs else sum(p[0] for p in cur) / len(cur)
        y = sum(ys) / len(ys) if ys else sum(p[1] for p in cur) / len(cur)
        for e, idx, _ in members:
            _set_end(e, idx, (x, y))
    return n


def _turn(a: Point, b: Point, c: Point) -> float:
    """Richtungsänderung in Grad am Knoten b (0 = gerade weiter)."""
    a1 = math.atan2(b[1] - a[1], b[0] - a[0])
    a2 = math.atan2(c[1] - b[1], c[0] - b[0])
    d = abs(math.degrees(a2 - a1)) % 360
    return min(d, 360 - d)


def align_axes(ents: list, skew: float = 0.0, center: Point = (0.0, 0.0),
               tol_deg: float = 3.0, join_tol: float = 2.0, min_px: float = 0.0,
               curve_turn: float = 20.0, max_shift: float = 0.0) -> int:
    """Richtet Linien **und Polylinien-Segmente** exakt an den Achsen aus (ändert ents).

    skew: Schräglage in Grad (Bild); ausgerichtet wird an den um skew gedrehten Achsen.
    Polylinien-Segmente werden nur genommen, wenn sie an beiden Enden „echte“ Ecken haben
    (Knick > curve_turn) oder offene Enden sind – Segmente in Rundungen (viele kleine
    Knicke) bleiben unberührt, damit Kurven nicht zu Treppen werden.
    Gibt die Anzahl exakt ausgerichteter Linien/Segmente zurück."""
    work: list = []           # (Proxy-Linie, Ziel) – Ziel: Line oder (Polyline, i, j)
    for e in ents:
        if isinstance(e, Line):
            work.append((Line(e.p1, e.p2), e))
        elif isinstance(e, Polyline) and len(e.points) >= 2:
            P, n = e.points, len(e.points)
            segs = n if e.closed and n >= 3 else n - 1
            for i in range(segs):
                j = (i + 1) % n
                if math.dist(P[i], P[j]) < 1e-9:
                    continue
                ok = True
                for k, (a, b, c) in enumerate(((i - 1, i, j), (i, j, j + 1))):
                    if not e.closed and (a < 0 or c >= n):
                        continue                       # offenes Ende
                    if _turn(P[a % n], P[b], P[c % n]) <= curve_turn:
                        ok = False
                        break
                if ok:
                    work.append((Line(P[i], P[j]), (e, i, j)))
    if not work:
        return 0
    proxies = [rotate(w, center, -skew) if skew else w for w, _ in work]
    n = orthogonalize(proxies, tol_deg=tol_deg, join_tol=join_tol, min_px=min_px,
                      max_shift=max_shift)
    newpts: dict = {}
    for prx, (_, tgt) in zip(proxies, work):
        r = rotate(prx, center, skew) if skew else prx
        if isinstance(tgt, Line):
            tgt.p1, tgt.p2 = r.p1, r.p2
        else:
            pl, i, j = tgt
            newpts.setdefault(id(pl), (pl, {}))[1].update({i: r.p1, j: r.p2})
    for pl, upd in newpts.values():
        pts = list(pl.points)
        for i, p in upd.items():
            pts[i] = p
        pl.points = pts
    return n


def snap_gaps(ents: list, dist: float) -> int:
    """Führt Endpunkte (Linien, offene Polylinien) innerhalb von dist zusammen."""
    pts = _endpoints(ents)
    n = 0
    for g in _clusters(pts, dist):
        cx = sum(pts[i][2][0] for i in g) / len(g)
        cy = sum(pts[i][2][1] for i in g) / len(g)
        for i in g:
            e, idx, _ = pts[i]
            _set_end(e, idx, (cx, cy))
        n += 1
    return n


def join_lines(lines: List[Line], tol: float = 0.5) -> List[Polyline]:
    """Verkettet Linien mit gemeinsamen Endpunkten zu Polylinien (geschlossen, wenn ein Ring)."""
    key = lambda p: (round(p[0] / tol), round(p[1] / tol))  # noqa: E731
    idx = {}
    for i, l in enumerate(lines):
        idx.setdefault(key(l.p1), []).append(i)
        idx.setdefault(key(l.p2), []).append(i)
    used = [False] * len(lines)
    out = []
    for i, l in enumerate(lines):
        if used[i]:
            continue
        used[i] = True
        chain = [l.p1, l.p2]
        for forward in (True, False):
            while True:
                end = chain[-1] if forward else chain[0]
                nxt = next((j for j in idx.get(key(end), []) if not used[j]), None)
                if nxt is None:
                    break
                used[nxt] = True
                a, b = lines[nxt].p1, lines[nxt].p2
                other = b if key(a) == key(end) else a
                if forward:
                    chain.append(other)
                else:
                    chain.insert(0, other)
        closed = len(chain) > 3 and key(chain[0]) == key(chain[-1])
        if closed:
            chain = chain[:-1]
        out.append(Polyline(chain, closed, LAYER_POLY, l.color, l.linetype, l.lineweight))
    return out


def explode(p: Polyline) -> List[Line]:
    pts = list(p.points) + ([p.points[0]] if p.closed and p.points else [])
    return [Line(a, b, LAYER_LINES, p.color, p.linetype, p.lineweight)
            for a, b in zip(pts, pts[1:]) if math.dist(a, b) > 1e-9]


def translate(e, dx: float, dy: float):
    """Gibt eine verschobene Kopie zurück."""
    e = copy.copy(e)
    if isinstance(e, Line):
        e.p1 = (e.p1[0] + dx, e.p1[1] + dy)
        e.p2 = (e.p2[0] + dx, e.p2[1] + dy)
    elif isinstance(e, (Circle, Arc)):
        e.center = (e.center[0] + dx, e.center[1] + dy)
    elif isinstance(e, Polyline):
        e.points = [(x + dx, y + dy) for x, y in e.points]
    elif isinstance(e, Text):
        e.position = (e.position[0] + dx, e.position[1] + dy)
    return e


def rotate(e, center: Point, deg: float):
    """Gibt eine um center gedrehte Kopie zurück (Grad im Bildsystem, y nach unten:
    positiv = im Uhrzeigersinn auf dem Bildschirm)."""
    e = copy.copy(e)
    a = math.radians(deg)
    ca, sa = math.cos(a), math.sin(a)

    def R(p):
        x, y = p[0] - center[0], p[1] - center[1]
        return (center[0] + x * ca - y * sa, center[1] + x * sa + y * ca)
    if isinstance(e, Line):
        e.p1, e.p2 = R(e.p1), R(e.p2)
    elif isinstance(e, Circle):
        e.center = R(e.center)
    elif isinstance(e, Arc):
        e.center = R(e.center)
        e.start_angle = (e.start_angle + deg) % 360
        e.end_angle = (e.end_angle + deg) % 360
    elif isinstance(e, Polyline):
        e.points = [R(p) for p in e.points]
    elif isinstance(e, Text):
        e.position = R(e.position)
        e.angle = (e.angle - deg) % 360          # Textwinkel zählt gegen den Uhrzeigersinn
    elif isinstance(e, Insert):
        e.position = R(e.position)
        e.rotation = (e.rotation - deg) % 360
    return e


def entity_points(e) -> List[Point]:
    """Bearbeitbare Knoten eines Objekts."""
    if isinstance(e, Line):
        return [e.p1, e.p2]
    if isinstance(e, Polyline):
        return list(e.points)
    if isinstance(e, Circle):
        return [e.center, (e.center[0] + e.radius, e.center[1])]
    if isinstance(e, Insert):
        return [e.position]
    if isinstance(e, Arc):
        a0, a1 = math.radians(e.start_angle), math.radians(e.end_angle)
        return [e.center,
                (e.center[0] + e.radius * math.cos(a0), e.center[1] + e.radius * math.sin(a0)),
                (e.center[0] + e.radius * math.cos(a1), e.center[1] + e.radius * math.sin(a1))]
    return []


def set_entity_point(e, i: int, p: Point) -> None:
    """Setzt Knoten i (siehe entity_points)."""
    if isinstance(e, Line):
        _set_end(e, i, p)
    elif isinstance(e, Insert):
        e.position = p
    elif isinstance(e, Polyline):
        e.points[i] = p
    elif isinstance(e, Circle):
        if i == 0:
            e.center = p
        else:
            e.radius = max(0.5, math.dist(e.center, p))
    elif isinstance(e, Arc):
        if i == 0:
            e.center = p
        else:
            e.radius = max(0.5, math.dist(e.center, p))
            ang = math.degrees(math.atan2(p[1] - e.center[1], p[0] - e.center[0])) % 360
            if i == 1:
                e.start_angle = ang
            else:
                e.end_angle = ang


def move_point(ents: list, e, i: int, p: Point, connected: bool = True, tol: float = 1.0) -> list:
    """Verschiebt Knoten i von e; mit connected werden deckungsgleiche Endpunkte anderer
    Linien/Polylinien mitbewegt (die Zeichnung bleibt zusammenhängend).
    Gibt alle geänderten Objekte zurück."""
    old = entity_points(e)[i]
    set_entity_point(e, i, p)
    changed = [e]
    if not connected or isinstance(e, (Circle, Arc, Insert)):
        return changed
    for other, idx, q in _endpoints([x for x in ents if x is not e]):
        if math.dist(q, old) <= tol:
            _set_end(other, idx, p)
            changed.append(other)
    return changed
