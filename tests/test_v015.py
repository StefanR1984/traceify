"""Tests für Version 0.15: Ausrichten von Polylinien."""
import math

from traceify.core.edit import align_axes, rotate
from traceify.core.model import Line, Polyline


def test_polylinie_rechteck_wird_exakt():
    pl = Polyline([(10, 10), (100, 11), (101, 60), (9, 59)], closed=True)
    n = align_axes([pl])
    assert n == 4
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = pl.points
    assert y0 == y1 and y2 == y3 and x1 == x2 and x0 == x3


def test_offene_polylinie_bleibt_mit_linie_verbunden():
    pl = Polyline([(0, 0), (50, 1), (51, 40)])
    ln = Line((51, 40), (90, 41))
    align_axes([pl, ln])
    assert pl.points[-1] == ln.p1
    assert pl.points[0][1] == pl.points[1][1]
    assert ln.p1[1] == ln.p2[1]


def test_rundung_bleibt_unberuehrt():
    pts = [(100 + 50 * math.cos(math.radians(a)), 100 + 50 * math.sin(math.radians(a)))
           for a in range(0, 360, 10)]
    pl = Polyline(list(pts), closed=True)
    assert align_axes([pl]) == 0
    assert pl.points == pts


def test_ausrichten_an_schraeglage():
    c = (50.0, 50.0)
    base = Polyline([(10, 10), (90, 10.6), (90.4, 80), (10, 80)], closed=True)
    pl = rotate(base, c, 1.0)
    align_axes([pl], skew=1.0, center=c)
    back = rotate(pl, c, -1.0)
    (_, y0), (x1, y1), (x2, y2), (_, y3) = back.points
    assert abs(y0 - y1) < 1e-6 and abs(x1 - x2) < 1e-6 and abs(y2 - y3) < 1e-6


# ------------------------------------------------------------------ Schraffur als Fläche
def _hatch_lines(angle=40.0, sp=8.0, jitter=0.0, seed=1):
    import random
    from shapely.geometry import LineString, Polygon
    from traceify.core.model import LAYER_HATCH
    rnd = random.Random(seed)
    area = Polygon([(10, 10), (210, 10), (210, 40), (40, 40), (40, 160), (10, 160)])
    u = (math.cos(math.radians(angle)), math.sin(math.radians(angle)))
    n = (-u[1], u[0])
    out = []
    for k in range(-80, 80):
        px, py = k * sp * n[0] + 3, k * sp * n[1]
        seg = LineString([(px - 500 * u[0], py - 500 * u[1]), (px + 500 * u[0], py + 500 * u[1])])
        c = area.intersection(seg)
        for g in getattr(c, "geoms", [c]):
            if g.length > 1:
                j = lambda p: (p[0] + rnd.uniform(-jitter, jitter), p[1] + rnd.uniform(-jitter, jitter))
                out.append(Line(j(g.coords[0]), j(g.coords[-1]), LAYER_HATCH))
    return out, area


def _export(ents, version="R2010", meta=None):
    import ezdxf
    import os
    import tempfile
    from traceify.core.model import Drawing
    from traceify.export.dxf import export_dxf
    d = Drawing(300, 250, 0.5, ents, meta=meta if meta is not None else {"schraffur_flaeche": "1"})
    f = os.path.join(tempfile.mkdtemp(), "h.dxf")
    export_dxf(d, f, version)
    return d, ezdxf.readfile(f).modelspace()


def test_schraffur_wird_flaeche_und_deckt_sich_mit_linien():
    from ezdxf.render.hatching import hatch_entity
    from shapely.geometry import LineString, Point
    for ang in (35.0, 135.0):
        ents, _ = _hatch_lines(ang)
        ents.append(Line((0, 200), (100, 200)))
        d, msp = _export(ents)
        assert len(msp.query("HATCH")) == 1
        assert len(msp.query("LINE")) == 1                # nur die normale Linie bleibt
        segs = list(hatch_entity(msp.query("HATCH")[0]))
        orig = [LineString([d.to_mm(l.p1), d.to_mm(l.p2)]) for l in ents[:-1]]
        assert len(segs) == len(orig)
        for a, b in segs:
            m = Point((a.x + b.x) / 2, (a.y + b.y) / 2)
            assert min(o.distance(m) for o in orig) < 0.02


