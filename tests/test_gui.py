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
QtCore = pytest.importorskip("PySide6.QtCore")


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
        if "kopf" in props:            # unerkannte Schrift lesen
            c = {"text": "Keller", "sicher": True, "kopf": False}
        elif "vorlage" in props:
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


def test_gui_scan_pdf_automatische_aufloesung(tmp_path, monkeypatch):
    """Gescannte PDFs öffnen in Originalauflösung; die DPI-Einstellung steht auf automatisch."""
    import pymupdf
    from traceify import config
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    img = np.full((1240, 1754), 255, np.uint8)               # A4 quer mit 150 dpi
    cv2.rectangle(img, (150, 150), (1600, 1100), 0, 5)
    cv2.line(img, (150, 600), (1600, 600), 0, 5)
    for x in range(200, 1500, 60):                           # Schraffur an der Mittellinie
        cv2.line(img, (x, 600), (x + 40, 560), 0, 2)
    ok, png = cv2.imencode(".png", img)
    doc = pymupdf.open()
    pg = doc.new_page(width=841.89, height=595.28)
    pg.insert_image(pg.rect, stream=png.tobytes())
    pdf = tmp_path / "scan.pdf"
    doc.save(str(pdf))

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from traceify.gui.main_window import MainWindow
    w = MainWindow()
    assert w.panel.pdf_dpi.value() == 0
    assert w.panel.pdf_dpi.text() == "automatisch"
    w.panel.ocr.setChecked(False)
    w.open_file(str(pdf))
    assert abs(w.gray.shape[0] - 1240) <= 2 and abs(w.gray.shape[1] - 1754) <= 2
    assert abs(25.4 / w.img_scale - 150) < 0.5
    w.run_convert()
    wait(app, lambda: w.worker is None and w.drawing is not None)
    from traceify.core.model import Line
    mid = [e for e in w.drawing.entities if isinstance(e, Line)
           and abs(e.p1[1] - 600) < 4 and abs(e.p2[1] - 600) < 4]
    assert len(mid) == 1          # Mittellinie trotz Schraffur in einem Stück
    # feste DPI per Eingabe wie ein Nutzer
    w.panel.pdf_dpi.selectAll()
    QtTest = pytest.importorskip("PySide6.QtTest")
    QtTest.QTest.keyClicks(w.panel.pdf_dpi, "300")
    w.panel.pdf_dpi.interpretText()
    w.open_file(str(pdf))
    assert w.gray.shape[1] > 3400
    w.close()


def test_gui_tools(tmp_path, monkeypatch):
    from traceify import config
    from traceify.core.model import Line
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from traceify.gui.main_window import MainWindow
    w = MainWindow()
    w.panel.ocr.setChecked(False)
    img = np.full((400, 600), 255, np.uint8)
    cv2.line(img, (50, 100), (500, 102), 0, 3)
    cv2.line(img, (500, 102), (502, 350), 0, 3)
    cv2.circle(img, (300, 250), 4, 0, -1)          # Fleck
    p = tmp_path / "t.png"
    cv2.imwrite(str(p), img)
    w.open_file(str(p))

    # Radierer entfernt den Fleck im Raster, Strg+Z stellt ihn wieder her
    w.set_tool("erase")
    w.on_brush_stroke([(300.0, 250.0)], "erase", 14)
    assert w.gray[250, 300] == 255 and w.raster_modified
    w.undo()
    assert w.gray[250, 300] == 0
    w.on_brush_stroke([(290.0, 250.0), (310.0, 250.0)], "erase", 14)
    w.set_tool("select")

    # Bereich direkt anlegen (ohne Menü) und konvertieren
    from traceify.core.pipeline import Region
    w.regions = [Region(0, 300, 600, 100, "ignorieren")]
    w._update_regions()
    assert len(w.canvas.region_items) == 1
    w.run_convert()
    wait(app, lambda: w.worker is None and w.drawing is not None)
    lines = w.drawing.by_type(Line)
    assert lines and all(max(l.p1[1], l.p2[1]) <= 305 for l in lines)  # unten ignoriert

    # Ausrichten aller Linien + Rückgängig
    before = [(l.p1, l.p2) for l in w.drawing.by_type(Line)]
    w.edit_orthogonalize()
    after = w.drawing.by_type(Line)
    assert any(abs(l.p1[1] - l.p2[1]) < 1e-9 for l in after)
    w.undo()
    assert [(l.p1, l.p2) for l in w.drawing.by_type(Line)] == before

    # Knoten-Griffe erscheinen bei genau einem markierten Objekt
    it = w.canvas.item_by_id[id(w.drawing.by_type(Line)[0])]
    it.setSelected(True)
    app.processEvents()
    assert len(w.canvas.handles) == 2
    h = w.canvas.handles[0]
    w.on_node_edit_started()
    h._dragging = True
    h.setPos(QtCore.QPointF(10, 10))
    h._dragging = False
    assert w.drawing.by_type(Line)[0].p1 == (10.0, 10.0) or \
        (10.0, 10.0) in [e.p1 for e in w.drawing.by_type(Line)]
    w.close()


