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


def compare(truth: list, ents: list, shape, mm_per_px: float, tol_mm: float = 0.3) -> dict:
    """Misst Traceify-Objekte (Bildpixel) gegen die Originalgeometrie (Bildpixel)."""
    tg = [e for e in truth if not isinstance(e, (Text, Insert))]
    mg = [e for e in ents if not isinstance(e, (Text, Insert))]
    T = render_entities(tg, shape, width_px=1, texts=False)
    M = render_entities(mg, shape, width_px=1, texts=False)
    tol = max(1.0, tol_mm / mm_per_px)
    dT = cv2.distanceTransform((T == 0).astype(np.uint8), cv2.DIST_L2, 3)
    dM = cv2.distanceTransform((M == 0).astype(np.uint8), cv2.DIST_L2, 3)
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
    wt, wm = words(e for e in truth if isinstance(e, Text)), words(e for e in ents
                                                                     if isinstance(e, Text))
    return {
        "trefferquote": round(float((dM[t_px] <= tol).mean()) if t_px.any() else 0.0, 4),
        "genauigkeit": round(float((dT[m_px] <= tol).mean()) if m_px.any() else 0.0, 4),
        "lage_median_mm": round(float(np.median(off)), 3) if off.size else None,
        "lage_p95_mm": round(float(np.percentile(off, 95)), 3) if off.size else None,
        "objekte": len(mg), "objekte_original": len(tg),
        "boegen": sum(isinstance(e, Arc) for e in mg),
        "boegen_original": sum(isinstance(e, (Arc, Circle)) for e in tg),
        "ortho": round(ortho_share(mg), 4), "ortho_original": round(ortho_share(tg), 4),
        "woerter": len(wt & wm), "woerter_original": len(wt),
        "woerter_falsch": len(wm - wt),
    }


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
    r = compare(sc.truth, res.drawing.expanded(), sc.gray.shape, sc.mm_per_px)
    r.update({"datei": path, "bild": [int(sc.gray.shape[1]), int(sc.gray.shape[0])],
              "sekunden": round(time.time() - t0, 1)})
    return r


def align_scan(cad: list, ink: np.ndarray, px_per_unit: float) -> list:
    """Legt die Original-CAD-Objekte auf einen echten Scan mit bekanntem Maßstab.

    Versatz grob über die Ausdehnung, dann per Kreuzkorrelation (Viertelauflösung), zuletzt
    pixelgenau. Das Original enthält oft mehr als gedruckt (ausgeblendete Layer), die
    Ausdehnung allein trifft dann nicht."""
    from .dxf_import import fit_to_image
    geo = [e for e in cad if not isinstance(e, Text)]
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
    return [transform(e, s, dx + best[1], dy + best[2]) for e in cad]


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


def run_real(dxf: str, scan: str, scale_n: float, settings=None, progress=None) -> dict:
    """Echter Scan/Plot eines Original-CAD-Plans → Traceify → Messung gegen das Original."""
    import time

    from ..api import open_file
    from . import loader
    cad, unit = load_cad(dxf)
    gray, mm_per_px = loader.load(scan)
    ink = ((gray < 160) * 255).astype(np.uint8)
    truth = printed(align_scan(cad, ink, unit / mm_per_px / scale_n), ink)
    t0 = time.time()
    res = open_file(scan, 0, settings, progress=progress)
    r = compare(truth, res.drawing.expanded(), gray.shape, mm_per_px)
    r.update({"datei": dxf, "scan": scan, "bild": [int(gray.shape[1]), int(gray.shape[0])],
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
