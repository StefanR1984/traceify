"""Tests für Vektor-PDF-Import, Maßstabserkennung, DXF-Attribute, DWG, Update und Support."""
import os
import stat
import sys

import pytest

import traceify as tf
from traceify.core import pdf_vector as pv
from traceify.core.scale_detect import find_scale


@pytest.fixture
def vector_pdf(tmp_path):
    import pymupdf
    doc = pymupdf.open()
    for rot in (0, 90):
        p = doc.new_page(width=842, height=595)  # A4 quer
        p.draw_rect(pymupdf.Rect(40, 40, 802, 555), color=(0, 0, 0), width=1)
        for k in range(12):  # genug Elemente, damit es als Vektor-PDF gilt
            p.draw_line((60, 80 + k * 30), (400, 80 + k * 30), color=(0, 0, 0), width=0.5)
        p.draw_line((450, 100), (750, 100), color=(1, 0, 0), width=2, dashes="[6 3] 0")
        p.draw_circle((600, 300), 72, color=(0, 0, 1), width=1)
        sh = p.new_shape()
        sh.draw_sector((600, 480), (672, 480), 90)  # Viertelkreis-Sektor
        sh.finish(color=(0, 0, 0), width=1)
        sh.commit()
        p.insert_text((450, 540), "GRUNDRISS  M 1:100", fontsize=14)
        p.set_rotation(rot)
    path = tmp_path / "plan.pdf"
    doc.save(str(path))
    return str(path)


def test_pdf_vector_detection(vector_pdf):
    assert pv.has_vectors(vector_pdf, 0)
    assert not pv.has_vectors(vector_pdf, 0, pv.PdfVectorSettings(enabled=False))


def test_pdf_vector_import_geometry(vector_pdf):
    d = pv.import_page(vector_pdf, 0, dpi=144)
    f = 2.0  # 144 dpi / 72
    assert (d.width, d.height) == (842 * f, 595 * f)
    assert abs(d.scale - 25.4 / 144) < 1e-9
    circles = d.by_type(tf.Circle)
    assert len(circles) == 1
    c = circles[0]
    assert abs(c.center[0] - 600 * f) < 0.5 and abs(c.center[1] - 300 * f) < 0.5
    assert abs(c.radius - 72 * f) < 0.5
    assert any(isinstance(e, tf.Arc) for e in d.entities)  # Viertelkreis
    dashed = [e for e in d.by_type(tf.Line) if e.linetype == "DASHED"]
    assert len(dashed) == 1 and dashed[0].color == (255, 0, 0)
    assert abs(dashed[0].lineweight - 2 * 25.4 / 72) < 1e-6
    texts = [t.text for t in d.by_type(tf.Text)]
    assert any("M 1:100" in t for t in texts)


def test_pdf_vector_rotated_page(vector_pdf):
    d0 = pv.import_page(vector_pdf, 0, dpi=72)
    d1 = pv.import_page(vector_pdf, 1, dpi=72)
    assert (d1.width, d1.height) == (d0.height, d0.width)
    c0, c1 = d0.by_type(tf.Circle)[0], d1.by_type(tf.Circle)[0]
    # 90° im Uhrzeigersinn: (x, y) -> (H - y, x)
    assert abs(c1.center[0] - (d0.height - c0.center[1])) < 0.5
    assert abs(c1.center[1] - c0.center[0]) < 0.5
    assert any(abs(t.angle + 90) < 0.1 for t in d1.by_type(tf.Text))


def test_open_file_uses_vectors_and_scale(vector_pdf):
    res = tf.open_file(vector_pdf, 0, pdf_dpi=150)
    d = res.drawing
    assert d.meta.get("quelle") == "PDF-Vektoren"
    assert d.meta.get("massstab") == "1:100"
    c = d.by_type(tf.Circle)[0]
    # Radius 72 pt = 25,4 mm auf dem Papier -> bei 1:100 = 2540 mm
    assert abs(c.radius * d.scale - 2540) < 2
    s = tf.ConvertSettings()
    s.auto_scale = False
    d2 = tf.open_file(vector_pdf, 0, s, pdf_dpi=150).drawing
    assert abs(d2.by_type(tf.Circle)[0].radius * d2.scale - 25.4) < 0.1


@pytest.mark.parametrize("texts,expected", [
    (["M 1:100"], 100),
    (["Maßstab 1:50"], 50),
    (["MASSSTAB: 1 : 20"], 20),
    (["SCALE 1/200"], 200),
    (["Plan", "1:250"], 250),
    (["Tel. 0911 1:23"], None),
    (["1:50", "1:100"], None),
    ([], None),
])
def test_find_scale(texts, expected):
    assert find_scale(texts) == expected


