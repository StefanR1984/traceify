"""Tests zu den Maßketten: Maßzahlen in Lücken der Maßlinie (0.23.0)."""
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
    (x, y, w, h), _ = g[0][0]
    assert g[0][1] == 0 and 270 < x and x + w < 400 and y < 150 < y + h


def test_luecke_senkrecht_gefunden():
    img = _plan(vertical=True)                           # Text läuft von unten nach oben
    g = dimensions.line_gaps(img, 10.0)
    assert len(g) == 1 and g[0][1] == 1
    (x, y, w, h), _ = g[0][0]
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
    for read, want in (("6.70", "6.70"), ("9295", None), ("Bad", None), ("6.70", "6.70")):
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


@pytest.mark.skipif(not tesseract_available(), reason="Tesseract fehlt")
def test_mazahl_mit_maslinie_wird_gelesen():
    img = _plan("6.70")
    gray = (255 - img * 255).astype(np.uint8)
    texts, _ = recognize(gray, OcrSettings(), px_per_mm=10.0)
    assert "6.70" in [t.text for t in texts]
