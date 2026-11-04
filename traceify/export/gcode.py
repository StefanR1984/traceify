"""G-Code für CNC-Fräsen, Laser und Plasma.

Ablauf:
  1. Werkzeugwege aus der Zeichnung (Linien werden verkettet, Bögen/Kreise bleiben G2/G3)
  2. optional Fräserradius-Korrektur (außen / innen / automatisch: Teile ausschneiden)
  3. Reihenfolge optimieren (bei „automatisch“: erst Löcher, dann Außenkonturen)
  4. optional Haltestege: das Teil bleibt über kleine Stege mit der Platte verbunden
  5. Bewegungen erzeugen -> G-Code, Vorschau und Zeitschätzung aus denselben Daten
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..core.model import Arc, Circle, Drawing, Line, Polyline, Text

MACHINE_MILL = "fraese"
MACHINE_LASER = "laser"

COMP_NONE, COMP_OUT, COMP_IN, COMP_AUTO = "keine", "aussen", "innen", "auto"
COMP_LABELS = {COMP_NONE: "Keine (Werkzeugmitte auf der Linie)",
               COMP_OUT: "Außen (Kontur bleibt stehen)",
               COMP_IN: "Innen (Tasche/Loch)",
               COMP_AUTO: "Automatisch – Teile ausschneiden"}


@dataclass
class GcodeSettings:
    machine: str = MACHINE_MILL
    feed_rate: float = 800.0       # mm/min
    plunge_rate: float = 200.0     # mm/min
    rapid_rate: float = 3000.0     # mm/min (nur für die Zeitschätzung)
    spindle_speed: int = 12000     # U/min bzw. Laserleistung (S-Wert)
    safe_z: float = 5.0            # mm
    cut_depth: float = 1.0         # Gesamttiefe mm (positiv)
    step_down: float = 0.5         # Zustellung pro Durchgang mm
    optimize_order: bool = True
    include_text: bool = False     # Texte werden nicht gefräst (Hinweis im Kopf)
    decimals: int = 3
    tool_diameter: float = 3.0     # mm (Radiuskorrektur, Haltestege)
    compensation: str = COMP_NONE
    climb: bool = True             # Gleichlauf (bei rechtsdrehender Spindel)
    tabs: int = 0                  # Haltestege je Außenkontur (0 = aus)
    tab_width: float = 4.0         # mm (verbleibendes Material)
    tab_height: float = 1.0        # mm (Fräse) – Laser: Steg = Unterbrechung


# Segment: ("L", x, y) oder ("A", x, y, i, j, cw)  – Koordinaten in mm (CAD, y nach oben)
@dataclass
class ToolPath:
    start: Tuple[float, float]
    segs: list
    closed: bool = False
    kind: str = "mitte"            # mitte | aussen | innen
    depth: int = 0                 # Verschachtelungstiefe (0 = außen)
    tabs: list = field(default_factory=list)   # [(s0, s1)] Bogenlängen-Intervalle


@dataclass
class Move:
    kind: str                      # rapid | plunge | feed | arc | retract | on | off
    x: float
    y: float
    z: float
    i: float = 0.0
    j: float = 0.0
    cw: bool = False
    tab: bool = False


@dataclass
class ToolpathResult:
    paths: List[ToolPath]
    moves: List[Move]
    warnings: List[str]
    cut_length: float = 0.0        # mm
    rapid_length: float = 0.0      # mm
    time_min: float = 0.0
    passes: int = 1


def _fmt(v: float, n: int) -> str:
    s = f"{v:.{n}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# ------------------------------------------------------------------ Wege sammeln
def _chain_lines(lines, tol=1e-3):
    """Verkettet Linien mit gemeinsamen Endpunkten zu Punktfolgen."""
    key = lambda p: (round(p[0] / tol), round(p[1] / tol))  # noqa: E731
    idx = {}
    for i, (a, b) in enumerate(lines):
        idx.setdefault(key(a), []).append(i)
        idx.setdefault(key(b), []).append(i)
    used = [False] * len(lines)
    chains = []
    for i in range(len(lines)):
        if used[i]:
            continue
        used[i] = True
        a, b = lines[i]
        chain = [a, b]
        for forward in (True, False):
            while True:
                end = chain[-1] if forward else chain[0]
                nxt = next((j for j in idx.get(key(end), []) if not used[j]), None)
                if nxt is None:
                    break
                used[nxt] = True
                p, q = lines[nxt]
                other = q if key(p) == key(end) else p
                if forward:
                    chain.append(other)
                else:
                    chain.insert(0, other)
        chains.append(chain)
    return chains


def _circle_path(cx, cy, r, ccw=True) -> ToolPath:
    start = (cx + r, cy)
    return ToolPath(start, [("A", start[0], start[1], -r, 0.0, not ccw)], True)


def _poly_path(pts, closed) -> ToolPath:
    pts = list(pts)
    if closed and math.dist(pts[0], pts[-1]) > 1e-6:
        pts.append(pts[0])
    return ToolPath(pts[0], [("L", x, y) for x, y in pts[1:]], closed)


def collect_paths(d: Drawing, visible_layers=None) -> List[ToolPath]:
    paths, lines = [], []
    for e in d.expanded():
        if visible_layers is not None and e.layer not in visible_layers:
            continue
        if isinstance(e, Line):
            lines.append((d.to_mm(e.p1), d.to_mm(e.p2)))
        elif isinstance(e, Polyline) and len(e.points) > 1:
            paths.append(_poly_path([d.to_mm(p) for p in e.points], e.closed))
        elif isinstance(e, Circle):
            c = d.to_mm(e.center)
            paths.append(_circle_path(c[0], c[1], e.radius * d.scale))
        elif isinstance(e, Arc):
            c = d.to_mm(e.center)
            r = e.radius * d.scale
            a0 = math.radians(-e.end_angle)   # CAD-Winkel (gegen Uhrzeigersinn)
            a1 = math.radians(-e.start_angle)
            p0 = (c[0] + r * math.cos(a0), c[1] + r * math.sin(a0))
            p1 = (c[0] + r * math.cos(a1), c[1] + r * math.sin(a1))
            paths.append(ToolPath(p0, [("A", p1[0], p1[1], c[0] - p0[0], c[1] - p0[1], False)]))
    for chain in _chain_lines(lines):
        closed = len(chain) > 3 and math.dist(chain[0], chain[-1]) < 1e-3
        paths.append(_poly_path(chain, closed))
    out = []
    for p in paths:
        segs, cur = [], p.start
        for sg in p.segs:
            if sg[0] == "L" and math.dist(cur, (sg[1], sg[2])) < 1e-4:
                continue
            segs.append(sg)
            cur = (sg[1], sg[2])
        if segs:
            p.segs = segs
            out.append(p)
    return out


# ------------------------------------------------------------------ Geometrie-Helfer
def _end(p: ToolPath):
    sg = p.segs[-1]
    return (sg[1], sg[2])


def _discretize(p: ToolPath, step_deg: float = 5.0) -> List[Tuple[float, float]]:
    pts = [p.start]
    cur = p.start
    for sg in p.segs:
        if sg[0] == "L":
            pts.append((sg[1], sg[2]))
        else:
            _, x, y, i, j, cw = sg
            cx, cy = cur[0] + i, cur[1] + j
            r = math.hypot(i, j)
            a0 = math.atan2(cur[1] - cy, cur[0] - cx)
            a1 = math.atan2(y - cy, x - cx)
            if cw:
                sweep = (a0 - a1) % (2 * math.pi) or 2 * math.pi
                sweep = -sweep
            else:
                sweep = (a1 - a0) % (2 * math.pi) or 2 * math.pi
            n = max(4, int(abs(math.degrees(sweep)) / step_deg))
            for k in range(1, n + 1):
                a = a0 + sweep * k / n
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
        cur = (sg[1], sg[2])
    return pts


def _signed_area(pts) -> float:
    return 0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(pts, pts[1:] + pts[:1]))


def _circle_of(p: ToolPath):
    if len(p.segs) == 1 and p.segs[0][0] == "A" and p.closed:
        _, x, y, i, j, cw = p.segs[0]
        if math.dist(p.start, (x, y)) < 1e-6:
            return (p.start[0] + i, p.start[1] + j, math.hypot(i, j), cw)
    return None


def _reverse(p: ToolPath) -> ToolPath:
    c = _circle_of(p)
    if c:
        cx, cy, r, cw = c
        q = _circle_path(cx, cy, r, ccw=cw)
        q.kind, q.depth = p.kind, p.depth
        return q
    pts = _discretize(p) if any(sg[0] == "A" for sg in p.segs) else \
        [p.start] + [(sg[1], sg[2]) for sg in p.segs]
    pts = pts[::-1]
    q = _poly_path(pts, p.closed)
    q.kind, q.depth = p.kind, p.depth
    return q


# ------------------------------------------------------------------ Radiuskorrektur
def _nesting(closed: List[ToolPath]):
    from shapely.geometry import Polygon
    polys = []
    for p in closed:
        pts = _discretize(p)
        try:
            poly = Polygon(pts).buffer(0)
        except Exception:
            poly = None
        polys.append(poly)
    depth = []
    for i, pi in enumerate(polys):
        dpt = 0
        if pi is not None and not pi.is_empty:
            rp = pi.representative_point()
            for j, pj in enumerate(polys):
                if i != j and pj is not None and not pj.is_empty and pj.area > pi.area \
                        and pj.contains(rp):
                    dpt += 1
        depth.append(dpt)
    return polys, depth


def compensate(paths: List[ToolPath], s: GcodeSettings, warnings: list) -> List[ToolPath]:
    if s.compensation == COMP_NONE or s.tool_diameter <= 0 or s.machine != MACHINE_MILL:
        return paths
    r = s.tool_diameter / 2
    closed = [p for p in paths if p.closed]
    open_ = [p for p in paths if not p.closed]
    if open_:
        warnings.append(f"{len(open_)} offene Wege ohne Radiuskorrektur (nur geschlossene "
                        "Konturen können korrigiert werden)")
    polys, depth = _nesting(closed)
    out = list(open_)
    skipped = 0
    for p, poly, dpt in zip(closed, polys, depth):
        if s.compensation == COMP_OUT:
            kind = "aussen"
        elif s.compensation == COMP_IN:
            kind = "innen"
        else:
            kind = "aussen" if dpt % 2 == 0 else "innen"
        off = r if kind == "aussen" else -r
        c = _circle_of(p)
        if c:
            cx, cy, rr, _ = c
            if rr + off <= 1e-3:
                skipped += 1
                continue
            q = _circle_path(cx, cy, rr + off)
            q.kind, q.depth = kind, dpt
            out.append(q)
            continue
        if poly is None or poly.is_empty:
            skipped += 1
            continue
        res = poly.buffer(off, quad_segs=8, join_style="round" if off > 0 else "mitre",
                          mitre_limit=4.0)
        geoms = [res] if res.geom_type == "Polygon" else list(getattr(res, "geoms", []))
        geoms = [g for g in geoms if not g.is_empty and g.area > 1e-6]
        if not geoms:
            skipped += 1
            continue
        for g in geoms:
            q = _poly_path(list(g.exterior.coords), True)
            q.kind, q.depth = kind, dpt
            out.append(q)
    if skipped:
        warnings.append(f"{skipped} Kontur(en) zu klein für Ø {s.tool_diameter:g} mm – ausgelassen")
    return out


def orient(paths: List[ToolPath], s: GcodeSettings) -> List[ToolPath]:
    """Fräsrichtung festlegen: Gleichlauf = außen gegen, innen im Uhrzeigersinn (Spindel M3)."""
    out = []
    for p in paths:
        if not p.closed or p.kind == "mitte" or s.machine != MACHINE_MILL:
            out.append(p)
            continue
        pts = _discretize(p)
        ccw = _signed_area(pts[:-1]) > 0
        want_ccw = (p.kind == "aussen") == s.climb
        out.append(p if ccw == want_ccw else _reverse(p))
    return out


# ------------------------------------------------------------------ Reihenfolge
def order(paths: List[ToolPath], s: GcodeSettings) -> List[ToolPath]:
    if not s.optimize_order or not paths:
        return paths
    groups = {}
    for p in paths:
        # tiefer verschachtelte (Löcher) zuerst, damit das Teil bis zuletzt hält
        key = -p.depth if s.compensation == COMP_AUTO else 0
        groups.setdefault(key, []).append(p)
    out, pos = [], (0.0, 0.0)
    for key in sorted(groups):
        rest = list(groups[key])
        while rest:
            i = min(range(len(rest)), key=lambda k: math.dist(pos, rest[k].start))
            p = rest.pop(i)
            out.append(p)
            pos = _end(p)
    return out


# ------------------------------------------------------------------ Haltestege
def _length(pts) -> float:
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def add_tabs(paths: List[ToolPath], s: GcodeSettings) -> List[ToolPath]:
    if s.tabs <= 0:
        return paths
    out = []
    span = s.tab_width + (s.tool_diameter if s.machine == MACHINE_MILL else 0.0)
    for p in paths:
        if not p.closed or p.kind == "innen":
            out.append(p)
            continue
        pts = _discretize(p, 3.0)
        L = _length(pts)
        if L < s.tabs * span * 2.5:
            out.append(p)            # zu kurz für Stege
            continue
        q = _poly_path(pts, True)
        q.kind, q.depth = p.kind, p.depth
        q.tabs = [((k + 0.5) * L / s.tabs - span / 2, (k + 0.5) * L / s.tabs + span / 2)
                  for k in range(s.tabs)]
        out.append(q)
    return out


def _split_tabs(p: ToolPath):
    """Zerlegt einen (Polylinien-)Weg in Stücke [(pts, ist_steg)]."""
    pts = [p.start] + [(sg[1], sg[2]) for sg in p.segs]
    cuts = sorted({max(0.0, t) for ab in p.tabs for t in ab})
    pieces, cur, acc = [], [pts[0]], 0.0

    def in_tab(sv):
        return any(a <= sv <= b for a, b in p.tabs)

    for a, b in zip(pts, pts[1:]):
        seg = math.dist(a, b)
        inner = [c for c in cuts if acc < c < acc + seg]
        for c in inner:
            t = (c - acc) / seg
            m = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
            cur.append(m)
            pieces.append((cur, in_tab(c - 1e-6)))
            cur = [m]
        cur.append(b)
        acc += seg
    pieces.append((cur, in_tab(acc - 1e-6)))
    return [(pc, tab) for pc, tab in pieces if len(pc) > 1]


# ------------------------------------------------------------------ Bewegungen
def plan(d: Drawing, s: GcodeSettings, visible_layers=None) -> ToolpathResult:
    warnings: list = []
    paths = collect_paths(d.export_view(), visible_layers)   # Schräglage herausdrehen
    paths = compensate(paths, s, warnings)
    paths = orient(paths, s)
    paths = order(paths, s)
    paths = add_tabs(paths, s)
    mill = s.machine == MACHINE_MILL
    if mill:
        depth, step = abs(s.cut_depth), max(0.01, abs(s.step_down))
        depths, z = [], 0.0
        while z < depth - 1e-9:
            z = min(depth, z + step)
            depths.append(-z)
        if not depths:
            depths = [0.0]
    else:
        depths = [0.0]
    tab_top = -(abs(s.cut_depth) - s.tab_height) if mill else 0.0
    moves: List[Move] = []
    pos = (0.0, 0.0, s.safe_z if mill else 0.0)
    moves.append(Move("rapid", 0.0, 0.0, pos[2]))
    for p in paths:
        for z in depths:
            moves.append(Move("rapid", p.start[0], p.start[1], s.safe_z if mill else 0.0))
            if mill:
                moves.append(Move("plunge", p.start[0], p.start[1], z))
            else:
                moves.append(Move("on", p.start[0], p.start[1], 0.0))
            if p.tabs and (not mill or z < tab_top - 1e-9):
                for pts, tab in _split_tabs(p):
                    if tab:
                        if mill:
                            moves.append(Move("retract", pts[0][0], pts[0][1], tab_top, tab=True))
                            for x, y in pts[1:]:
                                moves.append(Move("feed", x, y, tab_top, tab=True))
                            moves.append(Move("plunge", pts[-1][0], pts[-1][1], z))
                        else:
                            moves.append(Move("off", pts[0][0], pts[0][1], 0.0))
                            moves.append(Move("rapid", pts[-1][0], pts[-1][1], 0.0, tab=True))
                            moves.append(Move("on", pts[-1][0], pts[-1][1], 0.0))
                    else:
                        for x, y in pts[1:]:
                            moves.append(Move("feed", x, y, z))
            else:
                for sg in p.segs:
                    if sg[0] == "L":
                        moves.append(Move("feed", sg[1], sg[2], z))
                    else:
                        _, x, y, i, j, cw = sg
                        moves.append(Move("arc", x, y, z, i, j, cw))
            end = _end(p) if not p.tabs else (moves[-1].x, moves[-1].y)
            if mill:
                moves.append(Move("retract", end[0], end[1], s.safe_z))
            else:
                moves.append(Move("off", end[0], end[1], 0.0))
    res = ToolpathResult(paths, moves, warnings, passes=len(depths))
    _stats(res, s)
    return res


def _move_len(prev: Move, m: Move) -> float:
    if m.kind == "arc":
        cx, cy = prev.x + m.i, prev.y + m.j
        r = math.hypot(m.i, m.j)
        a0 = math.atan2(prev.y - cy, prev.x - cx)
        a1 = math.atan2(m.y - cy, m.x - cx)
        sweep = ((a0 - a1) if m.cw else (a1 - a0)) % (2 * math.pi) or 2 * math.pi
        return r * sweep
    return math.dist((prev.x, prev.y, prev.z), (m.x, m.y, m.z))


def _stats(res: ToolpathResult, s: GcodeSettings) -> None:
    t = cut = rapid = 0.0
    for a, b in zip(res.moves, res.moves[1:]):
        L = _move_len(a, b)
        if b.kind == "rapid":
            rapid += L
            t += L / max(1.0, s.rapid_rate)
        elif b.kind == "plunge":
            t += L / max(1.0, s.plunge_rate)
        elif b.kind == "retract":
            t += L / max(1.0, s.rapid_rate if b.z >= s.safe_z - 1e-9 else s.plunge_rate)
        elif b.kind in ("feed", "arc"):
            cut += L
            t += L / max(1.0, s.feed_rate)
    res.cut_length, res.rapid_length, res.time_min = cut, rapid, t


# ------------------------------------------------------------------ G-Code-Text
def generate_gcode(d: Drawing, s: GcodeSettings, visible_layers=None,
                   result: Optional[ToolpathResult] = None) -> str:
    n = s.decimals
    f = lambda v: _fmt(v, n)  # noqa: E731
    res = result or plan(d, s, visible_layers)
    mill = s.machine == MACHINE_MILL
    texts = sum(1 for e in d.entities if isinstance(e, Text))
    g = ["%", "(Erzeugt mit Traceify)", f"(Quelle: {d.source or '-'})",
         f"(Maschine: {'Fraese' if mill else 'Laser/Plasma'})",
         f"(Wege: {len(res.paths)}, Durchgaenge: {res.passes})",
         f"(Schnittweg: {res.cut_length:.0f} mm, geschaetzte Zeit: {res.time_min:.1f} min)"]
    if mill and s.compensation != COMP_NONE:
        g.append(f"(Radiuskorrektur: {s.compensation}, Werkzeug D{f(s.tool_diameter)} mm, "
                 f"{'Gleichlauf' if s.climb else 'Gegenlauf'})")
    if s.tabs:
        g.append(f"(Haltestege: {s.tabs} je Kontur, Breite {f(s.tab_width)} mm"
                 + (f", Hoehe {f(s.tab_height)} mm)" if mill else ")"))
    for w in res.warnings:
        g.append(f"(Hinweis: {w})".replace("ü", "ue").replace("ö", "oe").replace("ä", "ae")
                 .replace("ß", "ss").replace("Ø", "D").replace("–", "-"))
    if texts and not s.include_text:
        g.append(f"({texts} Texte nicht enthalten - nur als CAD-Text verfuegbar)")
    g += ["G21 (mm)", "G90 (absolut)", "G17 (XY-Ebene)", "G94"]
    if mill:
        g += [f"G0 Z{f(s.safe_z)}", f"S{s.spindle_speed} M3", "G4 P2"]
    else:
        g += ["M5", f"S{s.spindle_speed}"]
    feed_set = False
    for m in res.moves[1:]:
        if m.kind == "rapid":
            g.append(f"G0 X{f(m.x)} Y{f(m.y)}")
            feed_set = False
        elif m.kind == "plunge":
            g.append(f"G1 Z{f(m.z)} F{f(s.plunge_rate)}")
            feed_set = False
        elif m.kind == "retract":
            if m.z >= s.safe_z - 1e-9:
                g.append(f"G0 Z{f(m.z)}")
            else:
                g.append(f"G1 Z{f(m.z)} F{f(s.plunge_rate)}")
                feed_set = False
        elif m.kind == "feed":
            g.append(f"G1 X{f(m.x)} Y{f(m.y)}" + ("" if feed_set else f" F{f(s.feed_rate)}"))
            feed_set = True
        elif m.kind == "arc":
            g.append(f"{'G2' if m.cw else 'G3'} X{f(m.x)} Y{f(m.y)} I{f(m.i)} J{f(m.j)}"
                     + ("" if feed_set else f" F{f(s.feed_rate)}"))
            feed_set = True
        elif m.kind == "on":
            g.append("M3")
        elif m.kind == "off":
            g.append("M5")
    g += ["M5", "G0 X0 Y0", "M30", "%"]
    return "\n".join(g) + "\n"


def export_gcode(d: Drawing, path: str, s: GcodeSettings, visible_layers=None) -> None:
    with open(path, "w", encoding="ascii", errors="replace") as fh:
        fh.write(generate_gcode(d, s, visible_layers))


# Rückwärtskompatibel: frühere API lieferte (Start, Segmente)
def build_paths(d: Drawing, s: GcodeSettings, visible_layers=None):
    return [(p.start, p.segs) for p in plan(d, s, visible_layers).paths]