def test_dxf_attributes(tmp_path):
    import ezdxf
    d = tf.Drawing(100, 100, 1.0, [
        tf.Line((0, 0), (50, 0), "LINIEN", (255, 0, 0), "DASHED", 0.5),
        tf.Polyline([(0, 0), (10, 10), (20, 0)], False, "FARBE_1", None, "CONTINUOUS", 0.25),
    ])
    p = tmp_path / "a.dxf"
    tf.export(d, str(p))
    doc = ezdxf.readfile(str(p))
    ln = next(e for e in doc.modelspace() if e.dxftype() == "LINE")
    assert ln.dxf.linetype == "DASHED"
    assert ln.dxf.lineweight == 50
    assert ln.rgb == (255, 0, 0)
    assert "FARBE_1" in doc.layers
    # R12 kennt weder Truecolor noch Strichstärke – darf trotzdem nicht scheitern
    tf.export(d, str(tmp_path / "r12.dxf"), dxf_version="R12")


def test_dwg_without_oda(tmp_path, monkeypatch):
    from traceify.export import dwg
    monkeypatch.setattr(dwg, "find_oda", lambda: None)
    d = tf.Drawing(10, 10, 1.0, [tf.Line((0, 0), (5, 5))])
    with pytest.raises(RuntimeError, match="ODA File Converter"):
        dwg.export_dwg(d, str(tmp_path / "x.dwg"))


@pytest.mark.skipif(sys.platform == "win32", reason="Shell-Skript als ODA-Ersatz nur unter Unix")
def test_dwg_calls_oda(tmp_path):
    from traceify.export import dwg
    fake = tmp_path / "ODAFileConverter"
    # Ersatz: kopiert jede DXF als .dwg in den Ausgabeordner und prüft die Argumente
    fake.write_text('#!/bin/sh\n[ "$4" = "DWG" ] && [ "$3" = "ACAD2018" ] || exit 3\n'
                    'for f in "$1"/*.dxf; do b=$(basename "$f" .dxf); cp "$f" "$2/$b.dwg"; done\n')
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    d = tf.Drawing(10, 10, 1.0, [tf.Line((0, 0), (5, 5))])
    out = tmp_path / "plan.dwg"
    dwg.export_dwg(d, str(out), "R2018", oda=str(fake))
    assert out.exists() and out.stat().st_size > 100


def test_settings_from_dict_tolerant():
    s = tf.ConvertSettings.from_dict({"vectorize": {"tolerance": 2.0, "unbekannt": 1},
                                      "pdf": {"enabled": False}, "neu": 5})
    assert s.vectorize.tolerance == 2.0 and s.pdf.enabled is False


def test_update_check(monkeypatch, tmp_path):
    from traceify import config, update
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "c.json"))
    assert update.is_newer("0.10.0", "0.9.9")
    assert not update.is_newer("v0.3.2", "0.3.2")
    info = update.UpdateInfo("99.0.0", "https://x", "https://x/setup.exe", "")
    monkeypatch.setattr(update, "fetch_latest", lambda timeout=6: info)
    assert update.check(force=True) is info
    assert update.check() is None  # gerade erst geprüft -> heute nicht noch einmal
    config.save({"update_last_check": 0, "update_skip": "99.0.0"})
    assert update.check() is None  # übersprungene Version
    monkeypatch.setattr(update, "fetch_latest", lambda timeout=6: (_ for _ in ()).throw(OSError()))
    assert update.check(force=True) is None  # offline -> still


def test_issue_url():
    from urllib.parse import parse_qs, urlparse
    from traceify import support
    url = support.issue_url("fehler", "", "Absturz beim Export", '{"a": 1}')
    q = parse_qs(urlparse(url).query)
    assert q["template"] == ["fehler.yml"]
    assert "Traceify" in q["umgebung"][0]
    assert q["beschreibung"] == ["Absturz beim Export"]
    assert len(url) <= 7900
    assert os.path.basename(support.log_path()) == "traceify.log"


def test_pdf_load_with_float_dpi(vector_pdf):
    """Die Oberfläche liefert die DPI als Kommazahl (QDoubleSpinBox) – darf nicht scheitern."""
    from traceify.core import loader
    gray, scale = loader.load(vector_pdf, 0, 150.0)
    assert gray.shape == (int(595 * 150 / 72 + 0.5), int(842 * 150 / 72 + 0.5)) or gray.size > 0
    d = pv.import_page(vector_pdf, 0, dpi=150.0)
    assert d.width > 0
