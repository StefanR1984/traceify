"""Am Textende abgeschnittene Raumnamen (0.40.2)."""
from traceify.core.lexicon import Lexicon, correct


def _fix(t):
    return correct(t, Lexicon(), sure=True)[0]


def test_abgeschnittenes_wortende_wird_ergaenzt():
    assert _fix("20 Putzka") == "20 Putzkammer"
    assert _fix("0.27 Drucke") == "0.27 Druckerpool"
    assert _fix("Abmes ungen gem.") == "Abmessungen gem."


def test_wortende_nur_wenn_eindeutig_und_am_ende():
    assert _fix("Putzka Raum") == "Putzka Raum"      # nicht am Textende
    assert _fix("Pod") == "Pod"                      # zu kurz
    assert _fix("2.04 Waschr.") == "2.04 Waschr."    # Abkürzung mit Punkt
    assert _fix("Treppenh.") == "Treppenh."
    assert _fix("2.04 Waschr") == "2.04 Waschr"      # Punkt nicht gelesen
    assert _fix("Lagerr") == "Lagerr"
    assert _fix("Klasse") == "Klasse"                # bekanntes Wort bleibt
    assert _fix("2.20 Büro") == "2.20 Büro"
