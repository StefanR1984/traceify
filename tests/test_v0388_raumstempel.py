"""Raumstempel auf Allplan-Plots: typische Verleser und zerschnittene Wörter (0.38.8)."""
from traceify.core.lexicon import Lexicon, correct


def _fix(t, sure=True):
    return correct(t, Lexicon(), sure=sure)[0]


def test_bueroverleser_werden_korrigiert():
    assert _fix("2.16 Bure") == "2.16 Büro"
    assert _fix("2.12 Biro") == "2.12 Büro"
    assert _fix("Buro-") == "Büro-"
    assert _fix("BURE") == "BÜRO"


def test_l_und_t_sind_formverwechslung():
    assert _fix("1.28 Beralung") == "1.28 Beratung"
    assert _fix("1.09 Teekuche") == "1.09 Teeküche"
    for w in ("Halle", "Kalt", "Bett", "Platz", "Gast", "Stall", "Leiter", "Hotel"):
        assert _fix(w) == w, w


def test_vom_tuerbogen_zerschnittene_woerter():
    assert _fix("2.13 Druck pool") == "2.13 Druckerpool"
    assert _fix("0.28 Putz mmer") == "0.28 Putzkammer"
    assert _fix("1.24 Put ammer") == "1.24 Putzkammer"
    # zwei bekannte Wörter oder nichts dazwischen: nicht zusammenziehen
    assert _fix("Putz Raum") == "Putz Raum"
    assert _fix("Bad Zimmer") == "Bad Zimmer"
    assert _fix("Abstell Raum") == "Abstell Raum"
    # Zahlen bleiben, auch zwischen Wortstücken
    assert _fix("0 21a Flur") == "0 21a Flur"
    assert _fix("121WCD") == "121WCD"
