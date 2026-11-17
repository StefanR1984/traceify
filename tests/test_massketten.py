"""Tests zu den Maßketten: Maßzahlen in Lücken der Maßlinie (0.23.0), zwischen Sternen,
über/unter der Linie und mit Hochziffer."""
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
    x, y, w, h = g[0][0][0]
    assert g[0][1] == 0 and 270 < x and x + w < 400 and y < 150 < y + h


def test_luecke_senkrecht_gefunden():
    img = _plan(vertical=True)                           # Text läuft von unten nach oben
    g = dimensions.line_gaps(img, 10.0)
    assert len(g) == 1 and g[0][1] == 1
    x, y, w, h = g[0][0][0]
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
    # „67“: zu kurz für die Box (Teil einer Zahl) → nichts
    for read, want in (("6.70", "6.70"), ("9295", None), ("Bad", None), ("67", None), ("6,70", "6.70")):
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


def _star(img, x, y):
    """Maßbegrenzung: Schrägstrich, Maßlinienstummel und Maßhilfslinie durch einen Punkt."""
    cv2.line(img, (x - 8, y + 8), (x + 8, y - 8), 1, 2)
    cv2.line(img, (x - 8, y), (x + 8, y), 1, 2)
    cv2.line(img, (x, y - 8), (x, y + 8), 1, 2)