def test_schraffur_mit_scanrauschen():
    from traceify.core.hatch import find_regions
    from shapely.geometry import Polygon
    ents, area = _hatch_lines(50.0, jitter=0.6)
    regs = find_regions(ents)
    assert len(regs) == 1
    r = regs[0]
    assert abs(r.spacing - 8.0) < 0.6 and abs(r.angle - 50.0) < 1.0
    assert Polygon(r.outline, r.holes).symmetric_difference(area).area < 0.06 * area.area


def test_unregelmaessige_linien_bleiben_einzeln():
    from traceify.core.hatch import find_regions
    from traceify.core.model import LAYER_HATCH
    offs = [0, 3, 17, 21, 40, 41, 66, 90]
    ents = [Line((0 + o, 0), (40 + o, 40), LAYER_HATCH) for o in offs]
    assert find_regions(ents) == []


def test_ohne_option_und_r12_bleiben_linien():
    ents, _ = _hatch_lines()
    _, msp = _export(ents, meta={})
    assert len(msp.query("HATCH")) == 0 and len(msp.query("LINE")) == len(ents)
    _, msp = _export(ents, version="R12")
    assert len(msp.query("HATCH")) == 0


def test_pipeline_setzt_flaechen_option():
    from traceify.core.pipeline import ConvertSettings
    from traceify.ai.batch_rules import apply_named
    from traceify.export import GcodeSettings
    s = ConvertSettings()
    assert s.style.hatch_areas
    apply_named(s, GcodeSettings(), "schraffur_flaeche", "aus")
    assert not s.style.hatch_areas
    import os
    from traceify import api
    src = os.path.join(os.path.dirname(__file__), "..", "beispiele", "testzeichnung.png")
    assert api.open_file(src).drawing.meta.get("schraffur_flaeche") == "1"


# ------------------------------------------------------------------ OCR: Maßzahlen und Zeilen
def _w(txt, x, y=100, w=None, h=20, conf=90, key=(1, 1, 1)):
    return (key, x, y, w if w is not None else 11 * len(txt), h, txt, conf)


def test_kandidaten_fuer_maszahlen():
    from traceify.core.ocr import _number_candidates
    raw = [_w("Wohnen", 0), _w("24", 80), _w("85", 108), _w("251", 200), _w("BR", 300),
           _w("13.12", 400), _w("7", 500, key=(1, 1, 2))]
    c = [[raw[i][5] for i in g] for g in _number_candidates(raw)]
    assert ["24", "85"] in c and ["251"] in c and ["13.12"] in c
    assert not any("Wohnen" in g or "BR" in g for g in c)


def test_nachlesen_aendert_nie_ziffern():
    import numpy as np
    from traceify.core.ocr import OcrSettings, fix_numbers
    raw = [_w("24", 80), _w("85", 108), _w("251", 200), _w("176", 300)]
    answers = [("24,85", 95.0), ("2,61", 95.0), ("176", 95.0)]   # 2,61: andere Ziffern!

    def fake(crops, s, extra=""):
        assert "whitelist" in extra and len(crops) == 3
        return answers
    out = fix_numbers(np.full((300, 600), 255, np.uint8), raw, OcrSettings(), fake)
    texts = sorted(r[5] for r in out)
    assert texts == ["176", "24,85", "251"]


def test_einheit_hinter_zahl_bleibt():
    from traceify.core.ocr import _unit_words, plausible
    raw = [_w("24,85", 80), _w("qm", 145, conf=70), _w("qm", 600, conf=70)]
    assert not plausible("qm")
    assert _unit_words(raw) == {1}


