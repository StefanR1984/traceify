"""DXF-Export mit ezdxf (Layer, Linien, Bögen, Kreise, Polylinien, Texte).

Farbe, Linientyp und Strichstärke einzelner Objekte werden übernommen.
"""
from __future__ import annotations

import ezdxf
from ezdxf import colors as ezcolors
from ezdxf import units

from ..core.model import Arc, Circle, Drawing, Line, Polyline, Text, layer_color

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


def export_dxf(d: Drawing, path: str, version: str = "R2010",
               visible_layers=None) -> None:
    version = DXF_VERSIONS.get(version, "R2010")
    doc = ezdxf.new(version, setup=True)
    doc.units = units.MM
    if version != "R12":
        doc.header["$LWDISPLAY"] = 1
    msp = doc.modelspace()

    for name in sorted({e.layer for e in d.entities}):
        if name not in doc.layers:
            doc.layers.add(name, color=layer_color(name)[0])
    for lt in sorted({getattr(e, "linetype", "CONTINUOUS") for e in d.entities}):
        if lt and lt not in doc.linetypes:
            # unbekannter Linientyp: auf durchgezogen zurückfallen
            for e in d.entities:
                if getattr(e, "linetype", None) == lt:
                    e.linetype = "CONTINUOUS"

    s = d.scale
    if d.meta:
        doc.header["$PROJECTNAME"] = d.meta.get("massstab", "")[:60] if version != "R12" else ""
    for e in d.entities:
        if visible_layers is not None and e.layer not in visible_layers:
            continue
        attrs = _attribs(e, version)
        if isinstance(e, Line):
            msp.add_line(d.to_mm(e.p1), d.to_mm(e.p2), dxfattribs=attrs)
        elif isinstance(e, Circle):
            msp.add_circle(d.to_mm(e.center), e.radius * s, dxfattribs=attrs)
        elif isinstance(e, Arc):
            # y-Spiegelung kehrt die Drehrichtung um
            msp.add_arc(d.to_mm(e.center), e.radius * s,
                        start_angle=(-e.end_angle) % 360,
                        end_angle=(-e.start_angle) % 360, dxfattribs=attrs)
        elif isinstance(e, Polyline):
            pts = [d.to_mm(p) for p in e.points]
            if version == "R12":
                msp.add_polyline2d(pts, close=e.closed, dxfattribs=attrs)
            else:
                msp.add_lwpolyline(pts, close=e.closed, dxfattribs=attrs)
        elif isinstance(e, Text):
            attrs.pop("linetype", None)
            t = msp.add_text(e.text, height=max(e.height * s, 0.01),
                             rotation=e.angle, dxfattribs=attrs)
            t.set_placement(d.to_mm(e.position))
    doc.saveas(path)
