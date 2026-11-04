"""Direkter Import von Vektor-PDFs (aus CAD-Programmen, Plotdateien, Illustrator …).

Statt die Seite zu rastern und neu zu vektorisieren, werden Linien, Kurven,
Rechtecke und Texte unmittelbar aus dem PDF gelesen – millimetergenau.
Bézierkurven, die einem Kreis(bogen) entsprechen, werden als echte Bögen
bzw. Kreise übernommen, alles andere als Polylinie.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from .model import (Arc, Circle, Drawing, LAYER_ARCS, LAYER_CIRCLES, LAYER_FILL, LAYER_LINES,
                    LAYER_POLY, LAYER_TEXT, Line, Polyline, Text)
from .vectorize import fit_circle


@dataclass
class PdfVectorSettings:
    enabled: bool = True          # Vektordaten nutzen, wenn vorhanden
    min_items: int = 15           # ab so vielen Zeichenbefehlen gilt die Seite als Vektor-PDF
    include_fills: bool = False   # gefüllte Flächen (Schraffuren, Logos) als Konturen übernehmen
    include_text: bool = True
    keep_colors: bool = True
    arc_tolerance: float = 0.6    # max. Abweichung (px) für Kreis/Bogen-Erkennung
    curve_samples: int = 12


# ------------------------------------------------------------------ Hilfen
def _pts_transform(m, f):
    """Gibt eine Funktion zurück, die PDF-Punkte (ungedreht) in Bildpixel umrechnet."""
    a, b, c, d, e, g = m.a, m.b, m.c, m.d, m.e, m.f

    def tr(p):
        x, y = float(p.x), float(p.y)
        return ((a * x + c * y + e) * f, (b * x + d * y + g) * f)
    return tr


def _bezier(p0, p1, p2, p3, n):
    t = np.linspace(0, 1, n + 1)[:, None]
    P = [np.array(p, float) for p in (p0, p1, p2, p3)]
    return ((1 - t) ** 3 * P[0] + 3 * (1 - t) ** 2 * t * P[1] + 3 * (1 - t) * t * t * P[2]
            + t ** 3 * P[3])


def _rgb(col) -> Optional[Tuple[int, int, int]]:
    if not col:
        return None
    c = tuple(int(round(max(0.0, min(1.0, float(v))) * 255)) for v in col[:3])
    return None if c == (0, 0, 0) else c  # Schwarz = Layerfarbe


def _arc_from_points(pts: np.ndarray, tol: float):
    """Kreisbogen-Fit für eine abgetastete Kurve: (cx, cy, r, a0, a1) oder None."""
    c = fit_circle(pts)
    if not c or c[3] > tol or c[2] < 0.5:
        return None
    cx, cy, r, _ = c
    ang = np.unwrap(np.arctan2(pts[:, 1] - cy, pts[:, 0] - cx))
    d = np.diff(ang)
    if not (np.all(d >= -1e-3) or np.all(d <= 1e-3)):
        return None
    a0, a1 = math.degrees(ang[0]), math.degrees(ang[-1])
    if a1 < a0:
        a0, a1 = a1, a0
    return cx, cy, r, a0, a1


def _group_curves(raw: list, tol: float, closed_loop: bool) -> list:
    """raw: Liste aus Entities und ("curve", pts, attrs).  Aufeinanderfolgende Kurvenstücke
    auf demselben Kreis werden zu EINEM Bogen bzw. Kreis zusammengefasst."""
    out, group = [], []

    def emit():
        nonlocal group
        if not group:
            return
        pts = np.vstack([g[1] if i == 0 else g[1][1:] for i, g in enumerate(group)])
        attrs = group[0][2]
        whole_loop = closed_loop and len(group) == len([r for r in raw if isinstance(r, tuple)]) \
            and math.dist(pts[0], pts[-1]) < 1.0
        c = fit_circle(pts)
        if c and c[3] <= tol and c[2] >= 0.5:
            cx, cy, r = float(c[0]), float(c[1]), float(c[2])
            if whole_loop:
                out.append(Circle((cx, cy), r, LAYER_CIRCLES, *attrs))
                group = []
                return
            arc = _arc_from_points(pts, tol)
            if arc:
                _, _, _, a0, a1 = arc
                if a1 - a0 >= 359:
                    out.append(Circle((cx, cy), r, LAYER_CIRCLES, *attrs))
                else:
                    out.append(Arc((cx, cy), r, a0 % 360, a1 % 360, LAYER_ARCS, *attrs))
                group = []
                return
        # kein Kreis: jedes Stück als Polylinie
        for g in group:
            out.append(Polyline([(float(x), float(y)) for x, y in g[1]], False, LAYER_POLY, *attrs))
        group = []

    for r in raw:
        if isinstance(r, tuple):
            if group:
                c_prev = fit_circle(np.vstack([g[1] for g in group]))
                c_new = fit_circle(r[1])
                same = (c_prev and c_new and c_prev[3] <= tol and c_new[3] <= tol and
                        math.dist(c_prev[:2], c_new[:2]) < 2 * tol + 0.02 * c_prev[2] and
                        abs(c_prev[2] - c_new[2]) < 2 * tol + 0.02 * c_prev[2])
                if not same:
                    emit()
            group.append(r)
        else:
            emit()
            out.append(r)
    emit()
    return out


# ------------------------------------------------------------------ API
def page_vector_count(path: str, page: int = 0) -> int:
    import pymupdf
    with pymupdf.open(path) as doc:
        pg = doc.load_page(page)
        return sum(len(d.get("items", [])) for d in pg.get_drawings())


def has_vectors(path: str, page: int = 0, settings: Optional[PdfVectorSettings] = None) -> bool:
    s = settings or PdfVectorSettings()
    if not path.lower().endswith(".pdf") or not s.enabled:
        return False
    try:
        return page_vector_count(path, page) >= s.min_items
    except Exception:
        return False


def import_page(path: str, page: int = 0, dpi: int = 300,
                settings: Optional[PdfVectorSettings] = None) -> Drawing:
    """Liest Vektoren und Texte einer PDF-Seite. Koordinaten passen zum Raster bei `dpi`."""
    import pymupdf
    s = settings or PdfVectorSettings()
    dpi = int(round(float(dpi)))
    f = dpi / 72.0
    with pymupdf.open(path) as doc:
        pg = doc.load_page(page)
        rect = pg.rect
        W, H = int(round(rect.width * f)), int(round(rect.height * f))
        tr = _pts_transform(pg.rotation_matrix, f)
        ents: list = []
        for dr in pg.get_drawings():
            kind = dr.get("type", "s") or "s"
            stroked = "s" in kind
            if not stroked and not s.include_fills:
                continue
            color = _rgb(dr.get("color") if stroked else dr.get("fill")) if s.keep_colors else None
            width_mm = float(dr.get("width") or 0) * 25.4 / 72 if stroked else 0.0
            dashes = str(dr.get("dashes") or "")
            linetype = "DASHED" if stroked and dashes and not dashes.startswith("[] ") else \
                "CONTINUOUS"
            fill_layer = LAYER_FILL if not stroked else None
            ents += _convert_items(dr.get("items", []), bool(dr.get("closePath")), tr, s, color,
                                   linetype, width_mm, fill_layer)
        if s.include_text:
            ents += _texts(pg, tr, f)
    return Drawing(width=W, height=H, scale=25.4 / dpi, entities=ents,
                   source=f"{path}#S{page + 1}", meta={"quelle": "PDF-Vektoren"})


def _convert_items(items, close_path, tr, s: PdfVectorSettings, color, linetype, width_mm,
                   fill_layer) -> list:
    out: list = []
    seq: list = []          # Entities des aktuellen Teilpfads
    start = None            # Startpunkt des Teilpfads (für Schließen)
    last = None
    tol = s.arc_tolerance

    def L(a, b):
        return Line(a, b, fill_layer or LAYER_LINES, color, linetype, width_mm)

    def flush():
        nonlocal seq, start
        if seq:
            closed_loop = start is not None and last is not None and math.dist(start, last) < 1.0
            merged = _group_curves(seq, tol, closed_loop)
            if fill_layer:
                pts = []
                for e in merged:
                    if isinstance(e, Line):
                        pts += [e.p1, e.p2]
                    elif isinstance(e, Polyline):
                        pts += e.points
                    elif isinstance(e, (Arc, Circle)):
                        pts += _arc_points(e)
                if len(pts) >= 3:
                    out.append(Polyline(pts, True, fill_layer, color))
            else:
                out.extend(merged)
        seq, start = [], None

    for it in items:
        op = it[0]
        if op == "re":
            flush()
            r = it[1]
            q = [tr(r.tl), tr(r.tr), tr(r.br), tr(r.bl)]
            seq = [L(q[i], q[(i + 1) % 4]) for i in range(4)]
            flush()
            last = None
            continue
        if op == "qu":
            flush()
            qd = it[1]
            q = [tr(qd.ul), tr(qd.ur), tr(qd.lr), tr(qd.ll)]
            seq = [L(q[i], q[(i + 1) % 4]) for i in range(4)]
            flush()
            last = None
            continue
        p_start = tr(it[1])
        if last is None or math.dist(last, p_start) > 0.5:
            flush()
            start = p_start
        if op == "l":
            a, b = p_start, tr(it[2])
            if math.dist(a, b) > 1e-6:
                seq.append(L(a, b))
            last = b
        elif op == "c":
            p0, p1, p2, p3 = (tr(it[k]) for k in range(1, 5))
            pts = _bezier(p0, p1, p2, p3, s.curve_samples)
            seq.append(("curve", pts, (color, linetype, width_mm)))
            last = p3
    if close_path and start is not None and last is not None and math.dist(start, last) > 0.5:
        seq.append(L(last, start))
    flush()
    return out


def _arc_points(e, n: int = 24):
    if isinstance(e, Circle):
        a = np.linspace(0, 2 * math.pi, n, endpoint=False)
    else:
        span = (e.end_angle - e.start_angle) % 360
        a = np.radians(e.start_angle + np.linspace(0, span, n))
    return [(e.center[0] + e.radius * math.cos(t), e.center[1] + e.radius * math.sin(t)) for t in a]


def _texts(pg, tr, f) -> List[Text]:
    out = []
    m = pg.rotation_matrix
    for b in pg.get_text("dict").get("blocks", []):
        for ln in b.get("lines", []):
            spans = [sp for sp in ln.get("spans", []) if sp.get("text", "").strip()]
            if not spans:
                continue
            txt = "".join(sp["text"] for sp in ln["spans"]).strip()
            size = max(sp.get("size", 10) for sp in spans)
            ox, oy = spans[0]["origin"]
            import pymupdf
            pos = tr(pymupdf.Point(ox, oy))
            dx, dy = ln.get("dir", (1.0, 0.0))
            # Richtung mitdrehen (ohne Verschiebung)
            rx, ry = m.a * dx + m.c * dy, m.b * dx + m.d * dy
            angle = math.degrees(math.atan2(-ry, rx))
            angle = round(angle, 2) + 0.0
            out.append(Text(txt, (float(pos[0]), float(pos[1])), size * f * 0.7, angle, LAYER_TEXT))
    return out