def test_zahl_zwischen_sternen_ohne_masslinie():
    img = np.zeros((300, 700), np.uint8)                 # „✳74✳74✳“
    for x in (100, 250, 400):
        _star(img, x, 150)
    for x in (155, 305):
        cv2.putText(img, "74", (x, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 1, 2)
    assert len(dimensions._ticks(img, 10.0)[0]) == 3
    g = dimensions.line_gaps(img, 10.0)
    assert [(k, gap[3]) for gap, k in g] == [(0, 0), (0, 0)]
    gray = (255 - img * 255).astype(np.uint8)
    tt, _ = dimensions.read_gap_numbers(img, gray, 10.0, OcrSettings(),
                                        run_lines=lambda c, s, x: [("74", 90.0)] * len(c))
    assert [t.text for t in tt] == ["74", "74"]


def test_ziffern_sind_keine_sterne():
    img = np.zeros((200, 700), np.uint8)
    cv2.putText(img, "4714 1.47", (20, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 1, 2)
    cv2.putText(img, "4714 1.47", (350, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 1, 2)
    assert dimensions._ticks(img, 10.0)[0] == []


def test_zahlen_ueber_und_unter_der_linie():
    img = _plan("")                                      # nur Linie mit Lücke 270–400
    cv2.putText(img, "3.01", (285, 146), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 1, 2)
    cv2.putText(img, "3.00", (300, 173), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 1, 2)
    g = dimensions.line_gaps(img, 10.0)
    assert sorted(gap[3] for gap, _ in g) == [-1, 1]
    up = next(gap for gap, _ in g if gap[3] < 0)[0]
    lo = next(gap for gap, _ in g if gap[3] > 0)[0]
    assert up[1] + up[3] <= 150 <= lo[1]
    gray = (255 - img * 255).astype(np.uint8)
    crop = dimensions._crop(img, gray, lo, 0, 44, 1)     # die obere Zahl ist weggeschnitten
    assert crop[:3].min() > 200


def test_hochziffer_wird_angehaengt():
    img = _plan("4.17")
    cv2.putText(img, "5", (342, 156), cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1, 1)
    g = dimensions.line_gaps(img, 10.0)
    assert len(g) == 1 and g[0][0][2] is not None
    gray = (255 - img * 255).astype(np.uint8)
    # zweiter/dritter Fall: war keine Hochziffer; Randpunkt („4.17.“) ist nie eine Hochziffer
    for read, want in (("4.175", "4.17⁵"), ("4.17", "4.17"), ("4.17.", "4.17")):
        tt, bb = dimensions.read_gap_numbers(img, gray, 10.0, OcrSettings(),
                                             run_lines=lambda c, s, x, r=read: [(r, 90.0)] * len(c))
        assert [t.text for t in tt] == [want]
        sup = g[0][0][2]                                 # Box umfasst die Hochziffer nur, wenn gelesen
        assert (bb[0][0] + bb[0][2] >= sup[0] + sup[2]) == want.endswith("⁵")


@pytest.mark.skipif(not tesseract_available(), reason="Tesseract fehlt")
def test_mazahl_mit_maslinie_wird_gelesen():
    img = _plan("6.70")
    gray = (255 - img * 255).astype(np.uint8)
    texts, _ = recognize(gray, OcrSettings(), px_per_mm=10.0)
    assert "6.70" in [t.text for t in texts]


def _seg(t, L, conf=90.0, mid=True, side=0, sure=True):
    """Kandidat und Lücke für check_lengths: Maßsegment der Länge L ab x = 0."""
    x = L / 2.0 if mid else L / 5.0
    return [t if sure else None, t, conf], (None, None, None, side, (100.0, 0.0, float(L), x))


def test_laengenpruefung_masstab_aus_den_lesungen():
    r = 60.0                                             # Pixel je Meter
    rows = [_seg(t, metres * r) for t, metres in
            (("6.70", 6.70), ("2.35", 2.35), ("74", 0.74), ("2.12⁵", 2.125), ("88⁵", 0.885))]
    rows += [_seg("5.00", 0.5 * 5.00 * r),               # Segment zu kurz für die Zahl → weg
             _seg("7.10", 2 * 7.10 * r, mid=False),      # Stern verpasst → bleibt
             _seg("43⁵", 3 * 0.435 * r),                 # Segment zu lang beweist nichts → bleibt
             _seg("1875", 1.875 * r, conf=60, sure=False),  # Hochziffer voll gelesen → „1.87⁵“
             _seg("85", 0.885 * r, conf=60, sure=False),   # unter 1 m: geometrisch nicht trennscharf
             _seg("75", 0.75 * r, conf=40, sure=False),  # zu unsicher → nichts
             _seg("36", 1.8 * r, side=1)]                # unter der Linie (Höhe) → ungeprüft
    cand, gaps = [c for c, _ in rows], [g for _, g in rows]
    got = dimensions.check_lengths(cand, gaps, [0] * len(gaps))
    assert got == pytest.approx(r, rel=0.01)
    assert [c[0] for c in cand] == ["6.70", "2.35", "74", "2.12⁵", "88⁵", None, "7.10", "43⁵", "1.87⁵", None, None, "36"]


def test_laengenpruefung_ohne_einheitlichen_masstab():
    rows = [_seg(t, L) for t, L in (("6.70", 400), ("2.35", 300), ("74", 90), ("10", 400), ("5.00", 120))]
    cand, gaps = [c for c, _ in rows], [g for _, g in rows]
    assert dimensions.check_lengths(cand, gaps, [0] * 5) is None
    assert [c[0] for c in cand] == ["6.70", "2.35", "74", "10", "5.00"]


def test_meter_und_lesarten():
    assert dimensions.metres("6.70") == pytest.approx(6.70)
    assert dimensions.metres("74") == pytest.approx(0.74)
    assert dimensions.metres("88⁵") == pytest.approx(0.885)
    assert dimensions.metres("2.12⁵") == pytest.approx(2.125)
    assert dimensions.metres("9295") is None
    assert dimensions._variants("875") == ["875", "87⁵", "8.75"]
    assert dimensions._variants("2885") == ["28.85", "2.88⁵"]
    # Punkt am Rand (Rest von Maßlinie/Pfeilspitze) darf keinen ValueError auslösen
    assert dimensions._variants("2.45.") == dimensions._variants("2.45")
    assert dimensions._variants("1.87.") == dimensions._variants("1.87")
    assert dimensions._variants(".245") == dimensions._variants("245")
    assert dimensions._variants("..") == []


def test_masslinie_am_text_und_als_dimension(tmp_path):
    import ezdxf
    from traceify.core.model import Drawing
    from traceify.export.dxf import export_dxf
    img = np.zeros((300, 700), np.uint8)                 # „✳74✳“ waagrecht und senkrecht
    for x in (100, 250):
        _star(img, x, 150)
    cv2.putText(img, "74", (155, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 1, 2)
    for vertical in (False, True):
        bw = np.ascontiguousarray(np.rot90(img, 1)) if vertical else img
        gray = (255 - bw * 255).astype(np.uint8)
        tt, _ = dimensions.read_gap_numbers(bw, gray, 10.0, OcrSettings(),
                                            run_lines=lambda c, s, x: [("74", 90.0)] * len(c))
        assert len(tt) == 1 and tt[0].dim is not None
        p0, p1 = tt[0].dim_points()
        if vertical:                                     # rot90: (x, y) → (y, 700 - x)
            assert p0 == pytest.approx((150, 600), abs=2) and p1 == pytest.approx((150, 450), abs=2)
        else:
            assert p0 == pytest.approx((100, 150), abs=2) and p1 == pytest.approx((250, 150), abs=2)
        d = Drawing(bw.shape[1], bw.shape[0], 0.1, tt)
        export_dxf(d, str(tmp_path / "m.dxf"))
        dims = list(ezdxf.readfile(str(tmp_path / "m.dxf")).modelspace().query("DIMENSION"))
        assert len(dims) == 1 and dims[0].dxf.text == "74"
        assert dims[0].get_measurement() == pytest.approx(15.0, abs=0.3)   # 150 px × 0,1 mm
        export_dxf(d, str(tmp_path / "r12.dxf"), "R12")  # R12 kennt keine Bemaßung → TEXT
        assert [e.dxftype() for e in ezdxf.readfile(str(tmp_path / "r12.dxf")).modelspace()] == ["TEXT"]


def test_masslinie_folgt_dem_text():
    from traceify.core.edit import rotate
    t = Text("6.70", (100, 210), 20, 0.0, dim=(-5.0, 15.0, 0.5))
    flat = lambda t: [v for p in t.dim_points() for v in p]
    assert flat(t) == pytest.approx([0, 200, 400, 200])
    r = rotate(t, (0, 0), -90)                           # Bild: gegen den Uhrzeigersinn
    assert r.angle == 90 and flat(r) == pytest.approx([200, 0, 200, -400])


def test_kleines_mass_ueber_engem_sternpaar():
    img = np.zeros((300, 900), np.uint8)
    for x in (60, 210, 360):                             # „✳74✳74✳“ für die Schrifthöhe
        _star(img, x, 150)
    for x in (115, 265):
        cv2.putText(img, "74", (x, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 1, 2)
    _star(img, 500, 150)                                 # dazu „74“ für die dritte Zahl
    cv2.putText(img, "74", (405, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 1, 2)
    for x in (640, 662):                                 # enges Paar, „24“ darüber
        _star(img, x, 150)
    cv2.putText(img, "24", (632, 136), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 1, 2)
    g = [gap for gap, k in dimensions.line_gaps(img, 10.0) if gap[4] and len(gap[4]) > 4]
    assert len(g) == 1 and g[0][3] == -1
    x, y, w, h = g[0][0]
    assert x < 651 < x + w and y + h < 150


def test_laengenpruefung_kleines_mass_ueber_sternpaar():
    r = 60.0
    rows = [_seg(t, metres * r) for t, metres in
            (("6.70", 6.70), ("2.35", 2.35), ("3.01", 3.01), ("2.12⁵", 2.125), ("1.88⁵", 1.885))]
    pair = lambda t, L, **kw: ([t, t, 90.0], (None, None, None, -1, (100.0, 0.0, float(L), L / 2, True)))
    rows += [pair("24", 0.24 * r),                       # passt
             pair("74", 0.24 * r),                       # passt nicht zum Abstand → weg
             pair("24³", 0.24 * r)]                      # fremde Hochziffer → abgestreift
    cand, gaps = [c for c, _ in rows], [g for _, g in rows]
    dimensions.check_lengths(cand, gaps, [0] * len(gaps))
    assert [c[0] for c in cand[5:]] == ["24", None, "24"]


def _ziffern():
    """Schablonen 0–9 (Höhe TPL_H) aus der OpenCV-Schrift."""
    tpl = {}
    for ch in "0123456789":
        img = np.zeros((80, 80), np.uint8)
        cv2.putText(img, ch, (15, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.5, 1, 3)
        ys, xs = np.nonzero(img)
        c = img[ys.min():ys.max() + 1, xs.min():xs.max() + 1].astype(np.float32)
        tpl[ch] = cv2.resize(c, (int(round(c.shape[1] * dimensions.TPL_H / c.shape[0])), dimensions.TPL_H),
                             interpolation=cv2.INTER_AREA)
    return tpl


def _tuer(tpl, strich=True):
    """Türmaß an einem Stern (100, 150): „88⁵“ über der Linie, „2.12“ darunter, 100 px je Meter;
    der zweite Stern (188) ist nur ein Strich, die „2“ der Höhe läuft darüber."""
    hs, img = 20, np.zeros((300, 400), np.uint8)
    tp = {ch: dimensions._scaled(t, hs) for ch, t in tpl.items()}
    cw, pitch = max(t.shape[1] for t in tp.values()), dimensions.DIGIT_W * hs

    def put(ch, x, top, glyphs=tp):
        g = glyphs[ch]
        x += (cw - g.shape[1]) // 2
        img[top:top + g.shape[0], x:x + g.shape[1]] |= g.astype(np.uint8)
    cv2.line(img, (60, 150), (330, 150), 1, 2)
    _star(img, 100, 150)
    if strich:
        cv2.line(img, (188, 142), (188, 158), 1, 2)
    x0 = int(144 - (pitch + cw) / 2)                     # „88“ mittig zwischen 100 und 188
    for i in range(2):
        put("8", x0 + int(round(i * pitch)), 150 - 3 - hs)
    put("5", x0 + int(pitch) + cw - 3, 150 - 3 - hs - 5, {"5": dimensions._scaled(tpl["5"], 12)})
    for ch, o in zip("212", (0, 1.5, 2.5)):
        put(ch, 130 + int(round(o * pitch)), 154)
    img[170:173, 130 + int(1.1 * pitch):130 + int(1.1 * pitch) + 3] = 1      # Dezimalpunkt
    return img


def test_tuermass_per_schablone():
    tpl = _ziffern()
    img = _tuer(tpl)
    ticks, stars = dimensions._ticks(img, 10.0)
    assert [round(x) for x, _ in ticks] == [100]         # der zweite Stern ist keiner
    hor = cv2.morphologyEx(img, cv2.MORPH_OPEN, np.ones((1, 30), np.uint8))
    got = dimensions.template_numbers(img, ticks, stars | hor, 10.0, tpl, [20], 100.0)
    assert sorted(t for t, *_ in got) == ["2.12", "88⁵"]
    assert len({g[4] for g in got}) == 1                 # Breite und Höhe: dasselbe Sternpaar
    (x, y, w, h), = [b for t, b, *_ in got if t == "88⁵"]
    assert 100 < x and x + w < 215 and y + h <= 150
    # ohne Strich am anderen Ende passt die Breite zu nichts; Sternseite schon belegt → nichts
    assert dimensions.template_numbers(_tuer(tpl, False), ticks, stars | hor, 10.0, tpl, [20], 100.0) == []
    done = [(ticks[0][0], ticks[0][1], 1)]
    assert dimensions.template_numbers(img, ticks, stars | hor, 10.0, tpl, [20], 100.0, done) == []
    assert dimensions.template_numbers(img, ticks, stars | hor, 10.0, tpl, [20], 60.0) == []   # falscher Maßstab
    # nur unsicherer Ausgangspunkt (von Ziffern überdeckter Stern) reicht ebenso
    weak = dimensions.template_numbers(img, [], stars | hor, 10.0, tpl, [20], 100.0, extra=ticks)
    assert sorted(t for t, *_ in weak) == ["2.12", "88⁵"]


def test_massstab_aus_massketten():
    from traceify.core.model import Drawing
    from traceify.core.pipeline import ConvertSettings, apply_auto_scale
    # 1:200 bei 300 dpi: 1 m = 5 mm Papier = 59,06 px
    mm = 25.4 / 300
    r = 5.0 / mm
    texts = [Text(t, (0.0, 0.0), 10.0, 0.0, dim=(0.0, metres * r / 10.0, 0.5))
             for t, metres in (("6.70", 6.70), ("2.35", 2.35), ("74", 0.74), ("2.12⁵", 2.125), ("3.01", 3.01))]
    assert dimensions.scale_from_dims(texts, mm) == 200
    assert dimensions.scale_from_dims(texts[:4], mm) is None          # zu wenige
    d = Drawing(100, 100, mm, texts + [Text("M 1:100", (0, 0), 10)])
    apply_auto_scale(d, ConvertSettings())
    assert d.scale == pytest.approx(mm * 200)
    assert d.meta["massstab"] == "1:200" and "Plan nennt 1:100" in d.meta["massstab_quelle"]


def test_fette_schrift_ausduennen():
    """Fette Schablonenschrift (Strich ~ ¼ der Höhe) wird ausgedünnt, normale bleibt (0.38)."""
    import cv2
    import numpy as np
    from traceify.core.ocr import thin_bold

    def glyphs(t):                                         # 30 „H“, 40 px hoch, Strich t px
        img = np.zeros((100, 1600), np.uint8)
        for i in range(30):
            x = 20 + 50 * i
            cv2.line(img, (x, 30), (x, 70), 255, t)
            cv2.line(img, (x + 24, 30), (x + 24, 70), 255, t)
            cv2.line(img, (x, 50), (x + 24, 50), 255, t)
        return img
    ppm = 11.8                                             # 300 dpi
    bold, thin = glyphs(11), glyphs(4)
    out = thin_bold(bold, ppm)
    assert 0 < (out > 0).sum() < 0.7 * (bold > 0).sum()    # dünner, aber nicht weg
    assert np.array_equal(thin_bold(thin, ppm), thin)       # normale Schrift unverändert


def test_gui_schalter_fette_schrift():
    """Häkchen „Fette Schrift ausdünnen“ per Mausklick → OcrSettings.thin_bold."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QtWidgets = pytest.importorskip("PySide6.QtWidgets")
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from traceify.gui.main_window import MainWindow
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    w = MainWindow()
    w.show()
    cb = w.panel.ocr_bold
    w.panel.ensureWidgetVisible(cb)
    app.processEvents()
    assert cb.isChecked() and w.panel.settings().ocr.thin_bold
    QTest.mouseClick(cb, Qt.LeftButton, Qt.NoModifier, QPoint(8, cb.height() // 2))
    app.processEvents()
    assert not cb.isChecked() and not w.panel.settings().ocr.thin_bold
    w.close()
