"""Version 0.38.9: Türmaße und Maßpaare aus OCR-Zeilen (traceify/core/dimensions.py)."""
from traceify.core.dimensions import _split_off, merge, tidy_numbers
from traceify.core.model import Text


def test_tuerpaar_mit_kleiner_ocr_hoehe():
    # „101“ hat eine zu kleine OCR-Höhe (9,6 statt ~14); das Maß „2.75⁵“ steht darunter.
    # Breite 1,01 m, Höhe 2,75 m: eine Tür, also wird „101“ zu „1.01“.
    a = Text("101", (1982.0, 62.0), 9.6, 0.0)
    b = Text("2.75⁵", (1973.0, 85.0), 14.4, 0.0)
    tidy_numbers([a, b])
    assert a.text == "1.01"
    assert b.text == "2.75⁵"


def test_dreistellig_ohne_tuer_bleibt():
    # „250“ über „3.50“: 3,5 m ist weder Türbreite (0,55–1,5) noch Türhöhe (1,9–3,0) – bleibt.
    texts = [Text("250", (0.0, 0.0), 14.0, 0.0), Text("3.50", (0.0, 24.0), 14.0, 0.0)]
    tidy_numbers(texts)
    assert texts[0].text == "250"


def test_zwei_masse_in_einer_zeile_werden_getrennt():
    # OCR liest „25 1.01“ als eine Zeile; die Lückenzahl „25“ wird daraus herausgelöst.
    texts = [Text("25 1.01", (2737.0, 958.0), 12.8, 0.0)]
    boxes = [(2737, 942, 68, 16)]
    merge(texts, boxes, [Text("25", (2737.0, 958.0), 16.0, 0.0)], [(2737, 942, 20, 16)])
    namen = sorted(t.text for t in texts)
    assert namen == ["1.01", "25"], namen
    neu = next(t for t in texts if t.text == "1.01")
    assert 2755 <= neu.position[0] <= 2780, neu.position


def test_wort_neben_zahl_bleibt():
    # „Flur“ ist kein Maß: die Zahl wird nicht abgetrennt, der Text bleibt wie er ist.
    assert _split_off(Text("25 Flur", (0.0, 0.0), 12.0, 0.0), (0, 0, 60, 16), "25") is False
