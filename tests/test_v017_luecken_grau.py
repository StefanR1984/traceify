"""Lücken nur mit Tinte im Scan schließen, schräge Texte zusätzlich aus Graustufen lesen (0.17)."""
import numpy as np

from traceify.core.cad import close_gaps, ink_checker
from traceify.core.model import Line


def _papier(w=200, h=120):
    return np.full((h, w), 250, np.uint8)


def test_luecke_mit_tinte_wird_geschlossen():
    g = _papier()
    g[58:63, 20:181] = 40               # durchgehender dicker Strich im Scan
    g[30:100, 150:154] = 40             # Querwand
    a = Line((20, 60), (138, 60))       # Skelett endet 12 px vor der Querwand
    wand = Line((152, 30), (152, 100))
    ents = [a, wand]
    assert close_gaps(ents, 4.0) == 0                       # zu weit für die normale Reichweite
    assert close_gaps(ents, 4.0, far=15.0, ink_ok=ink_checker(g)) == 1
    assert abs(a.p2[0] - 152) < 0.5


def test_weisse_luecke_bleibt_offen():
    g = _papier()
    g[58:63, 20:139] = 40               # Strich hört im Scan wirklich auf (z. B. Maßhilfslinie)
    g[30:100, 150:154] = 40
    a = Line((20, 60), (138, 60))
    ents = [a, Line((152, 30), (152, 100))]
    assert close_gaps(ents, 4.0, far=15.0, ink_ok=ink_checker(g)) == 0
    assert a.p2 == (138, 60)


def test_ohne_pruefung_bleibt_es_bei_der_normalen_reichweite():
    a = Line((20, 60), (138, 60))
    ents = [a, Line((152, 30), (152, 100))]
    assert close_gaps(ents, 4.0, far=15.0) == 0
    assert close_gaps(ents, 15.0) == 1


def test_schraegtext_wird_auch_aus_graustufen_gelesen():
    from traceify.core.ocr import OcrSettings
    from traceify.core.textlines import Candidate, read_candidates
    pix = np.array([[x, y] for x in range(100, 220) for y in (50, 60)], float)
    c = Candidate((160.0, 55.0), 0.0, 120.0, 14.0, 9, pix)
    ink = np.zeros((200, 400), np.uint8)
    ink[pix[:, 1].astype(int), pix[:, 0].astype(int)] = 255
    gray = 255 - ink
    calls = []

    def fake(crops, s):
        calls.append(crops[0].dtype)
        # Binärbild: Brei; Graustufen: sicher gelesen
        return [("Mas 11", 55.0)] if len(calls) <= 2 else [("Pos 11", 90.0)]
    tt, _ = read_candidates([c], ink, OcrSettings(), run_ocr=fake, gray=gray)
    assert len(calls) == 4                          # 2 Leserichtungen × (binär, grau)
    assert [t.text for t in tt] == ["Pos 11"]
    calls.clear()
    tt, _ = read_candidates([c], ink, OcrSettings(), run_ocr=fake)
    assert len(calls) == 2 and tt == []             # ohne Graubild wie bisher
