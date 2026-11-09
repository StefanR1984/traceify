"""KI-Assistent als Seitenleiste – mit Ollama oder einem vLLM-/OpenAI-kompatiblen Server."""
from __future__ import annotations

import html
import traceback

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPlainTextEdit,
                               QProgressBar, QPushButton, QSpinBox, QTextBrowser, QToolButton,
                               QVBoxLayout, QWidget)

from .. import config
from ..ai import (RECOMMENDED_MODELS, RECOMMENDED_VLLM_MODELS, SERVER_KINDS, Assistant,
                  make_client, model_key)


class ServerDialog(QDialog):
    """Welcher KI-Server: Ollama (Standard) oder vLLM / OpenAI-kompatibel."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("KI-Server")
        cfg = config.load()
        f = QFormLayout(self)
        self.kind = QComboBox()
        for k, label in SERVER_KINDS.items():
            self.kind.addItem(label, k)
        self.kind.setCurrentIndex(max(0, self.kind.findData(cfg.get("ki_server") or "ollama")))
        f.addRow("Server:", self.kind)
        self.ollama_url = QLineEdit(cfg.get("ollama_url") or "http://127.0.0.1:11434")
        f.addRow("Ollama-Adresse:", self.ollama_url)
        self.openai_url = QLineEdit(cfg.get("openai_url") or "http://127.0.0.1:8000/v1")
        self.openai_url.setToolTip("z. B. http://gpu-server:8000/v1 (vLLM), "
                                   "http://localhost:1234/v1 (LM Studio)")
        f.addRow("vLLM-/OpenAI-Adresse:", self.openai_url)
        self.openai_key = QLineEdit(cfg.get("openai_key") or "")
        self.openai_key.setEchoMode(QLineEdit.Password)
        self.openai_key.setPlaceholderText("nur nötig, wenn der Server einen verlangt (--api-key)")
        f.addRow("API-Schlüssel:", self.openai_key)
        self.timeout = QSpinBox()
        self.timeout.setRange(10, 3600)
        self.timeout.setSuffix(" s")
        self.timeout.setValue(int(cfg.get("ollama_timeout") or 300))
        f.addRow("Zeitlimit je Anfrage:", self.timeout)
        hint = QLabel("vLLM lädt sein Modell beim Start, z. B.<br><code>vllm serve "
                      "Qwen/Qwen2.5-VL-7B-Instruct --port 8000</code><br>Für Bild-Funktionen "
                      "braucht es ein Bildmodell (VL/Vision).")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 11px;")
        f.addRow(hint)
        row = QHBoxLayout()
        self.btn_test = QPushButton("Verbindung testen")
        self.btn_test.clicked.connect(self.test_connection)
        row.addWidget(self.btn_test)
        self.test_result = QLabel("")
        self.test_result.setWordWrap(True)
        row.addWidget(self.test_result, 1)
        f.addRow(row)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        f.addRow(bb)
        from .tips import AI, apply_tips
        apply_tips(self, AI)
        self.kind.currentIndexChanged.connect(self._sync)
        self._sync()

    def _sync(self):
        o = self.kind.currentData() == "openai"
        self.ollama_url.setEnabled(not o)
        for w in (self.openai_url, self.openai_key):
            w.setEnabled(o)

    def test_connection(self):
        """Server mit den eingetragenen Werten ansprechen und Modelle anzeigen."""
        from PySide6.QtWidgets import QApplication
        cfg = dict(config.load())
        cfg.update(self.values())
        cfg["ollama_timeout"] = 10
        self.test_result.setText("prüfe …")
        QApplication.processEvents()
        try:
            c = make_client(cfg)
            ver = c.version()
            names = c.model_names()
        except Exception as exc:  # noqa: BLE001
            self.test_result.setText(f'<span style="color:#c0392b">✗ {html.escape(str(exc))}'
                                     '</span>')
            return False
        shown = ", ".join(names[:4]) + (" …" if len(names) > 4 else "")
        self.test_result.setText(f'<span style="color:#1a8a4a">✓ {html.escape(ver)}</span> – '
                                 + (html.escape(shown) if names else "keine Modelle"))
        return True

    def values(self) -> dict:
        return {"ki_server": self.kind.currentData(),
                "ollama_url": self.ollama_url.text().strip() or "http://127.0.0.1:11434",
                "openai_url": self.openai_url.text().strip() or "http://127.0.0.1:8000/v1",
                "openai_key": self.openai_key.text().strip(),
                "ollama_timeout": self.timeout.value()}


class FuncWorker(QThread):
    """Führt eine Funktion im Hintergrund aus. fn(worker) -> Ergebnis."""
    result = Signal(object)
    error = Signal(str)
    progress = Signal(int, str)

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.stop_requested = False

    def run(self):
        try:
            self.result.emit(self.fn(self))
        except Exception as exc:  # noqa: BLE001
            msg = str(exc) or traceback.format_exc()
            self.error.emit(msg)


class AiPanel(QWidget):
    """Signale gehen an das Hauptfenster, das die eigentlichen Aktionen ausführt."""
    suggestRequested = Signal()
    correctTextsRequested = Signal()
    unreadRequested = Signal()
    reviewRequested = Signal()
    chatRequested = Signal(str, bool)     # Text, Bild mitsenden
    actionsConfirmed = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        cfg = config.load()
        self.client = make_client(cfg)
        self.assistant = Assistant(self.client, cfg.get(model_key(cfg)) or "")
        self.workers = []
        self.pending_actions = []

        lay = QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)

        row = QHBoxLayout()
        self.status = QLabel("● prüfe …")
        row.addWidget(self.status, 1)
        self.btn_start = QPushButton("Ollama starten")
        self.btn_start.clicked.connect(self.start_ollama)
        self.btn_start.setVisible(False)
        row.addWidget(self.btn_start)
        self.btn_server = QToolButton()
        self.btn_server.setText("⚙")
        self.btn_server.setToolTip("KI-Server wählen: Ollama oder vLLM / OpenAI-kompatibel")
        self.btn_server.clicked.connect(self.choose_server)
        row.addWidget(self.btn_server)
        lay.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Modell:"))
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setMinimumWidth(150)
        self.model.currentTextChanged.connect(self.on_model_changed)
        row.addWidget(self.model, 1)
        b = QToolButton()
        b.setText("⟳")
        b.setToolTip("Modellliste aktualisieren")
        b.clicked.connect(self.refresh)
        row.addWidget(b)
        self.btn_pull = QPushButton("Laden")
        self.btn_pull.setToolTip("Gewähltes Modell aus der Ollama-Bibliothek herunterladen")
        self.btn_pull.clicked.connect(self.pull_model)
        row.addWidget(self.btn_pull)
        lay.addLayout(row)
        self.model_info = QLabel("")
        self.model_info.setWordWrap(True)
        self.model_info.setStyleSheet("color: gray; font-size: 11px;")
        lay.addWidget(self.model_info)
        self.pull_bar = QProgressBar()
        self.pull_bar.setVisible(False)
        lay.addWidget(self.pull_bar)

        self.btn_suggest = QPushButton("🔍  Bild analysieren && Einstellungen wählen")
        self.btn_suggest.clicked.connect(self.suggestRequested)
        self.btn_texts = QPushButton("🔤  Erkannte Texte mit KI prüfen")
        self.btn_texts.clicked.connect(self.correctTextsRequested)
        self.btn_unread = QPushButton("✍  Unerkannte Schrift mit KI lesen")
        self.btn_unread.setToolTip("Stellen, die wie Schrift aussehen, aber von der OCR nicht "
                                   "gelesen wurden (z. B. Handschrift), vom Bildmodell lesen lassen")
        self.btn_unread.clicked.connect(self.unreadRequested)
        self.btn_review = QPushButton("✅  Ergebnis bewerten && verbessern")
        self.btn_review.clicked.connect(self.reviewRequested)
        for btn in (self.btn_suggest, self.btn_texts, self.btn_unread, self.btn_review):
            btn.setStyleSheet("text-align: left; padding: 5px;")
            lay.addWidget(btn)

        self.chat = QTextBrowser()
        self.chat.setOpenExternalLinks(True)
        lay.addWidget(self.chat, 1)

        self.btn_apply = QPushButton("Vorgeschlagene Aktionen ausführen")
        self.btn_apply.setVisible(False)
        self.btn_apply.clicked.connect(self._confirm_actions)
        lay.addWidget(self.btn_apply)

        self.input = QPlainTextEdit()
        self.input.setPlaceholderText("Frag die KI oder gib einen Auftrag, z. B. "
                                      "„Lösche alle Texte und exportiere als DXF“ "
                                      "(Strg+Enter = senden)")
        self.input.setMaximumHeight(80)
        self.input.installEventFilter(self)
        lay.addWidget(self.input)

        row = QHBoxLayout()
        self.send_image = QCheckBox("Bild mitsenden")
        self.send_image.setChecked(True)
        self.auto_exec = QCheckBox("Aktionen sofort ausführen")
        self.auto_exec.setChecked(True)
        row.addWidget(self.send_image)
        row.addWidget(self.auto_exec)
        lay.addLayout(row)
        row = QHBoxLayout()
        self.busy = QProgressBar()
        self.busy.setRange(0, 0)
        self.busy.setMaximumHeight(8)
        self.busy.setTextVisible(False)
        self.busy.setVisible(False)
        row.addWidget(self.busy, 1)
        b = QPushButton("Verlauf leeren")
        b.clicked.connect(self.clear_chat)
        b.setToolTip("Löscht den bisherigen Gesprächsverlauf – die KI fängt wieder ohne Vorwissen an.")
        row.addWidget(b)
        self.btn_send = QPushButton("Senden")
        self.btn_send.setDefault(True)
        self.btn_send.clicked.connect(self.send)
        row.addWidget(self.btn_send)
        lay.addLayout(row)

        self.say("system", "Lokale KI über <b>Ollama</b>. Alles bleibt auf deinem Rechner. "
                 "Bildfunktionen brauchen ein Bildmodell (z. B. gemma3 oder qwen2.5vl).")
        from .tips import AI, apply_tips
        apply_tips(self, AI)
        self.refresh()

    # ------------------------------------------------------------ Helfer
    def eventFilter(self, obj, ev):
        from PySide6.QtCore import QEvent
        if obj is self.input and ev.type() == QEvent.KeyPress and \
                ev.key() in (Qt.Key_Return, Qt.Key_Enter) and ev.modifiers() & Qt.ControlModifier:
            self.send()
            return True
        return super().eventFilter(obj, ev)

    def run_bg(self, fn, on_result, on_error=None, on_progress=None, busy=True):
        w = FuncWorker(fn)
        w.result.connect(on_result)
        w.error.connect(on_error or (lambda m: self.say("fehler", html.escape(m))))
        if on_progress:
            w.progress.connect(on_progress)
        w.finished.connect(lambda: self._done(w))
        self.workers.append(w)
        if busy:
            self.set_busy(True)
        w.start()
        return w

    def _done(self, w):
        # „finished“ kommt kurz bevor der Thread wirklich endet – erst abwarten, dann die
        # letzte Referenz loslassen (sonst „QThread: Destroyed while thread is still running“)
        w.wait(5000)
        if w in self.workers:
            self.workers.remove(w)
        if not any(not getattr(x, "background", False) for x in self.workers):
            self.set_busy(False)

    def set_busy(self, on: bool):
        self.busy.setVisible(on)
        for b in (self.btn_send, self.btn_suggest, self.btn_texts, self.btn_unread,
                  self.btn_review):
            b.setEnabled(not on)

    def say(self, who: str, text_html: str):
        style = {"du": ("Du", "#2a6fdb"), "ki": ("KI", "#1a8a4a"),
                 "system": ("ℹ", "#888888"), "fehler": ("Fehler", "#c0392b"),
                 "aktion": ("⚙", "#b9770e")}[who]
        self.chat.append(f'<p style="margin:4px 0"><b style="color:{style[1]}">{style[0]}:</b> '
                         f'{text_html}</p>')
        self.chat.verticalScrollBar().setValue(self.chat.verticalScrollBar().maximum())

    def clear_chat(self):
        self.chat.clear()
        self.assistant.reset()
        self.btn_apply.setVisible(False)

    @property
    def model_name(self) -> str:
        return self.model.currentText().strip()

    # ------------------------------------------------------------ Ollama
    def refresh(self):
        def job(_w):
            if not self.client.available():
                return None
            return self.client.version(), self.client.model_names()
        w = self.run_bg(job, self._on_refresh, busy=False)
        w.background = True

    @property
    def is_ollama(self) -> bool:
        return getattr(self.client, "kind", "ollama") == "ollama"

    def choose_server(self):
        dlg = ServerDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        self.set_server(dlg.values())

    def set_server(self, values: dict):
        """Neuen KI-Server übernehmen (speichern, Client neu anlegen, Modelle neu laden)."""
        cfg = config.save(values)
        self.client = make_client(cfg)
        self.assistant.client = self.client
        self.assistant.model = cfg.get(model_key(cfg)) or ""
        self.model.blockSignals(True)
        self.model.setCurrentText(self.assistant.model)
        self.model.blockSignals(False)
        self.say("system", f"KI-Server: {html.escape(SERVER_KINDS[cfg['ki_server']])} "
                           f"({html.escape(getattr(self.client, 'url', ''))})")
        self.refresh()

    def _on_refresh(self, res):
        cfg = config.load()
        cur = self.model_name or cfg.get(model_key(cfg))
        self.model.blockSignals(True)
        self.model.clear()
        what = "Ollama" if self.is_ollama else "KI-Server"
        if res is None:
            self.status.setText(f'<span style="color:#c0392b">● {what} nicht erreichbar</span>')
            self.btn_start.setVisible(self.is_ollama)
            names = []
        else:
            ver, names = res
            label = f"Ollama {ver}" if self.is_ollama else ver
            self.status.setText(f'<span style="color:#1a8a4a">● {html.escape(label)} verbunden'
                                '</span>')
            self.btn_start.setVisible(False)
        for n in names:
            self.model.addItem(n)
        recommended = RECOMMENDED_MODELS if self.is_ollama else RECOMMENDED_VLLM_MODELS
        if self.is_ollama:     # vLLM: nur Modelle, die der Server wirklich anbietet
            for n, desc in recommended:
                if n not in names:
                    self.model.addItem(f"{n}")
                    self.model.setItemData(self.model.count() - 1, desc, Qt.ToolTipRole)
        self.model.blockSignals(False)
        self.installed = set(names)
        if not self.is_ollama and names and cur not in names:
            cur = names[0]                  # vLLM bietet meist genau ein Modell an
        fallback = RECOMMENDED_MODELS[0][0] if self.is_ollama else ""
        self.model.setCurrentText(cur or (names[0] if names else fallback))
        self.on_model_changed(self.model_name)

    def on_model_changed(self, name: str):
        name = name.strip()
        self.assistant.model = name
        if name:
            config.save({model_key(config.load()): name})
        inst = name in getattr(self, "installed", set())
        if self.is_ollama:
            desc = dict(RECOMMENDED_MODELS).get(name, "")
            self.model_info.setText(("✓ installiert" if inst
                                     else "nicht installiert – „Laden“ drücken")
                                    + (f" · {desc}" if desc else ""))
        else:
            desc = dict(RECOMMENDED_VLLM_MODELS).get(name, "")
            vision = "" if self.client.has_vision(name) else \
                " · vermutlich kein Bildmodell – Bild-Funktionen gehen dann nicht"
            self.model_info.setText(("✓ auf dem Server verfügbar" if inst
                                     else "nicht auf dem Server (Modell wird beim Start von vLLM "
                                          "festgelegt)") + (f" · {desc}" if desc else "") + vision)
        self.btn_pull.setVisible(self.is_ollama)
        self.btn_pull.setEnabled(self.is_ollama and not inst and bool(name))

    def start_ollama(self):
        from .. import installer

        def job(_w):
            exe = installer.find_ollama()
            if not exe:
                return "fehlt"
            return "ok" if installer.start_ollama(exe) else "nicht gestartet"

        def done(res):
            if res == "fehlt":
                if QMessageBox.question(self, "Ollama", "Ollama ist nicht installiert. "
                                        "Jetzt automatisch installieren?") == QMessageBox.Yes:
                    self.window().open_components(auto_ai=True)
            elif res != "ok":
                self.say("fehler", "Ollama konnte nicht gestartet werden.")
            self.refresh()
        self.say("system", "Starte Ollama …")
        self.run_bg(job, done)

    def pull_model(self):
        name = self.model_name
        if not name:
            return
        self.pull_bar.setVisible(True)
        self.pull_bar.setValue(0)
        self.btn_pull.setEnabled(False)
        self.say("system", f"Lade Modell <b>{html.escape(name)}</b> herunter …")

        def job(w):
            self.client.pull(name, lambda p, s: w.progress.emit(p, s),
                             lambda: w.stop_requested)
            return name

        def prog(p, s):
            if p >= 0:
                self.pull_bar.setValue(p)
            self.pull_bar.setFormat(f"{s} {p}%" if p >= 0 else s)

        def done(_):
            self.pull_bar.setVisible(False)
            self.say("system", f"Modell <b>{html.escape(name)}</b> ist bereit.")
            self.refresh()

        def err(m):
            self.pull_bar.setVisible(False)
            self.btn_pull.setEnabled(True)
            self.say("fehler", html.escape(m))
        w = self.run_bg(job, done, err, prog, busy=False)
        w.background = True

    # ------------------------------------------------------------ Chat
    def send(self):
        text = self.input.toPlainText().strip()
        if not text:
            return
        self.input.clear()
        self.say("du", html.escape(text).replace("\n", "<br>"))
        self.chatRequested.emit(text, self.send_image.isChecked())

    def show_answer(self, data: dict, executor):
        ans = data.get("antwort", "")
        self.say("ki", html.escape(ans).replace("\n", "<br>") if ans else "<i>(keine Antwort)</i>")
        acts = data.get("aktionen") or []
        if not acts:
            return
        if self.auto_exec.isChecked():
            executor(acts)
        else:
            self.pending_actions = acts
            self.say("aktion", "Vorschlag: " + html.escape("; ".join(
                _describe(a) for a in acts)))
            self.btn_apply.setVisible(True)

    def _confirm_actions(self):
        self.btn_apply.setVisible(False)
        acts, self.pending_actions = self.pending_actions, []
        self.actionsConfirmed.emit(acts)


def _describe(a: dict) -> str:
    k = a.get("aktion")
    if k == "einstellung":
        return f"{a.get('name')} = {a.get('wert')}"
    rest = ", ".join(f"{x}={y}" for x, y in a.items() if x != "aktion")
    return f"{k}" + (f" ({rest})" if rest else "")


describe_action = _describe
