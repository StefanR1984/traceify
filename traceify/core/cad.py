"""CAD-Geometrie für die Zeichenwerkzeuge: Fangpunkte, Schnittpunkte, Stutzen, Dehnen.

Alle Koordinaten in Bildpixeln (y nach unten). Bogenwinkel wie im Modell: Grad im
Bildkoordinatensystem, von start_angle im Uhrzeigersinn (Bildschirm) bis end_angle.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from .model import Arc, Circle, Insert, Line, Point, Polyline, Text

# Fangarten
SNAP_END, SNAP_MID, SNAP_CENTER, SNAP_INTERSECTION = "endpunkt", "mitte", "zentrum", "schnittpunkt"
SNAP_PERP, SNAP_NEAREST = "lot", "naechster"
SNAP_LABELS = {SNAP_END: "Endpunkt", SNAP_MID: "Mittelpunkt", SNAP_CENTER: "Zentrum",
               SNAP_INTERSECTION: "Schnittpunkt", SNAP_PERP: "Lotfußpunkt",
               SNAP_NEAREST: "Nächster Punkt"}
_PRIORITY = {SNAP_END: 0, SNAP_INTERSECTION: 0, SNAP_CENTER: 1, SNAP_MID: 2, SNAP_PERP: 3,
             SNAP_NEAREST: 4}


@dataclass
class Snap:
    point: Point
    kind: str
    entity: object = None


# ------------------------------------------------------------------ Grundformen
@dataclass
class Seg:
    a: Point
    b: Point
    src: object


@dataclass
class Circ:
    c: Point
    r: float
    a0: Optional[float]   # None = Vollkreis, sonst Bogen von a0 bis a1 (Grad, Bild)
    a1: Optional[float]
    src: object


def primitives(e) -> list:
    if isinstance(e, Line):
        return [Seg(e.p1, e.p2, e)]
    if isinstance(e, Polyline):
        pts = list(e.points) + ([e.points[0]] if e.closed and e.points else [])
        return [Seg(a, b, e) for a, b in zip(pts, pts[1:])]
    if isinstance(e, Circle):
        return [Circ(e.center, e.radius, None, None, e)]
    if isinstance(e, Arc):
        return [Circ(e.center, e.radius, e.start_angle, e.end_angle, e)]
    return []


def _ang(c, p) -> float:
    return math.degrees(math.atan2(p[1] - c[1], p[0] - c[0])) % 360


def on_arc(ci: Circ, p, tol_deg: float = 1e-6) -> bool:
    if ci.a0 is None:
        return True
    span = (ci.a1 - ci.a0) % 360
    rel = (_ang(ci.c, p) - ci.a0) % 360
    return rel <= span + tol_deg or rel >= 360 - tol_deg


def _seg_param(a, b, p) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    return 0.0 if L2 < 1e-12 else ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2


def closest_on_seg(a, b, p) -> Point:
    t = max(0.0, min(1.0, _seg_param(a, b, p)))
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def closest_on_circ(ci: Circ, p) -> Point:
    d = math.dist(ci.c, p)
    if d < 1e-9:
        q = (ci.c[0] + ci.r, ci.c[1])
    else:
        q = (ci.c[0] + (p[0] - ci.c[0]) / d * ci.r, ci.c[1] + (p[1] - ci.c[1]) / d * ci.r)
    if on_arc(ci, q):
        return q
    ends = [_arc_point(ci, ci.a0), _arc_point(ci, ci.a1)]
    return min(ends, key=lambda x: math.dist(x, p))


def _arc_point(ci: Circ, a: float) -> Point:
    t = math.radians(a)
    return (ci.c[0] + ci.r * math.cos(t), ci.c[1] + ci.r * math.sin(t))


# ------------------------------------------------------------------ Schnittpunkte
def line_line(a1, a2, b1, b2, infinite_a=False, infinite_b=False):
    """Schnittpunkt zweier Strecken/Geraden: (Punkt, ta, tb) oder None."""
    d1 = (a2[0] - a1[0], a2[1] - a1[1])
    d2 = (b2[0] - b1[0], b2[1] - b1[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-12:
        return None
    ta = ((b1[0] - a1[0]) * d2[1] - (b1[1] - a1[1]) * d2[0]) / den
    tb = ((b1[0] - a1[0]) * d1[1] - (b1[1] - a1[1]) * d1[0]) / den
    eps = 1e-9
    if not infinite_a and not (-eps <= ta <= 1 + eps):
        return None
    if not infinite_b and not (-eps <= tb <= 1 + eps):
        return None
    return (a1[0] + ta * d1[0], a1[1] + ta * d1[1]), ta, tb


def line_circle(a, b, ci: Circ, infinite=False):
    """Schnittpunkte Strecke/Gerade mit Kreis/Bogen: Liste (Punkt, t)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    fx, fy = a[0] - ci.c[0], a[1] - ci.c[1]
    A = dx * dx + dy * dy
    if A < 1e-12:
        return []
    B = 2 * (fx * dx + fy * dy)
    C = fx * fx + fy * fy - ci.r * ci.r
    disc = B * B - 4 * A * C
    if disc < -1e-9:
        return []
    disc = max(0.0, disc)
    out = []
    for sgn in ((-1, 1) if disc > 1e-12 else (1,)):
        t = (-B + sgn * math.sqrt(disc)) / (2 * A)
        if not infinite and not (-1e-9 <= t <= 1 + 1e-9):
            continue
        p = (a[0] + t * dx, a[1] + t * dy)
        if on_arc(ci, p):
            out.append((p, t))
    return out


