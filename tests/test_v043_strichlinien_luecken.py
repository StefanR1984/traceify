"""Strichlinien mit an Kreuzungen verschluckten Strichen (0.43.0, Befund Plan5/Plan7)."""
import cv2
import numpy as np

from traceify.core.model import LAYER_DASHED, Line
from traceify.core.pipeline import ConvertSettings, convert
from traceify.core.style import StyleSettings, detect_dashed


def _striche(x0, x1, strich, luecke, y=100.0, fehlt=()):
    out, x, i = [], x0, 0
    while x + strich <= x1:
        if i not in fehlt:
            out.append(Line((x, y), (x + strich, y)))
        x += strich + luecke
        i += 1
    return out


def test_ein_fehlender_strich_trennt_die_reihe_nicht():
    st = StyleSettings()
    ents = _striche(0, 700, 12, 18, fehlt=(3, 6, 9, 12, 15, 18))   # Lücke 48 statt 18
    assert len(detect_dashed(ents, st)) > 1                        # erster Durchgang: getrennt
    out = detect_dashed(ents, st, skip_missing=True)
    d = [e for e in out if e.layer == LAYER_DASHED]
    assert len(d) == 1 and len(out) == 1
    assert d[0].p1[0] < 1 and d[0].p2[0] > 650


def test_zwei_fehlende_striche_trennen():
    st = StyleSettings()
    ents = _striche(0, 300, 12, 18) + _striche(390, 700, 12, 18)   # Lücke ≈ 3 Lücken + 2 Striche
    out = detect_dashed(ents, st, skip_missing=True)
    assert len([e for e in out if e.layer == LAYER_DASHED]) == 2


def test_blasse_strichlinie_ueber_kreuzungen():
    g = np.full((400, 900), 255, np.uint8)
    for x in range(60, 840, 30):
        g[199:202, x:x + 16:2] = 170                       # blasse Rasterstriche
    for x in range(100, 840, 90):
        cv2.line(g, (x, 120), (x, 280), 0, 2)              # Querlinien verschlucken Striche
    s = ConvertSettings()
    s.ocr.enabled = False
    ents = convert(g, s, 25.4 / 300).drawing.entities
    d = [e for e in ents if isinstance(e, Line) and e.linetype != "CONTINUOUS"]
    assert len(d) == 1
    assert min(d[0].p1[0], d[0].p2[0]) < 70 and max(d[0].p1[0], d[0].p2[0]) > 780
