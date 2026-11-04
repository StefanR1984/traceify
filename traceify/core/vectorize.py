"""Vektorisierung von Binärbildern.

Zwei Verfahren, wie bei professionellen Konvertern üblich:

* **Mittellinie (CAD)** – das Bild wird auf 1 px skelettiert, das Skelett in
  Pfade zwischen Knoten zerlegt und jeder Pfad durch Linien, Bögen und Kreise
  angenähert. Ergebnis: saubere CAD-Geometrie für technische Zeichnungen.
* **Umriss (CNC)** – die Außen- und Innenkonturen jeder Fläche werden als
  geschlossene, geglättete Polylinien erzeugt. Ergebnis: fräsfertige Konturen
  für Logos, Schriftzüge, Dichtungen usw.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
from skimage.morphology import skeletonize

from .model import (Arc, Circle, Line, Polyline, LAYER_CONTOURS,
                    LAYER_POLY)

MODE_CENTERLINE = "mittellinie"
MODE_OUTLINE = "umriss"


@dataclass
class VectorizeSettings:
    mode: str = MODE_CENTERLINE
    tolerance: float = 1.5        # max. Abweichung in px bei der Annäherung
    detect_arcs: bool = True      # Bögen erkennen
    detect_circles: bool = True   # Kreise erkennen
    output_polylines: bool = False  # statt Linien/Bögen nur Polylinien
    min_length: float = 6.0       # kürzere Pfade verwerfen (px)
    min_arc_angle: float = 25.0   # Bögen mit kleinerem Öffnungswinkel -> Linien
    snap_distance: float = 3.0    # Endpunkte innerhalb dieser Distanz verbinden
    contour_smooth: int = 2       # Glättung der Umrisse (CNC), 0 = aus
    corner_angle: float = 40.0    # ab diesem Knickwinkel wird an einer Ecke getrennt


# --------------------------------------------------------------------------
# Skelett -> Pfade
# --------------------------------------------------------------------------
_NB8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
_NB_ORDER = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]


def skeletonize_fast(mask: np.ndarray, tile_px: int = 3000, margin: int = 160) -> np.ndarray:
    """Skelettierung; große Bilder in überlappenden Kacheln auf allen Kernen.

    Zhang-Suen ist ein lokales Verfahren: Mit einem Rand breiter als die halbe Strichstärke
    ist das Ergebnis pixelgenau gleich wie bei der Berechnung am Stück.
    """
    H, W = mask.shape
    if H * W <= 2 * tile_px * tile_px:
        return skeletonize(mask)
    import os
    from concurrent.futures import ThreadPoolExecutor
    out = np.zeros(mask.shape, dtype=bool)
    tiles = [(y, x, min(H, y + tile_px), min(W, x + tile_px))
             for y in range(0, H, tile_px) for x in range(0, W, tile_px)]

    def job(t):
        y0, x0, y1, x1 = t
        Y0, X0, Y1, X1 = max(0, y0 - margin), max(0, x0 - margin), min(H, y1 + margin), \
            min(W, x1 + margin)
        sub = mask[Y0:Y1, X0:X1]
        if not sub.any():
            return t, None
        sk = skeletonize(sub)
        return t, sk[y0 - Y0:y1 - Y0, x0 - X0:x1 - X0]

    with ThreadPoolExecutor(max_workers=max(1, min(8, os.cpu_count() or 2))) as ex:
        for (y0, x0, y1, x1), sk in ex.map(job, tiles):
            if sk is not None:
                out[y0:y1, x0:x1] = sk
    return out


def _prune_spurs(skel: np.ndarray, nb: np.ndarray, dist: np.ndarray, factor: float = 2.0) -> int:
    """Entfernt kurze Seitenäste („Fransen“), die die Skelettierung an Enden und Ecken
    dicker Striche erzeugt. Ein Ast gilt als Franse, wenn er von einem Endpunkt bis zu einem
    Knoten kürzer ist als ~1,4 × halbe Strichstärke am Knoten. Ändert skel in place."""
    ys, xs = np.nonzero((nb == 1) & (skel > 0))
    removed = 0
    H, W = skel.shape
    limit = 2 + int(factor * float(dist.max()))  # obere Schranke, verfeinert am Knoten
    for y0, x0 in zip(ys, xs):
        path = [(y0, x0)]
        prev = None
        cy, cx = y0, x0
        junction = None
        while len(path) <= limit:
            nxt = []
            for dy, dx in _NB8:
                ny, nx = cy + dy, cx + dx
                if 0 <= ny < H and 0 <= nx < W and skel[ny, nx] and (ny, nx) != prev \
                        and (ny, nx) not in path:
                    nxt.append((ny, nx))
            if not nxt:
                break                      # isolierter kurzer Strich – kein Seitenast
            if len(nxt) > 1 or nb[nxt[0]] >= 3:
                junction = nxt[0] if len(nxt) == 1 else (cy, cx)
                break
            prev = (cy, cx)
            cy, cx = nxt[0]
            path.append((cy, cx))
        if junction is None:
            continue
        thick = float(dist[junction])
        if thick < 2.5:                    # dünne Linien: echte kurze Striche behalten
            continue
        if len(path) <= max(2, factor * thick):
            for (py, px) in path:
                if (py, px) != junction:
                    skel[py, px] = 0
            removed += 1
    return removed


def _ends_at_junction(pts, centroid_set) -> bool:
    return tuple(pts[-1]) in centroid_set


def _extend(pts, dist):
    """Verlängert das Ende einer Punktfolge in Laufrichtung um (Abstandswert - 1)."""
    x, y = pts[-1]
    xi, yi = int(round(x)) + 1, int(round(y)) + 1   # dist ist um 1 Pixel gepolstert
    if not (0 <= yi < dist.shape[0] and 0 <= xi < dist.shape[1]):
        return pts
    ext = float(dist[yi, xi]) - 1.0
    if ext < 1.5:
        return pts
    k = min(len(pts) - 1, 8)
    dx, dy = x - pts[-1 - k][0], y - pts[-1 - k][1]
    n = math.hypot(dx, dy)
    if n < 1e-6:
        return pts
    return list(pts) + [(x + dx / n * ext, y + dy / n * ext)]


def trace_skeleton(bw: np.ndarray, prune: bool = True) -> List[Tuple[List[Tuple[float, float]], bool]]:
    """Zerlegt das Skelett in Pfade. Gibt Liste von (Punkte[x,y], geschlossen) zurück."""
    skel = skeletonize_fast(bw > 0)
    skel = np.pad(skel, 1).astype(np.uint8)
    k = np.ones((3, 3), np.uint8)
    k[1, 1] = 0
    nb = cv2.filter2D(skel, -1, k, borderType=cv2.BORDER_CONSTANT)
    nb = nb * skel
    dist = None
    if prune:
        dist = cv2.distanceTransform(np.pad((bw > 0).astype(np.uint8), 1), cv2.DIST_L2, 3)
        if _prune_spurs(skel, nb, dist):
            nb = cv2.filter2D(skel, -1, k, borderType=cv2.BORDER_CONSTANT) * skel

    junction = (nb >= 3) & (skel > 0)
    n_j, jlab = cv2.connectedComponents(junction.astype(np.uint8), connectivity=8)
    centroids = {}
    if n_j > 1:
        ys, xs = np.nonzero(jlab)
        labs = jlab[ys, xs]
        for lab in range(1, n_j):
            sel = labs == lab
            centroids[lab] = (float(xs[sel].mean()) - 1, float(ys[sel].mean()) - 1)

    centroid_set = set(centroids.values())
    normal = (skel > 0) & ~junction
    visited = np.zeros_like(normal)
    paths: List[Tuple[List[Tuple[float, float]], bool]] = []

    def adj_junction(y, x, exclude=0):
        for dy, dx in _NB8:
            lab = jlab[y + dy, x + dx]
            if lab and lab != exclude:
                return lab
        return 0

    def walk(y, x, start_lab):
        pts = []
        if start_lab:
            pts.append(centroids[start_lab])
        cy, cx = y, x
        while True:
            visited[cy, cx] = True
            pts.append((cx - 1.0, cy - 1.0))
            nxt = None
            for dy, dx in _NB_ORDER:
                ny, nx = cy + dy, cx + dx
                if normal[ny, nx] and not visited[ny, nx]:
                    nxt = (ny, nx)
                    break
            if nxt is None:
                end_lab = adj_junction(cy, cx, exclude=start_lab if len(pts) <= 2 else 0)
                if not end_lab and start_lab and len(pts) > 2:
                    end_lab = adj_junction(cy, cx)
                if end_lab:
                    pts.append(centroids[end_lab])
                return pts
            cy, cx = nxt

    ys, xs = np.nonzero(normal)
    # 1) Start an Endpunkten und an Knoten-Nachbarn
    starts = []
    for y, x in zip(ys, xs):
        if nb[y, x] == 1:
            starts.append((y, x, 0))
        else:
            lab = adj_junction(y, x)
            if lab:
                starts.append((y, x, lab))
    for y, x, lab in starts:
        if not visited[y, x]:
            pts = walk(y, x, lab)
            if dist is not None and len(pts) >= 3:
                # Freie Enden um die halbe Strichstärke verlängern: das Skelett endet sonst
                # eine halbe Breite vor der Stirnseite dicker Striche (z. B. Wandenden)
                if not lab:
                    pts = _extend(pts[::-1], dist)[::-1]
                if not _ends_at_junction(pts, centroid_set):
                    pts = _extend(pts, dist)
            paths.append((pts, False))

    # 2) übrig gebliebene Ringe (geschlossene Kurven ohne Knoten)
    for y, x in zip(ys, xs):
        if not visited[y, x]:
            pts = walk(y, x, 0)
            paths.append((pts, True))

    return paths


# --------------------------------------------------------------------------
# Annäherung von Punktfolgen durch Linien / Bögen
# --------------------------------------------------------------------------
def _pt(p):
    return (float(p[0]), float(p[1]))


def _line_dev(pts: np.ndarray) -> Tuple[float, int]:
    a, b = pts[0], pts[-1]
    d = b - a
    L = math.hypot(*d)
    if L < 1e-9:
        dist = np.hypot(*(pts - a).T)
    else:
        dist = np.abs(d[0] * (pts[:, 1] - a[1]) - d[1] * (pts[:, 0] - a[0])) / L
    i = int(np.argmax(dist))
    return float(dist[i]), i


def fit_circle(pts: np.ndarray) -> Optional[Tuple[float, float, float, float]]:
    """Algebraischer Kreis-Fit (Kasa). Gibt (cx, cy, r, max_residuum) zurück."""
    if len(pts) < 5:
        return None
    x, y = pts[:, 0], pts[:, 1]
    A = np.column_stack([x, y, np.ones_like(x)])
    b = x * x + y * y
    try:
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    cx, cy = sol[0] / 2, sol[1] / 2
    r2 = sol[2] + cx * cx + cy * cy
    if r2 <= 0:
        return None
    r = math.sqrt(r2)
    res = np.abs(np.hypot(x - cx, y - cy) - r)
    return cx, cy, r, float(res.max())


def _arc_span(pts: np.ndarray, cx: float, cy: float) -> Tuple[float, float, float]:
    ang = np.unwrap(np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx))
    a0, a1 = float(ang[0]), float(ang[-1])
    # monotonie prüfen – sonst kein echter Bogen
    d = np.diff(ang)
    if not (np.all(d >= -0.05) or np.all(d <= 0.05)):
        return 0.0, 0.0, 0.0
    return math.degrees(a0), math.degrees(a1), math.degrees(abs(a1 - a0))


class Fitter:
    def __init__(self, s: VectorizeSettings, max_radius: float):
        self.s = s
        self.max_radius = max_radius

    def fit(self, pts: np.ndarray, closed: bool) -> list:
        s = self.s
        if not closed and len(pts) > 8 and math.dist(pts[0], pts[-1]) < 2.5:
            closed = True
            pts = pts[:-1]
        corners = find_corners(pts, closed, s.corner_angle)
        if corners:
            if closed:
                # Ring an der ersten Ecke aufschneiden
                c0 = corners[0]
                pts = np.vstack([pts[c0:], pts[:c0 + 1]])
                corners = [c - c0 for c in corners[1:]] + [len(pts) - 1]
                closed = False
            out, last = [], 0
            for c in corners + [len(pts) - 1]:
                if c - last >= 1:
                    out += self._fit_open(pts[last:c + 1])
                last = c
            return out
        if closed and s.detect_circles and len(pts) >= 12:
            c = fit_circle(pts)
            if c and c[3] <= s.tolerance * 1.5 and c[2] < self.max_radius and c[2] >= 2:
                return [Circle((float(c[0]), float(c[1])), float(c[2]))]
        if closed:
            # an weitestem Punkt aufteilen, damit beide Hälften offen sind
            d = np.hypot(*(pts - pts[0]).T)
            i = int(np.argmax(d))
            if 2 <= i <= len(pts) - 3:
                return self._fit_open(pts[: i + 1]) + self._fit_open(
                    np.vstack([pts[i:], pts[:1]]))
        return self._fit_open(pts)

    def _fit_open(self, pts: np.ndarray, depth: int = 0) -> list:
        s = self.s
        if len(pts) < 2:
            return []
        dev, i = _line_dev(pts)
        if dev <= s.tolerance or len(pts) <= 3:
            return [Line(_pt(pts[0]), _pt(pts[-1]))]
        if s.detect_arcs and len(pts) >= 8:
            c = fit_circle(pts)
            if (not c or c[3] > s.tolerance) and len(pts) >= 16:
                # Robust: Enden (Knotenpunkte verzerren oft) beim Fit ignorieren
                k = max(2, len(pts) // 20)
                c2 = fit_circle(pts[k:-k])
                if c2:
                    end_res = max(abs(math.hypot(*(pts[0] - c2[:2])) - c2[2]),
                                  abs(math.hypot(*(pts[-1] - c2[:2])) - c2[2]))
                    if c2[3] <= s.tolerance and end_res <= 4 * s.tolerance:
                        c = (c2[0], c2[1], c2[2], c2[3])
            if c and c[3] <= s.tolerance and c[2] < self.max_radius:
                a0, a1, span = _arc_span(pts, c[0], c[1])
                if span >= 359:
                    return [Circle((float(c[0]), float(c[1])), float(c[2]))] if s.detect_circles else \
                        self._split(pts, i, depth)
                if span >= s.min_arc_angle:
                    if a1 < a0:
                        a0, a1 = a1, a0
                    return [Arc((float(c[0]), float(c[1])), float(c[2]), a0 % 360, a1 % 360)]
        return self._split(pts, i, depth)

    def _split(self, pts, i, depth):
        if depth > 60 or i <= 0 or i >= len(pts) - 1:
            return [Line(_pt(pts[0]), _pt(pts[-1]))]
        # Bei Bogen-Erkennung lieber an "Ecken" trennen: max. Krümmung nahe i
        return self._fit_open(pts[: i + 1], depth + 1) + self._fit_open(pts[i:], depth + 1)


def find_corners(pts: np.ndarray, closed: bool, min_angle: float, w: int = 6) -> List[int]:
    """Indizes scharfer Ecken (Richtungsänderung > min_angle) per Fenster-Methode."""
    n = len(pts)
    if n < 2 * w + 3 or min_angle <= 0:
        return []
    idx = np.arange(n)
    if closed:
        prev = pts[(idx - w) % n]
        nxt = pts[(idx + w) % n]
        valid = np.ones(n, bool)
    else:
        prev = pts[np.clip(idx - w, 0, n - 1)]
        nxt = pts[np.clip(idx + w, 0, n - 1)]
        valid = (idx >= w) & (idx < n - w)
    v1 = pts - prev
    v2 = nxt - pts
    a1 = np.arctan2(v1[:, 1], v1[:, 0])
    a2 = np.arctan2(v2[:, 1], v2[:, 0])
    turn = np.degrees(np.abs((a2 - a1 + np.pi) % (2 * np.pi) - np.pi))
    turn[~valid] = 0
    corners = []
    for i in np.argsort(-turn):
        if turn[i] < min_angle:
            break
        if all(min(abs(i - c), n - abs(i - c) if closed else n) > w for c in corners):
            corners.append(int(i))
    return sorted(corners)


def _path_length(pts: np.ndarray) -> float:
    return float(np.hypot(*np.diff(pts, axis=0).T).sum()) if len(pts) > 1 else 0.0


def merge_collinear(ents: list, angle_tol=2.0, tol=1.0) -> list:
    """Führt aufeinanderfolgende, kollineare Linien zusammen."""
    out = []
    for e in ents:
        if out and isinstance(e, Line) and isinstance(out[-1], Line):
            p = out[-1]
            if np.allclose(p.p2, e.p1, atol=tol):
                a1 = math.atan2(p.p2[1] - p.p1[1], p.p2[0] - p.p1[0])
                a2 = math.atan2(e.p2[1] - e.p1[1], e.p2[0] - e.p1[0])
                da = abs((math.degrees(a1 - a2) + 180) % 360 - 180)
                if da < angle_tol:
                    out[-1] = Line(p.p1, e.p2, p.layer)
                    continue
        out.append(e)
    return out


def snap_endpoints(ents: list, dist: float) -> None:
    """Fasst nahe beieinanderliegende Linienendpunkte auf einen Punkt zusammen."""
    if dist <= 0:
        return
    pts = []
    for idx, e in enumerate(ents):
        if isinstance(e, Line):
            pts.append((idx, 0, e.p1))
            pts.append((idx, 1, e.p2))
    if not pts:
        return
    arr = np.array([p[2] for p in pts])
    grid = {}
    for k, (x, y) in enumerate(arr):
        grid.setdefault((int(x // dist), int(y // dist)), []).append(k)
    parent = list(range(len(arr)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for (gx, gy), ks in grid.items():
        cand = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                cand += grid.get((gx + dx, gy + dy), [])
        for a in ks:
            for b in cand:
                if a < b and np.hypot(*(arr[a] - arr[b])) <= dist:
                    parent[find(a)] = find(b)
    groups = {}
    for k in range(len(arr)):
        groups.setdefault(find(k), []).append(k)
    for ks in groups.values():
        if len(ks) < 2:
            continue
        c = _pt(arr[ks].mean(axis=0))
        for k in ks:
            idx, end, _ = pts[k]
            if end == 0:
                ents[idx].p1 = c
            else:
                ents[idx].p2 = c


def vectorize_centerline(bw: np.ndarray, s: VectorizeSettings) -> list:
    max_r = 3 * max(bw.shape)
    fitter = Fitter(s, max_r)
    ents = []
    for pts, closed in trace_skeleton(bw):
        a = np.asarray(pts, dtype=float)
        if len(a) < 2 or _path_length(a) < s.min_length:
            continue
        if s.output_polylines:
            approx = cv2.approxPolyDP(a.astype(np.float32).reshape(-1, 1, 2),
                                      s.tolerance, closed).reshape(-1, 2)
            ents.append(Polyline([tuple(map(float, p)) for p in approx], closed, LAYER_POLY))
        else:
            ents.extend(merge_collinear(fitter.fit(a, closed)))
    if not s.output_polylines:
        snap_endpoints(ents, s.snap_distance)
    # degenerierte (fast punktförmige) Linien entfernen
    ents = [e for e in ents if not (isinstance(e, Line) and
                                    math.dist(e.p1, e.p2) < max(1.0, s.tolerance))]
    return ents


def _smooth_closed(pts: np.ndarray, k: int) -> np.ndarray:
    if k <= 0 or len(pts) < 2 * k + 3:
        return pts
    n = len(pts)
    w = 2 * k + 1
    padded = np.vstack([pts[-k:], pts, pts[:k]])
    ker = np.ones(w) / w
    xs = np.convolve(padded[:, 0], ker, mode="valid")
    ys = np.convolve(padded[:, 1], ker, mode="valid")
    return np.column_stack([xs, ys])[:n]


def vectorize_outline(bw: np.ndarray, s: VectorizeSettings) -> list:
    contours, _hier = cv2.findContours(bw, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    ents = []
    for c in contours:
        pts = c.reshape(-1, 2).astype(float)
        if len(pts) < 3 or cv2.arcLength(c, True) < s.min_length:
            continue
        pts = _smooth_closed(pts, s.contour_smooth)
        if s.detect_circles and len(pts) >= 16:
            fc = fit_circle(pts)
            if fc and fc[3] <= s.tolerance and fc[2] >= 2:
                ents.append(Circle((float(fc[0]), float(fc[1])), float(fc[2]), LAYER_CONTOURS))
                continue
        approx = cv2.approxPolyDP(pts.astype(np.float32).reshape(-1, 1, 2),
                                  s.tolerance, True).reshape(-1, 2)
        if len(approx) >= 3:
            ents.append(Polyline([tuple(map(float, p)) for p in approx], True, LAYER_CONTOURS))
    return ents


def vectorize(bw: np.ndarray, s: VectorizeSettings) -> list:
    if s.mode == MODE_OUTLINE:
        return vectorize_outline(bw, s)
    return vectorize_centerline(bw, s)
