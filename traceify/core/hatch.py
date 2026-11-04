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
    from shapely.geometry import LineString, MultiPolygon, Polygon
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
        quads = []
        # Vierecke zwischen benachbarten Schraffurlinien, die sich entlang der Richtung
        # überlappen – ihre Vereinigung ist die Fläche, begrenzt von den Linienenden
        for i, nb in enumerate(near):
            if loc[i] <= 0:
                continue
            for j in nb:
                do = offs[j] - offs[i]
                if do < 0.5 * loc[i] or do > 1.6 * loc[i] or not overlap(i, j):
                    continue
                q = Polygon([iv[i][0], iv[i][1], iv[j][1], iv[j][0]])
                if not q.is_valid:
                    q = q.buffer(0)
                if not q.is_empty:
                    quads.append(q)
        if not quads:
            continue
        geoms = [LineString([l.p1, l.p2]) for l in grp]
        area = unary_union(quads).buffer(0.01)
        polys = list(area.geoms) if isinstance(area, MultiPolygon) else \
            [area] if isinstance(area, Polygon) else []
        for poly in polys:
            if poly.is_empty or poly.area < sp * sp:
                continue
            pb = poly.buffer(0.5)
            midx = [i for i, g in enumerate(geoms) if pb.contains(g.centroid)]
            members = [grp[i] for i in midx]
            if len(members) < min_count:
                continue
            nn = loc[midx]
            nn = nn[nn > 0]
            if len(nn) < min_count:
                continue
            med = float(np.median(nn))
            # gleichmäßig: die Abstände zur jeweils nächsten Nachbarin streuen kaum
            if float(np.median(np.abs(nn - med))) > 0.2 * med:
                continue
            ang = _mean_angle(members)
            offs = _offsets(members, ang)
            msp = _spacing(offs)
            if msp <= 0:
                continue
            longest = max(members, key=lambda l: math.dist(l.p1, l.p2))
            base = ((longest.p1[0] + longest.p2[0]) / 2, (longest.p1[1] + longest.p2[1]) / 2)
            o0 = _offsets([longest], ang)[0]
            k = (offs - o0) / msp
            if float(np.median(np.abs(k - np.round(k)))) > max_residual:
                continue                         # kein festes Raster: Einzellinien behalten
            # Lücken im Raster (fehlende Linien) dürfen sein, aber nicht überwiegen
            if len(set(np.round(k).astype(int))) < 0.6 * (np.ptp(np.round(k)) + 1):
                continue
            p = poly.simplify(simplify, preserve_topology=True)
            # Rand minimal nach außen: die äußersten Schraffurlinien liegen sonst genau auf
            # dem Umriss und werden im CAD je nach Rundung mal gezeichnet, mal nicht
            p = p.buffer(max(0.25, 0.03 * msp), join_style="mitre", mitre_limit=3.0)
            if not isinstance(p, Polygon) or p.is_empty:
                continue
            out.append(HatchRegion(
                outline=[tuple(map(float, c)) for c in list(p.exterior.coords)[:-1]],
                holes=[[tuple(map(float, c)) for c in list(h.coords)[:-1]] for h in p.interiors],
                angle=ang, spacing=msp, base=base, members=members))
    return out


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
