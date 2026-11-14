"""DXF einlesen – z. B. Ergebnisse anderer Programme für den Prüfstand.

Die Objekte werden ins Traceify-Modell übernommen (Linien, Bögen, Kreise, Polylinien,
Texte; Blöcke und Schraffur-Blöcke aufgelöst). Die Koordinaten bleiben zunächst im
CAD-System (y nach oben, Einheit der Datei); ``fit_to_image`` legt sie passend auf ein
Rasterbild (Bildpixel, y nach unten).
"""
from __future__ import annotations

import math
import re
from typing import List, Optional, Tuple

import numpy as np

from .model import Arc, Circle, Line, Polyline, Text

_UNI = re.compile(r"\\U\+([0-9A-Fa-f]{4})")


def _plain(s: str) -> str:
    """\\U+XXXX-Folgen (z. B. aus kommerziellen Vektorisierungsprogrammen) in Zeichen umwandeln."""
    return _UNI.sub(lambda m: chr(int(m.group(1), 16)), s or "").strip()


_SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
# Stapel ohne unteren Teil: „2.38\S5^ ;“ = 2,38 mit hochgestellter 5 (Allplan-Maße)
_STACK_UP = re.compile(r"\\S([^;^/#]*)\^\s*;")
_LINE_SPACING = 5 / 3     # MTEXT-Zeilenabstand je Schrifthöhe (AutoCAD-Vorgabe)
_ARIAL = None


def _text_width(s: str, h: float) -> float:
    """Breite einer Textzeile mit Schrifthöhe h (Großbuchstabenhöhe), Arial-Maße."""
    global _ARIAL
    try:
        from PIL import ImageFont
        if _ARIAL is None:
            _ARIAL = ImageFont.truetype("arial.ttf", 100, layout_engine=ImageFont.Layout.BASIC)
        return _ARIAL.getlength(s) / 100 * h / 0.716
    except (OSError, ImportError):
        return 0.75 * h * len(s)    # shortcut: grobe Schätzung ohne Arial


def _mtext(e, out: list) -> None:
    """MTEXT zeilenweise als Text (Grundlinie links), mit Drehung und Ausrichtung."""
    from ezdxf.tools.text import plain_mtext
    raw = _STACK_UP.sub(lambda m: m.group(1).translate(_SUP), e.text or "")
    lines = [_plain(x) for x in plain_mtext(raw, split=True)]
    h = float(e.dxf.char_height)
    ls = h * _LINE_SPACING * float(e.dxf.get("line_spacing_factor", 1.0) or 1.0)
    ap = int(e.dxf.get("attachment_point", 1) or 1)
    row, col = (ap - 1) // 3, (ap - 1) % 3      # oben/Mitte/unten, links/Mitte/rechts
    n = len(lines)
    first = (-h, (h + (n - 1) * ls) / 2 - h, (n - 1) * ls)[row]   # erste Grundlinie
    rot = float(e.get_rotation()) % 360          # Allplan: Richtung als Vektor, nicht „rotation“
    c, s_ = math.cos(math.radians(rot)), math.sin(math.radians(rot))
    p = e.dxf.insert
    for i, txt in enumerate(lines):
        if not txt:
            continue
        dx, dy = -_text_width(txt, h) * col / 2, first - i * ls
        out.append(Text(txt, (p.x + dx * c - dy * s_, p.y + dx * s_ + dy * c), h, rot))


def _convert(e, out: list, depth: int = 0) -> None:
    t = e.dxftype()
    if t == "LINE":
        s, n = e.dxf.start, e.dxf.end
        out.append(Line((s.x, s.y), (n.x, n.y)))
    elif t == "ARC":
        c = e.dxf.center
        out.append(Arc((c.x, c.y), e.dxf.radius, e.dxf.start_angle, e.dxf.end_angle))
    elif t == "CIRCLE":
        c = e.dxf.center
        out.append(Circle((c.x, c.y), e.dxf.radius))
    elif t in ("LWPOLYLINE", "POLYLINE"):
        try:
            if any(abs(b) > 1e-9 for b in _bulges(e)):
                for v in e.virtual_entities():   # Bögen in Polylinien auflösen
                    _convert(v, out, depth + 1)
                return
            pts = [(p[0], p[1]) for p in (e.get_points("xy") if t == "LWPOLYLINE"
                                          else [v.dxf.location for v in e.vertices])]
        except Exception:
            return
        if len(pts) > 1:
            out.append(Polyline(pts, bool(e.closed)))
    elif t == "MTEXT":
        _mtext(e, out)
    elif t == "TEXT":
        txt = _plain(e.dxf.text)
        if txt:
            p = e.dxf.insert
            out.append(Text(txt, (p.x, p.y), float(e.dxf.height),
                            float(e.dxf.get("rotation", 0.0)) % 360))
    elif t in ("INSERT", "DIMENSION") and depth < 8:   # Bemaßung: Linien, Pfeile, Maßtext
        try:
            for v in e.virtual_entities():
                _convert(v, out, depth + 1)
        except Exception:
            pass


def _bulges(e) -> list:
    if e.dxftype() == "LWPOLYLINE":
        return [p[4] for p in e.get_points("xyseb")]
    return [v.dxf.get("bulge", 0.0) for v in e.vertices]


