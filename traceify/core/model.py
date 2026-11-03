"""Datenmodell für vektorisierte Zeichnungen.

Koordinaten sind in Pixeln des Quellbildes (Ursprung oben links, y nach unten).
Beim Export werden sie über `Drawing.scale` (mm pro Pixel) in Millimeter
umgerechnet und die y-Achse wird gespiegelt (CAD: y nach oben).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

Point = Tuple[float, float]

# Standard-Layer – entsprechen den Layern im DXF-Export
LAYER_LINES = "LINIEN"
LAYER_ARCS = "BOEGEN"
LAYER_CIRCLES = "KREISE"
LAYER_POLY = "POLYLINIEN"
LAYER_CONTOURS = "KONTUREN"
LAYER_TEXT = "TEXT"

LAYER_COLORS = {  # AutoCAD Color Index + RGB für die GUI
    LAYER_LINES: (7, (30, 30, 30)),
    LAYER_ARCS: (1, (220, 50, 50)),
    LAYER_CIRCLES: (5, (40, 90, 230)),
    LAYER_POLY: (3, (20, 160, 60)),
    LAYER_CONTOURS: (6, (190, 40, 190)),
    LAYER_TEXT: (2, (200, 140, 0)),
}


@dataclass
class Line:
    p1: Point
    p2: Point
    layer: str = LAYER_LINES


@dataclass
class Arc:
    center: Point
    radius: float
    start_angle: float  # Grad, im Bildkoordinatensystem (y nach unten)
    end_angle: float
    layer: str = LAYER_ARCS


@dataclass
class Circle:
    center: Point
    radius: float
    layer: str = LAYER_CIRCLES


@dataclass
class Polyline:
    points: List[Point]
    closed: bool = False
    layer: str = LAYER_POLY


@dataclass
class Text:
    text: str
    position: Point  # unten links
    height: float
    angle: float = 0.0
    layer: str = LAYER_TEXT


@dataclass
class Drawing:
    width: int
    height: int
    scale: float = 1.0  # mm pro Pixel
    entities: list = field(default_factory=list)
    source: str = ""

    def by_type(self, cls):
        return [e for e in self.entities if isinstance(e, cls)]

    def layers(self):
        return sorted({e.layer for e in self.entities})

    def stats(self) -> dict:
        return {
            "Linien": len(self.by_type(Line)),
            "Bögen": len(self.by_type(Arc)),
            "Kreise": len(self.by_type(Circle)),
            "Polylinien": len(self.by_type(Polyline)),
            "Texte": len(self.by_type(Text)),
        }

    def to_mm(self, p: Point) -> Point:
        """Bildkoordinate -> CAD-Koordinate in mm (y gespiegelt)."""
        return (p[0] * self.scale, (self.height - p[1]) * self.scale)
