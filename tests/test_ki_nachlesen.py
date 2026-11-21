"""Tests für das Nachlesen unerkannter Schrift per KI (`core.text_slots`, `ai.assistant`).

Die KI ist durch eine Attrappe ersetzt – keine Verbindung zu Ollama oder vLLM nötig."""
import json
import threading

import cv2
import numpy as np
import pytest

from traceify.ai.assistant import TextFix, apply_text_fixes, read_unrecognized
from traceify.core import text_slots
from traceify.core.model import Drawing, Text

PX = 12.0   # Pixel pro mm


class FakeClient:
    """Attrappe für `OllamaClient.chat`: liefert der Reihe nach die Lesungen aus `reply`."""

    def __init__(self, reply):
        self.seq = [reply] if isinstance(reply, str) else list(reply)
        self.calls = []
        self.lock = threading.Lock()

    def chat(self, model, msgs, fmt=None, temperature=0.0, **kw):
        with self.lock:
            text = self.seq[len(self.calls) % len(self.seq)]
            self.calls.append(text)
        return json.dumps({"text": text, "sicher": True, "kopf": False})


def _bild():
    """Weiße Fläche mit „2.40“ (ohne Text im Drawing) und einer langen waagrechten Linie."""
    img = np.full((800, 400), 255, np.uint8)
    cv2.putText(img, "2.40", (300, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.9, 0, 2)
    cv2.line(img, (50, 210), (750, 210), 0, 2)
    return img


def _lesen(client, texts=(), workers=2):
    """Ruft `read_unrecognized` mit dem Testbild auf."""
    img = _bild()
    d = Drawing(width=800, height=400, scale=1 / 12, entities=list(texts))
    return read_unrecognized(client, "m", img, 255 - img, d, PX, workers=workers)


@pytest.mark.parametrize("roh, erwartet", [
    ("r 30 *", "30"),
    ("- 1.95^5 —", "1.95⁵"),
    ("21^{25}", "21²⁵"),
    ("1.13 Büro", "1.13 Büro"),
    ("2,40", "2.40"),
])
def test_normalize(roh, erwartet):
    assert text_slots.normalize(roh) == erwartet


def test_accept_gleiche_lesung_passt():
    assert text_slots.accept("2.40", "2.40", (0, 0, 40, 14)) == "2.40"


def test_accept_verschiedene_lesungen_werden_verworfen():
    assert text_slots.accept("2.40", "2.48", (0, 0, 40, 14)) is None


def test_accept_einstellige_zahl_wird_verworfen():
    assert text_slots.accept("6", "6", (0, 0, 9, 14)) is None


def test_accept_zu_lang_fuer_die_box():
    assert text_slots.accept("13.06", "13.06", (0, 0, 300, 14)) is None


def test_accept_senkrechte_box_dreht_breite_und_hoehe():
    assert text_slots.accept("2.40", "2.40", (0, 0, 14, 40)) == "2.40"


def test_is_sure():
    assert text_slots.is_sure(Text("2.83⁵", (0, 0), 10))
    assert not text_slots.is_sure(Text("LOL", (0, 0), 10))
    assert text_slots.is_sure(Text("Treppenhaus", (0, 0), 10))
    assert not text_slots.is_sure(Text("29+", (0, 0), 10))


def test_find_slots_findet_text_ohne_linie():
    boxen = text_slots.find_slots(_bild(), [], PX)
    assert any(290 <= x + w / 2 <= 380 and 170 <= y + h / 2 <= 215 for x, y, w, h in boxen)
    assert all(w <= 300 for _, _, w, _ in boxen)     # die lange Linie ist weg


def test_find_slots_sicherer_text_wird_ausgespart():
    boxen = text_slots.find_slots(_bild(), [Text("2.40", (300.0, 200.0), 18.0)], PX)
    assert not any(290 <= x + w / 2 <= 380 and 170 <= y + h / 2 <= 215 for x, y, w, h in boxen)


def test_nachlesen_gleiche_lesung_wird_uebernommen():
    fixes = _lesen(FakeClient("2.40"))
    treffer = [f for f in fixes if f.new == "2.40"]
    assert treffer
    f = treffer[0]
    assert f.is_new and f.sure
    assert f.entity.text == "2.40" and f.entity.angle == 0.0


def test_nachlesen_abweichende_lesung_wird_verworfen():
    # workers=1: zwei aufeinanderfolgende Aufrufe gehören immer zur selben Stelle
    fixes = _lesen(FakeClient(["2.40", "2.48"]), workers=1)
    assert not any(f.new in ("2.40", "2.48") for f in fixes)


def test_nachlesen_gegenprobe_verwirft_und_bestaetigt(monkeypatch):
    # Gegenprobe: Lesungen 1+2 gleich, Lesung 3 (anderer Rand) weicht ab.
    # Mit Lesung 4 gleich bleibt die Stelle, mit Lesung 3+4 abweichend wird sie verworfen.
    # Nur die Stelle lesen (alte Kandidaten haben keine Gegenprobe und verbrauchen Lesungen).
    monkeypatch.setattr("traceify.ai.assistant.unread_candidates", lambda *a, **k: [])
    monkeypatch.setattr(text_slots, "find_slots", lambda *a, **k: [(298, 181, 60, 20)])
    verworfen = _lesen(FakeClient(["2.40", "2.40", "2.48", "2.48"]), workers=1)
    assert not any(f.new in ("2.40", "2.48") for f in verworfen)
    bestaetigt = _lesen(FakeClient(["2.40", "2.40", "2.48", "2.40"]), workers=1)
    assert any(f.new == "2.40" for f in bestaetigt)


def test_nachlesen_leere_antwort_liefert_nichts():
    client = FakeClient("")
    fixes = _lesen(client)
    assert fixes == []
    assert len(client.calls) > 0


def test_nachlesen_ersetzt_unsichere_ocr():
    lol = Text("LOL", (300.0, 200.0), 18.0)
    fixes = _lesen(FakeClient("2.40"), [lol])
    treffer = [f for f in fixes if f.new == "2.40" and any(e is lol for e in f.drop)]
    assert treffer
    d = Drawing(width=800, height=400, scale=1 / 12, entities=[lol])
    _, neu, _ = apply_text_fixes(d, treffer)
    assert neu >= 1
    texte = [e.text for e in d.entities if isinstance(e, Text)]
    assert "LOL" not in texte and "2.40" in texte


def test_apply_korrigiert_nur_den_text():
    t = Text("2.4", (10.0, 20.0), 18.0)
    d = Drawing(width=800, height=400, scale=1 / 12, entities=[t])
    korrigiert, neu, _ = apply_text_fixes(d, [TextFix(t, "2.4", "2.40", True)])
    assert korrigiert == 1 and neu == 0
    assert t.text == "2.40" and t.position == (10.0, 20.0) and t.height == 18.0


def _kand(h):
    from traceify.core.textlines import Candidate
    return Candidate((200.0, 300.0), 0.0, 120.0, float(h), 5, np.zeros((0, 2)))


def test_handschrift_locker_verglichen_und_kleckse_ausgelassen(monkeypatch):
    # Handschrift: „FaB Keller“ und „Fabkeller“ sind dieselbe Lesung (0.40.4, image-4)
    monkeypatch.setattr(text_slots, "find_slots", lambda *a, **k: [])
    monkeypatch.setattr("traceify.ai.assistant.unread_candidates", lambda *a, **k: [_kand(30)])
    fixes = _lesen(FakeClient(["FaB Keller", "Fabkeller"]), workers=1)
    assert [f.new for f in fixes] == ["FaB Keller"]
    fixes = _lesen(FakeClient(["Heizraum", "Heizraum-\nAbluftschach"]), workers=1)
    assert [f.new for f in fixes] == ["Heizraum"]
    # unter 12 px Höhe gar nicht erst fragen (Kleckse, Modell erfindet Raumnamen)
    monkeypatch.setattr("traceify.ai.assistant.unread_candidates", lambda *a, **k: [_kand(9)])
    client = FakeClient("Küche")
    assert _lesen(client, workers=1) == [] and client.calls == []


def test_stellen_nur_bei_plots(monkeypatch):
    # graue Scan-Tinte (Wert 40): keine Maß-Stellen – auf Scans erfand das Modell „3.50“ (0.40.4)
    monkeypatch.setattr("traceify.ai.assistant.unread_candidates", lambda *a, **k: [])
    gefragt = []
    monkeypatch.setattr(text_slots, "find_slots", lambda *a, **k: gefragt.append(1) or [])
    img = np.where(_bild() < 128, 40, 255).astype(np.uint8)
    d = Drawing(width=800, height=400, scale=1 / 12, entities=[])
    read_unrecognized(FakeClient("2.40"), "m", img, 255 - img, d, PX, workers=1)
    assert not gefragt
    _lesen(FakeClient("2.40"), workers=1)
    assert gefragt


def test_einzelbuchstabe_nicht_plausibel():
    assert not text_slots.plausible("H", (0, 0, 20, 20))
    assert text_slots.plausible("WC", (0, 0, 30, 20))


def test_wiederholte_stellenlesung_ohne_ocr_faellt_weg(monkeypatch):
    # dreimal „3.50“ an verschiedenen Stellen, OCR hat es nirgends sicher gelesen (0.40.5, Plan 03)
    monkeypatch.setattr("traceify.ai.assistant.unread_candidates", lambda *a, **k: [])
    boxes = [(298, 181, 60, 20), (100, 500, 60, 20), (200, 650, 60, 20)]
    monkeypatch.setattr(text_slots, "find_slots", lambda *a, **k: boxes)
    assert _lesen(FakeClient("3.50"), workers=1) == []
    sicher = Text("3.50", (10.0, 390.0), 20.0, 0.0)
    fixes = _lesen(FakeClient("3.50"), texts=[sicher], workers=1)
    assert len(fixes) == 3
