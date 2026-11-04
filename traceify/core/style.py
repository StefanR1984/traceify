"""Linienstil-Erkennung: gestrichelte Linien und Strichstärken.

* detect_dashed    – kollineare, kurze Liniensegmente mit regelmäßigen Lücken werden zu EINER
                     Linie mit Linientyp DASHED (bzw. CENTER bei lang-kurz-Wechsel) zusammengefasst.
* measure_widths   – misst die Strichstärke jedes Objekts im Binärbild (Distanztransformation)
                     und setzt `lineweight` (mm auf dem Papier).
* classify_thick   – deutlich dickere Linien kommen auf den Layer DICKE_LINIEN (z. B. Wände).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

import cv2
import numpy as np

from .model import Arc, Circle, LAYER_DASHED, LAYER_THICK, Line, Polyline, Text

ISO_PENS = [0.13, 0.18, 0.25, 0.35, 0.5, 0.7, 1.0, 1.4, 2.0]


@dataclass
class StyleSettings:
    detect_dashed: bool = True
    dash_max_len: float = 60.0      # px – längere Stücke sind keine Striche
    dash_max_gap: float = 40.0      # px – größte Lücke zwischen zwei Strichen (absolut)
    dash_min_count: int = 3         # so viele Striche mindestens
    measure_widths: bool = True
    thick_layer: bool = True        # dicke Linien auf eigenen Layer
    thick_ratio: float = 1.7        # ab x-facher Normalstärke „dick“
    color_layers: bool = False      # Farben auf Layer trennen
    color_count: int = 0            # 0 = automatisch, sonst feste Anzahl Farben


# ------------------------------------------------------------------ Strichlinien
def _dir(l: Line):
    dx, dy = l.p2[0] - l.p1[0], l.p2[1] - l.p1[1]
    n = math.hypot(dx, dy) or 1.0
    ux, uy = dx / n, dy / n
    if ux < -1e-9 or (abs(ux) < 1e-9 and uy < 0):   # eindeutige Richtung
        ux, uy = -ux, -uy
    return ux, uy


def detect_dashed(ents: list, s: StyleSettings, angle_tol: float = 4.0,
                  offset_tol: float = 2.5) -> list:
    """Fasst Strich-Segmente zu Linien mit Linientyp zusammen. Gibt die neue Liste zurück."""
    cand = [e for e in ents if isinstance(e, Line) and
            1.0 < math.dist(e.p1, e.p2) <= s.dash_max_len]
    if len(cand) < s.dash_min_count:
        return ents
    info = []
    for l in cand:
        ux, uy = _dir(l)
        ang = math.degrees(math.atan2(uy, ux)) % 180
        # Abstand der Trägergeraden vom Ursprung (Normale)
        rho = -uy * l.p1[0] + ux * l.p1[1]
        info.append((l, ang, rho, ux, uy))
    used = set()
    replaced = {}
    new_lines = []
    info.sort(key=lambda t: (round(t[1] / angle_tol), round(t[2] / offset_tol)))
    for i, (l, ang, rho, ux, uy) in enumerate(info):
        if id(l) in used:
            continue
        group = [t for t in info if id(t[0]) not in used and
                 min(abs(t[1] - ang), 180 - abs(t[1] - ang)) <= angle_tol and
                 abs(t[2] - rho) <= offset_tol]
        if len(group) < s.dash_min_count:
            continue
        # entlang der Richtung sortieren
        def span(t):
            a = t[0].p1[0] * ux + t[0].p1[1] * uy
            b = t[0].p2[0] * ux + t[0].p2[1] * uy
            return (min(a, b), max(a, b), t[0])
        spans = sorted(span(t) for t in group)
        med_len = float(np.median([b - a for a, b, _ in spans]))
        max_gap = min(s.dash_max_gap, max(8.0, 1.6 * med_len))
        chain = [spans[0]]
        chains = []
        for sp in spans[1:]:
            gap = sp[0] - chain[-1][1]
            if 0.5 < gap <= max_gap:
                chain.append(sp)
            elif gap <= 0.5:          # überlappend/berührend: kein Strichmuster
                chains.append(chain)
                chain = [sp]
            else:
                chains.append(chain)
                chain = [sp]
        chains.append(chain)
        for ch in chains:
            if len(ch) < s.dash_min_count:
                continue
            gaps = [b[0] - a[1] for a, b in zip(ch, ch[1:])]
            # regelmäßige Lücken (Streuung begrenzt)
            if max(gaps) > 3.5 * max(1.0, float(np.median(gaps))):
                continue
            lens = [c[1] - c[0] for c in ch]
            ltype = "DASHED"
            if len(lens) >= 4:
                longs, shorts = lens[0::2], lens[1::2]
                if (min(longs) > 2.2 * max(shorts)) or (min(shorts) > 2.2 * max(longs)):
                    ltype = "CENTER"
                elif max(gaps) > 2.2 * min(gaps) and len(gaps) >= 3 and \
                        (min(gaps[0::2]) > 2.0 * max(gaps[1::2]) or min(gaps[1::2]) > 2.0 * max(gaps[0::2])):
                    ltype = "CENTER"   # Punkte zu klein -> erkennbar am Wechsel der Lücken
            first, last = ch[0][2], ch[-1][2]
            t0, t1 = ch[0][0], ch[-1][1]
            # Endpunkte auf der Trägergeraden des ersten Strichs
            base = first.p1
            b0 = base[0] * ux + base[1] * uy
            p_start = (base[0] + (t0 - b0) * ux, base[1] + (t0 - b0) * uy)
            p_end = (base[0] + (t1 - b0) * ux, base[1] + (t1 - b0) * uy)
            widths = [c[2].lineweight for c in ch if c[2].lineweight]
            nl = Line(p_start, p_end, LAYER_DASHED, first.color, ltype,
                      float(np.median(widths)) if widths else 0.0)
            for c in ch:
                used.add(id(c[2]))
                replaced[id(c[2])] = True
            new_lines.append(nl)
            _ = last
    if not new_lines:
        return ents
    return [e for e in ents if id(e) not in replaced] + new_lines


# ------------------------------------------------------------------ Strichstärke
def _samples(e, n: int = 9):
    if isinstance(e, Line):
        t = np.linspace(0.1, 0.9, n)
        return [(e.p1[0] + (e.p2[0] - e.p1[0]) * k, e.p1[1] + (e.p2[1] - e.p1[1]) * k) for k in t]
    if isinstance(e, Circle):
        a = np.linspace(0, 2 * math.pi, n, endpoint=False)
        return [(e.center[0] + e.radius * math.cos(x), e.center[1] + e.radius * math.sin(x))
                for x in a]
    if isinstance(e, Arc):
        span = (e.end_angle - e.start_angle) % 360
        a = np.radians(e.start_angle + np.linspace(span * 0.1, span * 0.9, n))
        return [(e.center[0] + e.radius * math.cos(x), e.center[1] + e.radius * math.sin(x))
                for x in a]
    if isinstance(e, Polyline) and len(e.points) > 1:
        pts = e.points
        idx = np.linspace(0, len(pts) - 1, min(n, len(pts))).astype(int)
        return [pts[i] for i in idx]
    return []


def measure_widths(ents: list, bw: np.ndarray, mm_per_px: float) -> np.ndarray:
    """Setzt e.lineweight (mm) für alle Linienobjekte. Gibt die Stärken in px zurück."""
    if bw is None or not bw.any():
        return np.array([])
    dist = cv2.distanceTransform((bw > 0).astype(np.uint8), cv2.DIST_L2, 5)
    # Maximum in 5x5-Umgebung: die Vektorgeometrie liegt nicht exakt auf dem Skelett
    dmax = cv2.dilate(dist, np.ones((5, 5), np.uint8))
    H, W = bw.shape
    out = []
    for e in ents:
        if isinstance(e, Text):
            continue
        vals = []
        for x, y in _samples(e):
            xi, yi = int(round(x)), int(round(y))
            if 0 <= xi < W and 0 <= yi < H and dmax[yi, xi] > 0:
                vals.append(float(dmax[yi, xi]))
        if not vals:
            continue
        w_px = max(1.0, 2.0 * float(np.median(vals)) - 1.0)
        e.lineweight = round(w_px * mm_per_px, 3)
        e._width_px = w_px
        out.append(w_px)
    return np.array(out)


def snap_iso(mm: float) -> float:
    return min(ISO_PENS, key=lambda p: abs(p - mm)) if mm > 0 else 0.0


def classify_thick(ents: list, s: StyleSettings) -> int:
    """Linien, die deutlich dicker als die übliche Strichstärke sind, auf Layer DICKE_LINIEN."""
    widths = [(e, getattr(e, "_width_px", None) or 0) for e in ents
              if isinstance(e, (Line, Polyline)) and e.layer != LAYER_DASHED]
    vals = [w for _, w in widths if w > 0]
    if len(vals) < 4:
        return 0
    normal = float(np.percentile(vals, 40))
    n = 0
    for e, w in widths:
        if w >= max(3.0, normal * s.thick_ratio):
            e.layer = LAYER_THICK
            n += 1
    return n


def classify_thick_mm(ents: list, s: StyleSettings) -> int:
    """Wie classify_thick, aber nach vorhandener Strichstärke in mm (für Vektor-PDFs)."""
    vals = [e.lineweight for e in ents if isinstance(e, (Line, Polyline)) and e.lineweight > 0]
    if len(vals) < 4:
        return 0
    normal = float(np.percentile(vals, 40))
    n = 0
    for e in ents:
        if isinstance(e, (Line, Polyline)) and e.lineweight >= normal * s.thick_ratio \
                and e.lineweight > 0:
            e.layer = LAYER_THICK
            n += 1
    return n


def cleanup(ents: List) -> None:
    for e in ents:
        if hasattr(e, "_width_px"):
            try:
                del e._width_px
            except AttributeError:
                pass
