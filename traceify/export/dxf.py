"""DXF-Export mit ezdxf (Layer, Linien, Bögen, Kreise, Polylinien, Texte)."""
from __future__ import annotations

import ezdxf
from ezdxf import units

from ..core.model import (Arc, Circle, Drawing, LAYER_COLORS, Line, Polyline,
                          Text)

DXF_VERSIONS = {"R12": "R12", "R2000": "R2000", "R2007": "R2007", "R2010": "R2010",
                "R2013": "R2013", "R2018": "R2018"}


def export_dxf(d: Drawing, path: str, version: str = "R2010",
               visible_layers=None) -> None:
    doc = ezdxf.new(DXF_VERSIONS.get(version, "R2010"), setup=True)
    doc.units = units.MM
    msp = doc.modelspace()

    for name, (aci, _rgb) in LAYER_COLORS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=aci)

    s = d.scale
    for e in d.entities:
        if visible_layers is not None and e.layer not in visible_layers:
            continue
        attrs = {"layer": e.layer}
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
            t = msp.add_text(e.text, height=e.height * s,
                             rotation=e.angle, dxfattribs=attrs)
            t.set_placement(d.to_mm(e.position))
    doc.saveas(path)
