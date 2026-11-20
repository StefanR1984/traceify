"""Automatische Bildaufbereitung (preprocess.auto) und gepunktete Raster ≠ Kies."""
import cv2
import numpy as np

from traceify.core.dots import find_dots, regular_share
from traceify.core.preprocess import PreprocessSettings, fill_speckle_holes, to_binary

PPM = 300 / 25.4


def _sprenkelwand(rng):
    """Schwarze Wand (5 mm breit) mit vielen weißen Sprenkeln, daneben ein „o“ und ein Symbol
    mit einer einzelnen, gezeichneten Aussparung."""
    bw = np.zeros((400, 600), np.uint8)
    bw[50:350, 50:110] = 255                          # Wand
    for y in range(54, 344, 9):                       # Sprenkel dicht an dicht, ungleich groß
        for x in range(54, 104, 9):
            jy, jx = (int(v) for v in rng.integers(0, 2, 2))
            h, w = ((1, 2), (2, 3), (4, 6), (6, 7))[int(rng.integers(0, 4))]
            bw[y + jy:y + jy + h, x + jx:x + jx + w] = 0
    cv2.circle(bw, (300, 200), 9, 255, 3)             # Buchstabe „o“ mit Innenraum
    bw[150:250, 400:500] = 255                        # Symbol: schwarzer Block …
    bw[190:205, 440:455] = 0                          # … mit einer Aussparung
    return bw


def test_sprenkel_in_wand_geschlossen_buchstaben_und_symbole_bleiben():
    bw = _sprenkelwand(np.random.default_rng(2))
    out = fill_speckle_holes(bw, PPM)
    vorher, nachher = ((x[50:350, 50:110] == 0).sum() for x in (bw, out))
    assert nachher < 0.85 * vorher                             # Wand dichter (nur ungleich große Sprenkel)
    assert out[200, 300] == 0                                  # Innenraum des „o“ bleibt
    assert (out[190:205, 440:455] == 0).all()                  # einzelne Aussparung bleibt
    assert (out[:, 130:] == bw[:, 130:]).all()


def test_gitter_und_schraffur_bleiben_offen():
    bw = np.zeros((300, 300), np.uint8)
    bw[20:280, 20:120] = 255                          # Treppenrost: gleich große Zellen
    for y in range(26, 276, 9):
        for x in range(26, 116, 9):
            bw[y:y + 5, x:x + 5] = 0
    bw[20:60, 150:290] = 255                          # Wand mit enger Schraffur (Lücken als Streifen)
    for k in range(-60, 160, 6):
        cv2.line(bw, (150 + k, 60), (190 + k, 20), 0, 2)
    bw[:, 140:150] = 0
    bw[:, 290:] = 0
    assert np.array_equal(fill_speckle_holes(bw, PPM), bw)


def test_auto_aus_laesst_binaerbild_wie_bisher():
    gray = 255 - _sprenkelwand(np.random.default_rng(3))
    alt = to_binary(gray, PreprocessSettings(auto=False), PPM)
    neu = to_binary(gray, PreprocessSettings(), PPM)
    ohne_aufloesung = to_binary(gray, PreprocessSettings())    # ohne px/mm: kein Füllen
    assert (neu[50:350, 50:110] == 255).mean() > (alt[50:350, 50:110] == 255).mean()
    assert np.array_equal(alt, ohne_aufloesung)


def test_gepunktetes_raster_ist_kein_kies():
    ppm = PPM
    g = np.full((900, 900), 255, np.uint8)
    step, cell = int(1.0 * ppm), int(4.5 * ppm)        # Punkte alle 1 mm, Raster 4,5 mm
    for k in range(40, 860, cell):
        for p in range(40, 860, step):
            cv2.circle(g, (p, k), 2, 0, -1)
            cv2.circle(g, (k, p), 2, 0, -1)
    circles, _ = find_dots(g, ppm)
    assert circles == []
    # Kies: zufällig verstreute Punkte bleiben Kies
    rng = np.random.default_rng(5)
    k = np.full((900, 900), 255, np.uint8)
    for _ in range(2500):
        cv2.circle(k, (int(rng.integers(30, 870)), int(rng.integers(30, 870))), 2, 0, -1)
    circles, _ = find_dots(k, ppm)
    assert len(circles) > 300
    pts = np.array([c.center for c in circles])
    assert regular_share(pts).mean() < 0.35
