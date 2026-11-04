"""Tests: Qualitätsampel, Symbole/Blöcke, Symbol-Bibliothek, KI-Stapelregeln."""
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import pytest

import traceify as tf
from traceify.core import quality as Q
from traceify.core import symbols as S


def _settings():
    s = tf.ConvertSettings()
    s.ocr.enabled = False
    return s


# ------------------------------------------------------------------ Qualität
def test_quality_green_and_red():
    img = np.full((500, 800), 255, np.uint8)
    cv2.rectangle(img, (50, 50), (750, 450), 0, 3)
    cv2.circle(img, (400, 250), 100, 0, 3)
    cv2.line(img, (100, 380), (700, 380), 0, 14)   # Wand
    r = tf.convert(img, _settings(), dpi_scale=0.1)
    good = Q.assess(r.binary, r.drawing.entities, mm_per_px=0.1)
    assert good.rating == Q.GREEN and not good.problems
    ents = [e for e in r.drawing.entities if not isinstance(e, tf.Circle)]
    ents.append(tf.Line((100, 300), (300, 200)))
    bad = Q.assess(r.binary, ents, mm_per_px=0.1)
    assert bad.rating == Q.RED
    kinds = {p.kind for p in bad.problems}
    assert kinds == {"fehlt", "ueberfluessig"}
    miss = next(p for p in bad.problems if p.kind == "fehlt")
    assert abs(miss.x + miss.w / 2 - 400) < 10 and abs(miss.y + miss.h / 2 - 250) < 10


def test_quality_outline_mode_filled():
    img = np.full((400, 600), 255, np.uint8)
    cv2.circle(img, (300, 200), 120, 0, -1)
    cv2.circle(img, (300, 200), 50, 255, -1)
    s = _settings()
    s.vectorize.mode = tf.MODE_OUTLINE
    r = tf.convert(img, s)
    rep = Q.assess(r.binary, r.drawing.entities, fill_closed=True)
    assert rep.rating == Q.GREEN


