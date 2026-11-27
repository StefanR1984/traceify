"""Zerstückelte Linien durchziehen, Scanpunkte auf eigenen Layer (0.37)."""
import math
import os
import time

import cv2
import numpy as np
import pytest

from traceify.core import cad
from traceify.core.model import LAYER_DASHED, LAYER_GRAVEL, LAYER_LINES, LAYER_SPECKS, Circle, Line
from traceify.core.pipeline import ConvertSettings, convert


def test_stuecke_an_kreuzungen_werden_eine_linie():
    # waagrechte Linie, an zwei senkrechten Linien zerschnitten (Lücke 4 px um die Kreuzung)
    ents = [Line((0, 100), (98, 100)), Line((102, 100.6), (198, 100.4)), Line((202, 100), (300, 100)),
            Line((100, 0), (100, 200)), Line((200, 0), (200, 200))]
    n = cad.join_collinear(ents, 10)
    assert n == 2
    h = [e for e in ents if isinstance(e, Line) and abs(e.p1[1] - e.p2[1]) < 2]
    assert len(h) == 1 and len(ents) == 3
    xs = sorted((h[0].p1[0], h[0].p2[0]))
    assert xs[0] == pytest.approx(0, abs=0.5) and xs[1] == pytest.approx(300, abs=0.5)


def test_weisse_luecke_strichlinie_und_versatz_bleiben():
    ents = [Line((0, 0), (90, 0)), Line((96, 0), (200, 0)),                 # Lücke vor Maßzahl, nichts kreuzt
            Line((0, 50), (20, 50), LAYER_DASHED), Line((24, 50), (44, 50), LAYER_DASHED),
            Line((50, 52), (60, 50), LAYER_DASHED),
            Line((0, 100), (90, 100)), Line((91, 104), (200, 104)),         # 4 px versetzt: zwei Linien
            Line((0, 150), (90, 150)), Line((91, 150), (200, 150), "ANDERER_LAYER")]
    before = [(e.p1, e.p2) for e in ents]
    assert cad.join_collinear(ents, 10, skip_layers=(LAYER_DASHED,)) == 0
    assert [(e.p1, e.p2) for e in ents] == before


def test_beruehrende_stuecke_und_tinte():
    ents = [Line((0, 0), (50, 0)), Line((50.5, 0), (100, 0))]                # berühren sich (< 1 px)
    assert cad.join_collinear(ents, 10) == 1 and len(ents) == 1
    ents = [Line((0, 0), (50, 0)), Line((56, 0), (100, 0))]
    assert cad.join_collinear(ents, 10, ink_ok=lambda p, q: True) == 1 and len(ents) == 1
    ents = [Line((0, 0), (50, 0)), Line((56, 0), (100, 0))]
    assert cad.join_collinear(ents, 10, ink_ok=lambda p, q: False) == 0 and len(ents) == 2


def test_scanpunkte_auf_eigenen_layer():
    ents = [Line((0, 0), (200, 0)), Line((100, 100), (102, 101)),           # frei im Raum: Punkt
            Line((50, 2), (51, 3)),                                         # klebt an der Wand: bleibt
            Circle((300, 300), 1.0), Circle((150, 150), 1.0, LAYER_GRAVEL),
            Line((400, 400), (430, 400))]                                   # lang: bleibt
    n = cad.isolate_specks(ents, size=10, free=10, layer=LAYER_SPECKS)
    assert n == 2
    assert [e.layer for e in ents] == [LAYER_LINES, LAYER_SPECKS, LAYER_LINES, LAYER_SPECKS,
                                       LAYER_GRAVEL, LAYER_LINES]


def _raster():
    """Raumplan mit Deckenraster (Linien kreuzen sich) und Scanpunkten, 10 px/mm."""
    rng = np.random.default_rng(5)
    img = np.full((600, 800), 255, np.uint8)
    cv2.rectangle(img, (20, 20), (780, 580), 0, 3)
    for x in range(100, 760, 80):
        cv2.line(img, (x, 20), (x, 580), 0, 2)
    for y in range(100, 560, 80):
        cv2.line(img, (20, y), (780, y), 0, 2)
    for px, py in rng.uniform((40, 40), (760, 560), (40, 2)):
        if min((px - 100) % 80, (py - 100) % 80) > 15:
            cv2.line(img, (int(px), int(py)), (int(px) + 8, int(py) + 3), 0, 2)   # Krümel 0,9 mm
    return img


