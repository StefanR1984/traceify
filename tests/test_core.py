"""Grundlegende Tests der Konvertierung und der Exporte (ohne Oberfläche, ohne Ollama)."""
import json
import math
import os
import xml.etree.ElementTree as ET

import cv2
import numpy as np
import pytest

import traceify as tf
from traceify.ai.ollama_client import parse_json
from traceify.core.ocr import tesseract_available


def drawing_image():
    img = np.full((900, 1200), 255, np.uint8)
    cv2.rectangle(img, (100, 100), (1100, 800), 0, 3)
    cv2.line(img, (100, 450), (1100, 450), 0, 3)
    cv2.circle(img, (400, 280), 120, 0, 3)
    cv2.ellipse(img, (800, 620), (130, 130), 0, 180, 360, 0, 3)
    cv2.line(img, (670, 620), (930, 620), 0, 3)
    return img


@pytest.fixture
def no_ocr():
    s = tf.ConvertSettings()
    s.ocr.enabled = False
    return s


def test_centerline_detects_geometry(no_ocr):
    res = tf.convert(drawing_image(), no_ocr)
    st = res.drawing.stats()
    assert st["Kreise"] == 1
    assert st["Bögen"] == 1
    assert 6 <= st["Linien"] <= 12
    c = res.drawing.by_type(tf.Circle)[0]
    assert abs(c.center[0] - 400) < 3 and abs(c.center[1] - 280) < 3
    assert abs(c.radius - 120) < 3
    arc = res.drawing.by_type(tf.Arc)[0]
    span = (arc.end_angle - arc.start_angle) % 360
    assert 170 < span < 190


def test_outline_mode_closed(no_ocr):
    no_ocr.vectorize.mode = tf.MODE_OUTLINE
    res = tf.convert(drawing_image(), no_ocr)
    polys = res.drawing.by_type(tf.Polyline)
    assert polys and all(p.closed for p in polys)


def test_exports(tmp_path, no_ocr):
    import ezdxf
    res = tf.convert(drawing_image(), no_ocr, dpi_scale=0.1)
    dxf = tmp_path / "a.dxf"
    tf.export(res.drawing, str(dxf))
    doc = ezdxf.readfile(str(dxf))
    types = {e.dxftype() for e in doc.modelspace()}
    assert {"LINE", "CIRCLE", "ARC"} <= types
    circ = next(e for e in doc.modelspace() if e.dxftype() == "CIRCLE")
    assert math.isclose(circ.dxf.radius, 12.0, abs_tol=0.3)  # 120 px * 0.1 mm
    assert math.isclose(circ.dxf.center.y, (900 - 280) * 0.1, abs_tol=0.3)  # y gespiegelt

    svg = tmp_path / "a.svg"
    tf.export(res.drawing, str(svg))
    ET.parse(str(svg))

    nc = tmp_path / "a.nc"
    tf.export(res.drawing, str(nc), tf.GcodeSettings(cut_depth=1.0, step_down=0.5))
    g = nc.read_text()
    assert "G21" in g and "M30" in g
    assert "G3" in g or "G2" in g
    assert "Z-1" in g and "Z-0.5" in g


def test_dxf_r12(tmp_path, no_ocr):
    import ezdxf
    res = tf.convert(drawing_image(), no_ocr)
    p = tmp_path / "r12.dxf"
    tf.export(res.drawing, str(p), dxf_version="R12")
    assert ezdxf.readfile(str(p)).dxfversion == "AC1009"


def test_settings_roundtrip(tmp_path):
    s = tf.ConvertSettings()
    s.vectorize.tolerance = 3.5
    s.ocr.language = "deu"
    p = tmp_path / "s.json"
    tf.save_settings(s, str(p))
    s2 = tf.load_settings(str(p))
    assert s2.vectorize.tolerance == 3.5 and s2.ocr.language == "deu"
    json.loads(p.read_text())


def test_batch_pdf(tmp_path, no_ocr):
    import pymupdf
    png = tmp_path / "z.png"
    cv2.imwrite(str(png), drawing_image())
    pdf = tmp_path / "z.pdf"
    doc = pymupdf.open()
    for _ in range(2):
        page = doc.new_page(width=842, height=595)
        page.insert_image(page.rect, filename=str(png))
    doc.save(str(pdf))
    out = tmp_path / "out"
    res = tf.batch_convert(str(tmp_path), str(out), [".dxf"], no_ocr)
    assert not [r for r in res if r.error]
    names = sorted(os.listdir(out))
    assert names == ["z.dxf", "z_S001.dxf", "z_S002.dxf"]


@pytest.mark.skipif(not tesseract_available(), reason="Tesseract nicht installiert")
def test_ocr_reads_text():
    img = np.full((300, 900), 255, np.uint8)
    cv2.putText(img, "GRUNDRISS EG", (60, 180), cv2.FONT_HERSHEY_SIMPLEX, 2.0, 0, 5)
    s = tf.ConvertSettings()
    s.ocr.language = "eng"
    res = tf.convert(img, s)
    texts = [t.text for t in res.drawing.by_type(tf.Text)]
    assert any("GRUNDRISS" in t for t in texts), texts


def test_parse_json_variants():
    assert parse_json('{"a": 1}') == {"a": 1}
    assert parse_json('```json\n{"a": 2}\n```') == {"a": 2}
    assert parse_json('Hier: {"a": 3} fertig') == {"a": 3}


def test_selftest_entrypoint(tmp_path, monkeypatch):
    import tempfile
    from traceify.__main__ import selftest
    # Protokoll in den Testordner statt nach %TEMP% (stört sonst den EXE-Selbsttest im Build)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    assert selftest() == 0
