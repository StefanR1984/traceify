"""Blasse Graulinien aus Rasterpunkten ergänzen (0.42.0, Befund Plan5_EG)."""
import numpy as np

from traceify.core.preprocess import PreprocessSettings, add_pale_lines, to_binary

PPM = 11.8   # 300 dpi


def _bild():
    g = np.full((300, 400), 255, np.uint8)
    g[50:52, 40:360] = 0                   # schwarze Linie
    g[149:152, 40:360:2] = 170             # graue Linie aus Rasterpunkten (heller als die Schwelle)
    g[199:202, 40:360:2] = 170
    g[230:300, 200:300] = 200              # graue Fläche – keine Linie
    g[100, 100:104:2] = 190                # Punkt unter 1 mm – Schmutz
    return g


def test_blasse_linie_kommt_dazu():
    g = _bild()
    alt = to_binary(g, PreprocessSettings(threshold=128, auto=False, despeckle=0))
    assert alt[149:152].sum() == 0         # Schwelle verliert die graue Linie
    neu = to_binary(g, PreprocessSettings(threshold=128), PPM)
    assert (neu[148:154, 40:360].max(axis=0) > 0).mean() > 0.95   # durchgehend
    assert neu[198:204, 40:360].max() > 0


def test_flaeche_und_schmutz_bleiben_weg():
    g = _bild()
    bw = to_binary(g, PreprocessSettings(threshold=128, auto=False, despeckle=0))
    neu = add_pale_lines(g, bw, PPM)
    assert neu[240:290, 210:290].max() == 0
    assert neu[95:106, 95:110].max() == 0


def test_halo_dunkler_linie_wird_nicht_breiter():
    g = _bild()
    g[49, 40:360] = 200                    # heller Rand an der schwarzen Linie
    g[52, 40:360] = 200
    bw = to_binary(g, PreprocessSettings(threshold=128, auto=False, despeckle=0))
    neu = add_pale_lines(g, bw, PPM)
    assert np.array_equal(neu[40:60], bw[40:60])
