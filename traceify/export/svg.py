"""SVG-Export (Einheiten in mm)."""
from __future__ import annotations

import math
from xml.sax.saxutils import escape

from ..core.model import Arc, Circle, Drawing, LAYER_COLORS, Line, Polyline, Text


def _arc_path(e: Arc, s: float) -> str:
    cx, cy, r = e.center[0] * s, e.center[1] * s, e.radius * s
    a0, a1 = math.radians(e.start_angle), math.radians(e.end_angle)
    span = (e.end_angle - e.start_angle) % 360
    x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
    x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
    large = 1 if span > 180 else 0
    return f"M{x0:.3f},{y0:.3f} A{r:.3f},{r:.3f} 0 {large} 1 {x1:.3f},{y1:.3f}"


def export_svg(d: Drawing, path: str, visible_layers=None) -> None:
    s = d.scale
    W, H = d.width * s, d.height * s
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.2f}mm" height="{H:.2f}mm" '
           f'viewBox="0 0 {W:.3f} {H:.3f}">']
    by_layer = {}
    for e in d.entities:
        if visible_layers is None or e.layer in visible_layers:
            by_layer.setdefault(e.layer, []).append(e)
    for layer, ents in by_layer.items():
        rgb = LAYER_COLORS.get(layer, (7, (0, 0, 0)))[1]
        col = "#%02x%02x%02x" % rgb
        out.append(f'<g id="{layer}" stroke="{col}" fill="none" stroke-width="0.25">')
        for e in ents:
            if isinstance(e, Line):
                out.append(f'<line x1="{e.p1[0]*s:.3f}" y1="{e.p1[1]*s:.3f}" '
                           f'x2="{e.p2[0]*s:.3f}" y2="{e.p2[1]*s:.3f}"/>')
            elif isinstance(e, Circle):
                out.append(f'<circle cx="{e.center[0]*s:.3f}" cy="{e.center[1]*s:.3f}" '
                           f'r="{e.radius*s:.3f}"/>')
            elif isinstance(e, Arc):
                out.append(f'<path d="{_arc_path(e, s)}"/>')
            elif isinstance(e, Polyline):
                pts = " ".join(f"{x*s:.3f},{y*s:.3f}" for x, y in e.points)
                tag = "polygon" if e.closed else "polyline"
                out.append(f'<{tag} points="{pts}"/>')
            elif isinstance(e, Text):
                x, y = e.position[0] * s, e.position[1] * s
                out.append(f'<text x="{x:.3f}" y="{y:.3f}" font-size="{e.height*s:.3f}" '
                           f'fill="{col}" stroke="none" font-family="sans-serif" '
                           f'transform="rotate({-e.angle:.2f} {x:.3f} {y:.3f})">'
                           f'{escape(e.text)}</text>')
        out.append("</g>")
    out.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
