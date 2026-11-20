"""Raster-Vorverarbeitung: Schwellwert, Entrauschen, Begradigen, Invertieren …

Alle Funktionen arbeiten auf Graustufenbildern (uint8, 0=schwarz, 255=weiß)
bzw. liefern ein Binärbild, in dem die Zeichnung WEISS (255) auf SCHWARZ (0)
liegt – das ist die Form, die die Vektorisierung erwartet.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class PreprocessSettings:
    threshold: int = 0            # 0 = automatisch (Otsu), sonst 1..254
    adaptive: bool = False        # adaptiver Schwellwert für ungleichmäßige Scans
    invert: bool = False          # helle Linien auf dunklem Grund
    despeckle: int = 12           # Flecken bis zu dieser Fläche (px²) entfernen
    fill_holes: int = 0           # Löcher bis zu dieser Fläche (px²) füllen
    deskew: bool = False          # Schräglage korrigieren
    smooth: int = 0               # 0 = aus, sonst Kernelgröße für Glättung
    thicken: int = 0              # Linien um n Pixel verdicken (Lücken schließen)
    auto: bool = True             # automatische Bildaufbereitung (siehe `enhance_binary`)


def to_binary(gray: np.ndarray, s: PreprocessSettings, px_per_mm: float = 0.0) -> np.ndarray:
    """Graubild → Binärbild (Zeichnung weiß). Mit ``px_per_mm`` und ``s.auto`` zusätzlich die
    automatische Aufbereitung, die die Auflösung kennen muss."""
    img = gray
    if s.smooth and s.smooth > 1:
        k = s.smooth | 1
        img = cv2.GaussianBlur(img, (k, k), 0)

    if s.adaptive:
        bw = cv2.adaptiveThreshold(img, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 35, 15)
    elif s.threshold and 0 < s.threshold < 255:
        _, bw = cv2.threshold(img, s.threshold, 255, cv2.THRESH_BINARY_INV)
    else:
        _, bw = cv2.threshold(img, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)

    if s.invert:
        bw = 255 - bw
    if s.auto and px_per_mm > 0:
        bw = enhance_binary(bw, px_per_mm)
    if s.deskew:
        bw = deskew(bw)
    if s.despeckle:
        bw = remove_small(bw, s.despeckle)
    if s.fill_holes:
        bw = 255 - remove_small(255 - bw, s.fill_holes)
    if s.thicken:
        k = 2 * s.thicken + 1
        bw = cv2.dilate(bw, np.ones((k, k), np.uint8))
    return bw


# Rasterfüllung (z. B. Wand grau angelegt, im Scan schwarz mit weißen Sprenkeln)
HOLE_MAX_MM2 = 1.5      # größtes Loch
HOLE_MIN_MM2 = 0.04     # Sprenkel ab dieser Fläche zählen für die Dichte
HOLE_MAX_ELONG = 3.0    # Länge/Breite: Sprenkel bis 2,8 (90 %), Schraffurlücken länger
HOLE_RING_MM = 0.6      # Umgebung des Lochs …
HOLE_DENSITY = 0.6      # … muss so dicht schwarz sein
HOLE_NEAR_MM = 1.5      # und so nah …
HOLE_MIN_NEAR = 5       # … so viele weitere Löcher liegen (einzelne Löcher sind gezeichnet)
HOLE_MIN_CV = 0.7       # Sprenkel sind ungleich groß (Variationskoeffizient der Lochflächen ringsum);
                        # Gitter, Treppenroste, Dämmung, Schriftknäuel haben gleich große Zellen


def _elongation(lab: np.ndarray, n: int, sel: np.ndarray) -> np.ndarray:
    """Länge/Breite (Wurzel der Hauptachsen-Varianzen) der ausgewählten Komponenten (sonst 0)."""
    ys, xs = np.nonzero(sel[lab])
    L = lab[ys, xs]
    xs, ys = xs.astype(np.float64), ys.astype(np.float64)
    a = np.maximum(np.bincount(L, minlength=n), 1).astype(float)
    mx, my = np.bincount(L, xs, n) / a, np.bincount(L, ys, n) / a
    sxx = np.bincount(L, xs * xs, n) / a - mx * mx + 1 / 12
    syy = np.bincount(L, ys * ys, n) / a - my * my + 1 / 12
    sxy = np.bincount(L, xs * ys, n) / a - mx * my
    tr, det = sxx + syy, sxx * syy - sxy * sxy
    d = np.sqrt(np.maximum(tr * tr / 4 - det, 0))
    return np.where(sel, np.sqrt((tr / 2 + d) / np.maximum(tr / 2 - d, 1e-6)), 0.0)


def fill_speckle_holes(bw: np.ndarray, px_per_mm: float, max_mm2: float = HOLE_MAX_MM2) -> np.ndarray:
    """Weiße Sprenkel in dunklen Füllflächen schließen. Eine grau angelegte Wand wird im Scan zu
    Schwarz mit vielen kleinen weißen Löchern – jedes Loch würde zu einem Ring aus Linien.
    Gefüllt wird nur, wo das Loch klein ist, ringsum fast alles schwarz ist und viele weitere
    solche Löcher dicht daneben liegen, die ungleich groß sind; Buchstaben-Innenräume (Umgebung
    halb weiß), einzeln gezeichnete Aussparungen in Symbolen, Schraffurlücken und Gitter mit
    gleich großen Zellen bleiben."""
    ppm = float(px_per_mm)
    area = max(4, int(max_mm2 * ppm * ppm))
    n, lab, st, cen = cv2.connectedComponentsWithStats((bw == 0).astype(np.uint8), connectivity=4)
    small = st[:, cv2.CC_STAT_AREA] <= area
    small[0] = False
    if not small.any():
        return bw
    k = max(3, int(round(2 * HOLE_RING_MM * ppm)) | 1)
    dens = cv2.boxFilter((bw > 0).astype(np.float32), -1, (k, k))
    mean = np.bincount(lab.ravel(), dens.ravel(), n) / np.maximum(1, st[:, cv2.CC_STAT_AREA])
    cand = small & (mean >= HOLE_DENSITY)
    if not cand.any():
        return bw
    # gezählt werden nur Sprenkel ab HOLE_MIN_MM2 – feine Schraffur in Plots wird an der Schwelle
    # schwarz mit 1–2-px-Löchern (Allplan-Wände), die bleibt Schraffur
    # und nur rundliche: die Lücken zwischen Schraffurlinien sind lange, schmale Streifen
    big = cand & (st[:, cv2.CC_STAT_AREA] >= HOLE_MIN_MM2 * ppm * ppm)
    big &= _elongation(lab, n, big) < HOLE_MAX_ELONG
    cb = np.clip(np.round(cen[big]).astype(int), 0, [bw.shape[1] - 1, bw.shape[0] - 1])
    ab = st[big, cv2.CC_STAT_AREA].astype(np.float64)
    kk = max(3, int(round(2 * HOLE_NEAR_MM * ppm)) | 1)
    c = np.clip(np.round(cen[cand]).astype(int), 0, [bw.shape[1] - 1, bw.shape[0] - 1])
    sums = []
    for w in (np.ones_like(ab), ab, ab * ab):        # Anzahl, Σ Fläche, Σ Fläche² ringsum
        pts = np.zeros(bw.shape, np.float64)
        np.add.at(pts, (cb[:, 1], cb[:, 0]), w)
        sums.append(cv2.boxFilter(pts, -1, (kk, kk), normalize=False)[c[:, 1], c[:, 0]])
    cnt, s1, s2 = sums
    mean = s1 / np.maximum(cnt, 1)
    cv = np.sqrt(np.maximum(s2 / np.maximum(cnt, 1) - mean * mean, 0)) / np.maximum(mean, 1e-9)
    ok = np.zeros(n, bool)
    ok[cand] = (cnt >= HOLE_MIN_NEAR) & (cv >= HOLE_MIN_CV)
    fill = cand & ok
    if not fill.any():
        return bw
    out = bw.copy()
    out[fill[lab]] = 255
    return out


def enhance_binary(bw: np.ndarray, px_per_mm: float) -> np.ndarray:
    """Automatische Aufbereitung des Binärbilds (Befund an echten Scans, siehe CHANGELOG 0.40)."""
    # zweimal: nach dem ersten Füllen ist die Umgebung der übrigen Löcher dichter
    return fill_speckle_holes(fill_speckle_holes(bw, px_per_mm), px_per_mm)


def remove_small(bw: np.ndarray, max_area: int) -> np.ndarray:
    """Entfernt zusammenhängende weiße Komponenten mit Fläche <= max_area."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    keep = np.zeros(n, dtype=bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] > max_area
    return np.where(keep[labels], 255, 0).astype(np.uint8)


