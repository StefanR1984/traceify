"""Punktmuster (Kies) als kleine Kreise auf Layer KIES (0.35)."""
import os
import time

import cv2
import numpy as np
import pytest

from traceify.core import dots
from traceify.core.model import LAYER_GRAVEL, Circle, Line
from traceify.core.pipeline import ConvertSettings, convert


def _plan(grau=170, ring=True):
    """Dachfläche mit Kies (10 px/mm), Umrandung, Strichpunktreihe, einzelne Rauschpunkte."""
    rng = np.random.default_rng(3)
    img = np.full((500, 800), 255, np.uint8)
    cv2.rectangle(img, (20, 20), (420, 470), 0, 3)
    gx, gy = np.meshgrid(np.arange(45, 400, 14), np.arange(45, 450, 14))
    for px, py in np.column_stack([gx.ravel(), gy.ravel()]) + rng.uniform(-3, 3, (gx.size, 2)):
        cv2.circle(img, (int(px), int(py)), 2, grau, 1 if ring else -1)
    for k in range(45):                                  # Punktreihe (Strichpunktlinie)
        cv2.circle(img, (480 + 7 * k, 60), 1, 0, -1)
    for px, py in rng.uniform((470, 120), (780, 480), (25, 2)):   # verstreutes Rauschen
        cv2.circle(img, (int(px), int(py)), 1, 0, -1)
    return img


def test_punktfeld_wird_kreise_reihe_und_rauschen_nicht():
    img = _plan()
    circ, mask = dots.find_dots(img, 10.0)
    inside = [c for c in circ if c.center[0] < 420]
    assert len(inside) > 0.8 * 26 * 29 and len(circ) == len(inside)
    assert all(c.layer == LAYER_GRAVEL and 0.1 <= c.radius <= 0.25 * 10 for c in circ)
    assert mask[:, 430:].max() == 0
    # gefüllte schwarze Punkte (simulierter Scan) ebenso
    assert len(dots.find_dots(_plan(grau=0, ring=False), 10.0)[0]) > 0.8 * 26 * 29


def test_punkte_in_textboxen_zaehlen_nicht():
    circ, _ = dots.find_dots(_plan(), 10.0, boxes=[(0, 0, 800, 500)])
    assert circ == []


def test_leeres_bild_und_selbstprobe():
    assert dots.find_dots(np.full((50, 50), 255, np.uint8), 10.0)[0] == []
    dots._self_check()


def test_pipeline_kies_schalter():
    s = ConvertSettings()
    s.ocr.enabled = False
    res = convert(_plan(grau=0, ring=False), s, dpi_scale=0.1)
    kies = [e for e in res.drawing.entities if isinstance(e, Circle) and e.layer == LAYER_GRAVEL]
    assert len(kies) > 600
    assert sum(isinstance(e, Line) for e in res.drawing.entities) >= 4     # Umrandung bleibt
    s.style.dots = False
    res = convert(_plan(grau=0, ring=False), s, dpi_scale=0.1)
    assert not any(getattr(e, "layer", "") == LAYER_GRAVEL for e in res.drawing.entities)


def _wait(app, cond, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("Zeitüberschreitung")


def test_gui_kies_schalter_klicken(tmp_path):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from traceify.gui.main_window import MainWindow
    w = MainWindow()
    w.show()
    p = tmp_path / "dach.png"
    cv2.imwrite(str(p), _plan(grau=0, ring=False))
    w.panel.ocr.setChecked(False)
    w.open_file(str(p))
    for an in (True, False):
        if w.panel.dots.isChecked() != an:
            QTest.mouseClick(w.panel.dots, Qt.LeftButton, Qt.NoModifier,
                             QPoint(8, w.panel.dots.height() // 2))   # aufs Kästchen
        assert w.panel.dots.isChecked() == an
        assert w.panel.settings().style.dots == an
        w.drawing = None
        w.run_convert()
        _wait(app, lambda: w.worker is None and w.drawing is not None)
        n = sum(1 for e in w.drawing.entities if getattr(e, "layer", "") == LAYER_GRAVEL)
        assert (n > 600) == an
    w.close()
