"""Rauchtest der Oberfläche (offscreen) inkl. KI-Panel gegen einen nachgebauten Ollama-Server."""
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import cv2
import numpy as np
import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
QtWidgets = pytest.importorskip("PySide6.QtWidgets")


class FakeOllama(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, obj):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def do_GET(self):
        if self.path == "/api/version":
            self._send({"version": "test"})
        elif self.path == "/api/tags":
            self._send({"models": [{"name": "gemma3:4b"}]})
        else:
            self.send_error(404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])) or b"{}")
        if self.path != "/api/chat":
            return self._send({})
        props = (body.get("format") or {}).get("properties", {}) \
            if isinstance(body.get("format"), dict) else {}
        if "vorlage" in props:
            c = {"art": "Grundriss", "vorlage": "Grundriss / Architektur", "modus": "mittellinie",
                 "invertieren": False, "ungleichmaessig_beleuchtet": False, "schraeg": False,
                 "verrauscht": False, "enthaelt_text": False, "begruendung": "Test"}
        else:
            c = {"antwort": "ok", "aktionen": [{"aktion": "einstellung", "name": "toleranz",
                                                "wert": 2.5}]}
        self._send({"message": {"role": "assistant", "content": json.dumps(c)}, "done": True})


@pytest.fixture(scope="module")
def fake_ollama():
    srv = ThreadingHTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def wait(app, cond, timeout=60):
    end = time.time() + timeout
    while time.time() < end:
        app.processEvents()
        if cond():
            return
        time.sleep(0.02)
    raise AssertionError("Zeitüberschreitung")


def test_main_window(tmp_path, fake_ollama, monkeypatch):
    from traceify import config
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    config.save({"ollama_url": fake_ollama, "ollama_model": "gemma3:4b", "ki": None})

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from traceify.gui.main_window import MainWindow
    w = MainWindow()
    w.show()
    img = np.full((600, 800), 255, np.uint8)
    cv2.rectangle(img, (50, 50), (750, 550), 0, 3)
    cv2.circle(img, (400, 300), 100, 0, 3)
    p = tmp_path / "t.png"
    cv2.imwrite(str(p), img)
    w.panel.ocr.setChecked(False)
    w.open_file(str(p))
    w.run_convert()
    wait(app, lambda: w.worker is None and w.drawing is not None)
    assert w.drawing.stats()["Kreise"] == 1

    # Löschen + Rückgängig
    n = len(w.drawing.entities)
    next(iter(w.canvas.items_by_layer.values()))[0].setSelected(True)
    w.delete_selected()
    assert len(w.drawing.entities) == n - 1
    w.undo()
    assert len(w.drawing.entities) == n

    # KI-Panel gegen Fake-Ollama
    wait(app, lambda: "verbunden" in w.ai_panel.status.text())
    w.ai_chat("Toleranz hoch", False)
    wait(app, lambda: not w.ai_panel.workers)
    assert w.panel.tolerance.value() == 2.5
    w.close()


def test_gui_opens_vector_pdf(tmp_path, monkeypatch):
    import pymupdf
    from traceify import config
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    doc = pymupdf.open()
    p = doc.new_page(width=842, height=595)
    for k in range(20):
        p.draw_line((60, 80 + k * 20), (400, 80 + k * 20), width=0.5)
    p.draw_circle((600, 300), 72, width=1)
    p.insert_text((450, 540), "M 1:50", fontsize=14)
    pdf = tmp_path / "v.pdf"
    doc.save(str(pdf))

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from traceify.gui.main_window import MainWindow
    msgs = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "critical",
                        staticmethod(lambda *a, **k: msgs.append(a[2])))
    w = MainWindow()
    # wie auf einem Rechner ohne Tesseract: OCR aus – PDF-Texte müssen trotzdem kommen
    w.panel.ocr.setChecked(False)
    w.open_file(str(pdf))
    assert not msgs, msgs
    assert w.is_vector_pdf
    w.run_convert()
    wait(app, lambda: w.worker is None and w.drawing is not None)
    assert w.drawing.meta.get("quelle") == "PDF-Vektoren"
    assert w.drawing.meta.get("massstab") == "1:50"
    assert w.drawing.stats()["Kreise"] == 1
    w.close()
