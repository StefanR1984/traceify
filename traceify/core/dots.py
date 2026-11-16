"""Punktmuster (Kies, Splitt, Beton) als kleine Kreise.

Im Scan sind die Punkte winzige Kleckse oder Ringe (Ø ~0,3 mm). Das Entflecken löscht sie, das
Skelett eines Kleckses ist ein Punkt, und in Allplan-Plots sind sie zudem hellgrau und fallen
schon durch die Otsu-Schwelle. Deshalb ein eigener Schritt auf dem Graubild: kompakte, frei
stehende Kleckse, die in einer Fläche dicht beieinander liegen. Rauschen und Schriftpunkte
liegen verstreut, Strichpunkt-Linien in einer Reihe – beides fällt über Dichte und Fläche raus.
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

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


if __name__ == "__main__":
    _self_check()
    print("ok")
