"""0.21.0: Dateien aufs Programmsymbol ziehen; Allplan-MTEXT (Drehung, Hochziffern) einlesen."""
import os
import sys
import uuid

import ezdxf
import pytest

from traceify.core.benchmark import words
from traceify.core.dxf_import import _convert
from traceify.core.model import Text

QtWidgets = pytest.importorskip("PySide6.QtWidgets")


def test_datei_an_laufende_instanz_weiterreichen():
    import subprocess
    import time
    from traceify.gui.single import forward, listen
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    name = "Traceify-Test-" + uuid.uuid4().hex[:8]
    assert not forward(["x.png"], name, timeout_ms=200)      # noch keine Instanz
    got = []
    srv = listen(got.extend, name)
    assert srv is not None
    # zweiter Start als eigener Prozess (wie beim Ablegen aufs Programmsymbol)
    code = ("import sys;from PySide6.QtCore import QCoreApplication;a=QCoreApplication([]);"
            "from traceify.gui.single import forward;"
            f"sys.exit(0 if forward(['C:\\\\Pläne\\\\a b.pdf','c.png'],{name!r}) else 3)")
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = subprocess.Popen([sys.executable, "-c", code], cwd=root,
                         env={**os.environ, "PYTHONIOENCODING": "utf-8"})
    t = time.time()
    while (p.poll() is None or not got) and time.time() - t < 20:
        app.processEvents()
    srv.close()
    assert p.returncode == 0
    assert got == ["C:\\Pläne\\a b.pdf", "c.png"]


def test_mehrere_dateien_starten_die_oberflaeche(tmp_path, monkeypatch):
    import traceify.__main__ as m
    import traceify.gui.app as gapp
    a, b = tmp_path / "a.png", tmp_path / "b.pdf"
    a.write_bytes(b"x")
    b.write_bytes(b"x")
    called = []
    monkeypatch.setattr(gapp, "main", lambda: called.append(1) or 0)
    monkeypatch.setattr(sys, "argv", ["traceify", str(a), str(b)])
    with pytest.raises(SystemExit):
        m.run()
    assert called == [1]


def test_ablegen_oeffnet_erste_unterstuetzte_datei(tmp_path, monkeypatch):
    from traceify.gui.main_window import MainWindow
    QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    w = MainWindow()
    opened = []
    monkeypatch.setattr(w, "open_file", lambda p, page=0: opened.append(p))
    w.open_dropped([str(tmp_path / "plan.dxf"), str(tmp_path / "scan.tif")])
    w.open_dropped([str(tmp_path / "notiz.txt")])
    assert opened == [str(tmp_path / "scan.tif")]
    w.close()


def _schrift(txt, size=40):
    """Schwarz auf Weiß gerendert; Box (x, y, w, h) der Ziffern ohne Hochziffer."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    f = ImageFont.truetype("arial.ttf", size, layout_engine=ImageFont.Layout.BASIC)
    im = Image.new("L", (600, 120), 255)
    ImageDraw.Draw(im).text((20, 90), txt, fill=0, font=f, anchor="ls")
    return np.asarray(im).copy(), f


def test_hochziffer_hinter_mass_wird_gelesen():
    pytest.importorskip("PIL")
    from traceify.core.ocr import OcrSettings, fix_superscripts
    try:
        g, f = _schrift("2.38⁵   3.76")
    except OSError:
        pytest.skip("Arial fehlt")
    import numpy as np
    ys, xs = np.nonzero(g < 128)
    w_main = int(f.getlength("2.38"))
    h = int(f.getbbox("2")[3] - f.getbbox("2")[1])
    top = int(ys.min())
    x3 = 20 + int(f.getlength("2.38⁵   "))
    raw = [((1, 1, 1), 20, top, w_main + 14, h, "2.38°", 70.0),         # Hochziffer als „°“
           ((1, 1, 1), x3, top, int(f.getlength("3.76")), h, "3.76", 95.0)]
    asked = []

    def fake(crops, s, extra=""):
        asked.append(len(crops))
        assert "whitelist" in extra
        return [("5", 90.0)] * len(crops)

    out = fix_superscripts(g, raw, OcrSettings(), fake)
    assert asked == [1]                                   # nur hinter 2.38 steht eine
    assert sorted(r[5] for r in out) == ["2.38⁵", "3.76"]
    # unsichere Nachlesung (mehrere Zeichen) ändert nichts
    out = fix_superscripts(g, raw, OcrSettings(), lambda c, s, e="": [("55", 90.0)])
    assert sorted(r[5] for r in out) == ["2.38°", "3.76"]


def test_allplan_mtext_drehung_hochziffer_ausrichtung():
    doc = ezdxf.new("R2010")
    msp = doc.modelspace()
    # Allplan: Richtung als Vektor (senkrecht), Mitte-Mitte, hochgestellte 5 als Stapel
    mt = msp.add_mtext(r"\A1;{\A1;{2.38\H0.165000;\S5^ ;}}",
                       dxfattribs={"char_height": 0.35, "insert": (10, 20),
                                   "attachment_point": 5})
    mt.dxf.text_direction = (0, 1, 0)
    msp.add_mtext("Be-\\Psprechung", dxfattribs={"char_height": 0.4, "insert": (0, 5),
                                                 "attachment_point": 1})
    out = []
    for e in msp:
        _convert(e, out)
    t = [e for e in out if isinstance(e, Text)]
    assert [x.text for x in t] == ["2.38⁵", "Be-", "sprechung"]
    assert t[0].angle == pytest.approx(90)
    # Mitte-Mitte, senkrecht: Grundlinie liegt rechts der Einfügung, Anfang darunter
    assert t[0].position[0] > 10 and t[0].position[1] < 20
    assert t[1].position[1] == pytest.approx(5 - 0.4)                 # oben links
    assert t[2].position[1] < t[1].position[1]                         # zweite Zeile darunter
    assert words(t[:1]) == {"2.385"}                                    # 2,38⁵ = 2.385
    assert os.path.basename(__file__)


def test_woerterbuch_streicht_keine_echten_buchstaben():
    from traceify.core.lexicon import Lexicon, correct
    lex = Lexicon(with_plan_words=False, words=["Kasse", "Schlafen"])
    assert correct("Klasse", lex, sure=True)[0] == "Klasse"       # kein „l“ wegstreichen
    assert correct("Schiafen", lex, sure=True)[0] == "Schlafen"   # Formverwechslung bleibt
