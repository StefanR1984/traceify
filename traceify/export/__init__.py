"""Exporter: DXF, SVG, G-Code."""
import os

from .dxf import export_dxf
from .gcode import GcodeSettings, export_gcode
from .svg import export_svg

FORMATS = {".dxf": "DXF", ".svg": "SVG", ".nc": "G-Code", ".gcode": "G-Code", ".tap": "G-Code"}


def export(drawing, path, gcode_settings=None, dxf_version="R2010", visible_layers=None):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".dxf":
        export_dxf(drawing, path, dxf_version, visible_layers)
    elif ext == ".svg":
        export_svg(drawing, path, visible_layers)
    elif ext in (".nc", ".gcode", ".tap", ".ngc"):
        export_gcode(drawing, path, gcode_settings or GcodeSettings(), visible_layers)
    else:
        raise ValueError(f"Unbekanntes Exportformat: {ext}")
