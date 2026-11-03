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


def to_binary(gray: np.ndarray, s: PreprocessSettings) -> np.ndarray:
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
    for x1, y1, x2, y2 in lines[:, 0]:
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
