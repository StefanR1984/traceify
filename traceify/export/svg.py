"""SVG-Export (Einheiten in mm)."""
from __future__ import annotations

import math
from xml.sax.saxutils import escape

from ..core.dots import find_areas as find_gravel
from ..core.hatch import find_regions, wants_areas
from ..core.model import Arc, Circle, Drawing, LAYER_GRAVEL, LAYER_HATCH, Line, Polyline, Text, layer_color

_DASH = {"DASHED": "3 1.5", "HIDDEN": "1.5 0.75", "DOT": "0.3 1", "DASHDOT": "4 1 0.5 1",
         "CENTER": "6 1 1.5 1"}


def _style(e, s: float) -> str:
    st = []
    if getattr(e, "color", None):
        st.append('stroke="#%02x%02x%02x"' % tuple(int(c) for c in e.color))
    if getattr(e, "lineweight", 0):
        st.append(f'stroke-width="{max(0.05, e.lineweight):.2f}"')
    dash = _DASH.get(getattr(e, "linetype", "CONTINUOUS"))
    if dash:
        st.append(f'stroke-dasharray="{dash}"')
    return (" " + " ".join(st)) if st else ""


def _arc_path(e: Arc, s: float) -> str:
    cx, cy, r = e.center[0] * s, e.center[1] * s, e.radius * s
    a0, a1 = math.radians(e.start_angle), math.radians(e.end_angle)
    span = (e.end_angle - e.start_angle) % 360
    x0, y0 = cx + r * math.cos(a0), cy + r * math.sin(a0)
    x1, y1 = cx + r * math.cos(a1), cy + r * math.sin(a1)
    large = 1 if span > 180 else 0
    return f"M{x0:.3f},{y0:.3f} A{r:.3f},{r:.3f} 0 {large} 1 {x1:.3f},{y1:.3f}"


def _hatch_svg(regions, s: float, col: str) -> list:
    """Schraffur-Flächen: Umriss (mit Löchern) gefüllt mit einem Linienmuster je Fläche."""
    defs, body = [], []
    for i, reg in enumerate(regions):
        sp = reg.spacing * s
        bx, by = reg.base[0] * s, reg.base[1] * s
        # Kachel: eine Linie in halber Höhe; gedreht um den Winkel, verschoben auf den
        # Basispunkt (die gedrehte y-Achse ist die Normale der Schraffurlinien)
        defs.append(f'<pattern id="schraffur{i}" patternUnits="userSpaceOnUse" '
                    f'width="{sp:.4f}" height="{sp:.4f}" patternTransform="translate('
                    f'{bx:.3f} {by:.3f}) rotate({reg.angle:.3f}) translate(0 {-sp / 2:.4f})">'
                    f'<line x1="-1" y1="{sp / 2:.4f}" x2="{sp + 1:.4f}" y2="{sp / 2:.4f}" '
                    f'stroke="{col}" stroke-width="0.25"/></pattern>')
        d = " ".join("M" + " L".join(f"{x * s:.3f},{y * s:.3f}" for x, y in ring) + " Z"
                     for ring in [reg.outline] + reg.holes)
        body.append(f'<path d="{d}" fill="url(#schraffur{i})" fill-rule="evenodd" '
                    f'stroke="none"/>')
    return ["<defs>"] + defs + ["</defs>"] + body


def _gravel_svg(regions, s: float, col: str) -> list:
    """Kies-Flächen: Umriss gefüllt mit einem Punktmuster (versetzte Reihen im Punktabstand)."""
    defs, body = [], []
    for i, reg in enumerate(regions):
        sp, r = reg.spacing * s, max(reg.radius * s, 0.05)
        h = sp * 3 ** 0.5
        defs.append(f'<pattern id="kies{i}" patternUnits="userSpaceOnUse" width="{sp:.4f}" '
                    f'height="{h:.4f}"><circle cx="0" cy="0" r="{r:.4f}"/>'
                    f'<circle cx="{sp:.4f}" cy="0" r="{r:.4f}"/><circle cx="0" cy="{h:.4f}" r="{r:.4f}"/>'
                    f'<circle cx="{sp:.4f}" cy="{h:.4f}" r="{r:.4f}"/>'
                    f'<circle cx="{sp / 2:.4f}" cy="{h / 2:.4f}" r="{r:.4f}"/></pattern>')
        d = " ".join("M" + " L".join(f"{x * s:.3f},{y * s:.3f}" for x, y in ring) + " Z"
                     for ring in [reg.outline] + reg.holes)
        body.append(f'<path d="{d}" fill="url(#kies{i})" fill-rule="evenodd" stroke="none"/>')
    return [f'<defs fill="none" stroke="{col}" stroke-width="0.1">'] + defs + ["</defs>"] + body


