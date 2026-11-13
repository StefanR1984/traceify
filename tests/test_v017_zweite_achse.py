"""Zweite Bauachse (schräger Gebäudeflügel) wird exakt ausgerichtet (0.17)."""
import math

from traceify.core.model import LAYER_HATCH, Line
from traceify.core.straighten import second_axes, straighten


def _fluegel(winkel, wackeln=0.15):
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


def test_verzogener_fluegel_wird_nicht_verbogen():
    # lange Wand 1,2° neben der Flügelachse: Ausrichten würde ihr Ende um > 10 px verschieben
    ents = _haupt() + _fluegel(35.0)
    a = math.radians(36.2)
    w = Line((520, 900), (520 + 700 * math.cos(a), 900 + 700 * math.sin(a)))
    ents.append(w)
    p2 = w.p2
    straighten(ents, 1500, 1500)
    assert math.dist(w.p2, p2) < 0.01


def test_echt_schraege_linie_bleibt_mit_tintenpruefung():
    # Dachplan: Linie 2° schräg gezeichnet. Ohne Tintenprüfung wird sie waagrecht gezwungen und
    # liegt am Ende 10 px neben der Tinte; mit Prüfung bleibt sie schräg, die Wände nicht.
    import cv2
    import numpy as np
    from traceify.core.cad import ink_share
    img = np.full((700, 1000), 255, np.uint8)
    ents = _haupt()
    a = math.radians(2.0)
    schraeg = Line((150.0, 600.0), (150.0 + 580 * math.cos(a), 600.0 + 580 * math.sin(a)))
    for e in ents + [schraeg]:
        cv2.line(img, tuple(map(round, e.p1)), tuple(map(round, e.p2)), 0, 2)
    ents.append(Line(schraeg.p1, schraeg.p2))
    straighten(ents, 1000, 700, ink=ink_share(img))
    assert abs(ents[-1].p2[1] - schraeg.p2[1]) < 0.5            # schräg geblieben
    assert all(abs(e.p1[1] - e.p2[1]) < 1e-9 or abs(e.p1[0] - e.p2[0]) < 1e-9 for e in ents[:-1])
    ohne = _haupt() + [Line(schraeg.p1, schraeg.p2)]
    straighten(ohne, 1000, 700)
    assert abs(ohne[-1].p1[1] - ohne[-1].p2[1]) < 1e-9          # ohne Prüfung: waagrecht gezwungen