def test_gui_draw_snap_trim_extend(tmp_path, monkeypatch):
    """Zeichnen mit Fang, Länge per Tastatur, Stutzen, Dehnen, Rückgängig – mit echten Mausereignissen."""
    from PySide6.QtTest import QTest
    from traceify import config
    from traceify.core.model import Arc, Circle, Line, Polyline
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from traceify.gui.main_window import MainWindow
    w = MainWindow()
    w.resize(1200, 900)
    w.show()
    img = np.full((600, 800), 255, np.uint8)
    p = tmp_path / "leer.png"
    cv2.imwrite(str(p), img)
    w.open_file(str(p))
    assert w.drawing is None
    cv = w.canvas
    vp = cv.viewport()
    app.processEvents()
    cv.zoom_100()
    cv.centerOn(400, 300)
    app.processEvents()
    Qt = QtCore.Qt

    def at(x, y):
        return cv.mapFromScene(QtCore.QPointF(x, y))

    def click(x, y, btn=Qt.LeftButton):
        QTest.mouseMove(vp, at(x, y))
        QTest.mouseClick(vp, btn, Qt.NoModifier, at(x, y))
        app.processEvents()

    w.a_snap.setChecked(True)
    w.toggle_snap(True)
    w.a_ortho_mode.setChecked(False)
    w.toggle_ortho(False)
    w.draw_layer.setCurrentText("Meine Linien")

    # Linie 1 mit zwei Klicks (ohne Konvertierung – Zeichnung entsteht automatisch)
    w.set_tool("line")
    click(200, 200)
    click(500, 200)
    assert w.drawing is not None
    l1 = w.drawing.by_type(Line)[-1]
    assert l1.layer == "MEINE_LINIEN"
    assert abs(l1.p1[0] - 200) < 1.5 and abs(l1.p2[0] - 500) < 1.5
    QTest.keyClick(vp, Qt.Key_Escape)        # Esc bricht nur die Form ab, Werkzeug bleibt
    app.processEvents()
    assert w.canvas.tool == "line" and not w.canvas._draw_pts
    QTest.keyClick(vp, Qt.Key_Escape)        # zweites Esc: zurück zur Auswahl
    app.processEvents()
    assert w.canvas.tool == "select"
    w.set_tool("line")

    # Linie 2: Start rastet auf dem Mittelpunkt von Linie 1 ein, Länge per Tastatur
    click(352, 203)
    w.toggle_ortho(True)                     # Ortho: exakt senkrecht trotz schiefer Maus
    QTest.mouseMove(vp, at(358, 400))        # Richtung nach unten
    app.processEvents()
    mm = w.drawing.scale
    QTest.keyClicks(cv, f"{100 * mm:.4f}".replace(".", ","))
    QTest.keyClick(cv, Qt.Key_Return)
    app.processEvents()
    l2 = w.drawing.by_type(Line)[-1]
    assert l2 is not l1
    assert abs(l2.p1[0] - (l1.p1[0] + l1.p2[0]) / 2) < 1e-6 and abs(l2.p1[1] - l1.p1[1]) < 1e-6
    assert abs(math_dist(l2.p1, l2.p2) - 100) < 1e-3
    assert abs(l2.p1[0] - l2.p2[0]) < 1e-9
    QTest.keyClick(cv, Qt.Key_Escape)
    app.processEvents()
    w.toggle_ortho(False)

    # Kreis per Mittelpunkt + Radius-Klick
    w.set_tool("circle")
    click(650, 450)
    click(690, 450)
    c = w.drawing.by_type(Circle)[-1]
    assert abs(c.radius - 40) < 1.5

    # Bogen aus drei Punkten
    w.set_tool("arc")
    click(100, 450)
    click(200, 450)
    click(150, 500)
    assert w.drawing.by_type(Arc)

    # Polylinie, per Klick auf den Startpunkt geschlossen
    w.set_tool("polyline")
    for x, y in ((600, 100), (700, 100), (700, 180), (600, 100)):
        click(x, y)
    poly = w.drawing.by_type(Polyline)[-1]
    assert poly.closed and len(poly.points) == 3

    # Stutzen: rechte Hälfte von Linie 1 hinter der Kreuzung mit Linie 2 entfernen
    w.set_tool("trim")
    n_before = len(w.drawing.entities)
    click(450, 200)
    lines_y200 = [l for l in w.drawing.by_type(Line) if abs(l.p1[1] - 200) < 1e-6
                  and abs(l.p2[1] - 200) < 1e-6]
    assert len(lines_y200) == 1
    xs = sorted([lines_y200[0].p1[0], lines_y200[0].p2[0]])
    assert abs(xs[1] - l2.p1[0]) < 1e-6
    w.undo()
    assert len(w.drawing.entities) == n_before
    assert any(abs(max(l.p1[0], l.p2[0]) - l1.p2[0]) < 1e-6 for l in w.drawing.by_type(Line))

    # Dehnen: Linie 2 nach unten bis zu einer neuen Querlinie verlängern
    w.set_tool("line")
    click(250, 450)
    click(450, 450)
    QTest.keyClick(cv, Qt.Key_Escape)
    w.set_tool("extend")
    l2 = [l for l in w.drawing.by_type(Line) if abs(l.p1[0] - l.p2[0]) < 1e-6][0]
    end = l2.p2
    click(end[0], end[1] - 3)
    assert abs(l2.p2[1] - 450) < 1e-6
    w.undo()
    l2b = [l for l in w.drawing.by_type(Line) if abs(l.p1[0] - l.p2[0]) < 1e-6][0]
    assert abs(l2b.p2[1] - end[1]) < 1e-6

    # Fang aus: Klick landet genau auf der Mausposition (gerundet auf Pixel)
    w.a_snap.setChecked(False)
    w.toggle_snap(False)
    w.set_tool("line")
    click(352, 205)
    click(352, 260)
    l3 = w.drawing.by_type(Line)[-1]
    assert abs(l3.p1[1] - 205) < 1.5

    # Gezeichnetes überlebt das Konvertieren
    w.set_tool("select")
    w.panel.ocr.setChecked(False)
    w.run_convert()
    wait(app, lambda: w.worker is None)
    assert any(e.layer == "MEINE_LINIEN" for e in w.drawing.entities)
    w.close()


