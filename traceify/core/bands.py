"""Wandbänder: breite, fast volle Tintenbänder (schraffierte oder gefüllte Wände) als Umriss + Fläche.

In kleinen Maßstäben (1:200, 1:350) verschmilzt die Wandschraffur im Scan zu einem fast
schwarzen Band mit feinen weißen Lücken. Das Skelett eines solchen Bands ist ein
Knotengeflecht (Zickzack, Liniensterne). Stattdessen: Band finden, aus dem Skelettbild nehmen,
als geschlossene Umrisse (Layer WAENDE) zurückgeben. Export und Zeichenfläche füllen
geschlossene WAENDE-Polylinien als Fläche (Schalter „Schraffur als Fläche“).
"""
from __future__ import annotations

from typing import List

import cv2
import numpy as np

from .model import LAYER_WALLS, Polyline

W_MIN_MM = 0.8        # Band mindestens so breit (Papier-mm)
FILL_MIN = 0.7        # Tintenanteil im Band (Lücken der Schraffur ≤ 30 %)
LEN_MIN = 3.0         # Fläche mindestens LEN_MIN × W_MIN_MM
STROKE_FACTOR = 4.0   # und mindestens so viel mal breiter als der typische Strich der Zeichnung


def stroke_width(m: np.ndarray) -> float:
    """Typische Strichbreite (px): Median der doppelten Kammhöhe der Abstandstransformation."""
    d = cv2.distanceTransform(m, cv2.DIST_L2, 3)
    ridge = (d > 0) & (d >= cv2.dilate(d, np.ones((3, 3), np.uint8)))
    return float(np.median(2 * d[ridge])) if ridge.any() else 0.0


def find_bands(bw: np.ndarray, px_per_mm: float, w_min_mm: float = W_MIN_MM,
               fill_min: float = FILL_MIN) -> np.ndarray:
    """Maske (bool) der Wandbänder im Binärbild (Tinte > 0).

    Grobe Scans haben dicke Striche (Möbel, Schrift ~1 mm): ein Band muss deshalb auch deutlich
    breiter sein als der typische Strich, sonst bleibt alles beim Skelett."""
    m = (bw > 0).astype(np.uint8)
    w_px = max(w_min_mm * px_per_mm, STROKE_FACTOR * stroke_width(m))
    solid = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    r = max(2, int(round(w_px / 2)))
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1))
    band = cv2.morphologyEx(solid, cv2.MORPH_OPEN, k)
    n, lab, st, _ = cv2.connectedComponentsWithStats(band, connectivity=8)
    if n <= 1:
        return np.zeros(bw.shape[:2], bool)
    keep = np.zeros(n, bool)
    min_area = LEN_MIN * w_px * w_px
    for i in range(1, n):
        if st[i, cv2.CC_STAT_AREA] < min_area:
            continue
        x, y, w, h = st[i, :4]
        sub = lab[y:y + h, x:x + w] == i
        ink = m[y:y + h, x:x + w]
        keep[i] = ink[sub].mean() >= fill_min and not _lengthwise_gaps(sub, ink, px_per_mm)
    return keep[lab]


GAP_LEN_MM = 0.8      # weiße Lücke so lang waagrecht/senkrecht = Lücke zwischen Parallelen
GAP_SHARE = 0.2       # ab diesem Flächenanteil ist das Band ein Fenster (Rahmen-/Glaslinien)


def _lengthwise_gaps(sub: np.ndarray, ink: np.ndarray, px_per_mm: float) -> bool:
    """Fenster im Grundriss: 3–4 eng parallele Linien verschmelzen zum Band, das Weiß dazwischen
    läuft lang durch. Schraffur hat nur kurze, schräge Lücken."""
    inner = cv2.erode(sub.astype(np.uint8), np.ones((3, 3), np.uint8))
    white = (inner > 0) & (ink == 0)
    k = max(3, int(round(GAP_LEN_MM * px_per_mm)))
    w8 = white.astype(np.uint8)
    run = (cv2.morphologyEx(w8, cv2.MORPH_OPEN, np.ones((1, k), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0)
           | cv2.morphologyEx(w8, cv2.MORPH_OPEN, np.ones((k, 1), np.uint8), borderType=cv2.BORDER_CONSTANT, borderValue=0))
    return run.sum() >= GAP_SHARE * max(int(sub.sum()), 1)


def band_outlines(band: np.ndarray, tolerance: float = 1.0) -> List[Polyline]:
    """Umrisse (außen und Löcher) der Bänder als geschlossene Polylinien auf WAENDE."""
    cs, _ = cv2.findContours(band.astype(np.uint8), cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in cs:
        if len(c) < 4:
            continue
        a = cv2.approxPolyDP(c, max(0.5, tolerance), True).reshape(-1, 2)
        if len(a) < 3:
            continue
        p = Polyline([(float(x), float(y)) for x, y in a], True, LAYER_WALLS)
        p.lineweight = 0.0
        out.append(p)
    return out


def wall_polys(ents) -> List[Polyline]:
    """Geschlossene Polylinien auf WAENDE – diese werden als Fläche gefüllt."""
    return [e for e in ents if isinstance(e, Polyline) and e.closed and e.layer == LAYER_WALLS
            and len(e.points) >= 3]


def fill_mask(ents, shape) -> np.ndarray:
    """Gefüllte Wandflächen (gerade/ungerade: Löcher bleiben frei) als bool-Maske."""
    img = np.zeros(shape[:2], np.uint8)
    ps = [np.round(np.asarray(p.points)).astype(np.int32) for p in wall_polys(ents)]
    if ps:
        cv2.fillPoly(img, ps, 1)
    return img > 0


def groups(polys: List[Polyline]) -> List[List[Polyline]]:
    """Umrisse nach Schachtelung gruppieren: je Außenumriss seine direkten Löcher.

    Tiefe gerade = Fläche, ungerade = Loch (wie gerade/ungerade-Füllung)."""
    if not polys:
        return []
    cs = [np.asarray(p.points, np.float32) for p in polys]
    area = [abs(cv2.contourArea(c)) for c in cs]
    box = [(c[:, 0].min(), c[:, 1].min(), c[:, 0].max(), c[:, 1].max()) for c in cs]
    order = sorted(range(len(polys)), key=lambda i: area[i])
    parent = [-1] * len(polys)
    for k, i in enumerate(order):
        px, py = map(float, cs[i][0])
        for j in order[k + 1:]:
            b = box[j]
            if b[0] <= px <= b[2] and b[1] <= py <= b[3] and \
                    cv2.pointPolygonTest(cs[j], (px, py), False) > 0:
                parent[i] = j
                break
    depth = []
    for i in range(len(polys)):
        d, j = 0, parent[i]
        while j >= 0:
            d, j = d + 1, parent[j]
        depth.append(d)
    out = {i: [polys[i]] for i in range(len(polys)) if depth[i] % 2 == 0}
    for i in range(len(polys)):
        if depth[i] % 2 == 1 and parent[i] in out:
            out[parent[i]].append(polys[i])
    return list(out.values())
