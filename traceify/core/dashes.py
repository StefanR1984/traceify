"""Feine Strichlinien aus kleinen Strichen (Befund Plan4/Plan5, 0.41.0).

Grau gedruckte Strichlinien (Möbel, Verdecktes) bestehen im Scan aus Strichen von ~0,4 × 0,15 mm
(bei 300 dpi 5 × 2 px). Entflecken (12 px²) und die Mindestlänge des Skeletts (6 px) werfen sie
weg, bevor `style.detect_dashed` sie sieht. Hier werden sie direkt im ungefilterten Binärbild
gesucht: kleine längliche Teile, die in einer Reihe liegen (Richtung jedes Strichs passt zur
Reihe, Mitten auf einer Geraden, regelmäßige Lücken) → eine Linie mit Linientyp DASHED.
"""
from __future__ import annotations

import math
from typing import List

import cv2
import numpy as np

from .model import LAYER_DASHED, Line, Polyline

MAX_DASH_MM = 0.8      # längere Striche erkennt schon die normale Vektorisierung
MIN_DASH_MM = 0.2      # kürzere Teile sind Punkte/Rauschen
MIN_ELONG = 2.0        # Länge/Breite eines Strichs
MIN_COUNT = 5          # so viele Striche mindestens in einer Reihe
ANGLE_TOL = 25.0       # Grad: Strichrichtung / Richtung zum Nachbarn gegen die Reihe
PERP_TOL = 1.5         # px: Mitten so weit neben der Ausgleichsgeraden
GAP_FACTOR = 2.5       # Nachbar höchstens so viele Strichlängen entfernt
JOIN_MM = 2.0          # Reihen derselben Geraden über Kreuzungen hinweg verbinden (Lücke bis hier)

# Punktlinien (0.45.0): Allplan-Linientyp PUNKT plottet bei 1:350 Punkte von 1–4 px (≤ 0,35 mm) im
# Abstand ~1,7 mm – Entflecken löscht sie, die Linie fehlte ganz (PLAN3_UG1 Treffer dort 37 %).
DOT_MAX_MM = 0.4       # Punkt höchstens so groß (Ausdehnung)
DOT_STEP_MM = (0.5, 3.5)   # Abstand benachbarter Punkte
MIN_DOTS = 6           # so viele Punkte mindestens in einer Reihe
DOT_STEP_TOL = 0.15    # Punkt höchstens so weit (Anteil des Abstands) neben der erwarteten Lage
DOT_GRID = 1.6         # Querabstand (× Punktabstand), bis zu dem Nachbarpunkte als Nachbarreihe zählen
DOT_TRY = 4            # Richtungen je Startpunkt: die nächsten Nachbarn (Tempo bei Tonerstaub)
DOT_CV = 0.1           # Streuung der Abstände (Variationskoeffizient): geplottete Punkte sind gleichmäßig, Staub nicht


def small_dashes(bw: np.ndarray, px_per_mm: float) -> List[Line]:
    """Kleine längliche Teile des Binärbilds (Zeichnung weiß, nicht entfleckt) als kurze Linien
    entlang ihrer Hauptachse."""
    max_px = max(10.0, MAX_DASH_MM * px_per_mm)
    min_px = MIN_DASH_MM * px_per_mm
    n, lab, st, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    ext = np.hypot(st[:, 2], st[:, 3])
    ok = (ext <= max_px) & (ext >= min_px) & (st[:, cv2.CC_STAT_AREA] >= 3)
    ok[0] = False
    if not ok.any():
        return []
    ys, xs = np.nonzero(ok[lab])
    L = lab[ys, xs]
    o = np.argsort(L, kind="stable")
    xs, ys, L = xs[o].astype(float), ys[o].astype(float), L[o]
    # Schwerpunkt und Hauptachse je Teil aus den Momenten (vektorisiert)
    a = np.maximum(np.bincount(L, minlength=n), 1).astype(float)
    mx, my = np.bincount(L, xs, n) / a, np.bincount(L, ys, n) / a
    sxx = np.bincount(L, xs * xs, n) / a - mx * mx + 1 / 12
    syy = np.bincount(L, ys * ys, n) / a - my * my + 1 / 12
    sxy = np.bincount(L, xs * ys, n) / a - mx * my
    tr, det = sxx + syy, sxx * syy - sxy * sxy
    d = np.sqrt(np.maximum(tr * tr / 4 - det, 0))
    l1, l2 = tr / 2 + d, np.maximum(tr / 2 - d, 1e-6)
    ang = 0.5 * np.arctan2(2 * sxy, sxx - syy)
    ux, uy = np.cos(ang), np.sin(ang)
    t = (xs - mx[L]) * ux[L] + (ys - my[L]) * uy[L]
    starts = np.flatnonzero(np.r_[True, L[1:] != L[:-1]])
    ids = L[starts]
    tmin, tmax = np.minimum.reduceat(t, starts), np.maximum.reduceat(t, starts)
    keep = np.sqrt(l1[ids] / l2[ids]) >= MIN_ELONG
    out = []
    for i, t0, t1 in zip(ids[keep], tmin[keep], tmax[keep]):
        out.append(Line((float(mx[i] + t0 * ux[i]), float(my[i] + t0 * uy[i])),
                        (float(mx[i] + t1 * ux[i]), float(my[i] + t1 * uy[i]))))
    return out


