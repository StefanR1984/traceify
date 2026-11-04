"""Exporter: DXF, DWG (über ODA File Converter), SVG, G-Code."""
import os

from .dwg import export_dwg
from .dxf import export_dxf
from .gcode import GcodeSettings, export_gcode
from .svg import export_svg

__all__ = ["FORMATS", "GcodeSettings", "export", "export_dwg", "export_dxf", "export_gcode",
           "export_svg"]

FORMATS = {".dxf": "DXF", ".dwg": "DWG", ".svg": "SVG", ".nc": "G-Code", ".gcode": "G-Code",
           ".tap": "G-Code"}


def export(drawing, path, gcode_settings=None, dxf_version="R2010", visible_layers=None):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".dxf":
        export_dxf(drawing, path, dxf_version, visible_layers)
    elif ext == ".dwg":
        export_dwg(drawing, path, dxf_version, visible_layers)
    elif ext == ".svg":
        export_svg(drawing, path, visible_layers)
    elif ext in (".nc", ".gcode", ".tap", ".ngc"):
        export_gcode(drawing, path, gcode_settings or GcodeSettings(), visible_layers)
    else:
        raise ValueError(f"Unbekanntes Exportformat: {ext}")
