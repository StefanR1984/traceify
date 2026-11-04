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


def orthogonalize(ents: list, tol_deg: float = 3.0, join_tol: float = 2.0) -> int:
    """Richtet fast waagrechte/senkrechte Linien exakt aus. Gibt die Anzahl geänderter Linien zurück.

    Vorher verbundene Endpunkte bleiben verbunden (Ecke = x der Senkrechten, y der Waagrechten).
    """
    lines = [e for e in ents if isinstance(e, Line)]
    pts = _endpoints(lines)
    groups = _clusters(pts, join_tol)
    kind = {}
    n = 0
    for l in lines:
        a = _angle(l)
        if min(a, 180 - a) <= tol_deg:
            y = (l.p1[1] + l.p2[1]) / 2
            l.p1, l.p2 = (l.p1[0], y), (l.p2[0], y)
            kind[id(l)] = "h"
            n += 1
        elif abs(a - 90) <= tol_deg:
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