def small_dots(bw: np.ndarray, px_per_mm: float) -> np.ndarray:
    """Mitten kleiner, kompakter Teile des Binärbilds (nicht entfleckt) – Kandidaten für Punktlinien."""
    max_px = max(2.0, DOT_MAX_MM * px_per_mm)
    n, _, st, c = cv2.connectedComponentsWithStats(bw, connectivity=8)
    ok = np.maximum(st[:, 2], st[:, 3]) <= max_px
    ok[0] = False
    return c[ok].astype(float)


def chain_dots(C: np.ndarray, px_per_mm: float) -> List[Line]:
    """Punkte in gleichmäßigen Abständen auf einer Geraden → Linie mit Linientyp DOT (Layer
    STRICHLINIEN). Ein fehlender Punkt (Kreuzung) wird übersprungen. Punktraster (Rasterflächen)
    und Tonerstaub sind keine Linien: quer zur Reihe liegen dort mehrere Punkte; zwei parallele
    Punktlinien bleiben. Zufällig fluchtende Staubpunkte haben zudem ungleiche Abstände.
    Überlappende Reihen werden eine Linie."""
    if len(C) < MIN_DOTS:
        return []
    from scipy.spatial import cKDTree

    lo, hi = DOT_STEP_MM[0] * px_per_mm, DOT_STEP_MM[1] * px_per_mm
    tree = cKDTree(C)
    used = np.zeros(len(C), bool)
    rows = []

    def near(p, r):
        js = np.asarray(tree.query_ball_point(p, r), int)
        js = js[~used[js]]
        if not len(js):
            return None
        return int(js[np.argmin(np.hypot(*(C[js] - p).T))])

    for i in range(len(C)):
        if used[i]:
            continue
        nb = np.asarray(tree.query_ball_point(C[i], hi), int)
        dn = np.hypot(*(C[nb] - C[i]).T)
        ok = ~used[nb] & (dn >= lo)
        for j in nb[ok][np.argsort(dn[ok])][:DOT_TRY]:
            if used[j]:
                continue
            v0 = C[j] - C[i]
            r = max(1.5, DOT_STEP_TOL * float(np.hypot(*v0)))
            ch = [i, j]
            used[[i, j]] = True
            for sgn in (1, -1):
                cur, v = (j if sgn > 0 else i), sgn * v0
                while True:
                    k = near(C[cur] + v, r)
                    if k is not None:
                        v = C[k] - C[cur]
                    else:                               # ein Punkt fehlt (Kreuzung)
                        k = near(C[cur] + 2 * v, r)
                        if k is None:
                            break
                        v = (C[k] - C[cur]) / 2
                    used[k] = True
                    ch.append(k)
                    cur = k
            if len(ch) < MIN_DOTS:
                used[ch] = False
                continue
            P = C[ch]
            c0 = P.mean(0)
            u = np.linalg.svd(P - c0)[2][0]
            step = float(np.hypot(*v0))
            t = (P - c0) @ u
            gaps = np.diff(np.sort(t))
            gaps = np.where(gaps > 1.5 * np.median(gaps), gaps / 2, gaps)     # übersprungener Punkt
            if (np.abs((P - c0) @ (-u[1], u[0])).max() > PERP_TOL
                    or gaps.std() > DOT_CV * gaps.mean()):
                used[ch] = False
                continue
            rows.append((c0, u, float(t.min()), float(t.max()), ch, step))
            break
    # Quer zur Reihe (bis 2 × DOT_GRID Punktabstände, je Punkt ±½ Abstand längs) darf höchstens ein
    # Nachbarpunkt liegen – der einer zweiten, parallelen Punktlinie. Punktraster haben dort zwei
    # oder mehr (Reihen beidseitig oder zwei auf einer Seite), Tonerstaub viele.
    keep = []
    for c0, u, a, b, ch, st in rows:
        nrm = np.array((-u[1], u[0]))
        cnt = []
        for p, nb in zip(C[ch], tree.query_ball_point(C[ch], 2 * DOT_GRID * st)):
            D = C[nb] - p
            cnt.append(int(((np.abs(D @ u) <= 0.5 * st) & (np.abs(D @ nrm) > PERP_TOL)).sum()))
        if float(np.median(cnt)) < 2:
            keep.append((c0, u, a, b))
    return _merge_rows(keep)


