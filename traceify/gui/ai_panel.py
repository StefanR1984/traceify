"""KI-Assistent (Ollama) als Seitenleiste."""
from __future__ import annotations

import html
import traceback

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QHBoxLayout, QLabel,
                               QMessageBox, QPlainTextEdit, QProgressBar, QPushButton,
                               QTextBrowser, QToolButton, QVBoxLayout, QWidget)

from .. import config
from ..ai import RECOMMENDED_MODELS, Assistant, OllamaClient


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
        self.client = OllamaClient(cfg["ollama_url"], cfg.get("ollama_timeout") or 300)
        self.assistant = Assistant(self.client, cfg["ollama_model"])
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
        row.addWidget(b)
        self.btn_send = QPushButton("Senden")
        self.btn_send.setDefault(True)
        self.btn_send.clicked.connect(self.send)
        row.addWidget(self.btn_send)
        lay.addLayout(row)

        self.say("system", "Lokale KI über <b>Ollama</b>. Alles bleibt auf deinem Rechner. "
                 "Bildfunktionen brauchen ein Bildmodell (z. B. gemma3 oder qwen2.5vl).")
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

    def _on_refresh(self, res):
        cur = self.model_name or config.load().get("ollama_model")
        self.model.blockSignals(True)
        self.model.clear()
        if res is None:
            self.status.setText('<span style="color:#c0392b">● Ollama nicht erreichbar</span>')
            self.btn_start.setVisible(True)
            names = []
        else:
            ver, names = res
            self.status.setText(f'<span style="color:#1a8a4a">● Ollama {ver} verbunden</span>')
            self.btn_start.setVisible(False)
        for n in names:
            self.model.addItem(n)
        for n, desc in RECOMMENDED_MODELS:
            if n not in names:
                self.model.addItem(f"{n}")
                self.model.setItemData(self.model.count() - 1, desc, Qt.ToolTipRole)
        self.model.blockSignals(False)
        self.installed = set(names)
        self.model.setCurrentText(cur or (names[0] if names else RECOMMENDED_MODELS[0][0]))
        self.on_model_changed(self.model_name)

    def on_model_changed(self, name: str):
        name = name.strip()
        self.assistant.model = name
        if name:
            config.save({"ollama_model": name})
        inst = name in getattr(self, "installed", set())
        desc = dict(RECOMMENDED_MODELS).get(name, "")
        self.model_info.setText(("✓ installiert" if inst else "nicht installiert – „Laden“ drücken")
                                + (f" · {desc}" if desc else ""))
        self.btn_pull.setEnabled(not inst and bool(name))

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
