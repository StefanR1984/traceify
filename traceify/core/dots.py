"""Punktmuster (Kies, Splitt, Beton) als kleine Kreise.

Im Scan sind die Punkte winzige Kleckse oder Ringe (Ø ~0,3 mm). Das Entflecken löscht sie, das
Skelett eines Kleckses ist ein Punkt, und in Allplan-Plots sind sie zudem hellgrau und fallen
schon durch die Otsu-Schwelle. Deshalb ein eigener Schritt auf dem Graubild: kompakte, frei
stehende Kleckse, die in einer Fläche dicht beieinander liegen. Rauschen und Schriftpunkte
liegen verstreut, Strichpunkt-Linien in einer Reihe – beides fällt über Dichte und Fläche raus.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Sequence, Tuple

import math

import cv2
import numpy as np

from .model import LAYER_GRAVEL, Circle

MAX_MM = 0.9          # größter Klecks (Breite/Höhe)
RADIUS_MM = 3.0       # Nachbarschaft für die Dichte
MIN_NEIGHBOURS = 6    # so viele Kleckse im Umkreis
SPREAD_MM = 0.5       # Nachbarn müssen flächig liegen (kleinere Streuung quer = Reihe)
MIN_GROUP = 30        # Mindestgröße eines Punktfelds
FREE_MM = 0.25        # so weit um den Klecks keine andere Tinte (Schrift, Linien)


def find_dots(gray: np.ndarray, px_per_mm: float, boxes: Sequence[Tuple[int, int, int, int]] = (),
              invert: bool = False) -> Tuple[List[Circle], np.ndarray]:
    """Punktfelder im Graubild. Gibt (Kreise auf Layer KIES, Maske der Kleckse) zurück."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scipy.spatial import cKDTree

    g = 255 - gray if invert else gray
    otsu, _ = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    paper, dark = float(np.percentile(g, 95)), float(g.min())
    # auch hellgraue Ringe (Allplan-Plot: Otsu 144, Ringe ~150–200); Otsu kann bei wenig Grau
    # zwischen Schwarz und Grau liegen, daher mindestens 70 % des Wegs von Schwarz zum Papier
    th = max((otsu + paper) / 2, dark + 0.7 * (paper - dark))
    bw = (g < th).astype(np.uint8)
    n, lab, st, cen = cv2.connectedComponentsWithStats(bw, connectivity=8)
    mask = np.zeros(gray.shape, np.uint8)
    if n <= 1:
        return [], mask
    x, y, w, h, a = (st[1:, i] for i in range(5))
    big = np.maximum(w, h)
    idx = np.nonzero((big <= MAX_MM * px_per_mm) & (big <= 2 * np.minimum(w, h) + 1) & (a >= 3))[0]
    free = int(np.ceil(FREE_MM * px_per_mm))
    H, W = bw.shape
    cand = np.zeros(n, bool)
    cand[idx + 1] = True                                  # Hintergrund 0 zählt als Kandidat
    cand[0] = True
    keep = []
    for i in idx:                                         # frei stehend: daneben nur andere Kleckse
        sl = lab[max(0, y[i] - free):y[i] + h[i] + free, max(0, x[i] - free):x[i] + w[i] + free]
        if cand[sl].all():
            keep.append(i)
    idx = np.array(keep, int)
    if boxes and len(idx):                                # nicht in Textboxen (Satzzeichen, „o“)
        c = cen[1:][idx]
        inside = np.zeros(len(idx), bool)
        for bx, by, bw_, bh in boxes:
            inside |= (c[:, 0] >= bx) & (c[:, 0] < bx + bw_) & (c[:, 1] >= by) & (c[:, 1] < by + bh)
        idx = idx[~inside]
    if len(idx) < MIN_GROUP:
        return [], mask
    C = cen[1:][idx]
    tree = cKDTree(C)
    R = RADIUS_MM * px_per_mm
    ok = np.zeros(len(C), bool)
    for k, nb in enumerate(tree.query_ball_point(C, R)):
        if len(nb) - 1 < MIN_NEIGHBOURS:
            continue
        ev = np.linalg.eigvalsh(np.cov(C[nb].T))          # flächig, nicht in einer Reihe
        ok[k] = np.sqrt(max(ev[0], 0.0)) >= SPREAD_MM * px_per_mm
    P, idx = C[ok], idx[ok]
    if len(P) < MIN_GROUP:
        return [], mask
    pairs = cKDTree(P).query_pairs(R, output_type="ndarray")
    _, grp = connected_components(coo_matrix((np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])),
                                             shape=(len(P), len(P))), directed=False)
    sel = np.bincount(grp)[grp] >= MIN_GROUP
    out = []
    for i, p in zip(idx[sel], P[sel]):
        d = (w[i] + h[i]) / 2.0
        # shortcut: Klecks = Kreis + halbe Strichbreite ringsum, Strich ~1 px angenommen
        out.append(Circle((float(p[0]), float(p[1])), max(d / 2 - 0.5, d / 4), LAYER_GRAVEL))
    mask[np.isin(lab, idx[sel] + 1)] = 255
    return out, mask


