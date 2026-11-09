"""Wörterbuch für Planbegriffe und Fransen-Entfernung (0.16)."""
import numpy as np

from traceify.core.cad import remove_spurs
from traceify.core.lexicon import Lexicon, correct
from traceify.core.model import Arc, Line


def _fix(t, lex=None):
    return correct(t, lex or Lexicon())[0]


def test_verstuemmelte_planbegriffe_werden_korrigiert():
    assert _fix("Schiafen") == "Schlafen"
    assert _fix("Kuche") == "Küche"
    assert _fix("KUCHE") == "KÜCHE"
    assert _fix("Dele") == "Diele"
    assert _fix("Deckenhohe 3000") == "Deckenhöhe 3000"
    assert _fix("Pos 06.1 Arbeitapletz") == "Pos 06.1 Arbeitsplatz"
    assert _fix("Pee 05 Siehtweh") == "Pos 05 Sichtwahl"
    assert _fix("BALKon") == "BALKON"


def test_zahlen_und_fremde_woerter_bleiben():
    assert _fix("WFL 23,40 qm") == "WFL 23,40 qm"
    assert _fix("Pos 0B 12") == "Pos 0B 12"          # Ziffern werden nie „korrigiert“
    assert _fix("Hamburg") == "Hamburg"
    assert _fix("Meier") == "Meier"
    # kurze Wörter nur mit gleichem Anfangsbuchstaben: „lüche“ wird nicht zu „Küche“
    assert _fix("Gesamt lüche") == "Gesamt lüche"


def test_normale_woerter_werden_nicht_verbogen():
    lex = Lexicon()
    normal = """Wohnung Gartenhaus Kirche Schule Bahnhof Strasse Treppenlift Kellner Bauer Stuhl
    Betten Gerade Pfosten Posten Kosten Trockenbau Lichtschacht Garagen Lagen Ansichten Schnitte
    Details Zimmern Hallen Schmidt Fischer Meier Müller Wagner Becker""".split()
    for w in normal:
        assert _fix(w, lex) == w, w
        assert correct(w, lex, sure=True)[0] == w, w
    # sicher gelesen: kein Vokaltausch („HALLO“ bleibt), aber Formfehler werden behoben
    assert correct("HALLO 123", lex, sure=True)[0] == "HALLO 123"
    assert correct("Schiafen 1", lex, sure=True)[0] == "Schlafen 1"
    assert correct("Kuche", lex, sure=True)[0] == "Küche"
    assert correct("Laber", lex, sure=True)[0] == "Laber"          # nur unsicher: „Labor“
    assert _fix("Laber", lex) == "Labor"


def test_planeigene_woerter_aber_keine_verleser():
    lex = Lexicon()
    lex.add_own(["Schiafen", "Fahrenberger"])
    assert "Fahrenberger" in lex
    assert "Schiafen" not in lex                       # zu ähnlich zu „Schlafen“
    assert _fix("Fahrenbergen", lex) == "Fahrenberger"
    assert _fix("Schiafen 1", lex) == "Schlafen 1"


def test_ohne_woerterbuch_keine_korrektur():
    from traceify.core.ocr import OcrSettings
    assert OcrSettings().dictionary
    assert OcrSettings(dictionary=False).dictionary is False


def test_schraegtext_wird_mit_woerterbuch_gerettet():
    from traceify.core.ocr import OcrSettings
    from traceify.core.textlines import Candidate, read_candidates
    pix = np.array([[x, y] for x in range(100, 220) for y in (50, 60)], float)
    c = Candidate((160.0, 55.0), 0.0, 120.0, 14.0, 9, pix)
    ink = np.zeros((200, 400), np.uint8)
    ink[pix[:, 1].astype(int), pix[:, 0].astype(int)] = 255

    def fake(crops, s):          # unsicher gelesen (40 %), aber eindeutig „Sichtwahl“
        return [("Pee 05 Siehtweh", 40.0)]
    s = OcrSettings()
    assert read_candidates([c], ink, s, run_ocr=fake)[0] == []
    tt, _ = read_candidates([c], ink, s, run_ocr=fake, lexicon=Lexicon())
    assert [t.text for t in tt] == ["Pos 05 Sichtwahl"]

    def junk(crops, s):          # unsicherer Zeichensalat bleibt draußen
        return [("Xqzv brnk", 40.0)]
    assert read_candidates([c], ink, s, run_ocr=junk, lexicon=Lexicon())[0] == []


def test_fransen_an_wandkante_werden_entfernt():
    wand = Line((0, 0), (200, 0))
    stummel = [Line((50, 0), (52, 5)), Line((120, 0.5), (118, -5))]
    ecke = Line((200, 0), (200, 6))        # kurzes Stück an einer Ecke bleibt
    weiter = Line((200, 0), (206, 0))      # Verlängerung bleibt
    strich = Line((80, 20), (84, 20))      # freistehender Strich bleibt
    quer = Line((150, -3), (150, 3))       # kreuzt die Wand (beide Enden frei) bleibt
    lang = Line((30, 0), (30, 40))         # lange Abzweigung bleibt
    ents = [wand, *stummel, ecke, weiter, strich, quer, lang]
    assert remove_spurs(ents, 8.0) == 2
    assert all(s not in ents for s in stummel)
    for e in (wand, ecke, weiter, strich, quer, lang):
        assert e in ents


def test_fransen_an_boegen_und_kurzen_objekten():
    bogen = Arc((0, 0), 100, 0, 90)
    st = Line((70.71, 70.71), (74.5, 74.5))   # Stummel mitten auf dem Bogen (radial)
    kurz = Line((300, 0), (310, 0))
    st2 = Line((305, 0), (305, 6))          # das andere Objekt ist kaum länger: bleibt
    ents = [bogen, st, kurz, st2]
    assert remove_spurs(ents, 8.0) == 1
    assert st not in ents and st2 in ents


def test_pipeline_option_fransen():
    from traceify.core.pipeline import ConvertSettings
    s = ConvertSettings()
    assert s.style.spurs_mm == 1.5
    d = s.to_dict() if hasattr(s, "to_dict") else None
    if d is not None:
        assert ConvertSettings.from_dict(d).style.spurs_mm == 1.5
