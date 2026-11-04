"""Tests für G-Code: Radiuskorrektur, Fräsrichtung, Reihenfolge, Haltestege, Zeitschätzung."""
import math
import re

import pytest

import traceify as tf
from traceify.export import gcode as G


def part():
    """Platte 100×60 mit Loch Ø20 und rechteckigem Ausschnitt 30×30 (1 mm/px, y gespiegelt)."""
    return tf.Drawing(200, 100, 1.0, [
        tf.Polyline([(10, 10), (110, 10), (110, 70), (10, 70)], True),
        tf.Circle((40, 40), 10),
        tf.Polyline([(70, 25), (100, 25), (100, 55), (70, 55)], True),
    ])


def area(p):
    pts = G._discretize(p)[:-1]
    return G._signed_area(pts)


def test_auto_compensation_and_direction():
    r = G.plan(part(), G.GcodeSettings(compensation="auto", tool_diameter=4))
    kinds = [(p.kind, p.depth) for p in r.paths]
    # Löcher (Tiefe 1) zuerst, Außenkontur zuletzt
    assert kinds[-1] == ("aussen", 0) and all(k == ("innen", 1) for k in kinds[:-1])
    outer = r.paths[-1]
    assert area(outer) > 0                       # außen gegen Uhrzeigersinn (Gleichlauf)
    assert abs(abs(area(outer)) - 104 * 64) < 30  # um Fräserradius 2 mm nach außen
    circle = next(p for p in r.paths if G._circle_of(p))
    assert math.isclose(G._circle_of(circle)[2], 8.0)   # Loch r=10 -> Werkzeugweg r=8
    assert area(circle) < 0                      # innen im Uhrzeigersinn
    rect = next(p for p in r.paths if p.kind == "innen" and not G._circle_of(p))
    assert abs(abs(area(rect)) - 26 * 26) < 1


def test_conventional_milling_reverses():
    r = G.plan(part(), G.GcodeSettings(compensation="auto", tool_diameter=4, climb=False))
    assert area(r.paths[-1]) < 0


def test_no_compensation_keeps_geometry():
    r = G.plan(part(), G.GcodeSettings(compensation="keine"))
    areas = sorted(abs(area(p)) for p in r.paths)
    assert abs(areas[-1] - 6000) < 1 and abs(areas[0] - math.pi * 100) < 3


def test_too_small_hole_warns():
    d = tf.Drawing(100, 100, 1.0, [tf.Circle((50, 50), 1.0)])
    r = G.plan(d, G.GcodeSettings(compensation="innen", tool_diameter=3))
    assert not r.paths and any("zu klein" in w for w in r.warnings)


def test_tabs_mill_only_last_passes():
    s = G.GcodeSettings(compensation="auto", tool_diameter=4, tabs=3, tab_width=4,
                        tab_height=1, cut_depth=3, step_down=1)
    r = G.plan(part(), s)
    outer = r.paths[-1]
    assert len(outer.tabs) == 3
    tab_moves = [m for m in r.moves if m.tab]
    assert tab_moves and {round(m.z, 3) for m in tab_moves} == {-2.0}
    # Löcher bekommen keine Stege
    assert all(not p.tabs for p in r.paths if p.kind == "innen")
    g = G.generate_gcode(part(), s, result=r)
    assert "Haltestege: 3" in g


def test_laser_tabs_switch_beam():
    s = G.GcodeSettings(machine="laser", tabs=2, tab_width=1.5)
    g = G.generate_gcode(part(), s)
    assert "Z" not in "".join(l for l in g.splitlines() if l.startswith(("G0", "G1")))
    assert g.count("M5") > g.count("M3") >= 3   # Strahl wird an Stegen unterbrochen


def test_time_estimate_reasonable():
    s = G.GcodeSettings(compensation="keine", feed_rate=600, cut_depth=1, step_down=1)
    r = G.plan(part(), s)
    expected_cut = 320 + 2 * math.pi * 10 + 120
    assert abs(r.cut_length - expected_cut) < 2
    assert r.cut_length / 600 < r.time_min < r.cut_length / 600 + 1.0


def test_gcode_has_valid_lines():
    g = G.generate_gcode(part(), G.GcodeSettings(compensation="auto", tool_diameter=3,
                                                 tabs=2, cut_depth=2, step_down=1))
    allowed = re.compile(r"^(%|\(.*\)|G[0-4]\d?( [XYZIJF]-?\d+(\.\d+)?)*|G4 P\d+|S\d+ M3|M[35]|M30|"
                         r"G2[01] \(mm\)|G90 \(absolut\)|G17 \(XY-Ebene\)|G94)$")
    bad = [l for l in g.splitlines() if not allowed.match(l)]
    assert not bad, bad[:5]
    assert g.isascii()


@pytest.mark.parametrize("comp", ["keine", "aussen", "innen", "auto"])
def test_open_paths_survive(comp):
    d = tf.Drawing(100, 100, 1.0, [tf.Line((0, 0), (50, 0)), tf.Line((50, 0), (50, 30))])
    r = G.plan(d, G.GcodeSettings(compensation=comp))
    assert len(r.paths) == 1 and not r.paths[0].closed