@dataclass
class GravelRegion:
    """Kies-Fläche: Umriss (mit Löchern) und Punktabstand; ersetzt die Kreise in `members`."""
    outline: List[Tuple[float, float]]
    holes: List[List[Tuple[float, float]]] = field(default_factory=list)
    spacing: float = 10.0                    # px, mittlerer Abstand benachbarter Punkte
    radius: float = 1.0                      # px, mittlerer Punktradius
    members: list = field(default_factory=list)


def find_areas(ents: list, min_count: int = MIN_GROUP) -> List[GravelRegion]:
    """Kreise auf Layer KIES zu Flächen zusammenfassen (fürs CAD eine HATCH statt tausender Kreise).

    Umriss = Vereinigung der Punkte, so weit gewachsen, dass Nachbarn verschmelzen (0,75 × 90 %-Wert
    des Nachbarabstands), dann wieder geschrumpft und geglättet – die Fläche endet einen halben
    Punktabstand hinter den äußeren Punkten. Kleine Gruppen (< min_count) und Randpunkte, die beim
    Schrumpfen abreißen, bleiben Kreise."""
    from scipy.spatial import cKDTree
    from shapely.geometry import Point, Polygon
    from shapely.ops import unary_union

    circ = [e for e in ents if isinstance(e, Circle) and e.layer == LAYER_GRAVEL]
    if len(circ) < min_count:
        return []
    C = np.array([c.center for c in circ], float)
    nn = cKDTree(C).query(C, k=2)[0][:, 1]
    sp = float(np.median(nn))
    if sp <= 0:
        return []
    g = 0.75 * float(np.percentile(nn, 90))       # füllt auch Diagonal-Lücken (0,71 Abstände)
    area = unary_union([Point(p).buffer(g, 8) for p in C]).buffer(-g + 0.5 * sp, 8)
    polys = list(getattr(area, "geoms", [area]))
    tree = cKDTree(C)
    out = []
    for poly in polys:
        if poly.is_empty:
            continue
        poly = poly.simplify(0.15 * sp)
        near = poly.buffer(0.3 * sp)                  # Vereinfachen darf Randpunkte streifen
        x0, y0, x1, y1 = poly.bounds
        idx = [i for i in tree.query_ball_point(((x0 + x1) / 2, (y0 + y1) / 2),
                                                math.hypot(x1 - x0, y1 - y0) / 2 + 1)
               if near.covers(Point(C[i]))]
        if len(idx) < min_count:
            continue
        mem = [circ[i] for i in idx]
        # Löcher erst ab 4 × 4 fehlenden Punkten, kleinere Lücken gehören zum Zufallsraster
        out.append(GravelRegion([tuple(map(float, p)) for p in poly.exterior.coords[:-1]],
                                [[tuple(map(float, p)) for p in h.coords[:-1]]
                                 for h in poly.interiors if Polygon(h).area > 16 * sp * sp],
                                sp, float(np.mean([c.radius for c in mem])), mem))
    return out


def _self_check() -> None:
    rng = np.random.default_rng(1)
    img = np.full((400, 600), 255, np.uint8)
    gx, gy = np.meshgrid(np.arange(20, 280, 15), np.arange(20, 380, 15))
    pts = np.column_stack([gx.ravel(), gy.ravel()]) + rng.uniform(-3, 3, (gx.size, 2))  # Feld links
    for px, py in pts:
        cv2.circle(img, (int(px), int(py)), 2, 170, 1)
    for k in range(40):                                   # Punktreihe rechts: keine Fläche
        cv2.circle(img, (420 + 0 * k, 10 + 9 * k), 1, 0, -1)
    circ, _ = find_dots(img, 10.0)
    assert len(circ) > 100 and all(c.center[0] < 300 for c in circ)
    reg = find_areas(circ)
    assert len(reg) == 1 and len(reg[0].members) == len(circ) and 10 <= reg[0].spacing <= 20


if __name__ == "__main__":
    _self_check()
    print("ok")