def _merge_rows(rows) -> List[Line]:
    """Überlappende Reihen derselben Geraden (Richtung ±2°, Enden ≤ PERP_TOL neben der anderen)
    zu einer Linie."""
    segs = sorted(((c0 + a * u, c0 + b * u) for c0, u, a, b in rows), key=lambda s: -float(np.hypot(*(s[1] - s[0]))))
    cos_t = math.cos(math.radians(2.0))
    for _ in range(2):                  # zweiter Durchgang: über ein Zwischenstück verbundene Reihen
        out = []
        for q0, q1 in segs:
            v = (q1 - q0) / max(float(np.hypot(*(q1 - q0))), 1e-9)
            for k, (p0, p1) in enumerate(out):
                L = float(np.hypot(*(p1 - p0)))
                u = (p1 - p0) / max(L, 1e-9)
                nrm = np.array((-u[1], u[0]))
                if abs(u @ v) < cos_t or max(abs((q0 - p0) @ nrm), abs((q1 - p0) @ nrm)) > PERP_TOL:
                    continue
                t = sorted((float((q0 - p0) @ u), float((q1 - p0) @ u)))
                if t[0] <= L and t[1] >= 0:
                    out[k] = (p0 + min(0.0, t[0]) * u, p0 + max(L, t[1]) * u)
                    break
            else:
                out.append((q0, q1))
        segs = out
    return [Line(tuple(map(float, p0)), tuple(map(float, p1)), LAYER_DASHED, None, "DOT") for p0, p1 in segs]


def chain_dashes(dashes: List[Line]) -> List[Line]:
    """Striche zu Reihen verfolgen; jede Reihe mit ≥ MIN_COUNT Strichen wird eine DASHED-Linie."""
    if len(dashes) < MIN_COUNT:
        return []
    from scipy.spatial import cKDTree

    C = np.array([((e.p1[0] + e.p2[0]) / 2, (e.p1[1] + e.p2[1]) / 2) for e in dashes])
    U = np.array([(e.p2[0] - e.p1[0], e.p2[1] - e.p1[1]) for e in dashes], float)
    Ln = np.hypot(U[:, 0], U[:, 1])
    U /= np.maximum(Ln, 1e-9)[:, None]
    tree = cKDTree(C)
    used = np.zeros(len(dashes), bool)
    cos_t = math.cos(math.radians(ANGLE_TOL))
    out = []
    for i in np.argsort(-Ln):
        if used[i]:
            continue
        ch = [i]
        u, c0 = U[i].copy(), C[i].copy()
        for sgn in (1, -1):
            cur = i
            while True:
                best, bd = None, 1e9
                for j in tree.query_ball_point(C[cur], GAP_FACTOR * max(Ln[cur], 3.0) + Ln[cur]):
                    if used[j] or j in ch:
                        continue
                    v = C[j] - C[cur]
                    d = math.hypot(v[0], v[1])
                    if d < 0.6 * Ln[cur] or sgn * (v @ u) <= 0:
                        continue
                    if abs(v @ u) / d < cos_t or abs(U[j] @ u) < cos_t:
                        continue
                    if len(ch) >= 3 and abs((C[j] - c0) @ (-u[1], u[0])) > PERP_TOL:
                        continue
                    if d < bd:
                        best, bd = j, d
                if best is None:
                    break
                ch.append(best)
                cur = best
                if len(ch) >= 3:          # Richtung aus den Mitten statt aus einem Strich
                    c0 = C[ch].mean(0)
                    nu = np.linalg.svd(C[ch] - c0)[2][0]
                    u = nu if nu @ u > 0 else -nu
        if len(ch) < MIN_COUNT:
            continue
        P = C[ch]
        c0 = P.mean(0)
        u = np.linalg.svd(P - c0)[2][0]
        if np.abs((P - c0) @ (-u[1], u[0])).max() > PERP_TOL:
            continue
        t = (P - c0) @ u
        o = np.argsort(t)
        ts, half = t[o], Ln[np.array(ch)[o]] / 2
        gaps = np.diff(ts) - half[:-1] - half[1:]
        med = float(np.median(gaps))
        if med <= 0.3:                    # Teile berühren sich: kein Strichmuster
            continue
        # an zu großen Lücken (Kreuzung, fehlende Striche) teilen; jedes Stück muss reichen
        cut = np.flatnonzero(gaps > 3.5 * max(1.0, med)) + 1
        for part in np.split(np.arange(len(ts)), cut):
            if len(part) < MIN_COUNT:
                continue
            used[np.array(ch)[o[part]]] = True
            a, b = ts[part[0]] - half[part[0]], ts[part[-1]] + half[part[-1]]
            out.append(Line((float(c0[0] + a * u[0]), float(c0[1] + a * u[1])),
                            (float(c0[0] + b * u[0]), float(c0[1] + b * u[1])),
                            LAYER_DASHED, None, "DASHED"))
    return out