def read_dxf(path: str) -> List[object]:
    """Alle unterstützten Objekte des Modellbereichs (CAD-Koordinaten, y nach oben)."""
    import ezdxf
    doc = ezdxf.readfile(path)
    out: list = []
    for e in doc.modelspace():
        _convert(e, out)
    return out


def _samples(ents, step: float) -> np.ndarray:
    """Punkte entlang der Geometrie (für die Lage-Schätzung)."""
    pts = []
    for e in ents:
        if isinstance(e, Line):
            n = max(1, int(math.dist(e.p1, e.p2) / step))
            for k in range(n + 1):
                f = k / n
                pts.append((e.p1[0] + f * (e.p2[0] - e.p1[0]), e.p1[1] + f * (e.p2[1] - e.p1[1])))
        elif isinstance(e, Polyline):
            for a, b in zip(e.points, e.points[1:]):
                pts += [a, b]
        elif isinstance(e, (Arc, Circle)):
            pts.append(e.center)
    return np.array(pts, float) if pts else np.zeros((0, 2))


def fit_to_image(ents: list, ink: np.ndarray, scale: Optional[float] = None
                 ) -> Tuple[list, Tuple[float, float, float]]:
    """Legt CAD-Objekte auf das Bild: x' = s·x + dx, y' = dy − s·y.

    Maßstab und Versatz werden aus der Lage der Geometrie und der Tinte geschätzt
    (1.–99. Perzentil), sofern ``scale`` nicht vorgegeben ist. Gibt (Objekte, (s, dx, dy)).
    """
    ys, xs = np.nonzero(ink)
    geo = [e for e in ents if not isinstance(e, Text)]
    if len(xs) == 0 or not geo:
        return [], (1.0, 0.0, 0.0)
    ext = np.ptp(_samples(geo, 1e9), axis=0).max() if len(geo) else 1.0
    P = _samples(geo, max(ext / 4000.0, 1e-6))
    ix0, ix1 = np.percentile(xs, [1, 99])
    iy0, iy1 = np.percentile(ys, [1, 99])
    px0, px1 = np.percentile(P[:, 0], [1, 99])
    py0, py1 = np.percentile(P[:, 1], [1, 99])
    scale_given = scale is not None
    if scale is None:
        sx = (ix1 - ix0) / max(px1 - px0, 1e-9)
        sy = (iy1 - iy0) / max(py1 - py0, 1e-9)
        scale = float(np.median([sx, sy]))
    s = float(scale)
    dx = float((ix0 + ix1) / 2 - s * (px0 + px1) / 2)
    dy = float((iy0 + iy1) / 2 + s * (py0 + py1) / 2)
    s, dx, dy = _refine(P, ink, s, dx, dy, fixed_scale=scale_given)
    return [transform(e, s, dx, dy) for e in ents], (s, dx, dy)


def _refine(P: np.ndarray, ink: np.ndarray, s: float, dx: float, dy: float,
            fixed_scale: bool = False) -> Tuple[float, float, float]:
    """Lage feinjustieren: mittlerer Abstand der Geometrie zur nächsten Tinte minimieren."""
    import cv2
    if len(P) > 30000:
        P = P[np.random.default_rng(0).choice(len(P), 30000, replace=False)]
    dist = cv2.distanceTransform((ink == 0).astype(np.uint8), cv2.DIST_L2, 3)
    dist = np.minimum(dist, 15.0)
    H, W = dist.shape

    def cost(s_, dx_, dy_):
        x = np.clip(np.round(s_ * P[:, 0] + dx_).astype(int), 0, W - 1)
        y = np.clip(np.round(dy_ - s_ * P[:, 1]).astype(int), 0, H - 1)
        return float(dist[y, x].mean())

    best = (cost(s, dx, dy), s, dx, dy)
    for step_s, step_xy in ((0.004, 8.0), (0.001, 2.0), (0.00025, 0.5)):
        improved = True
        while improved:
            improved = False
            c0, s0, x0, y0 = best
            for ds in ((0,) if fixed_scale else (-step_s, 0, step_s)):
                for ddx in (-step_xy, 0, step_xy):
                    for ddy in (-step_xy, 0, step_xy):
                        if ds == ddx == ddy == 0:
                            continue
                        c = cost(s0 + ds, x0 + ddx, y0 + ddy)
                        if c < best[0] - 1e-6:
                            best = (c, s0 + ds, x0 + ddx, y0 + ddy)
                            improved = True
    return best[1], best[2], best[3]


def transform(e, s: float, dx: float, dy: float):
    """CAD (y nach oben) -> Bild (y nach unten) mit Maßstab s und Versatz."""
    T = lambda p: (s * p[0] + dx, dy - s * p[1])  # noqa: E731
    if isinstance(e, Line):
        return Line(T(e.p1), T(e.p2), e.layer)
    if isinstance(e, Arc):   # Spiegelung an der x-Achse: Winkel tauschen und negieren
        return Arc(T(e.center), s * e.radius, (-e.end_angle) % 360, (-e.start_angle) % 360,
                   e.layer)
    if isinstance(e, Circle):
        return Circle(T(e.center), s * e.radius, e.layer)
    if isinstance(e, Polyline):
        return Polyline([T(p) for p in e.points], e.closed, e.layer)
    if isinstance(e, Text):
        return Text(e.text, T(e.position), s * e.height, e.angle, e.layer)
    return e
