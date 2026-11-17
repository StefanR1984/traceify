"""Kies als Fläche (HATCH mit Punktmuster) statt tausender Kreise (0.36)."""
import ezdxf
import numpy as np

from traceify.core import dots, truth
from traceify.core.hatch import META_KEY
from traceify.core.model import LAYER_GRAVEL, Circle, Drawing, Line
from traceify.export.dxf import export_dxf
from traceify.export.svg import export_svg


def _feld(x0=20, y0=20, nx=20, ny=15, sp=12.0, seed=1):
    rng = np.random.default_rng(seed)
    return [Circle((x0 + i * sp + rng.uniform(-3, 3), y0 + j * sp + rng.uniform(-3, 3)), 1.5,
                   LAYER_GRAVEL) for i in range(nx) for j in range(ny)]


def test_zwei_felder_zwei_flaechen_kleine_gruppe_bleibt():
    a, b = _feld(), _feld(x0=400, seed=2)
    klein = _feld(x0=20, y0=400, nx=4, ny=4)
    reg = dots.find_areas(a + b + klein + [Line((0, 0), (10, 0))])
    assert len(reg) == 2
    # Randpunkte hinter einem schmalen Hals fallen beim Schrumpfen ab und bleiben Kreise
    assert all(295 <= len(r.members) <= 300 for r in reg)
    for r in reg:
        assert 9 <= r.spacing <= 15 and len(r.outline) >= 4
        xs = [p[0] for p in r.outline]
        m = [c.center[0] for c in r.members]
        assert min(xs) < min(m) and max(xs) > max(m)          # Umriss umschließt die Punkte


def test_feld_mit_loch():
    c = [k for k in _feld(nx=30, ny=30) if not (150 < k.center[0] < 250 and 150 < k.center[1] < 250)]
    reg = dots.find_areas(c)
    assert len(reg) == 1 and len(reg[0].holes) == 1


def _drawing(areas=True):
    d = Drawing(width=700, height=300, scale=0.1, entities=_feld() + [Line((5, 5), (300, 5))])
    if areas:
        d.meta[META_KEY] = "1"
    return d


def test_dxf_export_hatch_mit_punktmuster(tmp_path):
    p = str(tmp_path / "k.dxf")
    export_dxf(_drawing(), p)
    msp = ezdxf.readfile(p).modelspace()
    h = [e for e in msp if e.dxftype() == "HATCH"]
    assert len(h) == 1 and h[0].dxf.layer == LAYER_GRAVEL
    d0 = list(h[0].pattern.lines[0].dash_length_items)
    assert d0[0] == 0.0 and 0.9 < -d0[1] < 1.5            # Punkt, Abstand ~1,2 mm
    assert sum(e.dxftype() == "CIRCLE" for e in msp) <= 3
    assert any(e.dxftype() == "LINE" for e in msp)
    export_dxf(_drawing(areas=False), p)                      # Schalter aus: Kreise bleiben
    msp = ezdxf.readfile(p).modelspace()
    assert sum(e.dxftype() == "CIRCLE" for e in msp) == 300
    assert not any(e.dxftype() == "HATCH" for e in msp)


def test_svg_export_punktmuster(tmp_path):
    p = tmp_path / "k.svg"
    export_svg(_drawing(), str(p))
    s = p.read_text(encoding="utf-8")
    assert 'id="kies0"' in s and "url(#kies0)" in s
    assert 5 <= s.count("<circle") <= 8                       # Musterkachel + wenige Randpunkte


def test_wahrheit_wertet_kies_flaeche():
    orig = _feld()
    shape = (300, 700)
    mm = 0.1                                                  # Originalpunkte r = 0,15 mm < 0,5 mm
    ohne = truth.compare(orig, orig, shape, mm)
    reg = dots.find_areas(orig)
    mit = truth.compare(orig, [], shape, mm, areas=reg)
    assert ohne["objekte"] == 300 and mit["objekte"] == 1 and mit["kies_flaechen"] == 1
    assert mit["trefferquote"] > 0.99 and mit["kies_genau"] > 0.95
    # Fläche ohne Kies im Original: nichts getroffen, Fläche liegt daneben
    fremd = truth.compare([Line((5, 5), (300, 5))], [], shape, mm, areas=reg)
    assert fremd["trefferquote"] == 0.0 and fremd["kies_genau"] == 0.0


def test_gui_kies_flaeche_schalter_und_export(tmp_path, monkeypatch):
    """Häkchen „Schraffur und Kies als Fläche“ per Mausklick, umwandeln, DXF exportieren."""
    import os
    import time

    import cv2
    import pytest
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from tests.test_v035_kies import _plan
    from traceify.gui.main_window import MainWindow
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    w = MainWindow()
    w.show()
    p = tmp_path / "dach.png"
    cv2.imwrite(str(p), _plan(grau=0, ring=False))
    w.panel.ocr.setChecked(False)
    w.open_file(str(p))
    for an in (False, True):
        cb = w.panel.hatch_areas
        if cb.isChecked() != an:
            QTest.mouseClick(cb, Qt.LeftButton, Qt.NoModifier, QPoint(8, cb.height() // 2))
        assert cb.isChecked() == an
        w.drawing = None
        w.run_convert()
        end = time.time() + 60
        while not (w.worker is None and w.drawing is not None):
            assert time.time() < end
            app.processEvents()
            time.sleep(0.02)
        out = str(tmp_path / f"k{an}.dxf")
        monkeypatch.setattr(QtWidgets.QFileDialog, "getSaveFileName", lambda *a, **k: (out, ""))
        w.export_dialog(".dxf")
        msp = ezdxf.readfile(out).modelspace()
        kies = [e for e in msp if e.dxf.layer == LAYER_GRAVEL]
        if an:
            assert sum(e.dxftype() == "HATCH" for e in kies) == 1
            assert sum(e.dxftype() == "CIRCLE" for e in kies) < 20
        else:
            assert sum(e.dxftype() == "CIRCLE" for e in kies) > 600
            assert not any(e.dxftype() == "HATCH" for e in kies)
    w.close()
