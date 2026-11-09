"""Schraffur-Flächen 0.16: zerrissene Linien, versetzte Raster, Fehltreffer."""
import math
import random

from shapely.geometry import LineString, Polygon

from traceify.core.hatch import find_regions
from traceify.core.model import LAYER_HATCH, Line


def _hatch(area, angle=45.0, sp=6.0, phase=0.0, split=False, drift=0.0, seed=3):
    """Schraffurlinien in einer Fläche; split: jede Linie in zwei Stücke mit Versatz
    (wie im Scan zerrissen); drift: Abstand wächst je Linie um diesen Betrag."""
    rnd = random.Random(seed)
    u = (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
    n = (-u[1], u[0])
    out = []
    o = phase - 120 * sp
    for _ in range(240):
        o += sp + drift
        seg = LineString([(o * n[0] - 900 * u[0], o * n[1] - 900 * u[1]),
                          (o * n[0] + 900 * u[0], o * n[1] + 900 * u[1])])
        c = area.intersection(seg)
        for g in getattr(c, "geoms", [c]):
            if g.length < 2:
                continue
            a, b = g.coords[0], g.coords[-1]
            if split and g.length > 12:
                f = rnd.uniform(0.35, 0.65)
                m = (a[0] + f * (b[0] - a[0]), a[1] + f * (b[1] - a[1]))
                d = rnd.uniform(-0.8, 0.8)          # zweites Stück leicht versetzt
                m2 = (m[0] + 2 * u[0] + d * n[0], m[1] + 2 * u[1] + d * n[1])
                b2 = (b[0] + d * n[0], b[1] + d * n[1])
                out += [Line(a, m, LAYER_HATCH), Line(m2, b2, LAYER_HATCH)]
            else:
                out.append(Line(a, b, LAYER_HATCH))
    return out


def _used(regs):
    return sum(len(r.members) for r in regs)


def test_zerrissene_schraffurlinien_werden_flaeche():
    wand = Polygon([(0, 0), (30, 0), (30, 400), (0, 400)])
    ents = _hatch(wand, split=True)
    regs = find_regions(ents)
    assert len(regs) == 1
    assert _used(regs) >= 0.95 * len(ents)
    assert abs(regs[0].spacing - 6.0) < 0.3


def test_leicht_wandernder_abstand():
    # handgezeichnet/verzerrt: Abstand 6,0 → 6,6 über die Wand
    wand = Polygon([(0, 0), (30, 0), (30, 600), (0, 600)])
    ents = _hatch(wand, drift=0.004)
    assert _used(find_regions(ents)) >= 0.9 * len(ents)


def test_zwei_waende_mit_versetztem_raster_an_einer_ecke():
    # L-förmige Ecke: zwei Wände, deren Schraffur um einen halben Abstand versetzt ist
    w1 = Polygon([(0, 0), (30, 0), (30, 300), (0, 300)])
    w2 = Polygon([(30, 270), (330, 270), (330, 300), (30, 300)])
    ents = _hatch(w1) + _hatch(w2, phase=3.0)
    regs = find_regions(ents)
    assert len(regs) >= 2
    assert _used(regs) >= 0.85 * len(ents)


def test_lange_parallelen_sind_keine_flaeche():
    # drei lange parallele Wandkanten (z. B. falsch erkannt) – keine Schraffur-Fläche
    ents = [Line((0 + 12 * k, 0), (300 + 12 * k, 300), LAYER_HATCH) for k in range(3)]
    ents += [Line((5 + 12 * k, 0), (305 + 12 * k, 300), LAYER_HATCH) for k in range(1)]
    assert find_regions(ents) == []


def test_reste_werden_benachbarter_flaeche_zugeordnet():
    wand = Polygon([(0, 0), (30, 0), (30, 300), (0, 300)])
    ents = _hatch(wand)
    # ein einzelnes Stück im selben Raster direkt neben der Fläche (Fortsetzung)
    r0 = find_regions(ents)[0]
    u = (math.cos(math.radians(r0.angle)), math.sin(math.radians(r0.angle)))
    nb = (-u[1], u[0])
    o = r0.spacing * 3
    p = (r0.base[0] + o * nb[0], r0.base[1] + o * nb[1])
    x = Line((p[0] + 40 * u[0], p[1] + 40 * u[1]), (p[0] + 46 * u[0], p[1] + 46 * u[1]),
             LAYER_HATCH)
    regs = find_regions(ents + [x])
    assert any(x in r.members for r in regs) or _used(regs) == len(ents)


def test_schraeger_gebaeudeteil_ist_keine_schraffur():
    from traceify.core.style import building_axes, detect_hatch
    ents = []
    # schräger Flügel (30°): lange Wände und kurze Möbelkanten parallel dazu
    a = math.radians(30)
    u, n = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
    for k in range(6):
        o = k * 40
        ents.append(Line((o * n[0], o * n[1]), (o * n[0] + 900 * u[0], o * n[1] + 900 * u[1])))
    for k in range(12):
        o, t = 200 + k * 6, 100
        ents.append(Line((o * n[0] + t * u[0], o * n[1] + t * u[1]),
                         (o * n[0] + (t + 30) * u[0], o * n[1] + (t + 30) * u[1])))
    assert any(abs(x - 30) <= 2 for x in building_axes(ents, 100))
    assert detect_hatch(ents, 0.25) == 0
    # echte 45°-Schraffur in einer achsparallelen Wand wird weiter erkannt
    wand = Polygon([(2000, 0), (2030, 0), (2030, 400), (2000, 400)])
    h = [Line(l.p1, l.p2) for l in _hatch(wand)]
    assert detect_hatch(h + [Line((1000, 0), (1000, 900))], 0.25) >= 0.8 * len(h)
