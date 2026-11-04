"""Tests für Fangpunkte, Schnittpunkte, Stutzen, Dehnen und 3-Punkt-Bogen."""
import math

import traceify as tf
from traceify.core import cad


def close(a, b, tol=1e-6):
    return math.dist(a, b) <= tol


def test_snap_priorities():
    h = tf.Line((0, 0), (100, 0))
    v = tf.Line((50, -50), (50, 50))
    c = tf.Circle((200, 0), 20)
    ents = [h, v, c]
    assert cad.find_snap(ents, (98, 2), 10).kind == "endpunkt"
    s = cad.find_snap(ents, (52, 3), 10)
    assert s.kind == "schnittpunkt" and close(s.point, (50, 0))
    assert cad.find_snap(ents, (200, 3), 10, modes={"zentrum"}).point == (200, 0)
    s = cad.find_snap(ents, (25, 4), 6, modes={"mitte", "naechster"})
    assert s.kind == "naechster" and close(s.point, (25, 0))
    s = cad.find_snap(ents, (30, 2), 8, modes={"lot"}, last=(30, 40))
    assert s.kind == "lot" and close(s.point, (30, 0))
    assert cad.find_snap(ents, (300, 300), 10) is None


def test_intersections_line_circle_arc():
    ci = cad.Circ((0, 0), 10, None, None, None)
    pts = cad.line_circle((-20, 0), (20, 0), ci)
    assert sorted(round(p[0]) for p, _ in pts) == [-10, 10]
    # Bogen nur rechte Hälfte (Bildwinkel -90..90 = 270..90)
    arc = cad.Circ((0, 0), 10, 270, 90, None)
    pts = cad.line_circle((-20, 0), (20, 0), arc)
    assert [round(p[0]) for p, _ in pts] == [10]
    cc = cad.circle_circle(cad.Circ((0, 0), 10, None, None, None), cad.Circ((10, 0), 10, None, None, None))
    assert len(cc) == 2 and all(abs(p[0] - 5) < 1e-9 for p in cc)


def test_trim_line_between_intersections():
    target = tf.Line((0, 0), (100, 0))
    cut1 = tf.Line((30, -10), (30, 10))
    cut2 = tf.Line((70, -10), (70, 10))
    removed, added = cad.trim([target, cut1, cut2], target, (50, 1))
    assert removed == [target] and len(added) == 2
    assert {(round(a.p1[0]), round(a.p2[0])) for a in added} == {(0, 30), (70, 100)}
    # Ende stutzen: Klick hinter dem letzten Schnitt
    removed, added = cad.trim([target, cut1, cut2], target, (90, 0))
    assert [(round(a.p1[0]), round(a.p2[0])) for a in added] == [(0, 70)]
    # ohne Schnitt: ganz entfernen
    removed, added = cad.trim([target], target, (50, 0))
    assert removed == [target] and added == []


def test_trim_circle_to_arc():
    c = tf.Circle((0, 0), 10)
    l = tf.Line((-20, 0), (20, 0))
    removed, added = cad.trim([c, l], c, (0, -10))          # obere Hälfte (Bild: y<0) weg
    assert removed == [c] and len(added) == 1
    a = added[0]
    mid = (a.start_angle + ((a.end_angle - a.start_angle) % 360) / 2)
    assert abs(math.sin(math.radians(mid)) - 1) < 1e-6      # verbleibender Bogen unten (y>0)


def test_trim_polyline_segment():
    p = tf.Polyline([(0, 0), (100, 0), (100, 100)], False)
    cut = tf.Line((50, -10), (50, 10))
    removed, added = cad.trim([p, cut], p, (75, 1))
    assert removed == [p]
    xs = sorted((round(min(a.p1[0], a.p2[0])), round(max(a.p1[0], a.p2[0]))) for a in added)
    assert (0, 50) in xs and (100, 100) in xs and len(added) == 2


def test_extend_line():
    l = tf.Line((0, 0), (40, 0))
    wall = tf.Line((100, -50), (100, 50))
    circ = tf.Circle((-60, 0), 10)
    assert cad.extend([l, wall, circ], l, (39, 0))
    assert close(l.p2, (100, 0))
    assert cad.extend([l, wall, circ], l, (1, 0))
    assert close(l.p1, (-50, 0))
    lonely = tf.Line((0, 200), (10, 200))
    assert not cad.extend([lonely, wall], lonely, (10, 200)) or close(lonely.p2, (100, 200))


def test_arc_from_3_points():
    a = cad.arc_from_3_points((10, 0), (0, 10), (-10, 0))   # untere Hälfte im Bild
    assert a is not None and abs(a.radius - 10) < 1e-9 and close(a.center, (0, 0))
    span = (a.end_angle - a.start_angle) % 360
    assert abs(span - 180) < 1e-6
    mid = math.radians(a.start_angle + span / 2)
    assert abs(math.sin(mid) - 1) < 1e-6                    # Mitte bei (0, 10)
    assert cad.arc_from_3_points((0, 0), (1, 1), (2, 2)) is None


def test_ortho_and_distance():
    assert cad.ortho((0, 0), (10, 3)) == (10, 0)
    assert cad.ortho((0, 0), (2, -9)) == (0, -9)
    assert close(cad.point_at_distance((0, 0), (3, 4), 10), (6, 8))


def test_pick():
    l = tf.Line((0, 0), (100, 0))
    c = tf.Circle((50, 50), 20)
    assert cad.pick([l, c], (40, 2), 5) is l
    assert cad.pick([l, c], (50, 31), 5) is c
    assert cad.pick([l, c], (50, 50), 5) is None


def test_snap_index_matches_bruteforce():
    import random
    rnd = random.Random(3)
    ents = [tf.Line((rnd.uniform(0, 5000), rnd.uniform(0, 5000)),
                    (rnd.uniform(0, 5000), rnd.uniform(0, 5000))) for _ in range(300)]
    ents += [tf.Circle((rnd.uniform(0, 5000), rnd.uniform(0, 5000)), rnd.uniform(5, 200))
             for _ in range(50)]
    idx = cad.SnapIndex(ents)
    for _ in range(200):
        p = (rnd.uniform(0, 5000), rnd.uniform(0, 5000))
        a = cad.find_snap(ents, p, 40)
        b = cad.find_snap(idx.query(p, 40), p, 40)
        assert (a is None) == (b is None)
        if a:
            assert a.kind == b.kind and close(a.point, b.point)


def test_trim_keeps_layer():
    p = tf.Polyline([(0, 0), (100, 0), (100, 100)], False, layer="WAENDE")
    cut = tf.Line((50, -10), (50, 10))
    _, added = cad.trim([p, cut], p, (75, 1))
    assert all(a.layer == "WAENDE" for a in added)
    c = tf.Circle((0, 0), 10, layer="ROHRE")
    _, added = cad.trim([c, tf.Line((-20, 0), (20, 0))], c, (0, -10))
    assert added[0].layer == "ROHRE"
