"""Gerade ausrichten: Schräglage des Scans erkennen und Linien exakt achsparallel machen.

Gescannte Pläne liegen oft um 0,5–1,5° schief, und Linien wackeln um ihre Richtung.
Hier wird aus den langen Linien die Hauptrichtung (Schräglage) bestimmt. Fast
waagrechte/senkrechte Linien werden dann exakt auf diese Achsen gelegt, verbundene Ecken
bleiben verbunden. Die Vektoren liegen dabei weiter deckungsgleich auf dem Scan; beim
Export dreht ``Drawing.export_view`` die Schräglage heraus, sodass die Wände im CAD exakt
waagrecht und senkrecht sind.
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np

from .edit import orthogonalize, rotate
from .model import Line

META_KEY = "schraeglage"     # Grad, Bildsystem (y nach unten)


def estimate_skew(ents: list, min_len: float = 40.0, max_deg: float = 5.0) -> Optional[float]:
    """Hauptrichtung der langen, fast achsparallelen Linien in Grad (Bild, y nach unten).

    None, wenn es dafür zu wenige lange Linien gibt."""
    A, W = [], []
    for e in ents:
        if not isinstance(e, Line):
            continue
        L = math.dist(e.p1, e.p2)
        if L < min_len:
            continue
        a = math.degrees(math.atan2(e.p2[1] - e.p1[1], e.p2[0] - e.p1[0])) % 90.0
        if a > 45:
            a -= 90.0
        if abs(a) <= max_deg:
            A.append(a)
            W.append(L)
    if len(A) < 4 or sum(W) < 10 * min_len:
        return None
    A, W = np.array(A), np.array(W)
    hist, edges = np.histogram(A, bins=int(4 * max_deg * 10), range=(-max_deg, max_deg), weights=W)
    k = int(np.argmax(hist))
    peak = (edges[k] + edges[k + 1]) / 2
    near = np.abs(A - peak) <= 0.4                    # verfeinern: gewichtetes Mittel um die Spitze
    if W[near].sum() < 0.15 * W.sum():
        return None
    return float(np.average(A[near], weights=W[near]))


def straighten(ents: list, width: int, height: int, tol_deg: float = 3.0,
               join_tol: float = 2.0, min_len: float = 40.0,
               min_px: float = 1.5) -> Optional[float]:
    """Richtet fast achsparallele Linien exakt an der Schräglage aus (ändert ents).

    Gibt die Schräglage zurück (Grad, Bild) oder None, wenn keine bestimmbar war."""
    skew = estimate_skew(ents, min_len)
    if skew is None:
        return None
    c = (width / 2.0, height / 2.0)
    idx = [i for i, e in enumerate(ents) if isinstance(e, Line)]
    lines = [rotate(ents[i], c, -skew) for i in idx]
    orthogonalize(lines, tol_deg=tol_deg, join_tol=join_tol, min_px=min_px)
    for i, l in zip(idx, lines):
        r = rotate(l, c, skew)
        ents[i].p1, ents[i].p2 = r.p1, r.p2
    return skew
