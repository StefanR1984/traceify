"""Datenmodell für vektorisierte Zeichnungen.

Koordinaten sind in Pixeln des Quellbildes (Ursprung oben links, y nach unten).
Beim Export werden sie über `Drawing.scale` (mm pro Pixel) in Millimeter
umgerechnet und die y-Achse wird gespiegelt (CAD: y nach oben).

Jedes Objekt kann zusätzlich eine eigene Farbe (RGB), einen Linientyp
("CONTINUOUS", "DASHED", …) und eine Strichstärke (mm) tragen.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

Point = Tuple[float, float]
RGB = Tuple[int, int, int]

# Standard-Layer – entsprechen den Layern im DXF-Export
LAYER_LINES = "LINIEN"
LAYER_ARCS = "BOEGEN"
LAYER_CIRCLES = "KREISE"
LAYER_POLY = "POLYLINIEN"
LAYER_CONTOURS = "KONTUREN"
LAYER_TEXT = "TEXT"
LAYER_FILL = "FLAECHEN"
LAYER_DASHED = "STRICHLINIEN"
LAYER_THICK = "DICKE_LINIEN"
LAYER_SYMBOLS = "SYMBOLE"

LAYER_COLORS = {  # AutoCAD Color Index + RGB für die GUI
    LAYER_LINES: (7, (30, 30, 30)),
    LAYER_ARCS: (1, (220, 50, 50)),
    LAYER_CIRCLES: (5, (40, 90, 230)),
    LAYER_POLY: (3, (20, 160, 60)),
    LAYER_CONTOURS: (6, (190, 40, 190)),
    LAYER_TEXT: (2, (200, 140, 0)),
    LAYER_FILL: (8, (130, 130, 130)),
    LAYER_DASHED: (4, (0, 150, 170)),
    LAYER_THICK: (250, (0, 0, 0)),
    LAYER_SYMBOLS: (30, (215, 110, 0)),
}

LINETYPES = ("CONTINUOUS", "DASHED", "DASHDOT", "DOT", "CENTER", "HIDDEN")


def layer_color(layer: str) -> Tuple[int, RGB]:
    """(ACI, RGB) für einen Layer – auch für dynamische Layer wie FARBE_1_ROT."""
    if layer in LAYER_COLORS:
        return LAYER_COLORS[layer]
    h = int(hashlib.md5(layer.encode()).hexdigest()[:6], 16)
    rgb = ((h >> 16) & 0xFF, (h >> 8) & 0xFF, h & 0xFF)
    rgb = tuple(int(40 + c * 0.6) for c in rgb)
    return 7, rgb


@dataclass
class Line:
    p1: Point
    p2: Point
    layer: str = LAYER_LINES
    color: Optional[RGB] = None
    linetype: str = "CONTINUOUS"
    lineweight: float = 0.0  # mm, 0 = Standard


@dataclass
class Arc:
    center: Point
    radius: float
    start_angle: float  # Grad, im Bildkoordinatensystem (y nach unten)
    end_angle: float
    layer: str = LAYER_ARCS
    color: Optional[RGB] = None
    linetype: str = "CONTINUOUS"
    lineweight: float = 0.0


@dataclass
class Circle:
    center: Point
    radius: float
    layer: str = LAYER_CIRCLES
    color: Optional[RGB] = None
    linetype: str = "CONTINUOUS"
    lineweight: float = 0.0


@dataclass
class Polyline:
    points: List[Point]
    closed: bool = False
    layer: str = LAYER_POLY
    color: Optional[RGB] = None
    linetype: str = "CONTINUOUS"
    lineweight: float = 0.0


@dataclass
class Text:
    text: str
    position: Point  # unten links (Grundlinie)
    height: float
    angle: float = 0.0  # Grad, gegen den Uhrzeigersinn (CAD)
    layer: str = LAYER_TEXT
    color: Optional[RGB] = None
    linetype: str = "CONTINUOUS"
    lineweight: float = 0.0


@dataclass
class Insert:
    """Eingefügtes Symbol (CAD-Block). Geometrie steht in Drawing.blocks[name]."""
    name: str
    position: Point            # Einfügepunkt (Bildkoordinaten) = Mitte der Vorlage
    rotation: float = 0.0      # Grad, gegen den Uhrzeigersinn (CAD)
    scale: float = 1.0
    layer: str = LAYER_SYMBOLS
    color: Optional[RGB] = None
    linetype: str = "CONTINUOUS"
    lineweight: float = 0.0


@dataclass
class Drawing:
    width: int
    height: int
    scale: float = 1.0  # mm pro Pixel
    entities: list = field(default_factory=list)
    source: str = ""
    meta: Dict[str, str] = field(default_factory=dict)
    blocks: Dict[str, list] = field(default_factory=dict)  # Name -> Objekte relativ zu (0,0)

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
            "Symbole": len(self.by_type(Insert)),
        }

    def symbol_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for e in self.by_type(Insert):
            out[e.name] = out.get(e.name, 0) + 1
        return dict(sorted(out.items(), key=lambda kv: (-kv[1], kv[0])))

    def expanded(self) -> list:
        """Alle Objekte, eingefügte Symbole in Einzelobjekte aufgelöst (für SVG, G-Code, Prüfung)."""
        if not any(isinstance(e, Insert) for e in self.entities):
            return list(self.entities)
        from .symbols import explode_insert
        out = []
        for e in self.entities:
            if isinstance(e, Insert):
                out += explode_insert(self, e)
            else:
                out.append(e)
        return out

    def to_mm(self, p: Point) -> Point:
        """Bildkoordinate -> CAD-Koordinate in mm (y gespiegelt)."""
        return (p[0] * self.scale, (self.height - p[1]) * self.scale)