def test_pipeline_raster_durchgehend_und_punkte():
    s = ConvertSettings()
    s.ocr.enabled = False
    res = convert(_raster(), s, dpi_scale=0.1)
    lines = [e for e in res.drawing.entities if isinstance(e, Line) and e.layer != LAYER_SPECKS]
    long_h = [e for e in lines if abs(e.p1[1] - e.p2[1]) < 2 and math.dist(e.p1, e.p2) > 700]
    long_v = [e for e in lines if abs(e.p1[0] - e.p2[0]) < 2 and math.dist(e.p1, e.p2) > 500]
    assert len(long_h) >= 7 and len(long_v) >= 9          # Rasterlinien ganz durchgezogen
    assert sum(getattr(e, "layer", "") == LAYER_SPECKS for e in res.drawing.entities) >= 15
    s.style.specks_layer = False
    res_aus = convert(_raster(), s, dpi_scale=0.1)
    assert not any(getattr(e, "layer", "") == LAYER_SPECKS for e in res_aus.drawing.entities)


def test_gui_schalter_linien_durchziehen(tmp_path):
    """Häkchen per Mausklick aus/an, umwandeln – Scanpunkte folgen dem Schalter."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from traceify.gui.main_window import MainWindow
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    w = MainWindow()
    w.show()
    p = tmp_path / "raster.png"
    cv2.imwrite(str(p), _raster())
    w.panel.ocr.setChecked(False)
    w.open_file(str(p))
    n = {}
    for an in (False, True):
        for cb in (w.panel.join_lines, w.panel.specks_layer):
            if cb.isChecked() != an:
                QTest.mouseClick(cb, Qt.LeftButton, Qt.NoModifier, QPoint(8, cb.height() // 2))
            assert cb.isChecked() == an
        st = w.panel.settings().style
        assert st.join_lines == an and st.specks_layer == an
        w.drawing = None
        w.run_convert()
        end = time.time() + 60
        while not (w.worker is None and w.drawing is not None):
            assert time.time() < end
            app.processEvents()
            time.sleep(0.02)
        n[an] = sum(getattr(e, "layer", "") == LAYER_SPECKS for e in w.drawing.entities)
    assert n[False] == 0 and n[True] >= 15
    w.close()


def test_scanpunkt_neben_schraeger_linie():
    """Eine schräge Linie hat ein riesiges Hüllrechteck – der Punkt liegt trotzdem frei."""
    ents = [Line((0, 0), (500, 400)), Line((400, 50), (402, 51))]
    assert cad.isolate_specks(ents, size=10, free=10, layer=LAYER_SPECKS) == 1
    assert ents[1].layer == LAYER_SPECKS and ents[0].layer == LAYER_LINES


def test_allplan_mass_punkt_und_prozent():
    """„141⁵“ → „1.41⁵“ (Punkt verloren), „2.41%“ → „2.41⁵“; Winkel „135°“ und „2%“ bleiben (0.38)."""
    from traceify.core.ocr import OcrSettings, fix_superscripts
    g = np.full((60, 400), 255, np.uint8)                  # keine Hochziffer-Komponente im Bild
    raw = [((1, 1, 1), 10, 10, 40, 18, "141⁵", 90.0), ((1, 1, 2), 80, 10, 40, 18, "2.41%", 90.0),
           ((1, 1, 3), 150, 10, 40, 18, "135°", 90.0), ((1, 1, 4), 220, 10, 20, 18, "2%", 90.0),
           ((1, 1, 5), 280, 10, 40, 18, "88⁵", 90.0)]
    out = fix_superscripts(g, raw, OcrSettings(), lambda c, s, e="": [])
    assert [r[5] for r in out] == ["1.41⁵", "2.41⁵", "135°", "2%", "88⁵"]


def test_tuermass_paar_und_leerzeichen():
    """„101“ über „2.40“ (Tür) → „1.01“; „200“ über „2.35“ und „150“ unter „6.70“ bleiben (0.37.2)."""
    from traceify.core.dimensions import tidy_numbers
    from traceify.core.model import Text
    t = [Text("101", (100, 100), 15.0), Text("2.40", (100, 122), 15.0),          # waagrecht, Höhe darunter
         Text("240", (300, 300), 15.0, 90.0), Text("1.01", (278, 300), 15.0, 90.0),  # senkrecht, Breite links
         Text("200", (500, 100), 15.0), Text("2.35", (500, 122), 15.0),          # keine Tür (2,00 breit)
         Text("150", (700, 100), 15.0), Text("6.70", (700, 78), 15.0),           # keine Tür (6,70 hoch)
         Text("2 75°", (900, 100), 15.0), Text("101", (100, 500), 15.0)]         # allein: Raumnummer?
    assert tidy_numbers(t) == 3
    assert [x.text for x in t] == ["1.01", "2.40", "2.40", "1.01", "200", "2.35", "150", "6.70", "2.75⁵", "101"]


def test_wellen_boegen_werden_gerade():
    """Kleiner Bogen mit Sehne auf Tinte → Linie; Türschwenk (Sehne im Leeren) bleibt (0.38.1)."""
    from traceify.core.model import Arc
    g = np.full((200, 300), 255, np.uint8)
    cv2.line(g, (10, 100), (290, 100), 0, 3)                # dicke Wandlinie
    ents = [Arc((100, 107), 10, 225, 315),                   # Welle: Sehne y≈100 liegt auf der Linie
            Arc((200, 150), 40, 180, 270)]                   # Türschwenk, Sehne quer durchs Leere
    g2 = g.copy()
    cv2.ellipse(g2, (200, 150), (40, 40), 0, 180, 270, 0, 2)
    n = cad.flatten_arcs(ents, cad.ink_share(g2), max_radius=50)
    assert n == 1 and isinstance(ents[0], Line) and ents[0].layer == LAYER_LINES
    assert isinstance(ents[1], Arc)


def test_stuecke_mit_schwankender_strichstaerke_werden_eine_linie():
    """Die Strichstärke wird je Stück gemessen und springt um eine Pixelstufe, dünn/dick wechselt
    dabei den Layer: trotzdem eine Linie, mit Layer und Stärke der längeren Stücke (0.45.10)."""
    from traceify.core.model import LAYER_THICK
    ents = [Line((0, 100), (198, 100), LAYER_LINES, None, "CONTINUOUS", 0.085),
            Line((202, 100), (300, 100), LAYER_THICK, None, "CONTINUOUS", 0.152),
            Line((200, 0), (200, 200))]
    assert cad.join_collinear(ents, 10) == 1 and len(ents) == 2
    assert ents[0].layer == LAYER_LINES and ents[0].lineweight == 0.085
    assert ents[0].p2[0] == pytest.approx(300, abs=0.5)
    # dreifache Stärke: verschiedene Linien
    ents = [Line((0, 100), (198, 100), LAYER_LINES, None, "CONTINUOUS", 0.085),
            Line((202, 100), (300, 100), LAYER_THICK, None, "CONTINUOUS", 0.254),
            Line((200, 0), (200, 200))]
    assert cad.join_collinear(ents, 10) == 0


def test_kurzes_abgeknicktes_endstueck_wird_durchgezogen():
    """Hinter der letzten Kreuzung knickt ein kurzes Endstück zum Knoten hin ~5° ab: liegt es ganz
    in der Querprobe, gehört es zur Linie (0.45.11). Ein langes Stück im gleichen Winkel nicht."""
    ents = [Line((0, 100), (198, 100)), Line((202, 100), (220, 101.5)), Line((200, 0), (200, 200))]
    assert cad.join_collinear(ents, 10) == 1 and len(ents) == 2
    assert abs(ents[0].p1[1] - ents[0].p2[1]) < 0.5
    ents = [Line((0, 100), (198, 100)), Line((202, 100), (300, 108.5)), Line((200, 0), (200, 200))]
    assert cad.join_collinear(ents, 10) == 0


def test_kurzes_stueck_am_massstern_mit_falscher_staerke_wird_durchgezogen():
    """Ein kurzes Stück an einer Kreuzung misst die Tinte des Maßsterns mit (0,254 statt 0,085): seine
    Stärke zählt nicht, die Linie läuft durch und bleibt dünn (0.45.13). Lange Stücke bleiben getrennt."""
    from traceify.core.model import LAYER_THICK
    ents = [Line((0, 100), (198, 100), LAYER_LINES, None, "CONTINUOUS", 0.085),
            Line((202, 100), (220, 100), LAYER_THICK, None, "CONTINUOUS", 0.254),
            Line((200, 0), (200, 200))]
    assert cad.join_collinear(ents, 10, short_len=30) == 1 and len(ents) == 2
    assert ents[0].layer == LAYER_LINES and ents[0].lineweight == 0.085
    ents = [Line((0, 100), (198, 100), LAYER_LINES, None, "CONTINUOUS", 0.085),
            Line((202, 100), (300, 100), LAYER_THICK, None, "CONTINUOUS", 0.254),
            Line((200, 0), (200, 200))]
    assert cad.join_collinear(ents, 10, short_len=30) == 0