def test_gui_dehnen_polylinie_und_bogen(tmp_path, monkeypatch):
    """Dehnen per Mausklick bei offener Polylinie und Bogen."""
    from PySide6.QtTest import QTest
    from traceify import config
    from traceify.core.model import Arc, Drawing, Line, Polyline
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from traceify.gui.main_window import MainWindow
    w = MainWindow()
    w.resize(1200, 900)
    w.show()
    p = tmp_path / "leer.png"
    cv2.imwrite(str(p), np.full((600, 800), 255, np.uint8))
    w.open_file(str(p))
    wall = Line((600.0, 50.0), (600.0, 550.0))
    poly = Polyline([(100.0, 100.0), (300.0, 150.0), (450.0, 150.0)])
    arc = Arc((300.0, 400.0), 100.0, 180.0, 270.0)       # links unten bis oben (Bild)
    floor = Line((150.0, 480.0), (450.0, 480.0))       # schneidet den Kreis bei 53° und 127°
    w.drawing = Drawing(width=800, height=600, scale=0.25,
                        entities=[wall, poly, arc, floor])
    w.canvas.set_entities(w.drawing.entities)
    w.update_actions()
    cv, vp = w.canvas, w.canvas.viewport()
    app.processEvents()
    cv.zoom_100()
    cv.centerOn(400, 300)
    app.processEvents()
    Qt = QtCore.Qt

    def click(x, y):
        pt = cv.mapFromScene(QtCore.QPointF(x, y))
        QTest.mouseMove(vp, pt)
        QTest.mouseClick(vp, Qt.LeftButton, Qt.NoModifier, pt)
        app.processEvents()

    w.a_snap.setChecked(False)
    w.toggle_snap(False)
    w.set_tool("extend")
    click(445, 150)                          # nahe am Ende der Polylinie
    assert abs(poly.points[-1][0] - 600) < 1e-6 and abs(poly.points[-1][1] - 150) < 1e-6
    # Bogen: Startpunkt (180°, links) anklicken – er wächst entlang des Kreises nach unten
    # bis zur Linie floor
    click(202, 395)
    assert abs(arc.start_angle - 126.87) < 0.1 and arc.end_angle == 270.0
    w.undo()
    assert w.drawing.entities[2].start_angle == 180.0
    w.close()


