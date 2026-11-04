"""Tests zu den Verbesserungen aus dem Prüfstand mit echten Scans (0.11.0)."""
import math

import cv2
import numpy as np
import pytest

import traceify as tf
from traceify.core import benchmark, loader
from traceify.core.dxf_import import fit_to_image, read_dxf
from traceify.core.model import Arc, Drawing, Line, Text
from traceify.core.ocr import OcrSettings, plausible, recognize, tesseract_available, text_layer
from traceify.core.style import StyleSettings, detect_dashed
from traceify.core.vectorize import VectorizeSettings, merge_through_junctions, vectorize


def _lines(ents):
    return [e for e in ents if isinstance(e, Line)]


def test_kante_mit_abzweigungen_bleibt_eine_linie():
    """Wandkante mit Schraffur-Abzweigungen: früher in viele Stücke zerfallen."""
    img = np.zeros((300, 900), np.uint8)
    cv2.line(img, (50, 150), (850, 150), 255, 3)
    for x in range(100, 800, 40):                 # schräge „Schraffur“ an der Kante
        cv2.line(img, (x, 150), (x + 30, 120), 255, 2)
    ents = vectorize(img, VectorizeSettings())
    horiz = [l for l in _lines(ents) if abs(l.p1[1] - 150) < 3 and abs(l.p2[1] - 150) < 3]
    assert len(horiz) == 1
    l = horiz[0]
    assert abs(l.p1[0] - l.p2[0]) > 780


def test_merge_through_junctions_nur_kollinear():
    a = Line((0.0, 0.0), (10.0, 0.0))
    b = Line((10.0, 0.0), (20.0, 0.0))
    c = Line((10.0, 0.0), (10.0, 10.0))           # Abzweigung
    d = Line((20.0, 0.0), (25.0, 8.0))            # Knick – nicht verbinden
    out = merge_through_junctions([a, b, c, d])
    assert len(out) == 3
    long = [l for l in out if math.dist(l.p1, l.p2) > 15]
    assert len(long) == 1 and {long[0].p1, long[0].p2} == {(0.0, 0.0), (20.0, 0.0)}


def test_merge_through_junctions_haelt_toleranz_ein():
    # leicht geknickte Folge: Mittelpunkt 4 px neben der Geraden -> nicht zusammenfassen
    a = Line((0.0, 0.0), (50.0, 4.0))
    b = Line((50.0, 4.0), (100.0, 0.0))
    assert len(merge_through_junctions([a, b], angle_tol=10, tol=1.5)) == 2


def test_flacher_minibogen_wird_linie():
    # leicht ausgebeulte kurze Kante (Scanrauschen) -> Linie statt Bogen
    img = np.zeros((100, 200), np.uint8)
    pts = np.array([[20 + i, 50 + int(round(2.5 * math.sin(math.pi * i / 60)))] for i in range(61)],
                   np.int32)
    cv2.polylines(img, [pts.reshape(-1, 1, 2)], False, 255, 2)
    ents = vectorize(img, VectorizeSettings(merge_junctions=False))
    assert not any(isinstance(e, Arc) for e in ents)


def test_echter_bogen_bleibt_bogen():
    img = np.zeros((300, 300), np.uint8)
    cv2.ellipse(img, (150, 150), (100, 100), 0, 0, 90, 255, 3)
    ents = vectorize(img, VectorizeSettings())
    assert any(isinstance(e, Arc) and abs(e.radius - 100) < 4 for e in ents)


def test_strichlinien_mit_doppelten_strichen_stuerzt_nicht_ab():
    """Gleich lange, deckungsgleiche Striche ließen sorted() Linien vergleichen (TypeError)."""
    ents = []
    for i in range(6):
        x = 10 + i * 20
        ents.append(Line((x, 50.0), (x + 10, 50.0)))
        ents.append(Line((x, 50.0), (x + 10, 50.0)))   # doppelt gescannt
    detect_dashed(ents, StyleSettings())


def test_kurze_stuecke_zwischen_abzweigungen_bleiben_erhalten():
    # zwei Abzweigungen dicht hintereinander: das kurze Stück dazwischen darf nicht fehlen
    img = np.zeros((200, 400), np.uint8)
    cv2.line(img, (20, 100), (380, 100), 255, 3)
    cv2.line(img, (200, 100), (200, 20), 255, 3)
    cv2.line(img, (204, 100), (204, 180), 255, 3)
    ents = vectorize(img, VectorizeSettings())
    m = np.zeros_like(img)
    for l in _lines(ents):
        cv2.line(m, tuple(map(int, l.p1)), tuple(map(int, l.p2)), 255, 3)
    assert m[100, 195:210].all()


