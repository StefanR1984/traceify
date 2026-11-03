"""G-Code-Export für CNC-Fräsen, Laser und Plasma.

Linien werden zu zusammenhängenden Wegen verkettet, die Reihenfolge der Wege
wird per Nächster-Nachbar-Heuristik optimiert, Bögen und Kreise werden als
echte G2/G3-Bögen ausgegeben. Bei Fräsen sind mehrere Zustellungen möglich.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

from ..core.model import Arc, Circle, Drawing, Line, Polyline, Text

MACHINE_MILL = "fraese"
MACHINE_LASER = "laser"


@dataclass
class GcodeSettings:
    machine: str = MACHINE_MILL
    feed_rate: float = 800.0       # mm/min
    plunge_rate: float = 200.0     # mm/min
    spindle_speed: int = 12000     # U/min bzw. Laserleistung (S-Wert)
    safe_z: float = 5.0            # mm
    cut_depth: float = 1.0         # Gesamttiefe mm (positiv)
    step_down: float = 0.5         # Zustellung pro Durchgang mm
    optimize_order: bool = True
    include_text: bool = False     # Texte werden nicht gefräst (Hinweis im Kopf)
    decimals: int = 3


# Ein Weg ist eine Liste von Segmenten: ("L", x, y) oder ("A", x, y, i, j, cw)
Seg = tuple


def _fmt(v: float, n: int) -> str:
    s = f"{v:.{n}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _chain_lines(lines: List[Tuple[Tuple[float, float], Tuple[float, float]]], tol=1e-3):
    """Verkettet Linien mit gemeinsamen Endpunkten zu Polylinien."""
    key = lambda p: (round(p[0] / tol), round(p[1] / tol))
    remaining = list(lines)
    idx = {}
    for i, (a, b) in enumerate(remaining):
        idx.setdefault(key(a), []).append(i)
        idx.setdefault(key(b), []).append(i)
    used = [False] * len(remaining)
    chains = []
    for i in range(len(remaining)):
        if used[i]:
            continue
        used[i] = True
        a, b = remaining[i]
        chain = [a, b]
        for direction in (1, 0):  # nach hinten, dann nach vorne verlängern
            while True:
                end = chain[-1] if direction else chain[0]
                nxt = None
                for j in idx.get(key(end), []):
                    if not used[j]:
                        nxt = j
                        break
                if nxt is None:
                    break
                used[nxt] = True
                p, q = remaining[nxt]
                other = q if key(p) == key(end) else p
                if direction:
                    chain.append(other)
                else:
                    chain.insert(0, other)
        chains.append(chain)
    return chains


def build_paths(d: Drawing, s: GcodeSettings, visible_layers=None):
    """Erzeugt Werkzeugwege in mm: Liste von (Startpunkt, [Segmente])."""
    paths = []
    lines = []
    for e in d.entities:
        if visible_layers is not None and e.layer not in visible_layers:
            continue
        if isinstance(e, Line):
            lines.append((d.to_mm(e.p1), d.to_mm(e.p2)))
        elif isinstance(e, Polyline):
            pts = [d.to_mm(p) for p in e.points]
            if e.closed:
                pts.append(pts[0])
            paths.append((pts[0], [("L", x, y) for x, y in pts[1:]]))
        elif isinstance(e, Circle):
            c = d.to_mm(e.center)
            r = e.radius * d.scale
            start = (c[0] + r, c[1])
            paths.append((start, [("A", start[0], start[1], -r, 0.0, False)]))
        elif isinstance(e, Arc):
            c = d.to_mm(e.center)
            r = e.radius * d.scale
            a0 = math.radians(-e.end_angle)   # CAD-Winkel (gegen Uhrzeigersinn)
            a1 = math.radians(-e.start_angle)
            p0 = (c[0] + r * math.cos(a0), c[1] + r * math.sin(a0))
            p1 = (c[0] + r * math.cos(a1), c[1] + r * math.sin(a1))
            paths.append((p0, [("A", p1[0], p1[1], c[0] - p0[0], c[1] - p0[1], False)]))
    for chain in _chain_lines(lines):
        paths.append((chain[0], [("L", x, y) for x, y in chain[1:]]))
    paths = [_dedupe(p) for p in paths]
    paths = [p for p in paths if p[1]]
    if s.optimize_order:
        paths = _order(paths)
    return paths


def _dedupe(path, tol=1e-4):
    start, segs = path
    out, cur = [], start
    for seg in segs:
        if seg[0] == "L" and math.dist(cur, (seg[1], seg[2])) < tol:
            continue
        out.append(seg)
        cur = (seg[1], seg[2])
    return start, out


def _end(path):
    seg = path[1][-1]
    return (seg[1], seg[2])


def _order(paths):
    if not paths:
        return paths
    rest = list(paths)
    out = []
    pos = (0.0, 0.0)
    while rest:
        i = min(range(len(rest)), key=lambda k: math.dist(pos, rest[k][0]))
        p = rest.pop(i)
        out.append(p)
        pos = _end(p)
    return out


def generate_gcode(d: Drawing, s: GcodeSettings, visible_layers=None) -> str:
    n = s.decimals
    f = lambda v: _fmt(v, n)
    paths = build_paths(d, s, visible_layers)
    mill = s.machine == MACHINE_MILL
    texts = sum(1 for e in d.entities if isinstance(e, Text))

    g = ["%", "(Erzeugt mit Traceify)", f"(Quelle: {d.source or '-'})",
         f"(Maschine: {'Fraese' if mill else 'Laser/Plasma'})",
         f"(Wege: {len(paths)})"]
    if texts and not s.include_text:
        g.append(f"({texts} Texte nicht enthalten - nur als CAD-Text verfuegbar)")
    g += ["G21 (mm)", "G90 (absolut)", "G17 (XY-Ebene)", "G94"]
    if mill:
        g += [f"G0 Z{f(s.safe_z)}", f"S{s.spindle_speed} M3", "G4 P2"]
    else:
        g += ["M5", f"S{s.spindle_speed}"]

    depths = [0.0]
    if mill:
        depth, step = abs(s.cut_depth), max(0.01, abs(s.step_down))
        depths = []
        z = 0.0
        while z < depth - 1e-9:
            z = min(depth, z + step)
            depths.append(-z)

    for start, segs in paths:
        for z in depths:
            g.append(f"G0 X{f(start[0])} Y{f(start[1])}")
            if mill:
                g.append(f"G1 Z{f(z)} F{f(s.plunge_rate)}")
            else:
                g.append("M3")
            first = True
            for seg in segs:
                feed = f" F{f(s.feed_rate)}" if first else ""
                first = False
                if seg[0] == "L":
                    g.append(f"G1 X{f(seg[1])} Y{f(seg[2])}{feed}")
                else:
                    _, x, y, i, j, cw = seg
                    g.append(f"{'G2' if cw else 'G3'} X{f(x)} Y{f(y)} I{f(i)} J{f(j)}{feed}")
            if mill:
                g.append(f"G0 Z{f(s.safe_z)}")
            else:
                g.append("M5")
    g += ["M5", "G0 X0 Y0", "M30", "%"]
    return "\n".join(g) + "\n"


def export_gcode(d: Drawing, path: str, s: GcodeSettings, visible_layers=None) -> None:
    with open(path, "w", encoding="ascii", errors="replace") as fh:
        fh.write(generate_gcode(d, s, visible_layers))
