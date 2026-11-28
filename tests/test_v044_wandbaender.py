"""Schraffierte Wandbänder als gefüllter Umriss statt Skelett-Geflecht (0.44)."""
import os

import cv2
import ezdxf
import numpy as np
import pytest

from traceify.core import bands, truth
from traceify.core.hatch import META_KEY
from traceify.core.model import LAYER_LINES, LAYER_WALLS, Drawing, Line, Polyline
from traceify.core.pipeline import ConvertSettings, convert
from traceify.export.dxf import export_dxf
from traceify.export.svg import export_svg

PPM = 300 / 25.4          # px je mm bei 300 dpi


def _wandbild(fill_gap=4):
    """Weißes Bild mit schraffiertem Wandring (18 px breit, weiße 1-px-Schrägen) und dünnen Linien."""
    img = np.full((500, 700), 255, np.uint8)
    ring = np.zeros_like(img)
    cv2.rectangle(ring, (100, 100), (500, 400), 255, -1)
    cv2.rectangle(ring, (118, 118), (482, 382), 0, -1)
    yy, xx = np.mgrid[:500, :700]
    gaps = ((xx + yy) % fill_gap == 0)
    img[(ring > 0) & ~gaps] = 0
    cv2.line(img, (200, 200), (400, 200), 0, 3)         # Möbelkante innen
    cv2.line(img, (520, 250), (680, 250), 0, 3)         # Linie außen, stößt nicht an
    return img


def test_band_gefunden_duenne_linien_nicht():
    img = _wandbild()
    band = bands.find_bands(255 - img, PPM)
    assert band[109, 300] and band[300, 109]            # im Wandring
    assert not band[200, 300] and not band[250, 600]    # dünne Linien bleiben Linien
    assert not band[250, 300]                           # Innenraum


def test_lockere_schraffur_ist_kein_band():
    img = _wandbild(fill_gap=2)                         # 50 % weiß → aufgelöste Schraffur
    assert not bands.find_bands(255 - img, PPM).any()


def test_fenster_aus_parallelen_linien_ist_kein_band():
    """Fenster im Grundriss: 4 dicke Parallelen mit durchlaufenden 2-px-Lücken – kein Wandband (0.45.15)."""
    img = _wandbild()
    for y in (430, 437, 444):                           # 5 px Linie, 2 px weiß, 15 mm lang
        cv2.rectangle(img, (150, y), (330, y + 4), 0, -1)
    cv2.rectangle(img, (150, 451), (330, 453), 0, -1)
    band = bands.find_bands(255 - img, PPM)
    assert not band[440, 240]
    assert band[109, 300]                               # schraffierte Wand bleibt


def test_ring_umriss_mit_loch_und_fuellung():
    band = np.zeros((300, 300), bool)
    band[50:250, 50:250] = True
    band[80:220, 80:220] = False
    ps = bands.band_outlines(band, 1.0)
    assert len(ps) == 2 and all(p.closed and p.layer == LAYER_WALLS for p in ps)
    g = bands.groups(ps)
    assert len(g) == 1 and len(g[0]) == 2
    m = bands.fill_mask(ps, band.shape)
    assert m[60, 150] and not m[150, 150]
    assert abs(int(m.sum()) - int(band.sum())) < 0.05 * band.sum()