def export_svg(d: Drawing, path: str, visible_layers=None) -> None:
    d = d.export_view()          # Schräglage des Scans herausdrehen
    s = d.scale
    W, H = d.width * s, d.height * s
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.2f}mm" height="{H:.2f}mm" '
           f'viewBox="0 0 {W:.3f} {H:.3f}">']
    regions, skip = [], set()
    if wants_areas(d) and (visible_layers is None or LAYER_HATCH in visible_layers):
        regions = find_regions(d.entities)
        skip = {id(m) for r in regions for m in r.members}
    gravel = []
    if wants_areas(d) and (visible_layers is None or LAYER_GRAVEL in visible_layers):
        gravel = find_gravel(d.entities)
        skip |= {id(m) for r in gravel for m in r.members}
    by_layer = {}
    for e in d.expanded():
        if id(e) in skip:
            continue
        if visible_layers is None or e.layer in visible_layers:
            by_layer.setdefault(e.layer, []).append(e)
    for layer, ents in by_layer.items():
        rgb = layer_color(layer)[1]
        col = "#%02x%02x%02x" % rgb
        out.append(f'<g id="{layer}" stroke="{col}" fill="none" stroke-width="0.25">')
        if layer == LAYER_HATCH and regions:
            out += _hatch_svg(regions, s, col)
            regions = []
        if layer == LAYER_GRAVEL and gravel:
            out += _gravel_svg(gravel, s, col)
            gravel = []
        for e in ents:
            if isinstance(e, Line):
                out.append(f'<line x1="{e.p1[0]*s:.3f}" y1="{e.p1[1]*s:.3f}" '
                           f'x2="{e.p2[0]*s:.3f}" y2="{e.p2[1]*s:.3f}"{_style(e, s)}/>')
            elif isinstance(e, Circle):
                out.append(f'<circle cx="{e.center[0]*s:.3f}" cy="{e.center[1]*s:.3f}" '
                           f'r="{e.radius*s:.3f}"{_style(e, s)}/>')
            elif isinstance(e, Arc):
                out.append(f'<path d="{_arc_path(e, s)}"{_style(e, s)}/>')
            elif isinstance(e, Polyline):
                pts = " ".join(f"{x*s:.3f},{y*s:.3f}" for x, y in e.points)
                tag = "polygon" if e.closed else "polyline"
                out.append(f'<{tag} points="{pts}"{_style(e, s)}/>')
            elif isinstance(e, Text):
                x, y = e.position[0] * s, e.position[1] * s
                out.append(f'<text x="{x:.3f}" y="{y:.3f}" font-size="{e.height*s:.3f}" '
                           f'fill="{col}" stroke="none" font-family="sans-serif" '
                           f'transform="rotate({-e.angle:.2f} {x:.3f} {y:.3f})">'
                           f'{escape(e.text)}</text>')
        out.append("</g>")
    if regions:                  # nur Flächen, keine Einzellinien mehr auf SCHRAFFUR
        col = "#%02x%02x%02x" % layer_color(LAYER_HATCH)[1]
        out.append(f'<g id="{LAYER_HATCH}" fill="none">')
        out += _hatch_svg(regions, s, col)
        out.append("</g>")
    if gravel:                   # alle Kies-Kreise sind in Flächen aufgegangen
        col = "#%02x%02x%02x" % layer_color(LAYER_GRAVEL)[1]
        out.append(f'<g id="{LAYER_GRAVEL}">')
        out += _gravel_svg(gravel, s, col)
        out.append("</g>")
    out.append("</svg>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
