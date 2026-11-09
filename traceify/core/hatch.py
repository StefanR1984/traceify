"""Schraffur-Flächen: Linien auf dem Layer SCHRAFFUR zu echten Schraffuren zusammenfassen.

Die Erkennung (``style.detect_hatch``) legt Schraffurlinien auf den Layer SCHRAFFUR. Für den
DXF-Export werden sie hier zu Flächen gruppiert: je Fläche ein Umriss (mit Löchern),
eine Richtung und ein Linienabstand. Daraus entsteht im CAD ein HATCH-Objekt mit
benutzerdefiniertem Linienmuster – eine Fläche statt vieler Einzellinien, die sich im CAD
als Ganzes auswählen, umfärben, im Abstand ändern oder löschen lässt.

Unregelmäßige Gruppen (Abstände passen nicht zu einem festen Raster) bleiben Einzellinien.
Alles in Bildpixeln (y nach unten), Winkel in Grad im Bildsystem.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple

import numpy as np

from .model import LAYER_HATCH, Line, Point

META_KEY = "schraffur_flaeche"     # "1" = Schraffur als Fläche exportieren


@dataclass
class HatchRegion:
    outline: List[Point]                     # Außenumriss (geschlossen, ohne Wiederholung)
    holes: List[List[Point]] = field(default_factory=list)
    angle: float = 45.0                      # Grad, Bild (0..180)
    spacing: float = 10.0                    # px, quer zu den Linien
    base: Point = (0.0, 0.0)                 # ein Punkt auf einer Schraffurlinie
    members: list = field(default_factory=list)   # ersetzte Linien


def wants_areas(d) -> bool:
    return str(d.meta.get(META_KEY, "")) == "1"


def _angle(l: Line) -> float:
    return math.degrees(math.atan2(l.p2[1] - l.p1[1], l.p2[0] - l.p1[0])) % 180.0


def _angle_groups(lines: List[Line], tol: float = 8.0) -> List[List[Line]]:
    """Linien nach Richtung gruppieren (Lücken > tol trennen; 0/180 werden verbunden)."""
    items = sorted(((_angle(l), l) for l in lines), key=lambda t: t[0])
    groups: List[List[Tuple[float, Line]]] = []
    for a, l in items:
        if groups and a - groups[-1][-1][0] <= tol:
            groups[-1].append((a, l))
        else:
            groups.append([(a, l)])
    if len(groups) > 1 and groups[0][0][0] + 180 - groups[-1][-1][0] <= tol:
        groups[0] = groups.pop() + groups[0]
    return [[l for _, l in g] for g in groups]


def _mean_angle(lines: List[Line]) -> float:
    """Längengewichtete mittlere Richtung (über doppelte Winkel, wegen 0/180)."""
    sx = sy = 0.0
    for l in lines:
        L = math.dist(l.p1, l.p2)
        a = math.radians(2 * _angle(l))
        sx += L * math.cos(a)
        sy += L * math.sin(a)
    return (math.degrees(math.atan2(sy, sx)) / 2.0) % 180.0


def _offsets(lines: List[Line], angle: float) -> np.ndarray:
    """Lage der Linien quer zur Richtung (Abstand der Mittelpunkte entlang der Normalen)."""
    r = math.radians(angle)
    nx, ny = -math.sin(r), math.cos(r)
    return np.array([((l.p1[0] + l.p2[0]) / 2) * nx + ((l.p1[1] + l.p2[1]) / 2) * ny
                     for l in lines])


def _spacing(offs: np.ndarray) -> float:
    o = np.unique(np.round(np.sort(offs), 2))
    if len(o) < 2:
        return 0.0
    d = np.diff(o)
    d = d[d > 0.5]
    return float(np.median(d)) if len(d) else 0.0


def find_regions(ents: list, min_count: int = 4, max_residual: float = 0.22,
                 simplify: float = 0.7) -> List[HatchRegion]:
    """Schraffur-Flächen aus den Linien auf dem Layer SCHRAFFUR bilden."""
    from shapely.geometry import LineString, Polygon
    from shapely.ops import unary_union

    lines = [e for e in ents if isinstance(e, Line) and e.layer == LAYER_HATCH
             and math.dist(e.p1, e.p2) > 1e-6]
    out: List[HatchRegion] = []
    for grp in _angle_groups(lines):
        if len(grp) < min_count:
            continue
        from scipy.spatial import cKDTree
        ang0 = _mean_angle(grp)
        rr = math.radians(ang0)
        ux, uy = math.cos(rr), math.sin(rr)
        offs = _offsets(grp, ang0)
        iv = []
        for l in grp:
            t1, t2 = l.p1[0] * ux + l.p1[1] * uy, l.p2[0] * ux + l.p2[1] * uy
            iv.append((l.p1, l.p2) if t1 <= t2 else (l.p2, l.p1))
        tt = [(a_[0] * ux + a_[1] * uy, b_[0] * ux + b_[1] * uy) for a_, b_ in iv]
        mids = np.array([((l.p1[0] + l.p2[0]) / 2, (l.p1[1] + l.p2[1]) / 2) for l in grp])
        lens = np.array([t[1] - t[0] for t in tt])
        tree = cKDTree(mids)
        near = tree.query_ball_point(mids, r=lens / 2 + float(np.percentile(lens, 90)) / 2 + 2.0)

        def overlap(i, j) -> bool:
            lo, hi = max(tt[i][0], tt[j][0]), min(tt[i][1], tt[j][1])
            return hi - lo >= 0.3 * min(lens[i], lens[j])
        # Abstand je Linie zur nächsten parallelen Nachbarin (örtlich – verschiedene
        # Wände können verschieden dicht schraffiert sein)
        loc = np.zeros(len(grp))
        for i, nb in enumerate(near):
            ds = [abs(offs[j] - offs[i]) for j in nb if j != i and overlap(i, j)
                  and abs(offs[j] - offs[i]) > 0.5]
            loc[i] = min(ds) if ds else 0.0
        if not (loc > 0).any():
            continue
        sp = float(np.median(loc[loc > 0]))
        # Nachbarn: parallele Linien mit Überlappung entlang der Richtung, ein bis zwei
        # Rasterschritte entfernt; dazwischen ein Viereck (Vereinigung = Fläche)
        edges = {}
        quads = {}
        for i, nb in enumerate(near):
            if loc[i] <= 0:
                continue
            for j in nb:
                do = offs[j] - offs[i]
                if do < 0.5 * loc[i] or do > 2.6 * loc[i] or not overlap(i, j):
                    continue
                step = int(round(do / loc[i]))
                edges.setdefault(i, []).append((j, step))
                edges.setdefault(j, []).append((i, -step))
                if step == 1:
                    q = Polygon([iv[i][0], iv[i][1], iv[j][1], iv[j][0]])
                    if not q.is_valid:
                        q = q.buffer(0)
                    if not q.is_empty:
                        quads[(i, j)] = q
        geoms = [LineString([l.p1, l.p2]) for l in grp]
        for comp, kk in _number_lines(len(grp), edges, offs):
            if len(comp) < min_count:
                continue
            keep = _fit_grid(offs[comp], kk, max_residual)
            if keep is None:
                continue
            comp = [c for c, ok in zip(comp, keep) if ok]
            kmap = dict(zip(comp, kk[keep]))
            cs = set(comp)
            area = unary_union([q for (i, j), q in quads.items() if i in cs and j in cs])
            for poly in _pieces(area.buffer(0.01)):
                if poly.area < sp * sp:
                    continue
                pb = poly.buffer(0.5)
                mem = [i for i in comp if pb.contains(geoms[i].centroid)]
                reg = _make_region(poly, [grp[i] for i in mem],
                                   np.array([kmap[i] for i in mem], float),
                                   min_count, max_residual, simplify)
                if reg is not None:
                    out.append(reg)
    _adopt_rest(out, lines)
    return out


def _pieces(geom) -> list:
    """Polygone einer (Multi-)Geometrie."""
    from shapely.geometry import MultiPolygon, Polygon
    if isinstance(geom, MultiPolygon):
        return [g for g in geom.geoms if not g.is_empty]
    return [geom] if isinstance(geom, Polygon) and not geom.is_empty else []


def _number_lines(n: int, edges: dict, offs: np.ndarray = None, tol: float = 0.3):
    """Rasternummern vergeben: von Linie zu Nachbarlinie weiterzählen (Breitensuche).

    Stücke derselben, im Scan zerrissenen Linie bekommen dieselbe Nummer. Eine Gruppe wächst
    nur, solange die neue Linie zum bisherigen Raster passt (Lage = a + b·k, Abweichung
    höchstens tol·b) – so trennen sich aneinanderstoßende Wände mit versetztem Raster.
    Gibt [(Indizes, Nummern-Array)] je Gruppe."""
    seen = {}
    comps = []
    for s0 in range(n):
        if s0 in seen or s0 not in edges:
            continue
        kk = {s0: 0}
        seen[s0] = True
        order, queue = [s0], [s0]
        # Summen für die laufende Ausgleichsgerade
        S = [1.0, 0.0, 0.0, 0.0, 0.0] if offs is None else \
            [1.0, 0.0, 0.0, float(offs[s0]), 0.0]      # n, Σk, Σk², Σo, Σko
        qi = 0
        while qi < len(queue):
            i = queue[qi]
            qi += 1
            for j, st in edges[i]:
                if j in seen:
                    continue
                kj = kk[i] + st
                if offs is not None:
                    nn, sk, skk, so, sko = S
                    den = nn * skk - sk * sk
                    if den > 1e-9:
                        b = (nn * sko - sk * so) / den
                        a_ = (so - b * sk) / nn
                        if b <= 0 or abs(offs[j] - (a_ + b * kj)) > tol * b:
                            continue
                    o = float(offs[j])
                    S = [S[0] + 1, S[1] + kj, S[2] + kj * kj, S[3] + o, S[4] + kj * o]
                seen[j] = True
                kk[j] = kj
                order.append(j)
                queue.append(j)
        comps.append((order, np.array([kk[i] for i in order], float)))
    return comps

def _fit_grid(offs: np.ndarray, k: np.ndarray, max_residual: float = 0.22):
    """Prüft, ob Lage = a + b·k gut passt. Gibt eine Maske der passenden Linien (Ausreißer
    raus) oder None, wenn die Gruppe insgesamt kein festes Raster bildet."""
    if len(set(k)) < 2:
        return None
    keep = np.ones(len(k), bool)
    for _ in range(3):
        if len(set(k[keep])) < 2:
            return None
        b, a = np.polyfit(k[keep], offs[keep], 1)
        if b <= 0:
            return None
        res = np.abs(offs - (a + b * k))
        new = res <= 0.35 * b
        if (new == keep).all():
            break
        keep = new
    if keep.sum() < 0.6 * len(k) or float(np.median(res[keep])) > max_residual * b:
        return None
    return keep


def _make_region(poly, members: List[Line], k: np.ndarray, min_count: int,
                 max_residual: float, simplify: float):
    """HatchRegion für eine Fläche, deren Linien (Rasternummern k) ein festes Raster bilden."""
    from shapely.geometry import Polygon
    if len(members) < min_count or len(set(k)) < max(2, min_count - 1):
        return None
    # Schraffur besteht aus vielen kurzen Strichen; wenige lange Parallelen (Wandkanten,
    # Möbel) sind keine Fläche
    nk = len(set(k.astype(int)))
    if nk < 3:
        return None
    ang = _mean_angle(members)
    offs = _offsets(members, ang)
    msp, a = np.polyfit(k, offs, 1)
    msp, a = float(msp), float(a)
    if msp <= 0:
        return None
    med_len = float(np.median([math.dist(l.p1, l.p2) for l in members]))
    if (med_len > 12 * msp and nk < 8) or (nk < 4 and med_len > 6 * msp):
        return None
    res = np.abs(offs - (a + msp * k))
    if float(np.median(res)) > max_residual * msp:
        return None                              # kein festes Raster: Einzellinien behalten
    # Lücken im Raster (fehlende Linien) dürfen sein, aber nicht überwiegen
    if len(set(k.astype(int))) < 0.6 * (np.ptp(k) + 1):
        return None
    # Basispunkt genau auf die angepasste Rasterlinie k = 0 legen
    r = math.radians(ang)
    nx, ny = -math.sin(r), math.cos(r)
    longest = max(members, key=lambda l: math.dist(l.p1, l.p2))
    mx, my = (longest.p1[0] + longest.p2[0]) / 2, (longest.p1[1] + longest.p2[1]) / 2
    shift = a - (mx * nx + my * ny)
    base = (mx + shift * nx, my + shift * ny)
    p = poly.simplify(simplify, preserve_topology=True)
    # Rand minimal nach außen: die äußersten Schraffurlinien liegen sonst genau auf
    # dem Umriss und werden im CAD je nach Rundung mal gezeichnet, mal nicht
    p = p.buffer(max(0.25, 0.03 * msp), join_style="mitre", mitre_limit=3.0)
    if not isinstance(p, Polygon) or p.is_empty:
        return None
    return HatchRegion(
        outline=[tuple(map(float, c)) for c in list(p.exterior.coords)[:-1]],
        holes=[[tuple(map(float, c)) for c in list(h.coords)[:-1]] for h in p.interiors],
        angle=ang, spacing=msp, base=base, members=members)

def _adopt_rest(regions: List[HatchRegion], lines: List[Line], tol: float = 0.3) -> None:
    """Übrig gebliebene Schraffurlinien einer benachbarten Fläche zuordnen, wenn sie in
    deren Raster passen (Richtung, Lage quer zur Richtung); die Fläche wächst um sie."""
    if not regions:
        return
    from shapely.geometry import LineString, Polygon
    used = {id(m) for r in regions for m in r.members}
    rest = [l for l in lines if id(l) not in used]
    if not rest:
        return
    polys = [Polygon(r.outline, r.holes) for r in regions]
    from shapely.strtree import STRtree
    tree = STRtree(polys)
    for l in rest:
        g = LineString([l.p1, l.p2])
        best = None
        for k in tree.query(g.buffer(2.0 * max(r.spacing for r in regions))):
            r = regions[int(k)]
            da = abs((_angle(l) - r.angle + 90.0) % 180.0 - 90.0)
            if da > 6.0 or polys[k].distance(g) > 1.5 * r.spacing:
                continue
            o = _offsets([l], r.angle)[0] - _offsets([Line(r.base, r.base)], r.angle)[0]
            res = abs(o / r.spacing - round(o / r.spacing))
            if res <= tol and (best is None or res < best[0]):
                best = (res, int(k))
        if best is None:
            continue
        k = best[1]
        r = regions[k]
        grown = polys[k].union(g.buffer(0.5 * r.spacing, cap_style="flat"))
        if not isinstance(grown, Polygon):
            grown = grown.convex_hull if grown.is_empty is False and \
                polys[k].distance(g) < 0.6 * r.spacing else None
            if not isinstance(grown, Polygon):
                continue
        grown = grown.simplify(0.7, preserve_topology=True)
        polys[k] = grown
        r.outline = [tuple(map(float, c)) for c in list(grown.exterior.coords)[:-1]]
        r.holes = [[tuple(map(float, c)) for c in list(h.coords)[:-1]] for h in grown.interiors]
        r.members.append(l)

def pattern_lines(reg: HatchRegion) -> List[Tuple[Point, Point]]:
    """Die Linien, die das Muster im Umriss erzeugt (für Prüfung und Vorschau)."""
    from shapely.geometry import LineString, MultiLineString, Polygon
    poly = Polygon(reg.outline, reg.holes)
    r = math.radians(reg.angle)
    ux, uy, nx, ny = math.cos(r), math.sin(r), -math.sin(r), math.cos(r)
    minx, miny, maxx, maxy = poly.bounds
    R = math.hypot(maxx - minx, maxy - miny) + reg.spacing
    cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
    o_c = (cx - reg.base[0]) * nx + (cy - reg.base[1]) * ny
    k0 = math.floor((o_c - R) / reg.spacing)
    k1 = math.ceil((o_c + R) / reg.spacing)
    res = []
    for k in range(k0, k1 + 1):
        px, py = reg.base[0] + k * reg.spacing * nx, reg.base[1] + k * reg.spacing * ny
        # Projektion des Mittelpunkts auf diese Linie als Zentrum
        t = (cx - px) * ux + (cy - py) * uy
        mx, my = px + t * ux, py + t * uy
        seg = LineString([(mx - R * ux, my - R * uy), (mx + R * ux, my + R * uy)])
        cut = poly.intersection(seg)
        parts = cut.geoms if isinstance(cut, MultiLineString) else [cut]
        for g in parts:
            if isinstance(g, LineString) and not g.is_empty and g.length > 1e-6:
                c = list(g.coords)
                res.append((tuple(c[0]), tuple(c[-1])))
    return res