def test_gui_unerkannte_schrift_mit_ki(tmp_path, fake_ollama, monkeypatch):
    """Handschrift ohne OCR-Treffer: KI liest sie, Übernahme ersetzt die Linien durch Text."""
    from traceify import config
    from traceify.core.model import Text
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    config.save({"ollama_url": fake_ollama, "ollama_model": "gemma3:4b", "ki": None})
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from traceify.gui.main_window import MainWindow
    img = np.full((600, 900), 255, np.uint8)
    cv2.rectangle(img, (40, 40), (860, 560), 0, 5)
    cv2.putText(img, "Keller", (300, 320), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 2.4, 0, 4)
    p = tmp_path / "hand.png"
    cv2.imwrite(str(p), img)
    w = MainWindow()
    w.show()
    w.panel.ocr.setChecked(False)
    w.open_file(str(p))
    w.run_convert()
    wait(app, lambda: w.worker is None and w.drawing is not None)
    n_before = len(w.drawing.entities)
    wait(app, lambda: "verbunden" in w.ai_panel.status.text())
    shown = []

    def fake_review(fixes):
        shown.extend(fixes)
        # wie „OK“ im Dialog: alle neuen Texte übernehmen
        from traceify.ai.assistant import entities_in_region
        for f in fixes:
            gone = {id(e) for e in entities_in_region(w.drawing.entities, f.region)}
            w.drawing.entities = [e for e in w.drawing.entities if id(e) not in gone]
            w.drawing.entities.append(f.entity)
    monkeypatch.setattr(w, "_review_text_fixes", fake_review)
    w.ai_panel.btn_unread.click()
    wait(app, lambda: not w.ai_panel.workers)
    assert shown and all(f.is_new for f in shown)
    assert any(isinstance(e, Text) and e.text == "Keller" for e in w.drawing.entities)
    assert len(w.drawing.entities) < n_before      # Buchstaben-Linien sind ersetzt
    w.close()


def math_dist(a, b):
    import math
    return math.dist(a, b)


