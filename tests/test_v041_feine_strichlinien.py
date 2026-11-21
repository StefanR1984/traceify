"""Feine Strichlinien aus Strichen < 0,8 mm (0.41.0, Befund Plan4/Plan5)."""
import math

import cv2
import numpy as np

from traceify.core.dashes import JOIN_MM, chain_dashes, drop_covered, join_chains, small_dashes
from traceify.core.model import LAYER_DASHED, Line, Polyline
from traceify.core.pipeline import ConvertSettings, convert

PPM = 11.8   # 300 dpi


def _strichlinie(img, p0, p1, strich=5, luecke=5, dicke=2):
    """Strichlinie wie im Scan: kurze Striche (5 × 2 px), Lücken 5 px (bei 4 px verschmelzen schräge
    Striche teils beim Rastern – solche Doppelstriche sind zu lang und unterbrechen die Reihe)."""
    L = math.dist(p0, p1)
    ux, uy = (p1[0] - p0[0]) / L, (p1[1] - p0[1]) / L
    t = 0.0
    while t + strich <= L:
        a = (int(round(p0[0] + t * ux)), int(round(p0[1] + t * uy)))
        b = (int(round(p0[0] + (t + strich) * ux)), int(round(p0[1] + (t + strich) * uy)))
        cv2.line(img, a, b, 0, dicke)
        t += strich + luecke


def _bild():
    g = np.full((400, 600), 255, np.uint8)
    _strichlinie(g, (50, 100), (500, 100))            # waagrecht
    _strichlinie(g, (60, 150), (400, 330))            # schräg
    cv2.line(g, (300, 40), (300, 160), 0, 3)          # kreuzt die waagrechte → Kette unterbrochen
    rng = np.random.default_rng(3)                    # verstreute Rauschpunkte: keine Linie
    for x, y in zip(rng.integers(440, 590, 60), rng.integers(180, 390, 60)):
        cv2.line(g, (int(x), int(y)), (int(x) + 3, int(y) + 1), 0, 1)
    return g


def test_kleine_striche_werden_strichlinien():
    bw = 255 - _bild()
    _, bw = cv2.threshold(bw, 127, 255, cv2.THRESH_BINARY)
    d = small_dashes(bw, PPM)
    assert len(d) > 60
    lines = join_chains(chain_dashes(d), JOIN_MM * PPM)
    assert all(l.layer == LAYER_DASHED and l.linetype == "DASHED" for l in lines)
    waag = [l for l in lines if abs(l.p1[1] - l.p2[1]) < 3]
    assert len(waag) == 1                              # über die Kreuzung hinweg eine Linie
    xs = sorted((waag[0].p1[0], waag[0].p2[0]))
    assert xs[0] < 60 and xs[1] > 490
    schraeg = [l for l in lines if l not in waag]
    assert len(schraeg) == 1
    w = math.degrees(math.atan2(schraeg[0].p2[1] - schraeg[0].p1[1], schraeg[0].p2[0] - schraeg[0].p1[0]))
    assert abs(abs(w) - math.degrees(math.atan2(180, 340))) < 1.5


def test_lange_luecke_und_unregelmaessige_reihe_nicht():
    # zwei Reihen auf einer Geraden, 60 px (5 mm) Abstand: zwei Linien
    a = Line((0, 0), (100, 0), LAYER_DASHED, None, "DASHED")
    b = Line((160, 0.5), (300, 0.5), LAYER_DASHED, None, "DASHED")
    assert len(join_chains([a, b], JOIN_MM * PPM)) == 2
    c = Line((110, 0.3), (150, 0.3), LAYER_DASHED, None, "DASHED")
    assert len(join_chains([a, b, c], JOIN_MM * PPM)) == 1
    # nur 4 Striche: zu wenig
    assert chain_dashes([Line((i * 9.0, 0), (i * 9.0 + 5, 0)) for i in range(4)]) == []


def test_reste_auf_der_strichlinie_fallen_weg():
    neu = [Line((0, 0), (200, 0), LAYER_DASHED, None, "DASHED")]
    rest = Line((20, 0.8), (31, 0.4))
    poly = Polyline([(50, 0), (55, 1), (60, 0)])
    weg = Line((20, 5), (40, 5))
    lang = Line((-50, 0), (250, 0))                   # ragt über die Strichlinie hinaus
    out = drop_covered([rest, poly, weg, lang], neu, 1.8)
    assert out == [weg, lang]


def test_pipeline_feine_strichlinie():
    s = ConvertSettings()
    s.ocr.enabled = False
    res = convert(_bild(), s, dpi_scale=1 / PPM)
    gestr = [e for e in res.drawing.entities if isinstance(e, Line) and e.linetype == "DASHED"]
    assert len(gestr) >= 2
    s.style.detect_dashed = False
    res = convert(_bild(), s, dpi_scale=1 / PPM)
    assert not [e for e in res.drawing.entities if getattr(e, "linetype", "") == "DASHED"]


def test_genauigkeit_zaehlt_luecken_von_strichlinien_nicht():
    from traceify.core.quality import assess
    g = np.full((200, 400), 255, np.uint8)
    _strichlinie(g, (20, 50), (380, 50), strich=6, luecke=30)      # Lücken weit über der Toleranz
    ink = (g < 128).astype(np.uint8) * 255
    gestr = Line((20, 50), (380, 50), LAYER_DASHED, None, "DASHED")
    assert assess(ink, [gestr]).precision > 0.99
    # als durchgezogene Linie zählen die Lücken weiter als daneben
    assert assess(ink, [Line((20, 50), (380, 50))]).precision < 0.9
    # Strichlinie auf leerem Papier ist überflüssig
    falsch = Line((20, 150), (380, 150), LAYER_DASHED, None, "DASHED")
    assert assess(ink, [gestr, falsch]).precision < 0.6
    # feine Striche fehlen im entfleckten Bild: mit dem rohen Bild zählt die Linie wieder als richtig
    entfleckt = np.zeros_like(ink)
    entfleckt[150, 10:390] = 255                                # nur eine andere Linie übrig
    wand = Line((10, 150), (389, 150))
    assert assess(entfleckt, [wand, gestr]).precision < 0.6
    assert assess(entfleckt, [wand, gestr], dash_ink=ink).precision > 0.99
