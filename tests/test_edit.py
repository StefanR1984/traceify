"""Tests für Vektor-Bearbeitung (core/edit.py) und Bereiche in der Konvertierung."""
import math

import cv2
import numpy as np

import traceify as tf
from traceify.core import edit
from traceify.core.pipeline import Region


def test_close_corner():
    a = tf.Line((0, 0), (8, 0))
    b = tf.Line((10, 2), (10, 20))
    assert edit.close_corner(a, b)
    assert a.p2 == (10, 0) and b.p1 == (10, 0)
    assert not edit.close_corner(tf.Line((0, 0), (5, 0)), tf.Line((0, 3), (5, 3)))


def test_orthogonalize_keeps_corners():
    h = tf.Line((0, 0), (100, 2))       # fast waagrecht
    v = tf.Line((100, 2), (101, 80))    # fast senkrecht, teilt Ecke mit h
    far = tf.Line((0, 0), (50, 50))     # 45° – bleibt
    n = edit.orthogonalize([h, v, far], tol_deg=3)
    assert n == 2
    assert h.p1[1] == h.p2[1]
    assert v.p1[0] == v.p2[0]
    assert h.p2 == v.p1  # Ecke verbunden
    assert far.p2 == (50, 50)


def test_snap_gaps_and_join():
    a = tf.Line((0, 0), (10, 0))
    b = tf.Line((11, 1), (11, 10))
    c = tf.Line((11.5, 10.5), (0, 10))
    assert edit.snap_gaps([a, b, c], 2.0) == 2
    assert a.p2 == b.p1
    polys = edit.join_lines([a, b, c])
    assert len(polys) == 1 and len(polys[0].points) == 4 and not polys[0].closed
    ring = edit.join_lines([tf.Line((0, 0), (5, 0)), tf.Line((5, 0), (5, 5)),
                            tf.Line((5, 5), (0, 0))])
    assert len(ring) == 1 and ring[0].closed and len(ring[0].points) == 3
    lines = edit.explode(ring[0])
    assert len(lines) == 3


def test_move_point_connected():
    a = tf.Line((0, 0), (10, 0))
    b = tf.Line((10, 0), (10, 10))
    changed = edit.move_point([a, b], a, 1, (12, 1))
    assert a.p2 == (12, 1) and b.p1 == (12, 1) and b in changed
    edit.move_point([a, b], a, 1, (20, 0), connected=False)
    assert b.p1 == (12, 1)
    c = tf.Circle((0, 0), 5)
    edit.move_point([c], c, 1, (0, 9))
    assert math.isclose(c.radius, 9)


def test_translate_copies():
    t = tf.Text("A", (1, 2), 5)
    t2 = edit.translate(t, 10, 20)
    assert t2.position == (11, 22) and t.position == (1, 2)


def _two_part_image():
    img = np.full((400, 800), 255, np.uint8)
    cv2.rectangle(img, (20, 20), (380, 380), 0, 3)
    cv2.circle(img, (600, 200), 100, 0, -1)   # gefüllte Fläche rechts
    return img


def test_regions_outline_and_ignore():
    s = tf.ConvertSettings()
    s.ocr.enabled = False
    base = tf.convert(_two_part_image(), s).drawing.stats()
    s.regions = [Region(420, 50, 360, 320, "umriss")]
    d = tf.convert(_two_part_image(), s).drawing
    circ = d.by_type(tf.Circle)
    assert len(circ) == 1 and abs(circ[0].center[0] - 600) < 3  # an richtiger Stelle
    assert d.stats()["Linien"] == base["Linien"]
    s.regions = [{"x": 0, "y": 0, "w": 400, "h": 400, "mode": "ignorieren"}]
    assert tf.convert(_two_part_image(), s).drawing.stats()["Linien"] == 0


def test_regions_on_vector_pdf(tmp_path):
    import pymupdf
    doc = pymupdf.open()
    p = doc.new_page(width=600, height=400)
    for k in range(20):
        p.draw_line((20, 20 + k * 10), (250, 20 + k * 10), width=0.5)
    p.draw_circle((450, 200), 50, width=1)
    path = tmp_path / "v.pdf"
    doc.save(str(path))
    s = tf.ConvertSettings()
    s.regions = [Region(0, 0, 300 * 150 // 72, 400 * 150 // 72, "ignorieren")]
    d = tf.open_file(str(path), 0, s, pdf_dpi=150).drawing
    assert d.stats()["Linien"] == 0 and d.stats()["Kreise"] == 1