def join_chains(lines: List[Line], max_gap: float, angle_tol: float = 3.0) -> List[Line]:
    """An Kreuzungen unterbrochene Reihen derselben Strichlinie zusammenfügen (gleiche Gerade,
    Lücke ≤ max_gap)."""
    lines = list(lines)
    merged = True
    while merged:
        merged = False
        for i in range(len(lines)):
            a = lines[i]
            ua = np.subtract(a.p2, a.p1)
            la = float(np.hypot(*ua))
            ua = ua / la
            for j in range(i + 1, len(lines)):
                b = lines[j]
                ub = np.subtract(b.p2, b.p1)
                ub = ub / float(np.hypot(*ub))
                if abs(ua @ ub) < math.cos(math.radians(angle_tol)):
                    continue
                nrm = (-ua[1], ua[0])
                if max(abs(np.subtract(p, a.p1) @ nrm) for p in (b.p1, b.p2)) > PERP_TOL:
                    continue
                tb = sorted(float(np.subtract(p, a.p1) @ ua) for p in (b.p1, b.p2))
                gap = max(tb[0] - la, -tb[1])
                if gap > max_gap:
                    continue
                ts = [0.0, la] + tb
                p0 = np.asarray(a.p1, float)
                lines[i] = Line(tuple(map(float, p0 + min(ts) * ua)), tuple(map(float, p0 + max(ts) * ua)),
                                LAYER_DASHED, None, "DASHED")
                del lines[j]
                merged = True
                break
            if merged:
                break
    return lines


def drop_covered(ents: list, lines: List[Line], tol: float) -> list:
    """Linien/Polylinien weglassen, die ganz auf einer der neuen Strichlinien liegen (dort
    vektorisierte Strichreste)."""
    if not lines:
        return ents
    segs = [(np.array(l.p1), np.array(l.p2)) for l in lines]
    boxes = [(min(a[0], b[0]) - tol, min(a[1], b[1]) - tol, max(a[0], b[0]) + tol,
              max(a[1], b[1]) + tol) for a, b in segs]

    def on_line(pts):
        P = np.asarray(pts, float)
        lo, hi = P.min(0), P.max(0)
        for (a, b), bx in zip(segs, boxes):
            if lo[0] < bx[0] or lo[1] < bx[1] or hi[0] > bx[2] or hi[1] > bx[3]:
                continue
            d = b - a
            n2 = float(d @ d) or 1.0
            t = np.clip(((P - a) @ d) / n2, 0, 1)
            if (np.hypot(*(P - a - t[:, None] * d).T) <= tol).all():
                return True
        return False

    out = []
    for e in ents:
        if isinstance(e, Line) and e.layer != LAYER_DASHED:
            pts = [e.p1, e.p2]
        elif isinstance(e, Polyline) and not e.closed:
            pts = e.points
        else:
            out.append(e)
            continue
        if not on_line(pts):
            out.append(e)
    return out
