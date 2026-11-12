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

from .edit import align_axes
from .model import LAYER_HATCH, Line

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


def second_axes(ents: list, skew: float, min_len: float = 40.0, share: float = 0.04,
                min_sep: float = 8.0) -> list:
    """Weitere Bauachsen (z. B. schräger Gebäudeflügel): Richtungen in Grad (Bild, 0..90).

    Eine Richtung zählt, wenn mindestens ``share`` der Länge aller langen Linien nahe daran
    liegt und sie mehr als ``min_sep`` Grad von den Hauptachsen (Schräglage + 90°) entfernt ist.
    Der Wert ist das längengewichtete Mittel um die Spitze (±2°), also genauer als 1°."""
    A, W = [], []
    for e in ents:
        if isinstance(e, Line) and e.layer != LAYER_HATCH:      # Schraffur ist keine Bauachse
            L = math.dist(e.p1, e.p2)
            if L >= min_len:
                A.append(math.degrees(math.atan2(e.p2[1] - e.p1[1], e.p2[0] - e.p1[0])) % 90.0)
                W.append(L)
    if len(A) < 6:
        return []
    A, W = np.array(A), np.array(W)
    tot = W.sum()

    def dist(a, b):                          # Abstand auf dem 90°-Kreis
        d = np.abs(a - b) % 90.0
        return np.minimum(d, 90.0 - d)
    hist = np.zeros(90)
    for a, w in zip(A, W):
        hist[int(a) % 90] += w
    sm = sum(np.roll(hist, k) for k in range(-2, 3))
    out: list = []
    for a in sorted(range(90), key=lambda i: -sm[i]):          # stärkste Richtung zuerst
        if dist(a + 0.5, skew % 90.0) < min_sep:
            continue
        if sm[a] < share * tot or any(dist(a + 0.5, o) < min_sep for o in out):
            continue
        near = dist(A, a + 0.5) <= 2.0
        if W[near].sum() < share * tot:
            continue
        rel = ((A[near] - (a + 0.5) + 45.0) % 90.0) - 45.0      # zyklisches Mittel um die Spitze
        out.append(float((a + 0.5 + np.average(rel, weights=W[near])) % 90.0))
    return out


def straighten(ents: list, width: int, height: int, tol_deg: float = 3.0,
               join_tol: float = 2.0, min_len: float = 40.0,
               min_px: float = 1.5, second: bool = True,
               second_shift: float = 2.0) -> Optional[float]:
    """Richtet fast achsparallele Linien und Polylinien-Segmente exakt an der Schräglage aus (ändert ents).

    second: auch schräge Bauachsen (Gebäudeflügel) – deren Linien werden parallel/rechtwinklig
    zueinander ausgerichtet – aber nur, wenn sich eine Linie dabei höchstens um second_shift
    Pixel quer verschiebt (Flügel sind in Scans oft leicht verzogen; sonst wandern Wandenden
    neben die Tinte).
    Gibt die Schräglage zurück (Grad, Bild) oder None, wenn keine bestimmbar war."""
    skew = estimate_skew(ents, min_len)
    if skew is None:
        return None
    c = (width / 2.0, height / 2.0)
    align_axes(ents, skew, c, tol_deg=tol_deg, join_tol=join_tol, min_px=min_px)
    if second:
        bau = [e for e in ents if getattr(e, "layer", "") != LAYER_HATCH]
        for ax in second_axes(bau, skew, min_len):
            align_axes(bau, ax, c, tol_deg=min(tol_deg, 1.5), join_tol=join_tol,
                       max_shift=second_shift)
    return skew