def circle_circle(c1: Circ, c2: Circ):
    d = math.dist(c1.c, c2.c)
    if d < 1e-9 or d > c1.r + c2.r + 1e-9 or d < abs(c1.r - c2.r) - 1e-9:
        return []
    a = (c1.r ** 2 - c2.r ** 2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, c1.r ** 2 - a * a))
    mx = c1.c[0] + a * (c2.c[0] - c1.c[0]) / d
    my = c1.c[1] + a * (c2.c[1] - c1.c[1]) / d
    pts = [(mx + h * (c2.c[1] - c1.c[1]) / d, my - h * (c2.c[0] - c1.c[0]) / d),
           (mx - h * (c2.c[1] - c1.c[1]) / d, my + h * (c2.c[0] - c1.c[0]) / d)]
    if h < 1e-9:
        pts = pts[:1]
    return [p for p in pts if on_arc(c1, p) and on_arc(c2, p)]


def intersections(p1, p2) -> List[Point]:
    if isinstance(p1, Seg) and isinstance(p2, Seg):
        r = line_line(p1.a, p1.b, p2.a, p2.b)
        return [r[0]] if r else []
    if isinstance(p1, Seg) and isinstance(p2, Circ):
        return [p for p, _ in line_circle(p1.a, p1.b, p2)]
    if isinstance(p1, Circ) and isinstance(p2, Seg):
        return [p for p, _ in line_circle(p2.a, p2.b, p1)]
    return circle_circle(p1, p2)


# ------------------------------------------------------------------ Fang
def _bbox(e, pad=0.0):
    pts = []
    for pr in primitives(e):
        if isinstance(pr, Seg):
            pts += [pr.a, pr.b]
        else:
            pts += [(pr.c[0] - pr.r, pr.c[1] - pr.r), (pr.c[0] + pr.r, pr.c[1] + pr.r)]
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs) - pad, min(ys) - pad, max(xs) + pad, max(ys) + pad)


def near_entities(ents: Iterable, p: Point, radius: float) -> list:
    out = []
    for e in ents:
        if isinstance(e, (Text, Insert)):
            continue
        b = _bbox(e, radius)
        if b and b[0] <= p[0] <= b[2] and b[1] <= p[1] <= b[3]:
            out.append(e)
    return out


