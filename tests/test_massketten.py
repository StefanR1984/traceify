"""Tests zu den Maßketten: Maßzahlen in Lücken der Maßlinie (0.23.0), zwischen Sternen,
über/unter der Linie und mit Hochziffer."""
import cv2
import numpy as np
import pytest

from traceify.core import dimensions
from traceify.core.model import Text
from traceify.core.ocr import OcrSettings, recognize, tesseract_available


def _plan(text="6.70", vertical=False):
    """Maßlinie mit Lücke, die Zahl mittig darin (1 = Tinte), 10 px/mm."""
    img = np.zeros((300, 700), np.uint8)
    cv2.line(img, (20, 150), (270, 150), 1, 2)
    cv2.line(img, (400, 150), (680, 150), 1, 2)
    for x in (20, 680):                                  # Ticks an den Enden
        cv2.line(img, (x - 8, 158), (x + 8, 142), 1, 2)
    cv2.putText(img, text, (285, 163), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 1, 2)
    return np.ascontiguousarray(np.rot90(img, 1)) if vertical else img


def test_luecke_waagrecht_gefunden():
    g = dimensions.line_gaps(_plan(), 10.0)
    assert len(g) == 1
    x, y, w, h = g[0][0][0]
    assert g[0][1] == 0 and 270 < x and x + w < 400 and y < 150 < y + h


def test_luecke_senkrecht_gefunden():
    img = _plan(vertical=True)                           # Text läuft von unten nach oben
    g = dimensions.line_gaps(img, 10.0)
    assert len(g) == 1 and g[0][1] == 1
    x, y, w, h = g[0][0][0]
    assert x < 150 < x + w and h > w


def test_linie_ohne_luecke_und_wandecke_kein_treffer():
    img = np.zeros((300, 700), np.uint8)
    cv2.line(img, (20, 150), (680, 150), 1, 2)            # durchgehend
    cv2.line(img, (20, 250), (300, 250), 1, 2)            # Lücke ohne Schrift
    cv2.line(img, (360, 250), (680, 250), 1, 2)
    assert dimensions.line_gaps(img, 10.0) == []


def test_lesen_mit_attrappe_zahlenmuster():
    img = _plan()
    gray = (255 - img * 255).astype(np.uint8)
    # „67“: zu kurz für die Box (Teil einer Zahl) → nichts
    for read, want in (("6.70", "6.70"), ("9295", None), ("Bad", None), ("67", None), ("6,70", "6.70")):
        tt, bb = dimensions.read_gap_numbers(img, gray, 10.0, OcrSettings(),
                                             run_lines=lambda c, s, x, r=read: [(r, 90.0)] * len(c))
        assert [t.text for t in tt] == ([want] if want else [])
    tt, _ = dimensions.read_gap_numbers(img, gray, 10.0, OcrSettings(),
                                        run_lines=lambda c, s, x: [("6.70", 40.0)] * len(c))
    assert tt == []                                      # unsicher → nichts


def test_zusammenfuehren_ersetzt_nur_zahlenlesungen():
    T = [Text("144", (0, 0), 10), Text("Bad", (0, 0), 10), Text("2.10", (0, 0), 10)]
    B = [(0, 0, 50, 20), (100, 0, 50, 20), (200, 0, 50, 20)]
    dimensions.merge(T, B, [Text("14.45", (0, 0), 10), Text("2.40", (0, 0), 10),
                            Text("2.10", (0, 0), 10), Text("30", (0, 0), 10)],
                     [(2, 0, 60, 20), (100, 0, 40, 20), (200, 0, 50, 20), (400, 0, 20, 20)])
    assert sorted(t.text for t in T) == ["14.45", "2.10", "30", "Bad"]
    assert len(T) == len(B)


def _star(img, x, y):
    """Maßbegrenzung: Schrägstrich, Maßlinienstummel und Maßhilfslinie durch einen Punkt."""
    cv2.line(img, (x - 8, y + 8), (x + 8, y - 8), 1, 2)
    cv2.line(img, (x - 8, y), (x + 8, y), 1, 2)
    cv2.line(img, (x, y - 8), (x, y + 8), 1, 2)


def test_zahl_zwischen_sternen_ohne_masslinie():
    img = np.zeros((300, 700), np.uint8)                 # „✳74✳74✳“
    for x in (100, 250, 400):
        _star(img, x, 150)
    for x in (155, 305):
        cv2.putText(img, "74", (x, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 1, 2)
    assert len(dimensions._ticks(img, 10.0)[0]) == 3
    g = dimensions.line_gaps(img, 10.0)
    assert [(k, gap[3]) for gap, k in g] == [(0, 0), (0, 0)]
    gray = (255 - img * 255).astype(np.uint8)
    tt, _ = dimensions.read_gap_numbers(img, gray, 10.0, OcrSettings(),
                                        run_lines=lambda c, s, x: [("74", 90.0)] * len(c))
    assert [t.text for t in tt] == ["74", "74"]


def test_ziffern_sind_keine_sterne():
    img = np.zeros((200, 700), np.uint8)
    cv2.putText(img, "4714 1.47", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 1, 2)
    cv2.putText(img, "4714 1.47", (350, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 1, 2)
    assert dimensions._ticks(img, 10.0)[0] == []


def test_zahlen_ueber_und_unter_der_linie():
    img = _plan("")                                      # nur Linie mit Lücke 270–400
    cv2.putText(img, "3.01", (285, 146), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 1, 2)
    cv2.putText(img, "3.00", (300, 173), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 1, 2)
    g = dimensions.line_gaps(img, 10.0)
    assert sorted(gap[3] for gap, _ in g) == [-1, 1]
    up = next(gap for gap, _ in g if gap[3] < 0)[0]
    lo = next(gap for gap, _ in g if gap[3] > 0)[0]
    assert up[1] + up[3] <= 150 <= lo[1]
    gray = (255 - img * 255).astype(np.uint8)
    crop = dimensions._crop(img, gray, lo, 0, 44, 1)     # die obere Zahl ist weggeschnitten
    assert crop[:3].min() > 200


def test_hochziffer_wird_angehaengt():
    img = _plan("4.17")
    cv2.putText(img, "5", (342, 156), cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1, 1)
    g = dimensions.line_gaps(img, 10.0)
    assert len(g) == 1 and g[0][0][2] is not None
    gray = (255 - img * 255).astype(np.uint8)
    for read, want in (("4.175", "4.17⁵"), ("4.17", "4.17")):   # zweiter Fall: war keine Hochziffer
        tt, _ = dimensions.read_gap_numbers(img, gray, 10.0, OcrSettings(),
                                            run_lines=lambda c, s, x, r=read: [(r, 90.0)] * len(c))
        assert [t.text for t in tt] == [want]


@pytest.mark.skipif(not tesseract_available(), reason="Tesseract fehlt")
def test_mazahl_mit_maslinie_wird_gelesen():
    img = _plan("6.70")
    gray = (255 - img * 255).astype(np.uint8)
    texts, _ = recognize(gray, OcrSettings(), px_per_mm=10.0)
    assert "6.70" in [t.text for t in texts]