def test_gui_install_update(tmp_path, monkeypatch):
    """„Jetzt installieren“: Laden mit Fortschritt, Setup starten, Traceify beenden."""
    from traceify import config, update
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    config.save({"update_check": False})
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    from traceify.gui.main_window import MainWindow
    setup = tmp_path / "Traceify-Setup-9.9.9.exe"
    setup.write_bytes(b"MZ" + b"0" * 2000)

    def fake_download(info, progress=None, cancelled=None, **kw):
        for i in range(1, 5):
            progress(i * 500, 2000)
        return str(setup)
    launched, quits = [], []
    monkeypatch.setattr(update, "download", fake_download)
    monkeypatch.setattr(update, "launch_installer", lambda p: launched.append(p))
    monkeypatch.setattr(QtWidgets.QApplication, "quit", staticmethod(lambda: quits.append(1)))
    w = MainWindow()
    w.show()
    info = update.UpdateInfo("9.9.9", "https://x", "https://x/s.exe", "")
    w.install_update(info, confirm=False)
    wait(app, lambda: launched)
    assert launched == [str(setup)] and quits and not w.isVisible()

    # Fehler beim Laden: Warnung statt Absturz, Setup wird nicht gestartet
    def broken(info, **kw):
        raise update.UpdateError("Prüfsumme (SHA-256) stimmt nicht")
    monkeypatch.setattr(update, "download", broken)
    shown = []
    monkeypatch.setattr(QtWidgets.QMessageBox, "exec", lambda self: shown.append(self.text()))
    w2 = MainWindow()
    wk = w2.install_update(info, confirm=False)
    wait(app, lambda: wk.isFinished() and shown)
    app.processEvents()
    assert "SHA-256" in shown[0] and len(launched) == 1
    w2.close()


def test_gui_tooltips_bei_mauszeiger(tmp_path, monkeypatch):
    """Jeder Schalter erklärt sich, wenn die Maus darauf verweilt – auch die Beschriftung
    links daneben im Formular."""
    from traceify import config
    from traceify.gui.tips import ACTIONS, AI, SETTINGS, WINDOW
    monkeypatch.setattr(config, "CONFIG_PATH", str(tmp_path / "config.json"))
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    QtGui = pytest.importorskip("PySide6.QtGui")
    QtTest = pytest.importorskip("PySide6.QtTest")
    from traceify.gui.main_window import MainWindow
    w = MainWindow()
    w.resize(1400, 900)
    w.show()
    app.processEvents()
    p = w.panel
    for name in SETTINGS:
        assert getattr(p, name).toolTip(), name
    for name in WINDOW:
        assert getattr(w, name).toolTip(), name
    for name in ACTIONS:
        a = getattr(w, name)
        assert a.toolTip() and a.toolTip() != a.text(), name
    ai = w.ai_panel if hasattr(w, "ai_panel") else None
    if ai is not None:
        for name in AI:
            if hasattr(ai, name):
                assert getattr(ai, name).toolTip(), name
    # alle Kästchen und Zahlenfelder im Einstellungsbereich haben eine Erklärung
    kinds = (QtWidgets.QCheckBox, QtWidgets.QAbstractSpinBox, QtWidgets.QComboBox,
             QtWidgets.QRadioButton, QtWidgets.QPushButton)
    ohne = [x.text() if hasattr(x, "text") else type(x).__name__
            for x in p.findChildren(QtWidgets.QWidget) if isinstance(x, kinds) and not x.toolTip()]
    assert ohne == []
    # Beschriftung im Formular („Toleranz:“) zeigt dieselbe Erklärung
    lab = p.tolerance.parentWidget().layout().labelForField(p.tolerance)
    assert lab.toolTip() == p.tolerance.toolTip()

    # echte Maus: auf das Kästchen „Wörterbuch“ zeigen und verweilen → Tooltip erscheint
    p.ensureWidgetVisible(p.ocr_dict)
    app.processEvents()
    c = p.ocr_dict.rect().center()
    QtTest.QTest.mouseMove(p.ocr_dict, c)
    app.processEvents()
    ev = QtGui.QHelpEvent(QtCore.QEvent.ToolTip, c, p.ocr_dict.mapToGlobal(c))
    QtWidgets.QApplication.sendEvent(p.ocr_dict, ev)
    app.processEvents()
    assert QtWidgets.QToolTip.isVisible()
    assert "Planbegriffe" in QtWidgets.QToolTip.text()
    QtWidgets.QToolTip.hideText()
    # neue Optionen kommen in den Einstellungen an
    p.spurs.setValue(0.0)
    p.ocr_dict.setChecked(False)
    s = p.settings()
    assert s.style.spurs_mm == 0.0 and s.ocr.dictionary is False
    p.set_settings(type(s)())
    assert p.spurs.value() == 1.5 and p.ocr_dict.isChecked()
    w.close()
