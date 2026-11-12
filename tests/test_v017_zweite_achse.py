"""Zweite Bauachse (schräger Gebäudeflügel) wird exakt ausgerichtet (0.17)."""
import math

from traceify.core.model import LAYER_HATCH, Line
from traceify.core.straighten import second_axes, straighten


def _fluegel(winkel, wackeln=0.6):
    a = math.radians(winkel)
    u, n = (math.cos(a), math.sin(a)), (-math.sin(a), math.cos(a))
    out = []
    for k, d in enumerate((0, 90, 200, 330)):                     # lange Wände entlang u
        w = wackeln * (-1) ** k
        b = math.radians(winkel + w)
        out.append(Line((500 + d * n[0], 500 + d * n[1]),
                        (500 + d * n[0] + 600 * math.cos(b), 500 + d * n[1] + 600 * math.sin(b))))
    for t in (0, 300, 600):                                        # Querwände entlang n
        out.append(Line((500 + t * u[0], 500 + t * u[1]),
                        (500 + t * u[0] + 330 * n[0], 500 + t * u[1] + 330 * n[1])))
    return out


def _haupt():
    return [Line((100, 100 + 120 * k), (900, 100 + 120 * k)) for k in range(4)] + \
           [Line((100 + 250 * k, 100), (100 + 250 * k, 500)) for k in range(4)]


def test_zweite_achse_wird_gefunden():
    ents = _haupt() + _fluegel(35.0)
    ax = second_axes(ents, 0.0)
    assert len(ax) == 1 and abs(ax[0] - 35.0) < 1.0


def test_fluegel_wird_exakt_parallel():
    ents = _haupt() + _fluegel(35.0)
    straighten(ents, 1500, 1500)
    for l in ents[8:11 + 4]:
        a = math.degrees(math.atan2(l.p2[1] - l.p1[1], l.p2[0] - l.p1[0])) % 90
        assert min(abs(a - 35.0), 90 - abs(a - 35.0)) < 0.5 or abs(a % 90 - 35.0) < 0.5


def test_schraffur_ist_keine_zweite_achse():
    h = [Line((10 + 8 * k, 0), (60 + 8 * k, 50), LAYER_HATCH) for k in range(40)]
    assert second_axes(_haupt() + h, 0.0) == []


def test_ohne_fluegel_bleibt_alles_wie_es_war():
    ents = _haupt()
    assert second_axes(ents, 0.0) == []