class SnapIndex:
    """Rasterindex über die Hüllrechtecke – schneller Fang auch bei 50 000 Objekten."""

    def __init__(self, ents: Iterable, cell: float = 64.0):
        self.cell = cell
        self.grid: dict = {}
        for e in ents:
            if isinstance(e, (Text, Insert)):
                continue
            b = _bbox(e)
            if b is None:
                continue
            x0, y0, x1, y1 = (int(math.floor(v / cell)) for v in b)
            if (x1 - x0 + 1) * (y1 - y0 + 1) > 4096:      # riesige Objekte: grob eintragen
                self.grid.setdefault("gross", []).append(e)
                continue
            for gx in range(x0, x1 + 1):
                for gy in range(y0, y1 + 1):
                    self.grid.setdefault((gx, gy), []).append(e)

    def query(self, p: Point, radius: float) -> list:
        c = self.cell
        x0, x1 = int(math.floor((p[0] - radius) / c)), int(math.floor((p[0] + radius) / c))
        y0, y1 = int(math.floor((p[1] - radius) / c)), int(math.floor((p[1] + radius) / c))
        seen, out = set(), []
        for key in [(gx, gy) for gx in range(x0, x1 + 1) for gy in range(y0, y1 + 1)] + ["gross"]:
            for e in self.grid.get(key, ()):
                if id(e) not in seen:
                    seen.add(id(e))
                    out.append(e)
        return out


def find_snap(ents: Iterable, p: Point, radius: float, modes=None,
              last: Optional[Point] = None) -> Optional[Snap]:
    """Bester Fangpunkt um p (Bildpixel) im Umkreis radius, oder None."""
    modes = set(modes or _PRIORITY)
    near = near_entities(ents, p, radius)
    cands: List[Snap] = []
    prims = [(e, pr) for e in near for pr in primitives(e)]
    for e, pr in prims:
        if isinstance(pr, Seg):
            if SNAP_END in modes:
                cands += [Snap(pr.a, SNAP_END, e), Snap(pr.b, SNAP_END, e)]
            if SNAP_MID in modes:
                cands.append(Snap(((pr.a[0] + pr.b[0]) / 2, (pr.a[1] + pr.b[1]) / 2), SNAP_MID, e))
            if SNAP_PERP in modes and last is not None:
                t = _seg_param(pr.a, pr.b, last)
                if 0 <= t <= 1:
                    cands.append(Snap((pr.a[0] + (pr.b[0] - pr.a[0]) * t,
                                       pr.a[1] + (pr.b[1] - pr.a[1]) * t), SNAP_PERP, e))
            if SNAP_NEAREST in modes:
                cands.append(Snap(closest_on_seg(pr.a, pr.b, p), SNAP_NEAREST, e))
        else:
            if SNAP_CENTER in modes:
                cands.append(Snap(pr.c, SNAP_CENTER, e))
            if pr.a0 is not None:
                if SNAP_END in modes:
                    cands += [Snap(_arc_point(pr, pr.a0), SNAP_END, e),
                              Snap(_arc_point(pr, pr.a1), SNAP_END, e)]
                if SNAP_MID in modes:
                    cands.append(Snap(_arc_point(pr, pr.a0 + ((pr.a1 - pr.a0) % 360) / 2),
                                      SNAP_MID, e))
            if SNAP_PERP in modes and last is not None:
                q = closest_on_circ(pr, last)
                cands.append(Snap(q, SNAP_PERP, e))
            if SNAP_NEAREST in modes:
                cands.append(Snap(closest_on_circ(pr, p), SNAP_NEAREST, e))
    if SNAP_INTERSECTION in modes and len(prims) > 1:
        for i in range(len(prims)):
            for j in range(i + 1, len(prims)):
                if prims[i][0] is prims[j][0]:
                    continue
                for q in intersections(prims[i][1], prims[j][1]):
                    cands.append(Snap(q, SNAP_INTERSECTION, prims[i][0]))
    cands = [c for c in cands if math.dist(c.point, p) <= radius]
    if not cands:
        return None
    return min(cands, key=lambda c: (_PRIORITY[c.kind], math.dist(c.point, p)))


