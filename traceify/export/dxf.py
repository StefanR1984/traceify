"""DXF-Export mit ezdxf (Layer, Linien, Bögen, Kreise, Polylinien, Texte).

Farbe, Linientyp und Strichstärke einzelner Objekte werden übernommen.
"""
from __future__ import annotations

import re

import ezdxf
from ezdxf import colors as ezcolors
from ezdxf import units

from ..core.model import Arc, Circle, Drawing, Insert, Line, Polyline, Text, layer_color

DXF_VERSIONS = {"R12": "R12", "R2000": "R2000", "R2007": "R2007", "R2010": "R2010",
                "R2013": "R2013", "R2018": "R2018"}

# zulässige DXF-Strichstärken in 1/100 mm
_LINEWEIGHTS = [0, 5, 9, 13, 15, 18, 20, 25, 30, 35, 40, 50, 53, 60, 70, 80, 90, 100, 106, 120,
                140, 158, 200, 211]


def _lineweight(mm: float) -> int:
    if not mm or mm <= 0:
        return -1  # BYLAYER
    v = mm * 100
    return min(_LINEWEIGHTS, key=lambda w: abs(w - v))


def _attribs(e, version: str) -> dict:
    a = {"layer": e.layer}
    lt = getattr(e, "linetype", "CONTINUOUS") or "CONTINUOUS"
    if lt != "CONTINUOUS":
        a["linetype"] = lt
    if version != "R12":
        lw = _lineweight(getattr(e, "lineweight", 0.0))
        if lw >= 0:
            a["lineweight"] = lw
        col = getattr(e, "color", None)
        if col:
            a["true_color"] = ezcolors.rgb2int(tuple(int(c) for c in col))
    return a


def block_name(name: str) -> str:
    """DXF-taugliche Blocknamen (keine Sonderzeichen, Umlaute umschreiben)."""
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "AE"), ("Ö", "OE"), ("Ü", "UE"),
                 ("ß", "ss")):
        name = name.replace(a, b)
    return (re.sub(r"[^A-Za-z0-9_\-]+", "_", name).strip("_") or "SYMBOL")[:31]


def _add(layout, e, P, s: float, version: str, layer_override=None) -> None:
    """Fügt ein Objekt hinzu. P: Bildkoordinate -> CAD-Koordinate, s: mm pro Pixel."""
    attrs = _attribs(e, version)
    if layer_override is not None:
        attrs["layer"] = layer_override
    if isinstance(e, Line):
        layout.add_line(P(e.p1), P(e.p2), dxfattribs=attrs)
    elif isinstance(e, Circle):
        layout.add_circle(P(e.center), e.radius * s, dxfattribs=attrs)
    elif isinstance(e, Arc):
        # y-Spiegelung kehrt die Drehrichtung um
        layout.add_arc(P(e.center), e.radius * s, start_angle=(-e.end_angle) % 360,
                       end_angle=(-e.start_angle) % 360, dxfattribs=attrs)
    elif isinstance(e, Polyline):
        pts = [P(p) for p in e.points]
        if version == "R12":
            layout.add_polyline2d(pts, close=e.closed, dxfattribs=attrs)
        else:
            layout.add_lwpolyline(pts, close=e.closed, dxfattribs=attrs)
    elif isinstance(e, Text):
        attrs.pop("linetype", None)
        t = layout.add_text(e.text, height=max(e.height * s, 0.01), rotation=e.angle,
                            dxfattribs=attrs)
        t.set_placement(P(e.position))


def export_dxf(d: Drawing, path: str, version: str = "R2010",
               visible_layers=None) -> None:
    d = d.export_view()          # Schräglage des Scans herausdrehen
    version = DXF_VERSIONS.get(version, "R2010")
    doc = ezdxf.new(version, setup=True)
    doc.units = units.MM
    if version != "R12":
        doc.header["$LWDISPLAY"] = 1
    msp = doc.modelspace()

    s = d.scale
    all_ents = list(d.entities) + [e for v in d.blocks.values() for e in v]
    for e in all_ents:
        lt = getattr(e, "linetype", "CONTINUOUS")
        if lt and lt not in doc.linetypes:
            e.linetype = "CONTINUOUS"   # unbekannter Linientyp: durchgezogen
    # Blöcke (Symbole): Geometrie relativ zum Einfügepunkt, Layer 0 (erbt vom Verweis)
    used = {e.name for e in d.entities if isinstance(e, Insert)}
    for name in sorted(used):
        blk = doc.blocks.new(block_name(name))
        for e in d.blocks.get(name, []):
            _add(blk, e, lambda p: (p[0] * s, -p[1] * s), s, version, layer_override="0")

    for name in sorted({e.layer for e in d.entities}):
        if name not in doc.layers:
            doc.layers.add(name, color=layer_color(name)[0])

    if d.meta:
        doc.header["$PROJECTNAME"] = d.meta.get("massstab", "")[:60] if version != "R12" else ""
    for e in d.entities:
        if visible_layers is not None and e.layer not in visible_layers:
            continue
        if isinstance(e, Insert):
            msp.add_blockref(block_name(e.name), d.to_mm(e.position),
                             dxfattribs={"layer": e.layer, "rotation": e.rotation,
                                         "xscale": e.scale, "yscale": e.scale})
            continue
        _add(msp, e, d.to_mm, s, version)
    doc.saveas(path)
