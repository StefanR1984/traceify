"""Tests mit echtem Ollama und echtem ODA File Converter.

Laufen nur, wenn TRACEIFY_ECHT=1 gesetzt ist – über den Workflow „Integration (echt)“
(.github/workflows/integration.yml), der beides auf einem Windows-Runner installiert.
Im normalen Testlauf werden sie übersprungen (dort gibt es nur Attrappen).
"""
import os

import cv2
import numpy as np
import pytest

pytestmark = pytest.mark.skipif(os.environ.get("TRACEIFY_ECHT") != "1",
                                reason="nur im Workflow „Integration (echt)“")

MODEL = os.environ.get("TRACEIFY_MODELL", "gemma3:4b")


def _client():
    from traceify.ai import OllamaClient
    return OllamaClient(os.environ.get("OLLAMA_HOST_URL", "http://127.0.0.1:11434"), 900)


def _plan():
    img = np.full((700, 1000), 255, np.uint8)
    cv2.rectangle(img, (60, 60), (940, 640), 0, 6)
    cv2.line(img, (500, 60), (500, 640), 0, 6)
    cv2.putText(img, "KUECHE", (150, 330), cv2.FONT_HERSHEY_SIMPLEX, 1.6, 0, 4)
    cv2.putText(img, "Keller", (600, 360), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 2.2, 0, 3)
    return img


def test_ollama_laeuft_und_modell_ist_da():
    c = _client()
    assert c.version()
    names = [m.get("name", "") for m in c.list_models()]
    assert any(n.startswith(MODEL.split(":")[0]) for n in names), names


def test_ollama_einstellungen_vorschlagen():
    from traceify.ai import suggest_settings
    sug = suggest_settings(_client(), MODEL, _plan())
    assert isinstance(sug, dict) and sug.get("modus") in ("mittellinie", "umriss")


def test_ollama_liest_unerkannte_schrift():
    """Handschriftähnliches Wort ohne OCR: die KI soll es lesen."""
    from traceify.ai import read_unrecognized
    from traceify.core.model import Drawing
    from traceify.core.preprocess import PreprocessSettings, to_binary
    img = _plan()
    bw = to_binary(img, PreprocessSettings())
    d = Drawing(width=img.shape[1], height=img.shape[0], scale=25.4 / 150, entities=[])
    fixes = read_unrecognized(_client(), MODEL, img, bw, d, 150 / 25.4, limit=10)
    texts = " ".join(f.new.lower() for f in fixes)
    assert "kel" in texts or "küche" in texts or "kueche" in texts, texts


def test_ollama_chat_antwortet_mit_aktionen():
    from traceify.ai import Assistant
    a = Assistant(_client(), MODEL)
    res = a.ask("Stelle die Toleranz auf 3 ein.")
    assert "antwort" in res and isinstance(res.get("aktionen"), list)


def test_oda_dwg_hin_und_zurueck(tmp_path):
    """DXF -> DWG mit dem echten ODA File Converter und wieder zurück nach DXF."""
    import subprocess

    import ezdxf

    from traceify.core.model import Circle, Drawing, Line, Text
    from traceify.export import dwg
    oda = dwg.find_oda()
    if not oda:
        pytest.fail("ODA File Converter wurde nicht installiert")
    d = Drawing(width=1000, height=700, scale=0.5, entities=[
        Line((10, 10), (900, 10)), Line((10, 10), (10, 600)), Circle((400, 300), 120),
        Text("TEST 123", (100, 200), 20)])
    out = tmp_path / "plan.dwg"
    dwg.export_dwg(d, str(out), "R2018", oda=oda)
    assert out.is_file() and out.stat().st_size > 1000
    back = tmp_path / "zurueck"
    back.mkdir()
    subprocess.run([oda, str(tmp_path), str(back), "ACAD2018", "DXF", "0", "1", "*.DWG"],
                   check=True, timeout=180)
    dxf = ezdxf.readfile(str(back / "plan.dxf"))
    types = [e.dxftype() for e in dxf.modelspace()]
    assert types.count("LINE") == 2 and types.count("CIRCLE") == 1
    assert any(t in ("TEXT", "MTEXT") for t in types)