def ortho(base: Point, p: Point, angle_deg: float = 0.0) -> Point:
    """Nur waagrecht oder senkrecht von base aus – bezogen auf Achsen, die um angle_deg
    (Bildsystem) gedreht sind, z. B. die Schräglage eines Scans."""
    if abs(angle_deg) < 1e-9:
        return (p[0], base[1]) if abs(p[0] - base[0]) >= abs(p[1] - base[1]) \
            else (base[0], p[1])
    a = math.radians(angle_deg)
    ux, uy = math.cos(a), math.sin(a)          # „waagrecht“
    vx, vy = -uy, ux                           # „senkrecht“
    dx, dy = p[0] - base[0], p[1] - base[1]
    su, sv = dx * ux + dy * uy, dx * vx + dy * vy
    if abs(su) >= abs(sv):
        return (base[0] + su * ux, base[1] + su * uy)
    return (base[0] + sv * vx, base[1] + sv * vy)


def point_at_distance(base: Point, toward: Point, dist: float) -> Point:
    dx, dy = toward[0] - base[0], toward[1] - base[1]
    n = math.hypot(dx, dy)
    if n < 1e-9:
        return (base[0] + dist, base[1])
    return (base[0] + dx / n * dist, base[1] + dy / n * dist)


def arc_from_3_points(a: Point, b: Point, c: Point) -> Optional[Arc]:
    """Bogen durch drei Punkte (Anfang, Zwischenpunkt, Ende)."""
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-9:
        return None
    ux = ((ax * ax + ay * ay) * (by - cy) + (bx * bx + by * by) * (cy - ay) +
          (cx * cx + cy * cy) * (ay - by)) / d
    uy = ((ax * ax + ay * ay) * (cx - bx) + (bx * bx + by * by) * (ax - cx) +
          (cx * cx + cy * cy) * (bx - ax)) / d
    ctr = (ux, uy)
    r = math.dist(ctr, a)
    aa, ab, ac = _ang(ctr, a), _ang(ctr, b), _ang(ctr, c)
    # Richtung so wählen, dass b zwischen a und c liegt (Modell: von start im Bild-Uhrzeigersinn)
    if (ab - aa) % 360 <= (ac - aa) % 360:
        return Arc(ctr, r, aa, ac)
    return Arc(ctr, r, ac, aa)


# ------------------------------------------------------------------ Stutzen / Dehnen
def _cut_params_line(target: Line, others) -> List[float]:
    ts = []
    for e in others:
        for pr in primitives(e):
            if isinstance(pr, Seg):
                r = line_line(target.p1, target.p2, pr.a, pr.b)
                if r:
                    ts.append(r[1])
            else:
                ts += [t for _, t in line_circle(target.p1, target.p2, pr)]
    return sorted({round(t, 9) for t in ts if 1e-6 < t < 1 - 1e-6})


