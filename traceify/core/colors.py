"""Farbtrennung: farbige Pläne nach Farbe auf eigene Layer verteilen.

Die „Tinte“ (alles, was nicht Papierweiß ist) wird im Lab-Farbraum mit k-Means
gruppiert; ähnliche Gruppen werden zusammengelegt, sehr kleine verworfen.
Jede Farbe ergibt eine Maske, die getrennt vektorisiert wird
(Layer FARBE_ROT, FARBE_BLAU, FARBE_SCHWARZ, …).
"""
from __future__ import annotations

import colorsys
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np


@dataclass
class ColorGroup:
    name: str                    # Layername, z. B. FARBE_ROT
    rgb: Tuple[int, int, int]
    mask: np.ndarray             # uint8, 255 = Tinte dieser Farbe
    share: float                 # Anteil an der gesamten Tinte


def color_name(rgb) -> str:
    r, g, b = [c / 255.0 for c in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    if s < 0.22 or l < 0.12:
        return "SCHWARZ" if l < 0.45 else "GRAU"
    h *= 360
    if l > 0.85:
        return "HELL"
    if h < 15 or h >= 340:
        return "ROT"
    if h < 40:
        return "ORANGE" if l > 0.35 else "BRAUN"
    if h < 70:
        return "GELB"
    if h < 160:
        return "GRUEN"
    if h < 200:
        return "CYAN"
    if h < 260:
        return "BLAU"
    if h < 300:
        return "VIOLETT"
    return "MAGENTA"


def ink_mask(bgr: np.ndarray) -> np.ndarray:
    """Alles, was sich deutlich vom (hellen, unbunten) Papier abhebt."""
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    s, v = hsv[..., 1].astype(np.int16), hsv[..., 2].astype(np.int16)
    # Papierhelligkeit robust schätzen (helle 60 %)
    paper = np.percentile(v, 60)
    m = (v < paper - 60) | ((s > 70) & (v > 40))
    m = m.astype(np.uint8) * 255
    from .preprocess import remove_small   # Rauschpunkte entfernen, ohne Linien zu verschieben
    return remove_small(m, 4)


def is_colorful(bgr: Optional[np.ndarray], min_share: float = 0.02) -> bool:
    if bgr is None or bgr.ndim != 3:
        return False
    m = ink_mask(bgr) > 0
    if m.sum() < 50:
        return False
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    chroma = (hsv[..., 1] > 70) & m
    return chroma.sum() / m.sum() >= min_share


def separate(bgr: np.ndarray, k: int = 0, max_k: int = 8, merge_de: float = 22.0,
             min_share: float = 0.01, sample: int = 60000) -> List[ColorGroup]:
    """Teilt die Tinte in Farbgruppen. k=0: Anzahl automatisch bestimmen."""
    ink = ink_mask(bgr)
    ys, xs = np.nonzero(ink)
    if len(ys) < 20:
        return []
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    px = lab[ys, xs].astype(np.float32)
    rng = np.random.default_rng(0)
    idx = rng.choice(len(px), size=min(sample, len(px)), replace=False)
    data = px[idx]
    kk = max(1, min(k if k > 0 else max_k, len(data)))
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
    _, _, centers = cv2.kmeans(data, kk, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    centers = centers.astype(np.float32)

    def assign(c):
        d = ((px[:, None, :] - c[None, :, :]) ** 2).sum(-1)
        return d.argmin(1)

    if k <= 0:
        # ähnliche Zentren zusammenlegen (ΔE in OpenCV-Lab-Skala grob ×1)
        changed = True
        while changed and len(centers) > 1:
            changed = False
            d = np.sqrt(((centers[:, None] - centers[None]) ** 2).sum(-1))
            np.fill_diagonal(d, 1e9)
            i, j = np.unravel_index(d.argmin(), d.shape)
            if d[i, j] < merge_de:
                centers[i] = (centers[i] + centers[j]) / 2
                centers = np.delete(centers, j, axis=0)
                changed = True
    lbl = assign(centers)
    # kleine Gruppen dem nächsten Zentrum zuschlagen
    counts = np.bincount(lbl, minlength=len(centers))
    keep = counts >= max(20, min_share * len(lbl))
    if not keep.all() and keep.any():
        centers = centers[keep]
        lbl = assign(centers)
    groups = []
    used = {}
    H, W = ink.shape
    for ci, c in enumerate(centers):
        sel = lbl == ci
        if not sel.any():
            continue
        m = np.zeros((H, W), np.uint8)
        m[ys[sel], xs[sel]] = 255
        m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        bgr_c = cv2.cvtColor(np.uint8([[np.clip(c, 0, 255)]]), cv2.COLOR_LAB2BGR)[0, 0]
        rgb = (int(bgr_c[2]), int(bgr_c[1]), int(bgr_c[0]))
        base = "FARBE_" + color_name(rgb)
        used[base] = used.get(base, 0) + 1
        name = base if used[base] == 1 else f"{base}_{used[base]}"
        groups.append(ColorGroup(name, rgb, m, float(sel.mean())))
    groups.sort(key=lambda g: -g.share)
    return groups


def layer_for_rgb(rgb) -> str:
    """Layername für eine vorhandene Objektfarbe (Vektor-PDF); None/Schwarz -> FARBE_SCHWARZ."""
    if not rgb:
        return "FARBE_SCHWARZ"
    return "FARBE_" + color_name(rgb)
