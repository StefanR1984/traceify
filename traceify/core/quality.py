"""Qualitätsprüfung: Wie gut decken die Vektoren den Scan ab?

Die Vektoren werden in ein Bild gezeichnet und mit der „Tinte“ des Scans verglichen:
* fehlt        – Tinte, die von keinem Vektor (oder Text) abgedeckt ist
* überflüssig  – Vektoren, wo im Scan nichts ist
Daraus ergeben sich Abdeckung, Genauigkeit, eine Ampel und eine Liste von Problemstellen.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List

import cv2
import numpy as np

from .model import Arc, Circle, Line, Polyline, Text

GREEN, YELLOW, RED = "gruen", "gelb", "rot"


@dataclass
class Problem:
    x: int
    y: int
    w: int
    h: int
    kind: str      # "fehlt" | "ueberfluessig"
    size: int      # Pixel


@dataclass
class QualityReport:
    rating: str
    coverage: float    # Anteil der Tinte, die abgedeckt ist
    precision: float   # Anteil der Vektoren, die auf Tinte liegen
    problems: List[Problem] = field(default_factory=list)
    hints: List[str] = field(default_factory=list)

    def summary(self) -> str:
        n_miss = sum(1 for p in self.problems if p.kind == "fehlt")
        n_extra = len(self.problems) - n_miss
        return (f"Abdeckung {self.coverage * 100:.1f} %, Genauigkeit {self.precision * 100:.1f} %"
                f" – {n_miss} fehlende, {n_extra} überflüssige Stellen"
                + "".join(" · " + h for h in self.hints))


def small_text_hint(ink: np.ndarray, mm_per_px: float, min_count: int = 100):
    """Hinweis, wenn ein grober Scan (< 200 dpi) viel sehr kleine Schrift (< 2 mm) enthält.

    Solche Schrift ist bei 150 dpi nur ~7 px hoch – mit 300 dpi gescannt liest die
    Texterkennung sie ein Vielfaches besser (gemessen: 13 → 45 von 55 Wörtern)."""
    if mm_per_px <= 0 or 25.4 / mm_per_px >= 200:
        return None
    n, _, st, _ = cv2.connectedComponentsWithStats((ink > 0).astype(np.uint8), connectivity=8)
    w, h, a = st[1:, 2], st[1:, 3], st[1:, 4]
    fill = a / np.maximum(1, w * h)
    hmm = h * mm_per_px
    chars = (hmm >= 0.8) & (hmm < 2.0) & (w * mm_per_px <= 2.0) & (h >= 4) \
        & (fill > 0.15) & (fill < 0.9)
    if int(chars.sum()) < min_count:
        return None
    return (f"viel sehr kleine Schrift bei {25.4 / mm_per_px:.0f} dpi – für die Texterkennung "
            "besser mit 300 dpi scannen")


def render_entities(ents, shape, width_px: int = 3, texts: bool = True,
                    mm_per_px: float = 0.0, fill_closed: bool = False) -> np.ndarray:
    """Zeichnet Vektoren als Maske (255 = Vektor).

    mm_per_px: damit gemessene Strichstärken (lineweight) in Pixel umgerechnet werden.
    fill_closed: geschlossene Konturen füllen (CNC-Umriss-Modus; Löcher per XOR).
    """
    m = np.zeros(shape[:2], np.uint8)
    P = lambda p: (int(round(p[0])), int(round(p[1])))  # noqa: E731
    if fill_closed:
        acc = np.zeros_like(m)
        for e in ents:
            tmp = None
            if isinstance(e, Polyline) and e.closed and len(e.points) > 2:
                tmp = np.zeros_like(m)
                cv2.fillPoly(tmp, [np.array([P(p) for p in e.points], np.int32)], 255)
            elif isinstance(e, Circle):
                tmp = np.zeros_like(m)
                cv2.circle(tmp, P(e.center), int(round(e.radius)), 255, -1)
            if tmp is not None:
                acc = cv2.bitwise_xor(acc, tmp)
        m |= acc
    for e in ents:
        w = width_px
        lw = getattr(e, "lineweight", 0.0) or 0.0
        if mm_per_px > 0 and lw > 0:
            w = max(width_px, int(round(lw / mm_per_px)))
        if isinstance(e, Line):
            cv2.line(m, P(e.p1), P(e.p2), 255, w)
        elif isinstance(e, Circle):
            cv2.circle(m, P(e.center), int(round(e.radius)), 255, w)
        elif isinstance(e, Arc):
            span = (e.end_angle - e.start_angle) % 360
            cv2.ellipse(m, P(e.center), (int(round(e.radius)),) * 2, 0, e.start_angle,
                        e.start_angle + span, 255, w)
        elif isinstance(e, Polyline) and len(e.points) > 1:
            pts = np.array([P(p) for p in e.points], np.int32).reshape(-1, 1, 2)
            if e.layer == "FLAECHEN" and e.closed:
                cv2.fillPoly(m, [pts], 255)
            else:
                cv2.polylines(m, [pts], e.closed, 255, w)
        elif isinstance(e, Text) and texts:
            h = e.height / 0.72
            L = max(1, len(e.text)) * h * 0.62
            a = math.radians(e.angle)
            x, y = e.position
            dx, dy = math.cos(a), -math.sin(a)          # Textrichtung (Bild, y nach unten)
            nx, ny = -math.sin(a), -math.cos(a)         # senkrecht dazu, „nach oben“
            corners = [(x, y), (x + dx * L, y + dy * L),
                       (x + dx * L + nx * h, y + dy * L + ny * h), (x + nx * h, y + ny * h)]
            cv2.fillPoly(m, [np.array([P(c) for c in corners], np.int32)], 255)
    return m


def _components(mask: np.ndarray, kind: str, min_area: int) -> List[Problem]:
    n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    out = []
    for i in range(1, n):
        x, y, w, h, a = stats[i]
        if a >= min_area:
            out.append(Problem(int(x), int(y), int(w), int(h), kind, int(a)))
    return out


DASH_MIN_ON_INK = 0.3   # Strichlinie liegt richtig, wenn so viel von ihr auf Tinte liegt


def _dashed(e) -> bool:
    return getattr(e, "linetype", "CONTINUOUS") not in ("CONTINUOUS", "", None)


def _dashed_off(ents, ink_near: np.ndarray) -> tuple:
    """(Pixel neben der Tinte, Pixel gesamt) der Strichlinien. Ihre Lücken liegen absichtlich
    auf weißem Papier – je Linie zählt nur, ob genug von ihr auf Tinte liegt (dann ganz
    richtig, sonst ganz überflüssig)."""
    off = total = 0
    H, W = ink_near.shape
    for e in ents:
        if not _dashed(e) or isinstance(e, Text):
            continue
        if isinstance(e, (Arc, Circle)):
            pts = [(e.center[0] - e.radius, e.center[1] - e.radius),
                   (e.center[0] + e.radius, e.center[1] + e.radius)]
        else:
            pts = [e.p1, e.p2] if isinstance(e, Line) else list(getattr(e, "points", []))
        if not pts:
            continue
        x0 = max(0, int(min(p[0] for p in pts)) - 2)
        y0 = max(0, int(min(p[1] for p in pts)) - 2)
        x1 = min(W, int(max(p[0] for p in pts)) + 3)
        y1 = min(H, int(max(p[1] for p in pts)) + 3)
        if x1 <= x0 or y1 <= y0:
            continue
        from .edit import translate
        m = render_entities([translate(e, -x0, -y0)], (y1 - y0, x1 - x0), width_px=1, texts=False)
        n = int((m > 0).sum())
        if not n:
            continue
        on = int(((m > 0) & (ink_near[y0:y1, x0:x1] > 0)).sum())
        total += n
        off += 0 if on >= DASH_MIN_ON_INK * n else n
    return off, total


def assess(ink: np.ndarray, ents: list, tolerance_px: int = 3, min_area: int = 25,
           max_problems: int = 60, extra_boxes=None, mm_per_px: float = 0.0,
           fill_closed: bool = False, dash_ink=None) -> QualityReport:
    """ink: Binärbild (255 = Tinte). extra_boxes: zusätzlich abgedeckte Rechtecke (z. B. OCR).
    dash_ink: Binärbild ohne Entflecken für die Strichlinien – feine Striche (< 0,8 mm) fehlen im
    entfleckten Bild, die Strichlinie darauf läge sonst scheinbar auf leerem Papier."""
    ink = (ink > 0).astype(np.uint8) * 255
    if not ink.any():
        return QualityReport(GREEN, 1.0, 1.0, [])
    vec = render_entities(ents, ink.shape, width_px=3, mm_per_px=mm_per_px,
                          fill_closed=fill_closed)
    for (x, y, w, h) in (extra_boxes or []):
        vec[max(0, y):y + h, max(0, x):x + w] = 255
    from .bands import fill_mask
    vec[fill_mask(ents, ink.shape)] = 255          # gefüllte Wandflächen decken ihr Band ab
    k = 2 * tolerance_px + 1
    ker = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    covered = cv2.dilate(vec, ker)
    missing = cv2.bitwise_and(ink, cv2.bitwise_not(covered))
    # Rauschen (Einzelpixel, Kanten) ignorieren
    missing = cv2.morphologyEx(missing, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    thin = render_entities([e for e in ents if not _dashed(e)], ink.shape, width_px=1, texts=False)
    ink_near = cv2.dilate(ink, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k + 4, k + 4)))
    if dash_ink is not None and dash_ink.shape == ink.shape:
        d_near = cv2.dilate(((dash_ink > 0) | (ink > 0)).astype(np.uint8) * 255,
                            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k + 4, k + 4)))
    else:
        d_near = ink_near
    d_off, d_total = _dashed_off(ents, d_near)
    extra = cv2.bitwise_and(thin, cv2.bitwise_not(ink_near))
    extra = cv2.dilate(extra, np.ones((3, 3), np.uint8))   # dünne Reste zu Flächen
    ink_px = int((ink > 0).sum())
    thin_px = max(1, int((thin > 0).sum()) + d_total)
    coverage = 1.0 - (missing > 0).sum() / ink_px
    off_px = int((cv2.bitwise_and(thin, cv2.bitwise_not(ink_near)) > 0).sum()) + d_off
    precision = 1.0 - min(1.0, off_px / thin_px)
    probs = _components(missing, "fehlt", min_area) + _components(extra, "ueberfluessig",
                                                                 max(min_area, 30))
    probs.sort(key=lambda p: -p.size)
    probs = probs[:max_problems]
    if coverage >= 0.97 and precision >= 0.97:
        rating = GREEN
    elif coverage >= 0.90 and precision >= 0.90:
        rating = YELLOW
    else:
        rating = RED
    hint = small_text_hint(ink, mm_per_px)
    return QualityReport(rating, float(coverage), float(precision), probs,
                         [hint] if hint else [])