def trim(ents: list, target, click: Point) -> Tuple[list, list]:
    """Stutzt target am Klickpunkt zwischen den nächsten Schnittpunkten.

    Gibt (entfernte Objekte, neue Objekte) zurück; ents wird nicht verändert.
    """
    others = [e for e in ents if e is not target and not isinstance(e, (Text, Insert))]
    if isinstance(target, Polyline):
        from .edit import explode
        segs = explode(target)
        hit = min(segs, key=lambda s: math.dist(closest_on_seg(s.p1, s.p2, click), click))
        for s in segs:
            s.layer = target.layer
        rest = [s for s in segs if s is not hit]
        removed, added = trim(rest + others, hit, click)
        return [target], rest + added
    if isinstance(target, Line):
        ts = _cut_params_line(target, others)
        tc = _seg_param(target.p1, target.p2, click)
        lo = max([t for t in ts if t < tc], default=0.0)
        hi = min([t for t in ts if t > tc], default=1.0)
        new = []
        P = lambda t: (target.p1[0] + (target.p2[0] - target.p1[0]) * t,  # noqa: E731
                       target.p1[1] + (target.p2[1] - target.p1[1]) * t)
        import copy
        if lo > 0:
            a = copy.copy(target)
            a.p1, a.p2 = target.p1, P(lo)
            new.append(a)
        if hi < 1:
            b = copy.copy(target)
            b.p1, b.p2 = P(hi), target.p2
            new.append(b)
        return [target], new
    if isinstance(target, (Circle, Arc)):
        ci = primitives(target)[0]
        angs = []
        for e in others:
            for pr in primitives(e):
                if isinstance(pr, Seg):
                    angs += [_ang(ci.c, p) for p, _ in line_circle(pr.a, pr.b, ci)]
                else:
                    angs += [_ang(ci.c, p) for p in circle_circle(ci, pr)]
        ac = _ang(ci.c, click)
        import copy
        if isinstance(target, Circle):
            if len(angs) < 2:
                return [target], []        # nur ein/kein Schnitt: Kreis ganz entfernen
            rel = sorted(((a - ac) % 360) for a in angs)
            # verbleibender Bogen: vom nächsten Schnitt nach dem Klick bis zum letzten davor
            start = (ac + rel[0]) % 360
            end = (ac + rel[-1]) % 360
            return [target], [Arc(target.center, target.radius, start, end, target.layer,
                                  target.color, target.linetype, target.lineweight)]
        a0, span = target.start_angle, (target.end_angle - target.start_angle) % 360
        rels = sorted({round((a - a0) % 360, 9) for a in angs if 1e-6 < (a - a0) % 360 < span - 1e-6})
        rc = (ac - a0) % 360
        lo = max([r for r in rels if r < rc], default=0.0)
        hi = min([r for r in rels if r > rc], default=span)
        new = []
        if lo > 0:
            x = copy.copy(target)
            x.start_angle, x.end_angle = a0 % 360, (a0 + lo) % 360
            new.append(x)
        if hi < span:
            y = copy.copy(target)
            y.start_angle, y.end_angle = (a0 + hi) % 360, target.end_angle
            new.append(y)
        return [target], new
    return [], []


def _extend_ray(others, a: Point, b: Point, forward: bool) -> Optional[float]:
    """Nächster Schnittparameter der Geraden a→b mit anderen Objekten jenseits von b
    (forward) bzw. vor a (rückwärts)."""
    best = None
    for e in others:
        for pr in primitives(e):
            if isinstance(pr, Seg):
                r = line_line(a, b, pr.a, pr.b, infinite_a=True)
                cands = [r[1]] if r else []
            else:
                cands = [t for _, t in line_circle(a, b, pr, infinite=True)]
            for t in cands:
                if forward and t > 1 + 1e-6 and (best is None or t < best):
                    best = t
                if not forward and t < -1e-6 and (best is None or t > best):
                    best = t
    return best


def _lerp(a: Point, b: Point, t: float) -> Point:
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)


def extend(ents: list, target, click: Point) -> bool:
    """Verlängert das dem Klick nähere Ende von target bis zum nächsten Objekt. True bei Erfolg.

    Linien und offene Polylinien wachsen in Richtung ihres End-Segments, Bögen entlang
    ihres Kreises."""
    others = [e for e in ents if e is not target and not isinstance(e, (Text, Insert))]
    if isinstance(target, Line):
        at_end = math.dist(click, target.p2) < math.dist(click, target.p1)
        t = _extend_ray(others, target.p1, target.p2, at_end)
        if t is None:
            return False
        p = _lerp(target.p1, target.p2, t)
        if at_end:
            target.p2 = p
        else:
            target.p1 = p
        return True
    if isinstance(target, Polyline) and not target.closed and len(target.points) >= 2:
        pts = target.points
        at_end = math.dist(click, pts[-1]) < math.dist(click, pts[0])
        a, b = (pts[-2], pts[-1]) if at_end else (pts[0], pts[1])
        t = _extend_ray(others, a, b, True) if at_end else _extend_ray(others, a, b, False)
        if t is None:
            return False
        p = _lerp(a, b, t)
        if at_end:
            pts[-1] = p
        else:
            pts[0] = p
        return True
    if isinstance(target, Arc):
        return _extend_arc(others, target, click)
    return False