def estimate_skew(bw: np.ndarray) -> float:
    """Schätzt die Schräglage in Grad über Hough-Linien (±15°)."""
    edges = cv2.Canny(bw, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 720, threshold=100,
                            minLineLength=max(bw.shape) // 10, maxLineGap=10)
    if lines is None:
        return 0.0
    angles = []
    for x1, y1, x2, y2 in lines.reshape(-1, 4):  # OpenCV 5 liefert (N, 4) statt (N, 1, 4)
        a = np.degrees(np.arctan2(y2 - y1, x2 - x1))
        a = (a + 45) % 90 - 45  # auf nächste Achse beziehen
        if abs(a) < 15:
            angles.append(a)
    return float(np.median(angles)) if angles else 0.0


def rotate(img: np.ndarray, angle: float, border=0) -> np.ndarray:
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_NEAREST,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=border)


def deskew(bw: np.ndarray) -> np.ndarray:
    a = estimate_skew(bw)
    return rotate(bw, a) if abs(a) > 0.05 else bw


def rotate90(gray: np.ndarray, times: int = 1) -> np.ndarray:
    return np.ascontiguousarray(np.rot90(gray, -times))


def crop(gray: np.ndarray, x: int, y: int, w: int, h: int) -> np.ndarray:
    return gray[y:y + h, x:x + w].copy()
