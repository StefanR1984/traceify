"""Wahrheits-Prüfstand: Original-CAD-Pläne als Scan simulieren und das Ergebnis messen.

Aus einer Original-DXF (z. B. Allplan-Export) wird ein Rasterbild erzeugt, wie es ein
gedruckter und gescannter Plan liefern würde (Maßstab 1:N, dpi, Strichbreite, leichte
Unschärfe und Rauschen). Weil die Abbildung CAD → Bild exakt bekannt ist, lässt sich das
Traceify-Ergebnis direkt gegen die Originalgeometrie messen – ohne Lage-Schätzung und ohne
den Umweg über ein anderes Programm:

* Trefferquote – Anteil der Originalgeometrie, den Traceify wiedergibt
* Genauigkeit – Anteil der Traceify-Geometrie, der auf Originalgeometrie liegt
* Lagefehler – Abstand der Traceify-Linien zur nächsten Originallinie (Median, 95 %)
* Objekte, Ortho-Anteil und Wörter im Vergleich zum Original
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np

from .benchmark import ortho_share, words
from .dxf_import import _convert, transform
from .model import Arc, Circle, Insert, Line, Polyline, Text
from .quality import render_entities


def load_cad(path: str) -> Tuple[List[object], float]:
    """Objekte des Modellbereichs (Einheit der Datei, y nach oben) und mm je Einheit ($INSUNITS)."""
    import ezdxf
    from ezdxf import units
    doc = ezdxf.readfile(path)
    ents: list = []
    for e in doc.modelspace():
        _convert(e, ents)
    return ents, units.conversion_factor(doc.units or units.MM, units.MM)


@dataclass
class Scan:
    gray: np.ndarray          # simuliertes Scanbild (0 = schwarz)
    truth: list               # Originalobjekte in Bildpixeln (y nach unten)
    mm_per_px: float          # Papier-mm pro Pixel


def _bbox(ents) -> Tuple[float, float, float, float]:
    pts = []
    for e in ents:
        if isinstance(e, Line):
            pts += [e.p1, e.p2]
        elif isinstance(e, Polyline):
            pts += list(e.points)
        elif isinstance(e, (Arc, Circle)):
            pts += [(e.center[0] - e.radius, e.center[1] - e.radius),
                    (e.center[0] + e.radius, e.center[1] + e.radius)]
    P = np.array(pts, float)
    # vereinzelte, weit entfernte Objekte sollen das Blatt nicht aufblähen
    (x0, y0), (x1, y1) = np.percentile(P, 0.2, axis=0), np.percentile(P, 99.8, axis=0)
    return float(x0), float(y0), float(x1), float(y1)


def _font(px: int):
    from PIL import ImageFont
    for name in ("arial.ttf", "Arial.ttf", "DejaVuSans.ttf", "LiberationSans-Regular.ttf"):
        try:
            # einfaches Layout: kein libraqm – fremde DLLs im PATH (z. B. von Tesseract) bringen
            # sonst eine unpassende Version mit und PIL bricht ab
            return ImageFont.truetype(name, px, layout_engine=ImageFont.Layout.BASIC)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_text(img: np.ndarray, t: Text) -> None:
    """Text als Schrift ins Bild (255 = Tinte); Lage: Grundlinie links, Drehung gegen Uhrzeigersinn."""
    from PIL import Image, ImageDraw
    size = max(6, int(round(t.height / 0.72)))
    if size > 400:
        return
    font = _font(size)
    L = int(font.getlength(t.text)) + size
    R = L + size
    tile = Image.new("L", (2 * R, 2 * R), 0)
    ImageDraw.Draw(tile).text((R, R), t.text, fill=255, font=font, anchor="ls")
    tile = np.asarray(tile.rotate(t.angle, center=(R, R)))
    x0, y0 = int(round(t.position[0])) - R, int(round(t.position[1])) - R
    H, W = img.shape
    ax0, ay0, ax1, ay1 = max(0, x0), max(0, y0), min(W, x0 + 2 * R), min(H, y0 + 2 * R)
    if ax0 >= ax1 or ay0 >= ay1:
        return
    sub = tile[ay0 - y0:ay1 - y0, ax0 - x0:ax1 - x0]
    np.maximum(img[ay0:ay1, ax0:ax1], sub, out=img[ay0:ay1, ax0:ax1])


def render_scan(cad: list, scale_n: float = 100.0, dpi: float = 150.0, pen_mm: float = 0.25,
                margin_mm: float = 10.0, noise: float = 8.0, blur: float = 0.6,
                seed: int = 0, unit_mm: float = 1.0) -> Scan:
    """Simuliert einen Scan des Plans im Maßstab 1:scale_n mit dpi (unit_mm: mm je CAD-Einheit).

    shortcut: einheitliche Strichbreite pen_mm, keine Füllflächen (SOLID-HATCH), keine
    Schräglage/Verzerrung – erweitern, wenn diese Fälle gemessen werden sollen."""
    s = dpi / 25.4 / scale_n * unit_mm           # Pixel pro CAD-Einheit
    geo = [e for e in cad if not isinstance(e, Text)]
    x0, y0, x1, y1 = _bbox(geo)
    m = margin_mm * dpi / 25.4
    W, H = int((x1 - x0) * s + 2 * m), int((y1 - y0) * s + 2 * m)
    truth = [transform(e, s, m - s * x0, m + s * y1) for e in cad]
    width = max(1, int(round(pen_mm * dpi / 25.4)))
    ink = render_entities([e for e in truth if not isinstance(e, Text)], (H, W),
                          width_px=width, texts=False)
    for t in truth:
        if isinstance(t, Text):
            _draw_text(ink, t)
    gray = 255.0 - ink.astype(np.float32) * (225.0 / 255.0)
    if blur > 0:
        gray = cv2.GaussianBlur(gray, (0, 0), blur)
    if noise > 0:
        gray += np.random.default_rng(seed).normal(0.0, noise, gray.shape).astype(np.float32)
    return Scan(np.clip(gray, 0, 255).astype(np.uint8), truth, 25.4 / dpi)


KIES_MM = 0.5          # Originalkreise bis zu diesem Radius (Papier) gelten als Kies-/Punktmuster


def _area_mask(areas, shape) -> np.ndarray:
    A = np.zeros(shape[:2], np.uint8)
    for a in areas:
        cv2.fillPoly(A, [np.round(np.array(a.outline)).astype(np.int32)], 1)
        for h in a.holes:
            cv2.fillPoly(A, [np.round(np.array(h)).astype(np.int32)], 0)
    return A > 0


MIN_TEXT_MM = 0.6      # kleinere Originalschrift (Papier) zählt nicht bei den Wörtern: < 7 px bei 300 dpi
_SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def merge_superscripts(texts: list) -> list:
    """Allplan zerlegt Maße beim Auflösen in Hauptzahl und kleine Hochziffer („2“ + „5“ = 2⁵),
    zweistellige Hochziffern sogar Ziffer für Ziffer („14“ + „7“ + „5“ = 14⁷⁵).

    Kleine Ziffern (0,4–0,8 der Höhe, gleiche Richtung) rechts oben hinter einer Zahl werden in
    Leserichtung deren Hochziffern – so wie Traceify sie liest. Bildpixel, y nach unten."""
    num = [t for t in texts if re.fullmatch(r"[\d.,]+", t.text.strip())]
    groups: dict = {}                           # id(Zahl) → [(x entlang der Schrift, Hochziffer)]
    for s in texts:
        if not re.fullmatch(r"\d{1,2}", s.text.strip()):
            continue
        best = None
        for m in num:
            if m is s or not 0.4 <= s.height / m.height <= 0.8 or abs((s.angle - m.angle + 180) % 360 - 180) > 2:
                continue
            a = math.radians(m.angle)
            dx, dy = s.position[0] - m.position[0], s.position[1] - m.position[1]
            x = (dx * math.cos(a) - dy * math.sin(a)) / m.height       # entlang der Schrift
            y = (-dx * math.sin(a) - dy * math.cos(a)) / m.height      # nach oben
            n = len(m.text.strip())
            if 0.2 <= x <= 0.75 * n + 1.0 and 0.2 <= y <= 1.2:
                d = abs(x - 0.7 * n) + abs(y - 0.6)
                if best is None or d < best[0]:
                    best = (d, m, x)
        if best is not None:
            groups.setdefault(id(best[1]), (best[1], []))[1].append((best[2], s))
    used, out = set(), []
    for m, sups in groups.values():
        sups.sort(key=lambda q: q[0])
        used |= {id(m)} | {id(s) for _, s in sups}
        high = "".join(s.text.strip() for _, s in sups).translate(_SUP)
        out.append(Text(m.text.strip() + high, m.position, m.height, m.angle, m.layer))
    return out + [t for t in texts if id(t) not in used]


def _texts_right(truth_texts: list, mine: list) -> int:
    """Je gedrucktem Originaltext: alle seine Wörter stehen in Traceify-Texten in der Nähe (Abstand der
    Einfügepunkte ≤ Texthöhe × (Zeichen + 3)). Zählt wiederholte Maße einzeln – anders als `woerter`."""
    from scipy.spatial import cKDTree
    if not mine:
        return 0
    tree = cKDTree(np.array([m.position for m in mine], float))
    n = 0
    for t in truth_texts:
        w = words([t])
        if w and w <= words(mine[i] for i in tree.query_ball_point(t.position, t.height * (len(t.text) + 3))):
            n += 1
    return n


def compare(truth: list, ents: list, shape, mm_per_px: float, tol_mm: float = 0.3,
            areas: list = ()) -> dict:
    """Misst Traceify-Objekte (Bildpixel) gegen die Originalgeometrie (Bildpixel).

    areas: Kies-Flächen (`dots.GravelRegion`, ihre Kreise schon aus ents entfernt). Die Punkte im
    Muster liegen nicht da, wo die Originalpunkte lagen – deshalb gilt Original-Kies (kleine
    Kreise) in einer Fläche als getroffen, und die Fläche wird eigens gewertet: Anteil ihrer
    Fläche höchstens 1 mm neben Original-Kies (`kies_genau`)."""
    tg = [e for e in truth if not isinstance(e, (Text, Insert))]
    mg = [e for e in ents if not isinstance(e, (Text, Insert))]
    T = render_entities(tg, shape, width_px=1, texts=False)
    M = render_entities(mg, shape, width_px=1, texts=False)
    tol = max(1.0, tol_mm / mm_per_px)
    dT = cv2.distanceTransform((T == 0).astype(np.uint8), cv2.DIST_L2, 3)
    dM = cv2.distanceTransform((M == 0).astype(np.uint8), cv2.DIST_L2, 3)
    kies_genau = None
    if areas:
        A = _area_mask(areas, shape)
        K = render_entities([e for e in tg if isinstance(e, Circle)
                             and e.radius * mm_per_px <= KIES_MM], shape, width_px=1, texts=False)
        dM[A & (K > 0)] = 0.0
        dK = cv2.distanceTransform((K == 0).astype(np.uint8), cv2.DIST_L2, 3)
        kies_genau = round(float((dK[A] * mm_per_px <= 1.0).mean()), 4) if A.any() else 0.0
    # Schrift wird über die Wörter gemessen: Geometrie in Textbereichen des Originals zählt
    # nicht (sonst verfälschen ungelesene, als Linien vektorisierte Buchstaben die Werte)
    tx = np.zeros(shape[:2], np.uint8)
    for t in truth:
        if isinstance(t, Text):
            _draw_text(tx, t)
    tx = cv2.dilate(tx, np.ones((7, 7), np.uint8)) > 0
    t_px, m_px = (T > 0) & ~tx, (M > 0) & ~tx
    H, W = tx.shape

    def in_text(e) -> bool:
        if isinstance(e, Line):
            p = ((e.p1[0] + e.p2[0]) / 2, (e.p1[1] + e.p2[1]) / 2)
        elif isinstance(e, Arc):
            a = math.radians((e.start_angle + ((e.end_angle - e.start_angle) % 360) / 2))
            p = (e.center[0] + e.radius * math.cos(a), e.center[1] + e.radius * math.sin(a))
        elif isinstance(e, Circle):
            p = e.center
        else:
            p = e.points[0]
        x, y = int(p[0]), int(p[1])
        return 0 <= x < W and 0 <= y < H and bool(tx[y, x])

    mg = [e for e in mg if not in_text(e)]
    off = dT[m_px] * mm_per_px                  # Abstand Traceify -> Original, Papier-mm
    tt = [t for t in merge_superscripts([e for e in truth if isinstance(e, Text)])
          if t.height * mm_per_px >= MIN_TEXT_MM]
    mt = [e for e in ents if isinstance(e, Text)]
    wt, wm = words(tt), words(mt)
    return {
        "trefferquote": round(float((dM[t_px] <= tol).mean()) if t_px.any() else 0.0, 4),
        "genauigkeit": round(float((dT[m_px] <= tol).mean()) if m_px.any() else 0.0, 4),
        "lage_median_mm": round(float(np.median(off)), 3) if off.size else None,
        "lage_p95_mm": round(float(np.percentile(off, 95)), 3) if off.size else None,
        "objekte": len(mg) + len(areas), "objekte_original": len(tg),
        "kies_flaechen": len(areas), "kies_genau": kies_genau,
        "boegen": sum(isinstance(e, Arc) for e in mg),
        "boegen_original": sum(isinstance(e, (Arc, Circle)) for e in tg),
        "ortho": round(ortho_share(mg), 4), "ortho_original": round(ortho_share(tg), 4),
        "woerter": len(wt & wm), "woerter_original": len(wt),
        "woerter_falsch": len(wm - wt),
        "texte_richtig": _texts_right(tt, mt), "texte_original": sum(1 for t in tt if words([t])),
    }


def _with_areas(d) -> Tuple[list, list]:
    """Objekte wie im DXF-Export: Kies als Fläche (Schalter „als Fläche“), deren Kreise entfallen."""
    from .dots import find_areas
    from .hatch import wants_areas
    ents = d.expanded()
    areas = find_areas(ents) if wants_areas(d) else []
    skip = {id(m) for a in areas for m in a.members}
    return [e for e in ents if id(e) not in skip], areas


def run(path: str, out_png: str, settings=None, scale_n: float = 100.0, dpi: float = 150.0,
        pen_mm: float = 0.25, progress=None) -> dict:
    """DXF → simulierter Scan (PNG mit dpi) → Traceify → Messung gegen das Original."""
    import time

    from PIL import Image

    from ..api import open_file
    cad, unit = load_cad(path)
    sc = render_scan(cad, scale_n, dpi, pen_mm, unit_mm=unit)
    Image.fromarray(sc.gray).save(out_png, dpi=(dpi, dpi))
    t0 = time.time()
    res = open_file(out_png, 0, settings, progress=progress)
    ents, areas = _with_areas(res.drawing)
    r = compare(sc.truth, ents, sc.gray.shape, sc.mm_per_px, areas=areas)
    r.update({"datei": path, "bild": [int(sc.gray.shape[1]), int(sc.gray.shape[0])],
              "sekunden": round(time.time() - t0, 1)})
    return r


def align_scan(cad: list, ink: np.ndarray, px_per_unit: float) -> list:
    """Legt die Original-CAD-Objekte auf einen echten Scan mit bekanntem Maßstab.

    Versatz grob über die Ausdehnung, dann per Kreuzkorrelation (Viertelauflösung), zuletzt
    pixelgenau. Das Original enthält oft mehr als gedruckt (ausgeblendete Layer), die
    Ausdehnung allein trifft dann nicht."""
    s, dx, dy = _align([e for e in cad if not isinstance(e, Text)], ink, px_per_unit)
    return [transform(e, s, dx, dy) for e in cad]


def _align(geo: list, ink: np.ndarray, px_per_unit: float) -> Tuple[float, float, float]:
    """Abbildung (s, dx, dy) für `align_scan`: x' = s·x + dx, y' = dy − s·y."""
    from .dxf_import import fit_to_image
    _, (s, dx, dy) = fit_to_image(geo, ink, px_per_unit)
    H, W = ink.shape
    P, Q = W // 2, H // 2
    T = render_entities([transform(e, s, dx + P, dy + Q) for e in geo], (H + 2 * Q, W + 2 * P),
                        width_px=3, texts=False).astype(np.float32)
    f = 0.25
    I = cv2.dilate(ink, np.ones((3, 3), np.uint8)).astype(np.float32)
    r = cv2.matchTemplate(cv2.resize(T, None, fx=f, fy=f, interpolation=cv2.INTER_AREA),
                          cv2.resize(I, None, fx=f, fy=f, interpolation=cv2.INTER_AREA),
                          cv2.TM_CCORR_NORMED)
    lx, ly = cv2.minMaxLoc(r)[3]
    dx, dy = dx - (lx / f - P), dy - (ly / f - Q)
    dist = cv2.distanceTransform((ink == 0).astype(np.uint8), cv2.DIST_L2, 3)
    pts = [_points(transform(e, s, dx, dy), 2.0) for e in geo]
    P0 = np.vstack(pts) if pts else np.zeros((0, 2))
    best = (-1.0, 0, 0)
    for ox in range(-6, 7, 2):
        for oy in range(-6, 7, 2):
            P = (P0 + (ox, oy)).astype(int)
            P = P[(P[:, 0] >= 0) & (P[:, 1] >= 0) & (P[:, 0] < W) & (P[:, 1] < H)]
            v = float((dist[P[:, 1], P[:, 0]] <= 1.5).mean()) if len(P) else 0.0
            if v > best[0]:
                best = (v, ox, oy)
    return s, dx + best[1], dy + best[2]


def _points(e, step: float = 1.0) -> np.ndarray:
    """Punkte im Abstand step entlang eines Objekts (Bildpixel)."""
    if isinstance(e, Line):
        segs = [(e.p1, e.p2)]
    elif isinstance(e, Polyline):
        P = list(e.points) + ([e.points[0]] if e.closed else [])
        segs = list(zip(P, P[1:]))
    elif isinstance(e, (Arc, Circle)):
        a0, a1 = (e.start_angle, e.start_angle + (e.end_angle - e.start_angle) % 360) \
            if isinstance(e, Arc) else (0.0, 360.0)
        n = max(2, int(math.radians(a1 - a0) * e.radius / step))
        a = np.radians(np.linspace(a0, a1, n))
        return np.c_[e.center[0] + e.radius * np.cos(a), e.center[1] + e.radius * np.sin(a)]
    else:
        return np.zeros((0, 2))
    out = [np.linspace(a, b, max(2, int(math.dist(a, b) / step) + 1)) for a, b in segs]
    return np.vstack(out) if out else np.zeros((0, 2))


def _on_ink(ents, dist: np.ndarray, tol: float = 1.5) -> float:
    pts = [_points(e) for e in ents]
    P = np.vstack(pts) if pts else np.zeros((0, 2))
    H, W = dist.shape
    P = P[(P[:, 0] >= 0) & (P[:, 1] >= 0) & (P[:, 0] < W) & (P[:, 1] < H)].astype(int)
    return float((dist[P[:, 1], P[:, 0]] <= tol).mean()) if len(P) else 0.0


def printed(truth: list, ink: np.ndarray, share: float = 0.6) -> list:
    """Nur Originalobjekte, die auf dem Scan zu sehen sind (≥ share auf Tinte).

    Ausgeblendete Layer, nicht gedruckte Maßketten usw. sollen nicht als „fehlt“ zählen."""
    dist = cv2.distanceTransform((ink == 0).astype(np.uint8), cv2.DIST_L2, 3)
    out = []
    for e in truth:
        if isinstance(e, Text):
            R = int(e.height * (len(e.text) + 2)) + 4      # Text in eigener Kachel zeichnen
            tile = np.zeros((2 * R, 2 * R), np.uint8)
            _draw_text(tile, Text(e.text, (R, R), e.height, e.angle))
            ys, xs = np.nonzero(tile)
            xs, ys = xs + int(round(e.position[0])) - R, ys + int(round(e.position[1])) - R
            ok = (xs >= 0) & (ys >= 0) & (xs < ink.shape[1]) & (ys < ink.shape[0])
            v = float((dist[ys[ok], xs[ok]] <= 2.0).mean()) if ok.any() else 0.0
        else:
            v = _on_ink([e], dist, 2.0)
        if v >= share:
            out.append(e)
    return out


def scan_scale(cad: list, unit: float, ink: np.ndarray, mm_per_px: float) -> Tuple[float, float]:
    """Plotmaßstab N (1:N) eines echten Plots: Schätzung aus der Ausdehnung (±30 %, ausgeblendete
    Layer und Plankopf verfälschen sie), dann alle üblichen Maßstäbe und Vielfache von 25 in diesem
    Bereich ausprobieren. Bewertet wird, wie gut Original und Tinte gegenseitig aufeinander liegen
    (harmonisches Mittel); der richtige Maßstab ist ein scharfes Maximum (PLAN3: 1:350 → 0,8,
    ±1,5 % daneben schon < 0,45). Gibt (N, Bewertung 0–1)."""
    from .dxf_import import fit_to_image
    from .scale_detect import COMMON
    geo = [e for e in cad if not isinstance(e, Text)]
    _, (s, _, _) = fit_to_image(geo, ink)
    n0 = unit / (mm_per_px * s)
    cands = sorted({n for n in set(COMMON) | set(range(25, 2001, 25)) if 0.7 * n0 <= n <= 1.4 * n0})
    dist = cv2.distanceTransform((ink == 0).astype(np.uint8), cv2.DIST_L2, 3)
    H, W = ink.shape
    sub = geo[::max(1, len(geo) // 3000)]       # Ausrichten: ~3000 Objekte genügen (Tempo)
    C = np.vstack([_points(e, 2.0 * mm_per_px * n0 / unit) for e in geo])   # alle, CAD-Einheiten
    best = (-1.0, n0)
    for n in cands:
        s, dx, dy = _align(sub, ink, unit / mm_per_px / n)
        P = np.column_stack([s * C[:, 0] + dx, dy - s * C[:, 1]])
        P = P[(P[:, 0] >= 0) & (P[:, 1] >= 0) & (P[:, 0] < W) & (P[:, 1] < H)].astype(int)
        if not len(P):
            continue
        a = float((dist[P[:, 1], P[:, 0]] <= 1.5).mean())          # Original auf Tinte
        m = np.zeros(ink.shape, np.uint8)
        m[P[:, 1], P[:, 0]] = 1
        m = cv2.dilate(m, np.ones((5, 5), np.uint8))
        c = float(((m > 0) & (ink > 0)).sum() / max(1, int((ink > 0).sum())))  # Tinte am Original
        v = 2 * a * c / (a + c) if a + c else 0.0
        if v > best[0]:
            best = (v, float(n))
    return best[1], max(best[0], 0.0)


def _printed_ink(gray: np.ndarray, mm_per_px: float) -> np.ndarray:
    """Tinte für „gedruckt?“: dunkel (< 160) und kleine hellgraue Teile bis 1 mm (Allplan plottet Kies
    als graue Ringe, Grau ~170). Große graue Flächen zählen nicht – darunter liegen sonst ausgeblendete
    Objekte (PLAN1: Trefferquote 97 → 50 %)."""
    ink = gray < 160
    n, lab, st, _ = cv2.connectedComponentsWithStats((gray < 210).astype(np.uint8), connectivity=8)
    small = np.maximum(st[:, 2], st[:, 3]) <= 1.0 / mm_per_px
    small[0] = False
    return ((ink | small[lab]) * 255).astype(np.uint8)


def run_real(dxf: str, scan: str, scale_n: float = 0, settings=None, progress=None,
             ki=None) -> dict:
    """Echter Scan/Plot eines Original-CAD-Plans → Traceify → Messung gegen das Original.
    scale_n ≤ 0: Plotmaßstab je Plan erkennen (`scan_scale`). ki = (Client, Modell): danach
    unerkannte Schrift per KI nachlesen und alle Vorschläge übernehmen."""
    import time

    from ..api import open_file
    from . import loader
    cad, unit = load_cad(dxf)
    gray, mm_per_px = loader.load(scan)
    ink = ((gray < 160) * 255).astype(np.uint8)
    fit = None
    if not scale_n or scale_n <= 0:
        scale_n, fit = scan_scale(cad, unit, ink, mm_per_px)
    truth = printed(align_scan(cad, ink, unit / mm_per_px / scale_n), _printed_ink(gray, mm_per_px))
    t0 = time.time()
    res = open_file(scan, 0, settings, progress=progress)
    n_ki = None
    if ki:
        from ..ai.assistant import apply_text_fixes, read_unrecognized
        fixes = read_unrecognized(ki[0], ki[1], gray, res.binary, res.drawing, 1.0 / mm_per_px)
        n_ki = apply_text_fixes(res.drawing, fixes)[1]
    ents, areas = _with_areas(res.drawing)
    r = compare(truth, ents, gray.shape, mm_per_px, areas=areas)
    if n_ki is not None:
        r["ki_texte"] = n_ki
    r.update({"datei": dxf, "scan": scan, "bild": [int(gray.shape[1]), int(gray.shape[0])],
              "massstab": float(scale_n), "passung": None if fit is None else round(fit, 3),
              "sekunden": round(time.time() - t0, 1)})
    return r


def _self_check() -> None:
    """Rundweg-Probe: Original gegen sich selbst ergibt 100 % und Lagefehler 0."""
    cad = [Line((0, 0), (5000, 0)), Line((0, 0), (0, 3000)), Arc((2500, 1500), 500, 0, 90),
           Text("Bad", (1000, 1000), 300, 0.0)]
    sc = render_scan(cad, noise=0, blur=0)
    r = compare(sc.truth, sc.truth, sc.gray.shape, sc.mm_per_px)
    assert r["trefferquote"] == 1.0 and r["genauigkeit"] == 1.0 and r["lage_median_mm"] == 0.0
    assert math.isclose(r["ortho_original"], 1.0)
