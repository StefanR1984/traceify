"""vLLM / OpenAI-kompatible KI-Server – gegen einen nachgebauten Server."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from traceify.ai import OllamaError, OpenAICompatClient, make_client, model_key

REQUESTS = []


class FakeVllm(BaseHTTPRequestHandler):
    reject_schema = False

    def log_message(self, *a):
        pass

    def _send(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        REQUESTS.append(("GET", self.path, dict(self.headers), None))
        if self.path == "/version":
            self._send({"version": "0.11.0"})
        elif self.path == "/v1/models":
            self._send({"object": "list", "data": [{"id": "Qwen/Qwen2.5-VL-7B-Instruct",
                                                    "object": "model"}]})
        else:
            self._send({"error": {"message": "nicht gefunden"}}, 404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        REQUESTS.append(("POST", self.path, dict(self.headers), body))
        rf = body.get("response_format") or {}
        if FakeVllm.reject_schema and rf.get("type") == "json_schema":
            return self._send({"error": {"message": "json_schema nicht unterstützt"}}, 400)
        schema = (rf.get("json_schema") or {}).get("schema") or {}
        props = schema.get("properties", {})
        if "vorlage" in props:
            c = {"art": "Grundriss", "vorlage": "Grundriss / Architektur", "modus": "mittellinie",
                 "invertieren": False, "ungleichmaessig_beleuchtet": False, "schraeg": False,
                 "verrauscht": False, "enthaelt_text": False, "begruendung": "Test"}
        elif "kopf" in props:
            c = {"text": "Keller", "sicher": True, "kopf": False}
        else:
            c = {"antwort": "ok", "aktionen": [{"aktion": "einstellung", "name": "toleranz",
                                                "wert": 2.5}]}
        content = json.dumps(c)
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for i in range(0, len(content), 7):
                ev = {"choices": [{"delta": {"content": content[i:i + 7]}}]}
                self.wfile.write(f"data: {json.dumps(ev)}\n\n".encode())
            self.wfile.write(b"data: [DONE]\n\n")
            return
        self._send({"choices": [{"message": {"role": "assistant", "content": content}}]})


@pytest.fixture(scope="module")
def fake_vllm():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeVllm)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/v1"
    srv.shutdown()


def test_client_modelle_und_version(fake_vllm):
    c = OpenAICompatClient(fake_vllm)
    assert c.available()
    assert c.version() == "vLLM 0.11.0"
    assert c.model_names() == ["Qwen/Qwen2.5-VL-7B-Instruct"]
    assert c.has_vision("Qwen/Qwen2.5-VL-7B-Instruct") and not c.has_vision("Qwen/Qwen2.5-7B")
    assert not c.can_pull
    with pytest.raises(OllamaError):
        c.pull("x")


def test_adresse_ohne_v1_wird_ergaenzt(fake_vllm):
    c = OpenAICompatClient(fake_vllm[:-3])
    assert c.url.endswith("/v1") and c.model_names()


def test_chat_mit_bild_schema_und_schluessel(fake_vllm):
    REQUESTS.clear()
    c = OpenAICompatClient(fake_vllm, api_key="geheim")
    schema = {"type": "object", "properties": {"text": {"type": "string"},
                                               "kopf": {"type": "boolean"}}}
    out = c.chat("Qwen/Qwen2.5-VL-7B-Instruct",
                 [{"role": "user", "content": "lies", "images": ["QUJD"]}], fmt=schema)
    assert json.loads(out)["text"] == "Keller"
    _, path, headers, body = REQUESTS[-1]
    assert path == "/v1/chat/completions"
    assert headers.get("Authorization") == "Bearer geheim"
    parts = body["messages"][0]["content"]
    assert parts[0] == {"type": "text", "text": "lies"}
    assert parts[1]["image_url"]["url"] == "data:image/png;base64,QUJD"
    assert body["response_format"]["type"] == "json_schema"


def test_schema_abgelehnt_dann_json_object(fake_vllm):
    REQUESTS.clear()
    FakeVllm.reject_schema = True
    try:
        c = OpenAICompatClient(fake_vllm)
        out = c.chat("m", [{"role": "user", "content": "x"}], fmt={"type": "object"})
        assert json.loads(out)["antwort"] == "ok"
        kinds = [(r[3] or {}).get("response_format", {}).get("type") for r in REQUESTS
                 if r[0] == "POST"]
        assert kinds == ["json_schema", "json_object"]
    finally:
        FakeVllm.reject_schema = False


def test_streaming(fake_vllm):
    toks = []
    out = OpenAICompatClient(fake_vllm).chat("m", [{"role": "user", "content": "x"}],
                                            on_token=toks.append)
    assert len(toks) > 3 and "".join(toks) == out and json.loads(out)["antwort"] == "ok"


def test_nicht_erreichbar():
    c = OpenAICompatClient("http://127.0.0.1:9/v1", timeout=2)
    assert not c.available()
    with pytest.raises(OllamaError):
        c.chat("m", [{"role": "user", "content": "x"}])


def test_make_client_und_modellschluessel():
    o = make_client({"ki_server": "ollama"})
    v = make_client({"ki_server": "openai", "openai_url": "http://x:8000/v1", "openai_key": "k"})
    assert o.kind == "ollama" and v.kind == "openai" and v.api_key == "k"
    assert model_key({"ki_server": "openai"}) == "openai_model"
    assert model_key({}) == "ollama_model"


def test_ki_funktionen_ueber_vllm(fake_vllm):
    """Einstellungsvorschlag und Handschrift-Lesen laufen unverändert über vLLM."""
    import cv2
    import numpy as np

    from traceify.ai import read_unrecognized, suggest_settings
    from traceify.core.model import Drawing
    c = OpenAICompatClient(fake_vllm)
    img = np.full((300, 600), 255, np.uint8)
    cv2.putText(img, "Keller", (150, 170), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 2.2, 0, 3)
    assert suggest_settings(c, "m", img)["modus"] == "mittellinie"
    d = Drawing(width=600, height=300, scale=0.2, entities=[])
    fixes = read_unrecognized(c, "m", img, 255 - img, d, 6.0)
    assert fixes and fixes[0].new == "Keller"


# ------------------------------------------------------------------ Oberfläche
QtWidgets = pytest.importorskip("PySide6.QtWidgets")
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _wait(app, cond, timeout=30):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("Zeitüberschreitung")


def test_gui_vllm_server_waehlen_und_chat(tmp_path, fake_vllm, monkeypatch):
    from PySide6.QtCore import QTimer
    from traceify import config
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    config.save({"ki": None, "ki_server": "ollama", "ollama_url": "http://127.0.0.1:9"})
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from traceify.gui.ai_panel import AiPanel, ServerDialog
    p = AiPanel()
    p.refresh()
    _wait(app, lambda: "nicht erreichbar" in p.status.text())
    _wait(app, lambda: not p.workers)

    # Server-Dialog wie ein Nutzer ausfüllen
    def fill():
        dlg = app.activeModalWidget()
        assert isinstance(dlg, ServerDialog)
        dlg.kind.setCurrentIndex(dlg.kind.findData("openai"))
        assert dlg.openai_url.isEnabled() and not dlg.ollama_url.isEnabled()
        dlg.openai_url.setText(fake_vllm)
        dlg.accept()
    QTimer.singleShot(50, fill)
    p.btn_server.click()
    _wait(app, lambda: "vLLM 0.11.0 verbunden" in p.status.text())
    assert p.model_name == "Qwen/Qwen2.5-VL-7B-Instruct"
    assert not p.btn_pull.isVisible() and not p.btn_start.isVisible()
    cfg = config.load()
    assert cfg["ki_server"] == "openai" and cfg["openai_model"] == "Qwen/Qwen2.5-VL-7B-Instruct"
    res = p.assistant.ask("Toleranz hoch")
    assert res["aktionen"][0]["wert"] == 2.5
    # zurück auf Ollama: eigenes Modell bleibt getrennt gespeichert
    p.set_server({"ki_server": "ollama", "ollama_url": "http://127.0.0.1:9"})
    assert config.load()["openai_model"] == "Qwen/Qwen2.5-VL-7B-Instruct"
    # Hintergrund-Threads (Verbindungsprüfung) erst beenden lassen – unter Windows stürzt
    # Python sonst beim Beenden ab („QThread: Destroyed while thread is still running“)
    _wait(app, lambda: not p.workers, timeout=60)
    for w in list(p.workers):
        w.wait(5000)
    p.deleteLater()
    app.processEvents()
