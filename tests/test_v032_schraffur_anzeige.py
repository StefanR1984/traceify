"""Schraffur-Flächen auch im SVG und in der Zeichenfläche (0.32)."""
import os
import re

import cv2
import numpy as np
import pytest
from shapely.geometry import Polygon

from traceify.core.hatch import META_KEY
from traceify.core.model import Drawing, LAYER_HATCH, Line
from traceify.export.svg import export_svg
from test_v016_schraffur import _hatch


def _drawing(areas=True):
    wand = Polygon([(100, 100), (130, 100), (130, 500), (100, 500)])
    ents = _hatch(wand) + [Line((50, 50), (700, 50), "0")]
    d = Drawing(800, 600, 0.5, ents)
    d.meta[META_KEY] = "1" if areas else "0"
    return d


def test_svg_schraffur_als_flaeche(tmp_path):
    d = _drawing()
    n_hatch = sum(1 for e in d.entities if e.layer == LAYER_HATCH)
    p = tmp_path / "a.svg"
    export_svg(d, str(p))
    s = p.read_text(encoding="utf-8")
    assert 'fill="url(#schraffur0)"' in s and "<pattern" in s
    g = re.search(r'<g id="SCHRAFFUR".*?</g>', s, re.S).group(0)
    assert g.count("<line") <= 2            # nur die Musterlinie(n), keine Einzellinien
    assert "rotate(45.000)" in g
    # Abstand 6 px * 0,5 mm = 3 mm
    assert 'height="3.0000"' in g
    # umgeschaltet: Einzellinien wie bisher
    d2 = _drawing(areas=False)
    export_svg(d2, str(p))
    s2 = p.read_text(encoding="utf-8")
    assert "<pattern" not in s2 and s2.count("<line") == n_hatch + 1


def test_svg_ausgeblendeter_layer_ohne_flaeche(tmp_path):
    p = tmp_path / "b.svg"
    export_svg(_drawing(), str(p), visible_layers={"0"})
    assert "<pattern" not in p.read_text(encoding="utf-8")