def test_plausible():
    for gut in ("Wohnen", "WC", "KG", "Bad", "NFL 18,76 m²", "26/26", "143.50 qm", "4"):
        assert plausible(gut), gut
    for schlecht in ("Mm", "om>Z", "%y", "z|", "oOo", "ce", ":D", "_J"):
        assert not plausible(schlecht), schlecht


def test_text_layer_entfernt_linien():
    ink = np.zeros((400, 600), np.uint8)
    cv2.line(ink, (10, 300), (590, 300), 255, 3)          # lange Linie
    cv2.rectangle(ink, (400, 20), (560, 200), 255, -1)    # Vollfläche
    cv2.putText(ink, "AB", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, 255, 3)
    t = text_layer(ink, px_per_mm=6.0, max_char_mm=15.0)
    assert not t[300, 100:500].any()
    assert not t[100, 450:520].any()
    assert t[60:110, 40:150].any()


@pytest.mark.skipif(not tesseract_available(), reason="Tesseract nicht installiert")
def test_ocr_liest_text_auf_dem_kopf():
    img = np.full((300, 900), 255, np.uint8)
    cv2.putText(img, "KELLER 26", (60, 180), cv2.FONT_HERSHEY_SIMPLEX, 2.2, 0, 5)
    img = np.ascontiguousarray(np.rot90(img, 2))
    texts, boxes = recognize(img, OcrSettings(), px_per_mm=12.0)
    hits = [t for t in texts if "KELLER" in t.text.upper()]
    assert hits and hits[0].angle == 180.0
    assert boxes


def _scan_pdf(path, dpi=150):
    import pymupdf as fitz
    img = np.full((int(8.27 * dpi), int(11.69 * dpi)), 255, np.uint8)
    cv2.rectangle(img, (100, 100), (img.shape[1] - 100, img.shape[0] - 100), 0, 4)
    ok, png = cv2.imencode(".png", img)
    doc = fitz.open()
    pg = doc.new_page(width=841.89, height=595.28)
    pg.insert_image(pg.rect, stream=png.tobytes())
    doc.save(path)
    doc.close()


def test_scan_pdf_in_originalaufloesung(tmp_path):
    p = str(tmp_path / "scan.pdf")
    _scan_pdf(p, 150)
    assert loader.native_dpi(p) == 150
    gray, mm = loader.load(p)                     # automatisch
    assert abs(25.4 / mm - 150) < 0.5
    assert abs(gray.shape[1] - 1753) <= 2
    gray3, _ = loader.load(p, 0, 300)             # feste DPI bleibt möglich
    assert gray3.shape[1] > 3000


def test_vektor_pdf_bleibt_bei_300_dpi(tmp_path):
    import pymupdf as fitz
    p = str(tmp_path / "vektor.pdf")
    doc = fitz.open()
    pg = doc.new_page(width=595, height=842)
    pg.draw_line((50, 50), (500, 700))
    doc.save(p)
    doc.close()
    assert loader.native_dpi(p) == 0
    assert loader.resolve_dpi(p, 0, 0) == 300


def test_dxf_import_und_ausrichtung(tmp_path):
    """Eigener DXF-Export wieder eingelesen landet pixelgenau auf dem Bild."""
    img = np.zeros((600, 800), np.uint8)
    cv2.rectangle(img, (100, 80), (700, 520), 255, 3)
    cv2.line(img, (100, 300), (700, 300), 255, 3)
    cv2.ellipse(img, (400, 300), (120, 120), 0, 180, 270, 255, 3)
    d = Drawing(width=800, height=600, scale=25.4 / 150,
                entities=vectorize(img, VectorizeSettings()) + [Text("RAUM 1", (300, 200), 20)])
    p = str(tmp_path / "x.dxf")
    tf.export(d, p)
    ents = read_dxf(p)
    assert any(isinstance(e, Text) and e.text == "RAUM 1" for e in ents)
    placed, (s, dx, dy) = fit_to_image(ents, img)
    assert abs(s - 150 / 25.4) < 0.05
    m = benchmark.measure("x", placed, img, 25.4 / 150)
    assert m.coverage > 0.97 and m.precision > 0.97
    assert m.texts == 1 and "raum" in m.words


def test_benchmark_wortvergleich():
    a = benchmark.Metrics("a", words=sorted(benchmark.words(["Keller 26", "Garage"])))
    b = benchmark.Metrics("b", words=sorted(benchmark.words(["Keller", "Koks", "26"])))
    w = benchmark.word_overlap(a, b)
    assert w["gemeinsam"] == 2 and w["nur_vergleich"] == 1
