"""Prüfstand: Ergebnisse an echten Scans messen und mit anderen Programmen vergleichen.

Für jede Zeichnung werden dieselben Kennzahlen erhoben – egal, ob die Vektoren von
Traceify stammen oder aus einer DXF-Datei eines anderen Programms (z. B. Scan2CAD):

* Abdeckung / Genauigkeit – wie in der Qualitätsampel (Vektoren gegen die Scan-Tinte),
  aber ohne Strichstärken, damit alle Programme gleich behandelt werden
* Objekte je Art und „Splitter“ (Linien kürzer als 1 mm auf dem Papier) – je weniger
  Objekte bei gleicher Abdeckung, desto sauberer lässt sich die Zeichnung im CAD bearbeiten
* Texte und Wort-Übereinstimmung zwischen beiden Ergebnissen
"""
from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

import numpy as np

from .model import Arc, Circle, Insert, Line, Polyline, Text
from .quality import assess

_TOK = re.compile(r"[A-Za-zÄÖÜäöüß]{3,}|\d+(?:[.,]\d+)?")


def words(texts) -> set:
    """Vergleichbare Wörter: Buchstabenfolgen ab 3 Zeichen und Zahlen, klein geschrieben."""
    out = set()
    for t in texts:
        s = t.text if isinstance(t, Text) else str(t)
        out |= {w.lower().replace(",", ".") for w in _TOK.findall(s)}
    return out


@dataclass
class Metrics:
    name: str
    objects: int = 0
    lines: int = 0
    arcs: int = 0
    circles: int = 0
    polylines: int = 0
    texts: int = 0
    splinters: int = 0          # Linien < 1 mm (Papier)
    coverage: float = 0.0
    precision: float = 0.0
    rating: str = ""
    seconds: float = 0.0
    words: List[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = asdict(self)
        d.pop("words")
        return d


def measure(name: str, ents: list, ink: np.ndarray, mm_per_px: float,
            text_boxes=None, seconds: float = 0.0) -> Metrics:
    """Kennzahlen für Objekte in Bildkoordinaten (ink: 255 = Tinte des Scans)."""
    geo = [e for e in ents if not isinstance(e, (Text, Insert))]
    texts = [e for e in ents if isinstance(e, Text)]
    min_len = 1.0 / mm_per_px if mm_per_px > 0 else 0.0
    m = Metrics(name, seconds=round(seconds, 1))
    m.lines = sum(isinstance(e, Line) for e in geo)
    m.arcs = sum(isinstance(e, Arc) for e in geo)
    m.circles = sum(isinstance(e, Circle) for e in geo)
    m.polylines = sum(isinstance(e, Polyline) for e in geo)
    m.texts = len(texts)
    m.objects = len(geo) + len(texts)
    m.splinters = sum(1 for e in geo if isinstance(e, Line) and math.dist(e.p1, e.p2) < min_len)
    boxes = list(text_boxes or [])
    if not boxes:   # fremde Ergebnisse: Textbereiche grob aus Lage und Höhe schätzen
        boxes = [_text_box(t) for t in texts]
    # Strichstärken bewusst nicht einrechnen: andere Programme liefern meist keine, der
    # Vergleich soll nur die Geometrie bewerten (gleiche Bedingungen für alle)
    q = assess(ink, geo, mm_per_px=0.0, extra_boxes=boxes)
    m.coverage, m.precision, m.rating = round(q.coverage, 4), round(q.precision, 4), q.rating
    m.words = sorted(words(texts))
    return m


def _text_box(t: Text):
    h = t.height / 0.8
    L = max(1, len(t.text)) * h * 0.6
    a = math.radians(t.angle)
    x, y = t.position
    pts = [(x, y), (x + L * math.cos(a), y - L * math.sin(a)),
           (x - h * math.sin(a), y - h * math.cos(a)),
           (x + L * math.cos(a) - h * math.sin(a), y - L * math.sin(a) - h * math.cos(a))]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return (int(min(xs)), int(min(ys)), int(max(xs) - min(xs)) + 1, int(max(ys) - min(ys)) + 1)


def word_overlap(a: Metrics, ref: Metrics) -> Dict[str, object]:
    """Wie viele Wörter des Vergleichsergebnisses findet auch dieses Ergebnis?"""
    A, R = set(a.words), set(ref.words)
    return {"gemeinsam": len(A & R), "nur_hier": len(A - R), "nur_vergleich": len(R - A),
            "anteil": round(len(A & R) / len(R), 3) if R else None}


def run_file(path: str, settings=None, page: int = 0, reference: Optional[str] = None,
             ref_name: str = "Vergleich", progress=None) -> dict:
    """Konvertiert eine Datei mit Traceify und misst; optional Vergleich mit einer DXF."""
    import time

    from ..api import open_file
    from . import loader
    from .dxf_import import fit_to_image, read_dxf
    from .preprocess import to_binary

    t0 = time.time()
    res = open_file(path, page, settings, progress=progress)
    dt = time.time() - t0
    d = res.drawing
    gray, mm_px = loader.load(path, page, 0)
    ink = res.binary if res.binary is not None and res.binary.any() else \
        to_binary(gray, settings.preprocess if settings else _pp())
    mine = measure("Traceify", d.expanded(), ink, mm_px, res.text_boxes, dt)
    out = {"datei": path, "bild": [int(ink.shape[1]), int(ink.shape[0])],
           "mm_pro_px": mm_px, "traceify": mine}
    if reference:
        ents, (s, dx, dy) = fit_to_image(read_dxf(reference), ink)
        ref = measure(ref_name, ents, ink, mm_px)
        out["vergleich"] = ref
        out["lage"] = {"massstab": round(s, 5), "dx": round(dx, 1), "dy": round(dy, 1)}
        out["woerter"] = word_overlap(mine, ref)
    return out


def _pp():
    from .preprocess import PreprocessSettings
    return PreprocessSettings()