def test_gui_schraffur_flaeche_klicken_loeschen(tmp_path, monkeypatch):
    """Fläche in der Zeichenfläche: ein Klick wählt alle Schraffurlinien, Entf löscht sie."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    QtCore = pytest.importorskip("PySide6.QtCore")
    from PySide6.QtTest import QTest
    from traceify import config
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from traceify.gui.canvas import HatchItem
    from traceify.gui.main_window import MainWindow
    w = MainWindow()
    w.resize(1200, 900)
    w.show()
    p = tmp_path / "leer.png"
    cv2.imwrite(str(p), np.full((600, 800), 255, np.uint8))
    w.open_file(str(p))
    d = _drawing()
    n_hatch = sum(1 for e in d.entities if e.layer == LAYER_HATCH)
    w.drawing = d
    cv = w.canvas
    cv.set_entities(d.entities)
    w.refresh_layers()
    w.update_actions()
    assert w.a_hatch_areas.isChecked()
    assert len(cv.hatch_items) == 1
    hidden = [it for it in cv.items_by_layer[LAYER_HATCH] if not it.isVisible()]
    assert len(hidden) >= 0.9 * n_hatch          # Einzellinien hinter der Fläche verborgen

    # Umschalten: Einzellinien, kein Flächen-Element
    w.a_hatch_areas.trigger()
    assert d.meta[META_KEY] == "0" and not cv.hatch_items
    assert all(it.isVisible() for it in cv.items_by_layer[LAYER_HATCH])
    w.a_hatch_areas.trigger()
    assert len(cv.hatch_items) == 1

    # Layer ausblenden blendet auch die Fläche aus
    cv.set_layer_visible(LAYER_HATCH, False)
    assert not cv.hatch_items[0].isVisible()
    cv.set_layer_visible(LAYER_HATCH, True)
    assert cv.hatch_items[0].isVisible()

    vp = cv.viewport()
    app.processEvents()
    cv.zoom_100()
    cv.centerOn(115, 300)
    app.processEvents()
    Qt = QtCore.Qt
    pt = cv.mapFromScene(QtCore.QPointF(115, 300))
    QTest.mouseMove(vp, pt)
    QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, pt)
    app.processEvents()
    assert isinstance(cv.scene().selectedItems()[0], HatchItem)
    sel = cv.selected_entities()
    assert len(sel) >= 0.9 * n_hatch and all(e.layer == LAYER_HATCH for e in sel)
    QTest.keyClick(vp, Qt.Key_Delete)
    app.processEvents()
    assert not cv.hatch_items
    left = [e for e in d.entities if e.layer == LAYER_HATCH]
    assert len(left) <= 0.1 * n_hatch
    w.undo()
    app.processEvents()
    assert sum(1 for e in w.drawing.entities if e.layer == LAYER_HATCH) == n_hatch
    w.close()


def test_schraffurenden_bis_zur_wandkante():
    """Schraffur endet vor der Kante: ziehen, wenn Nachbarn an derselben (zerstückelten) Kante
    enden; ein einzelnes Ende ohne Nachbarn und Ziele auf SCHRAFFUR bleiben."""
    from traceify.core.cad import extend_hatch_ends
    kante = [Line((0, 0), (60, 0), "LINIEN"), Line((60, 0), (120, 0), "LINIEN")]
    hatch = []
    for k in range(10):
        x = 10 + 10 * k
        gap = 3 if k % 2 else 0                # jede zweite endet 3 px vor der Kante
        hatch.append(Line((x - 15, 15), (x - gap / 1.414, gap / 1.414), LAYER_HATCH))
    allein = Line((200, 30), (215, 15), LAYER_HATCH)
    ziel = Line((210, 0), (260, 0), "LINIEN")
    ents = kante + hatch + [allein, ziel]
    n = extend_hatch_ends(ents, 5.0, 40.0, LAYER_HATCH)
    assert n == 5
    assert all(abs(h.p2[1]) < 1e-6 for h in hatch)
    assert allein.p2 == (215, 15)              # Ziel in Reichweite, aber keine Nachbarn
    # nicht weiter, als die Linie lang ist
    kurz = Line((30, 4), (31, 3), LAYER_HATCH)
    assert extend_hatch_ends([kante[0], kurz] + hatch, 5.0, 40.0, LAYER_HATCH) == 0


def test_mauerwerk_lange_und_kurze_striche():
    """Mauerwerks-Schraffur: lange Striche, dazwischen kurze – beide sind Schraffur; ein
    gedrehtes Möbelstück aus langen Parallelen und einem kurzen Strich nicht."""
    from traceify.core.style import detect_hatch
    mm = 0.17
    ppm = 1 / mm
    ents = []
    for k in range(14):                       # Wand 6 mm breit, Schraffur 45°
        o = k * 1.6 * ppm
        L = 6 * ppm if k % 2 == 0 else 1.8 * ppm
        cx, cy = 100 + o, 100 + o * 0.3
        d = L / 2 / 1.414
        ents.append(Line((cx - d, cy + d), (cx + d, cy - d), "LINIEN"))
    kurze = ents[1::2]
    sessel = [Line((500, 500), (500 + 15 * ppm / 1.414, 500 - 15 * ppm / 1.414), "LINIEN")
              for _ in range(1)]
    for k in range(1, 4):
        o = k * 1.2 * ppm
        sessel.append(Line((500 + o, 500 + o), (500 + o + 15 * ppm / 1.414,
                                                500 + o - 15 * ppm / 1.414), "LINIEN"))
    sessel.append(Line((505 + 2 * ppm, 503 + 2 * ppm), (505 + 2.7 * ppm, 503 + 1.3 * ppm),
                       "LINIEN"))
    detect_hatch(ents + sessel, mm)
    assert all(e.layer == LAYER_HATCH for e in kurze)
    assert sum(e.layer == LAYER_HATCH for e in ents) >= 12
    assert not any(e.layer == LAYER_HATCH for e in sessel)