def _extend_arc(others, arc: Arc, click: Point) -> bool:
    full = Circ(arc.center, arc.radius, None, None, arc)
    p_start = _arc_point(full, arc.start_angle)
    p_end = _arc_point(full, arc.end_angle)
    at_end = math.dist(click, p_end) < math.dist(click, p_start)
    span = (arc.end_angle - arc.start_angle) % 360
    best = None
    for e in others:
        for pr in primitives(e):
            if isinstance(pr, Seg):
                hits = [p for p, _ in line_circle(pr.a, pr.b, full)]
            else:
                hits = circle_circle(full, pr)
            for p in hits:
                ang = _ang(arc.center, p)
                travel = (ang - arc.end_angle) % 360 if at_end else (arc.start_angle - ang) % 360
                # nur echte Verlängerung, ohne den Bogen selbst zu überlappen
                if 1e-6 < travel < 360 - span - 1e-6 and (best is None or travel < best):
                    best = travel
    if best is None:
        return False
    if at_end:
        arc.end_angle = (arc.end_angle + best) % 360
    else:
        arc.start_angle = (arc.start_angle - best) % 360
    return True


def close_gaps(ents: list, dist: float) -> int:
    """Kleine Lücken schließen: freie Linienenden, die in ihrer Richtung nach höchstens
    ``dist`` auf ein anderes Objekt treffen, werden bis dorthin verlängert (T-Stöße und Ecken,
    die im Scan knapp nicht zusammenkommen). Gibt die Zahl der verlängerten Enden zurück.

    Ein Ende gilt als frei, wenn kein anderes Objekt näher als 1 px liegt."""
    if dist <= 0:
        return 0
    prims = [(pr, e) for e in ents if not isinstance(e, (Text, Insert)) for pr in primitives(e)]
    cell = max(32.0, 4 * dist)
    grid = {}
    for k, (pr, _) in enumerate(prims):
        if isinstance(pr, Seg):
            xs, ys = (pr.a[0], pr.b[0]), (pr.a[1], pr.b[1])
        else:
            xs, ys = (pr.c[0] - pr.r, pr.c[0] + pr.r), (pr.c[1] - pr.r, pr.c[1] + pr.r)
        for gx in range(int((min(xs) - dist) // cell), int((max(xs) + dist) // cell) + 1):
            for gy in range(int((min(ys) - dist) // cell), int((max(ys) + dist) // cell) + 1):
                grid.setdefault((gx, gy), []).append(k)

    def nearby(p, owner):
        seen = set()
        for k in grid.get((int(p[0] // cell), int(p[1] // cell)), ()):
            pr, src = prims[k]
            if src is not owner and id(src) not in seen:
                seen.add(id(src))
                yield src

    def touching(p, owner) -> bool:
        for src in nearby(p, owner):
            for pr in primitives(src):
                q = closest_on_seg(pr.a, pr.b, p) if isinstance(pr, Seg) else closest_on_circ(pr, p)
                if math.dist(p, q) <= 1.0:
                    return True
        return False
    n = 0
    for e in ents:
        if isinstance(e, Line):
            ends = [(e.p1, e.p2, False), (e.p2, e.p1, True)]       # (Ende, anderes Ende, …)
        elif isinstance(e, Polyline) and not e.closed and len(e.points) >= 2:
            ends = [(e.points[0], e.points[1], False), (e.points[-1], e.points[-2], True)]
        else:
            continue
        for end, prev, last in ends:
            L = math.dist(prev, end)
            if L < 1e-6 or touching(end, e):
                continue
            t = _extend_ray(list(nearby(end, e)), prev, end, True)
            if t is None or (t - 1.0) * L > dist:
                continue
            p = _lerp(prev, end, t)
            if isinstance(e, Line):
                if last:
                    e.p2 = p
                else:
                    e.p1 = p
            elif last:
                e.points[-1] = p
            else:
                e.points[0] = p
            n += 1
    return n


def pick(ents: Iterable, p: Point, radius: float):
    """Objekt, dessen Kontur dem Punkt am nächsten liegt (innerhalb radius)."""
    best, bd = None, radius
    for e in near_entities(ents, p, radius):
        for pr in primitives(e):
            q = closest_on_seg(pr.a, pr.b, p) if isinstance(pr, Seg) else closest_on_circ(pr, p)
            d = math.dist(q, p)
            if d <= bd:
                best, bd = e, d
    return best
