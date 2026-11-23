"""0.45.0: Punktlinien (Allplan-Linientyp PUNKT) – winzige Punkte in Reihe → Linie mit Linientyp DOT."""
import numpy as np

from traceify.core import dashes, truth
from traceify.core.model import LAYER_DASHED, Line
from traceify.core.pipeline import ConvertSettings, convert

PPM = 300 / 25.4          # px je mm (300 dpi)


def _punkte(img, p0, p1, step=20, r=1):
    n = int(np.hypot(p1[0] - p0[0], p1[1] - p0[1]) // step)
    for k in range(n + 1):
        x = int(round(p0[0] + (p1[0] - p0[0]) * k / n))
        y = int(round(p0[1] + (p1[1] - p0[1]) * k / n))
        img[y - r + 1:y + r, x - r + 1:x + r] = 0
    return img


def test_reihe_wird_punktlinie_raster_und_rauschen_nicht():
    bw = np.full((400, 600), 255, np.uint8)
    _punkte(bw, (40, 50), (540, 50), r=2)                                           # Punktlinie 3×3 px
    _punkte(bw, (40, 120), (40, 380), r=1)                                          # senkrecht, 1 px
    for y in range(200, 380, 20):                                                   # Punktraster
        _punkte(bw, (300, y), (560, y), r=2)
    rng = np.random.default_rng(1)                                                  # Rauschen
    for x, y in rng.integers((100, 150), (280, 380), size=(60, 2)):
        bw[y, x] = 0
    ink = (bw == 0).astype(np.uint8) * 255
    C = dashes.small_dots(ink, PPM)
    L = dashes.chain_dots(C, PPM)
    assert len(L) == 2, L
    assert all(l.linetype == "DOT" and l.layer == LAYER_DASHED for l in L)
    h = [l for l in L if abs(l.p1[1] - l.p2[1]) < 1][0]
    assert abs(h.p1[1] - 50) < 1 and min(h.p1[0], h.p2[0]) < 45 and max(h.p1[0], h.p2[0]) > 535


def test_fehlender_punkt_an_kreuzung_wird_uebersprungen():
    bw = np.full((100, 600), 255, np.uint8)
    _punkte(bw, (40, 50), (540, 50), r=2)
    bw[48:53, 238:243] = 255            # ein Punkt fehlt
    L = dashes.chain_dots(dashes.small_dots((bw == 0).astype(np.uint8) * 255, PPM), PPM)
    assert len(L) == 1 and abs(L[0].p1[0] - L[0].p2[0]) > 490


def test_pipeline_punktlinie_im_ergebnis():
    img = np.full((400, 700), 255, np.uint8)
    img[300:304, 50:650] = 0                         # normale Linie
    _punkte(img, (50, 100), (650, 100), r=2)
    res = convert(img, ConvertSettings(), dpi_scale=1.0 / PPM)
    dot = [e for e in res.drawing.entities if isinstance(e, Line) and e.linetype == "DOT"]
    assert len(dot) == 1 and abs(dot[0].p1[1] - 100) < 2
    assert any(isinstance(e, Line) and e.linetype != "DOT" and abs(e.p1[1] - 301.5) < 3
               for e in res.drawing.entities)


def test_wahrheit_punktlinie_gilt_als_gedruckt():
    img = _punkte(np.full((100, 600), 255, np.uint8), (40, 50), (540, 50), r=2)
    ink = ((img == 0) * 255).astype(np.uint8)        # Tinte = 255
    dot = Line((40, 50), (540, 50), "X", None, "PUNKT2_S9")
    voll = Line((40, 50), (540, 50))
    assert truth.printed([dot], ink) == [dot]
    assert truth.printed([voll], ink) == []


def test_zwei_parallele_punktlinien_bleiben():
    """PLAN1_OG1: zwei Punktlinien 1,4 mm nebeneinander sind kein Raster."""
    bw = np.full((150, 600), 255, np.uint8)
    _punkte(bw, (40, 50), (540, 50), step=14, r=2)
    _punkte(bw, (40, 66), (540, 66), step=14, r=2)
    L = dashes.chain_dots(dashes.small_dots((bw == 0).astype(np.uint8) * 255, PPM), PPM)
    assert len(L) == 2


def test_tonerstaub_und_doppelte_reihen():
    """Plan6_UG: Tonerstaub ergab schräge Scheinlinien; eine Reihe darf nur einmal entstehen."""
    rng = np.random.default_rng(3)
    bw = np.full((500, 500), 255, np.uint8)
    for x, y in rng.integers(10, 490, size=(900, 2)):
        bw[y, x] = 0
    assert dashes.chain_dots(dashes.small_dots((bw == 0).astype(np.uint8) * 255, PPM), PPM) == []
    bw = np.full((100, 600), 255, np.uint8)
    _punkte(bw, (40, 50), (540, 50), step=12, r=1)
    L = dashes.chain_dots(dashes.small_dots((bw == 0).astype(np.uint8) * 255, PPM), PPM)
    assert len(L) == 1