def test_getrennte_zeilenteile_werden_zusammengefasst():
    from traceify.core.ocr import _merge_rows
    items = [(100, 50, 40, 20, "NFL", 300), (150, 51, 55, 20, "13,12", 450),
             (100, 120, 60, 20, "Diele", 400), (400, 50, 40, 20, "Bad", 300)]
    out = sorted(t[4] for t in _merge_rows(items))
    assert out == ["Bad", "Diele", "NFL 13,12"]


def _font(px):
    import os
    from PIL import ImageFont
    for f in ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
              r"C:\Windows\Fonts\arial.ttf"):
        if os.path.isfile(f):
            return ImageFont.truetype(f, px)
    return None


def test_kommas_in_maszahlen_auf_grobem_scan():
    import os
    import tempfile
    import pytest
    from PIL import Image, ImageDraw
    from traceify import api
    from traceify.core.model import Text
    from traceify.core.ocr import tesseract_available
    ppm = 100 / 25.4
    font = _font(int(3.2 * ppm))
    if not tesseract_available() or font is None:
        pytest.skip("Tesseract oder Schrift fehlt")
    img = Image.new("L", (int(220 * ppm), int(80 * ppm)), 255)
    dr = ImageDraw.Draw(img)
    for t, (x, y) in [("Wohnen 24,85 qm", (20, 20)), ("2,51", (150, 20)), ("1,76", (150, 50)),
                      ("Diele 7,40", (20, 50))]:
        dr.text((x * ppm, y * ppm), t, font=font, fill=0)
    p = os.path.join(tempfile.mkdtemp(), "plan.png")
    img.save(p, dpi=(100, 100))
    got = {e.text for e in api.open_file(p).drawing.entities if isinstance(e, Text)}
    assert {"2,51", "1,76"} <= got
    assert any("24,85" in t for t in got) and any("7,40" in t for t in got)


def test_gui_polylinie_ausrichten_per_klick_und_taste(tmp_path, monkeypatch):
    """Polylinie anklicken, „O“ drücken: Segmente exakt, Rückgängig stellt sie wieder her."""
    import os
    import cv2
    import numpy as np
    import pytest
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    from PySide6 import QtCore
    from PySide6.QtTest import QTest
    from traceify import config
    from traceify.core.model import Drawing
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from traceify.gui.main_window import MainWindow
    w = MainWindow()
    w.resize(1200, 900)
    w.show()
    p = tmp_path / "leer.png"
    cv2.imwrite(str(p), np.full((600, 800), 255, np.uint8))
    w.open_file(str(p))
    poly = Polyline([(100.0, 100.0), (400.0, 104.0), (403.0, 300.0), (99.0, 297.0)], closed=True)
    other = Line((500.0, 100.0), (700.0, 106.0))          # nicht markiert: bleibt schief
    w.drawing = Drawing(width=800, height=600, scale=0.25, entities=[poly, other])
    w.canvas.set_entities(w.drawing.entities)
    w.update_actions()
    cv, vp = w.canvas, w.canvas.viewport()
    cv.zoom_100()
    cv.centerOn(400, 300)
    app.processEvents()
    w.set_tool("select")
    pt = cv.mapFromScene(QtCore.QPointF(250, 102))
    QTest.mouseMove(vp, pt)
    QTest.mouseClick(vp, QtCore.Qt.LeftButton, QtCore.Qt.NoModifier, pt)
    app.processEvents()
    assert cv.selected_entities() == [poly]
    before = list(poly.points)
    QTest.keyClick(vp, QtCore.Qt.Key_O)
    app.processEvents()
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = w.drawing.entities[0].points
    assert y0 == y1 and x1 == x2 and y2 == y3 and x0 == x3
    assert w.drawing.entities[1].p1[1] != w.drawing.entities[1].p2[1]
    w.undo()
    assert w.drawing.entities[0].points == before
    w.close()