# ------------------------------------------------------------------ Symbole
def _socket(img, x, y, rot=0):
    t = np.full((40, 40), 255, np.uint8)
    cv2.circle(t, (20, 20), 14, 0, 2)
    cv2.line(t, (14, 12), (14, 28), 0, 2)
    cv2.line(t, (26, 12), (26, 28), 0, 2)
    cv2.line(t, (20, 6), (20, 0), 0, 2)
    t = np.rot90(t, rot // 90)
    img[y - 20:y + 20, x - 20:x + 20] = np.minimum(img[y - 20:y + 20, x - 20:x + 20], t)


@pytest.fixture
def socket_plan():
    img = np.full((600, 900), 255, np.uint8)
    cv2.rectangle(img, (20, 20), (880, 580), 0, 2)
    for x, y, r in [(100, 100, 0), (300, 100, 0), (500, 300, 90), (700, 450, 180),
                    (200, 450, 270)]:
        _socket(img, x, y, r)
    cv2.rectangle(img, (400, 80), (440, 120), 0, 2)   # ähnlich, aber kein Symbol
    return img


def test_symbols_find_rotated_and_replace(socket_plan):
    r = tf.convert(socket_plan, _settings())
    d = r.drawing
    circles_before = sorted((round(e.center[0]), round(e.center[1])) for e in d.entities
                            if isinstance(e, tf.Circle))
    tpl = S.make_template("Steckdose", r.binary, d, 78, 78, 44, 44)
    m = S.find_matches(r.binary, tpl)
    assert sorted((round(x.cx), round(x.cy), int(x.rotation)) for x in m) == \
        [(100, 100, 0), (200, 450, 270), (300, 100, 0), (500, 300, 90), (700, 450, 180)]
    assert S.apply_matches(d, tpl, m) == 5
    assert d.symbol_counts() == {"Steckdose": 5}
    assert d.stats()["Symbole"] == 5
    # aufgelöste Geometrie liegt dort, wo vorher die Einzelobjekte waren
    circles_after = sorted((round(e.center[0]), round(e.center[1])) for e in d.expanded()
                           if isinstance(e, tf.Circle))
    for c in circles_after:
        assert any(abs(c[0] - b[0]) <= 1 and abs(c[1] - b[1]) <= 1 for b in circles_before)
    # das Quadrat bleibt erhalten
    assert any(isinstance(e, tf.Line) and 395 < e.p1[0] < 445 for e in d.entities)


def test_symbol_dxf_blocks(socket_plan, tmp_path):
    import ezdxf
    from ezdxf.disassemble import recursive_decompose
    r = tf.convert(socket_plan, _settings())
    d = r.drawing
    tpl = S.make_template("Steckdose groß", r.binary, d, 78, 78, 44, 44)
    S.apply_matches(d, tpl, S.find_matches(r.binary, tpl))
    p = tmp_path / "s.dxf"
    tf.export(d, str(p))
    doc = ezdxf.readfile(str(p))
    inserts = [e for e in doc.modelspace() if e.dxftype() == "INSERT"]
    assert len(inserts) == 5 and inserts[0].dxf.name == "Steckdose_gross"
    assert sorted(round(e.dxf.rotation) for e in inserts) == [0, 0, 90, 180, 270]
    centers = sorted((round(e.dxf.center.x, 1), round(e.dxf.center.y, 1))
                     for e in recursive_decompose(doc.modelspace()) if e.dxftype() == "CIRCLE")
    expected = sorted((round(c[0] * d.scale, 1), round((d.height - c[1]) * d.scale, 1))
                      for c in [(100, 100), (300, 100), (500, 300), (700, 450), (200, 450)])
    assert all(abs(a[0] - b[0]) < 0.2 and abs(a[1] - b[1]) < 0.2 for a, b in zip(centers, expected))
    # SVG und G-Code lösen die Symbole auf
    tf.export(d, str(tmp_path / "s.svg"))
    g = tf.export(d, str(tmp_path / "s.nc")) or (tmp_path / "s.nc").read_text()
    assert g.count("G2") + g.count("G3") >= 5


def test_symbol_library(socket_plan, tmp_path, monkeypatch):
    monkeypatch.setattr(S, "library_dir", lambda: str(tmp_path))
    r = tf.convert(socket_plan, _settings())
    tpl = S.make_template("Steckdose", r.binary, r.drawing, 78, 78, 44, 44)
    S.save_template(tpl)
    lib = S.load_library()
    assert [t.name for t in lib] == ["Steckdose"] and len(lib[0].entities) == len(tpl.entities)
    # automatisch beim Konvertieren
    s = _settings()
    s.symbols_auto = True
    d = tf.convert(socket_plan, s).drawing
    assert d.symbol_counts() == {"Steckdose": 5}
    assert "Steckdose ×5" in d.meta.get("symbole", "")


# ------------------------------------------------------------------ KI-Stapel
class FakeOllama(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def do_GET(self):
        self._send({"version": "test"} if self.path == "/api/version" else {"models": []})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        txt = body["messages"][-1]["content"]
        name = txt.split("Datei: ")[1].split("\n")[0]
        assert "Logos als CNC" in txt and body["messages"][-1].get("images")
        if "logo" in name:
            c = {"art": "Logo", "ueberspringen": False, "formate": ["nc", "G-Code"],
                 "einstellungen": [{"name": "modus", "wert": "umriss"},
                                   {"name": "fraestiefe", "wert": 2},
                                   {"name": "unsinn", "wert": 1}],
                 "begruendung": "Logo"}
        elif "notiz" in name:
            c = {"art": "Notiz", "ueberspringen": True, "formate": [], "einstellungen": [],
                 "begruendung": "handschriftlich"}
        else:
            c = {"art": "Grundriss", "ueberspringen": False, "formate": [],
                 "einstellungen": [{"name": "vorlage", "wert": "Grundriss"}],
                 "begruendung": "Plan"}
        self._send({"message": {"role": "assistant", "content": json.dumps(c)}, "done": True})


def test_ai_batch_rules(tmp_path, monkeypatch):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    from traceify import config
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "c.json"))
    config.save({"ollama_url": f"http://127.0.0.1:{srv.server_address[1]}",
                 "ollama_model": "gemma3:4b"})
    src = tmp_path / "in"
    src.mkdir()
    img = np.full((300, 400), 255, np.uint8)
    cv2.rectangle(img, (50, 50), (350, 250), 0, 3)
    for n in ("plan.png", "logo.png", "notiz.png"):
        cv2.imwrite(str(src / n), img)
    out = tmp_path / "out"
    res = tf.batch_convert(str(src), str(out), [".dxf"], _settings(),
                           rules="Logos als CNC-Umriss mit 2 mm Tiefe, Notizen überspringen")
    srv.shutdown()
    by = {r.source.split("/")[-1].split("\\")[-1]: r for r in res}
    assert by["notiz.png"].skipped and not by["notiz.png"].outputs
    assert [o.split(".")[-1] for o in by["logo.png"].outputs] == ["nc"]
    assert "Z-2" in open(by["logo.png"].outputs[0]).read()
    assert by["plan.png"].outputs[0].endswith(".dxf")
    assert "Grundriss" in by["plan.png"].note and "Logo" in by["logo.png"].note


def test_apply_named():
    from traceify.ai.batch_rules import apply_named
    s, g = tf.ConvertSettings(), tf.GcodeSettings()
    apply_named(s, g, "vorlage", "Logo")
    assert s.vectorize.mode == tf.MODE_OUTLINE
    apply_named(s, g, "radiuskorrektur", "außen")
    apply_named(s, g, "haltestege", "4")
    apply_named(s, g, "farben_trennen", "ja")
    assert g.compensation == "aussen" and g.tabs == 4 and s.style.color_layers
    with pytest.raises(ValueError):
        apply_named(s, g, "gibtsnicht", 1)
