"""Prüfstand: Ergebnisse an echten Scans messen und mit anderen Programmen vergleichen.

Für jede Zeichnung werden dieselben Kennzahlen erhoben – egal, ob die Vektoren von
Traceify stammen oder aus der DXF-Datei eines anderen Vektorisierungsprogramms:

* Abdeckung / Genauigkeit – wie in der Qualitätsampel (Vektoren gegen die Scan-Tinte),
  aber ohne Strichstärken, damit alle Programme gleich behandelt werden
* Objekte je Art und „Splitter“ (Linien kürzer als 1 mm auf dem Papier) – je weniger
  Objekte bei gleicher Abdeckung, desto sauberer lässt sich die Zeichnung im CAD bearbeiten
* Linienqualität: Anteil exakt waagrechter/senkrechter Linien (bei Plänen ein Zeichen für
  saubere Geometrie) und offene Enden (Linienenden ohne Anschluss an ein anderes Objekt)
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
    ortho: float = 0.0          # Anteil Linien (nach Länge), die auf 0,5° waagrecht/senkrecht sind
    free_ends: int = 0          # Linienenden ohne Anschluss
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
            text_boxes=None, seconds: float = 0.0, export_ents=None) -> Metrics:
    """Kennzahlen für Objekte in Bildkoordinaten (ink: 255 = Tinte des Scans).

    export_ents: dieselben Objekte so, wie sie exportiert werden (Schräglage herausgedreht)
    – für den Ortho-Anteil."""
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
    exp = [e for e in (export_ents if export_ents is not None else geo)
           if not isinstance(e, (Text, Insert))]
    m.ortho = round(ortho_share(exp), 4)
    m.free_ends = free_ends(geo, tol=max(2.0, 0.3 / mm_per_px if mm_per_px > 0 else 2.0))
    boxes = list(text_boxes or [])
    if not boxes:   # fremde Ergebnisse: Textbereiche grob aus Lage und Höhe schätzen
        boxes = [text_box(t) for t in texts]
    # Strichstärken bewusst nicht einrechnen: andere Programme liefern meist keine, der
    # Vergleich soll nur die Geometrie bewerten (gleiche Bedingungen für alle)
    q = assess(ink, geo, mm_per_px=0.0, extra_boxes=boxes)
    m.coverage, m.precision, m.rating = round(q.coverage, 4), round(q.precision, 4), q.rating
    m.words = sorted(words(texts))
    return m


def ortho_share(ents, tol_deg: float = 0.5) -> float:
    """Anteil der Linienlänge, der exakt (± tol_deg) waagrecht oder senkrecht verläuft."""
    tot = ok = 0.0
    for e in ents:
        segs = []
        if isinstance(e, Line):
            segs = [(e.p1, e.p2)]
        elif isinstance(e, Polyline):
            segs = list(zip(e.points, e.points[1:]))
        for a, b in segs:
            L = math.dist(a, b)
            if L < 1e-9:
                continue
            ang = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 90.0
            tot += L
            if min(ang, 90.0 - ang) <= tol_deg:
                ok += L
    return ok / tot if tot else 0.0


def free_ends(ents, tol: float = 2.0) -> int:
    """Zahl der Enden (Linien, offene Polylinien, Bögen), die kein anderes Objekt berühren."""
    from .cad import closest_on_circ, closest_on_seg, primitives, Seg, _arc_point
    prims = [(pr, e) for e in ents for pr in primitives(e)]
    cell = 64.0
    grid = {}
    for k, (pr, _) in enumerate(prims):
        if isinstance(pr, Seg):
            xs, ys = (pr.a[0], pr.b[0]), (pr.a[1], pr.b[1])
        else:
            xs, ys = (pr.c[0] - pr.r, pr.c[0] + pr.r), (pr.c[1] - pr.r, pr.c[1] + pr.r)
        for gx in range(int((min(xs) - tol) // cell), int((max(xs) + tol) // cell) + 1):
            for gy in range(int((min(ys) - tol) // cell), int((max(ys) + tol) // cell) + 1):
                grid.setdefault((gx, gy), []).append(k)
    ends = []
    for e in ents:
        if isinstance(e, Line):
            ends += [(e.p1, e), (e.p2, e)]
        elif isinstance(e, Polyline) and not e.closed and e.points:
            ends += [(e.points[0], e), (e.points[-1], e)]
        elif isinstance(e, Arc):
            for pr in primitives(e):
                ends += [(_arc_point(pr, pr.a0), e), (_arc_point(pr, pr.a1), e)]
    n = 0
    for p, owner in ends:
        hit = False
        for k in grid.get((int(p[0] // cell), int(p[1] // cell)), ()):
            pr, src = prims[k]
            if src is owner:
                continue
            q = closest_on_seg(pr.a, pr.b, p) if isinstance(pr, Seg) else closest_on_circ(pr, p)
            if math.dist(p, q) <= tol:
                hit = True
                break
        n += not hit
    return n


def text_box(t: Text, pad: float = 0.0):
    """Achsparallele Bildbox (x, y, w, h) um einen Text beliebiger Drehung (geschätzt).

    pad: zusätzlicher Rand in Schrifthöhen (die Breite ist nur geschätzt)."""
    h = t.height / 0.8
    L = max(1, len(t.text)) * h * 0.7
    a = math.radians(t.angle)
    x, y = t.position
    pts = [(x, y), (x + L * math.cos(a), y - L * math.sin(a)),
           (x - h * math.sin(a), y - h * math.cos(a)),
           (x + L * math.cos(a) - h * math.sin(a), y - L * math.sin(a) - h * math.cos(a))]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    q = pad * h
    return (int(min(xs) - q), int(min(ys) - q), int(max(xs) - min(xs) + 2 * q) + 1,
            int(max(ys) - min(ys) + 2 * q) + 1)


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
    mine = measure("Traceify", d.expanded(), ink, mm_px, res.text_boxes, dt,
                   export_ents=d.export_view().expanded())
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