def test_pipeline_wand_als_umriss_kein_geflecht():
    img = _wandbild()
    res = convert(img, ConvertSettings(), dpi_scale=1.0 / PPM)
    ents = res.drawing.entities
    walls = bands.wall_polys(ents)
    assert len(walls) >= 2
    m = bands.fill_mask(walls, img.shape)
    assert m[109, 300] and not m[250, 300]
    inner = cv2.erode(m.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    # keine Skelett-Linien mehr im Band
    zick = [e for e in ents if isinstance(e, Line)
            and inner[int((e.p1[1] + e.p2[1]) / 2), int((e.p1[0] + e.p2[0]) / 2)]]
    assert not zick
    assert any(isinstance(e, Line) and e.layer == LAYER_LINES and abs(e.p1[1] - 200) < 3 for e in ents)
    assert res.drawing.meta[META_KEY] == "1"
    # Schalter aus: wieder Skelett, keine Wandumrisse
    s = ConvertSettings()
    s.style.wall_bands = False
    assert not bands.wall_polys(convert(img, s, dpi_scale=1.0 / PPM).drawing.entities)


def test_wahrheit_original_in_wandflaeche_gilt_als_getroffen():
    band = np.zeros((300, 300), bool)
    band[50:70, 40:260] = True
    ws = bands.band_outlines(band, 1.0)
    orig = [Line((40, 51), (260, 51)), Line((40, 68), (260, 68))] + \
        [Line((x, 52), (x + 15, 67)) for x in range(45, 240, 6)]       # Kanten + Schraffurstriche
    r = truth.compare(orig, ws, (300, 300), 0.1)
    assert r["trefferquote"] > 0.99 and r["wand_genau"] > 0.9 and r["wand_mm2"] > 30
    r0 = truth.compare(orig, [], (300, 300), 0.1)
    assert r0["trefferquote"] < 0.1 and r0["wand_genau"] is None


def _drawing(areas=True):
    band = np.zeros((300, 400), bool)
    band[50:250, 50:350] = True
    band[80:220, 80:320] = False
    d = Drawing(width=400, height=300, scale=0.1,
                entities=bands.band_outlines(band, 1.0) + [Line((5, 5), (300, 5))])
    if areas:
        d.meta[META_KEY] = "1"
    return d


def test_dxf_svg_wandflaeche(tmp_path):
    p = str(tmp_path / "w.dxf")
    export_dxf(_drawing(), p)
    msp = ezdxf.readfile(p).modelspace()
    h = [e for e in msp if e.dxftype() == "HATCH"]
    assert len(h) == 1 and h[0].dxf.layer == LAYER_WALLS and h[0].dxf.solid_fill == 1
    assert len(h[0].paths) == 2                          # Außenumriss + Loch
    assert sum(e.dxftype() == "LWPOLYLINE" for e in msp) == 2   # Umrisse bleiben als Linien
    export_dxf(_drawing(areas=False), p)
    assert not any(e.dxftype() == "HATCH" for e in ezdxf.readfile(p).modelspace())
    s = str(tmp_path / "w.svg")
    export_svg(_drawing(), s)
    txt = open(s, encoding="utf-8").read()
    assert 'fill-rule="evenodd"' in txt and txt.count(" Z") == 2


def test_gui_wandflaeche_anzeigen_loeschen(tmp_path, monkeypatch):
    """Zeichenfläche füllt die Wand; Umriss anklicken und löschen nimmt die Füllung mit."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    QtCore = pytest.importorskip("PySide6.QtCore")
    from PySide6.QtTest import QTest
    from traceify import config
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from traceify.gui.main_window import MainWindow
    w = MainWindow()
    w.resize(1200, 900)
    w.show()
    p = tmp_path / "leer.png"
    cv2.imwrite(str(p), np.full((300, 400), 255, np.uint8))
    w.open_file(str(p))
    d = _drawing()
    w.drawing = d
    cv = w.canvas
    cv.set_entities(d.entities)
    w.refresh_layers()
    w.update_actions()
    assert cv.wall_fill is not None and cv.wall_fill.isVisible()
    assert cv.wall_fill.path().contains(QtCore.QPointF(60, 150))
    assert not cv.wall_fill.path().contains(QtCore.QPointF(200, 150))   # Loch frei
    cv.set_layer_visible(LAYER_WALLS, False)
    assert not cv.wall_fill.isVisible()
    cv.set_layer_visible(LAYER_WALLS, True)
    w.a_hatch_areas.trigger()                            # Schalter „als Fläche“ aus
    assert cv.wall_fill is None
    w.a_hatch_areas.trigger()
    assert cv.wall_fill is not None

    vp = cv.viewport()
    app.processEvents()
    cv.zoom_100()
    cv.centerOn(200, 50)
    app.processEvents()
    Qt = QtCore.Qt
    pt = cv.mapFromScene(QtCore.QPointF(200, 50))        # oberer Außenumriss
    QTest.mouseMove(vp, pt)
    QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, pt)
    app.processEvents()
    sel = cv.selected_entities()
    assert len(sel) == 1 and isinstance(sel[0], Polyline) and sel[0].layer == LAYER_WALLS
    QTest.keyClick(vp, Qt.Key_Delete)
    app.processEvents()
    assert len(bands.wall_polys(w.drawing.entities)) == 1
    assert not cv.wall_fill.path().contains(QtCore.QPointF(60, 150))
    w.undo()
    app.processEvents()
    assert len(bands.wall_polys(w.drawing.entities)) == 2
    assert cv.wall_fill.path().contains(QtCore.QPointF(60, 150))
    w.close()


def test_wahrheit_fuellung_des_originals_zaehlt_fuer_wandflaeche(tmp_path):
    """0.44.1: schwarz gefülltes Dreieck – im Original HATCH (Vollfüllung), keine Linien darin."""
    doc = ezdxf.new()
    h = doc.modelspace().add_hatch()
    h.set_solid_fill()
    h.paths.add_polyline_path([(0, 0), (10, 0), (0, 10)], is_closed=True)
    doc.modelspace().add_solid([(20, 0), (30, 0), (20, 5), (30, 5)])
    doc.modelspace().add_line((0, 20), (10, 20))
    f = tmp_path / "f.dxf"
    doc.saveas(f)
    fills = truth.load_fills(str(f))
    assert len(fills) == 2 and all(p.closed for p in fills)
    # Rechteck aus SOLID in DXF-Reihenfolge 0-1-3-2 → kein Schmetterling
    xs = sorted(round(x) for x, _ in fills[1].points)
    assert xs == [20, 20, 30, 30]
    # gedruckt? dunkel = ja, hellgrau = nein
    gray = np.full((100, 100), 255, np.uint8)
    tri = [Polyline([(10, 10), (60, 10), (10, 60)], True)]
    assert not truth.printed_fills(tri, gray)
    gray[10:60, 10:60] = 0
    assert truth.printed_fills(tri, gray)
    # Wandfläche auf dem gefüllten Dreieck: ohne Füllung daneben, mit Füllung richtig
    band = np.zeros((100, 100), np.uint8)
    cv2.fillPoly(band, [np.array([(10, 10), (60, 10), (10, 60)], np.int32)], 1)
    ws = bands.band_outlines(band > 0, 1.0)
    orig = [Line((10, 10), (60, 10)), Line((10, 10), (10, 60)), Line((60, 10), (10, 60)), Line((80, 90), (95, 90))]
    r0 = truth.compare(orig, ws, (100, 100), 0.1)
    r1 = truth.compare(orig, ws, (100, 100), 0.1, fills=tri)
    assert r0["wand_genau"] < 0.6 and r1["wand_genau"] > 0.98
    assert r1["trefferquote"] == r0["trefferquote"] and r1["genauigkeit"] == r0["genauigkeit"]
