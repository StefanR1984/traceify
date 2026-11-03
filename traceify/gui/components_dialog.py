"""Dialog: Zustand der Komponenten anzeigen und Fehlendes automatisch installieren."""
from __future__ import annotations

from PySide6.QtWidgets import (QCheckBox, QComboBox, QDialog, QHBoxLayout, QLabel,
                               QPlainTextEdit, QPushButton, QVBoxLayout)

from .. import config, installer
from ..ai import RECOMMENDED_MODELS
from .ai_panel import FuncWorker


class ComponentsDialog(QDialog):
    def __init__(self, parent=None, auto_ai: bool = False):
        super().__init__(parent)
        self.setWindowTitle("Komponenten")
        self.resize(620, 520)
        self.worker = None
        lay = QVBoxLayout(self)
        self.state = QLabel("")
        self.state.setWordWrap(True)
        lay.addWidget(self.state)

        row = QHBoxLayout()
        self.with_ai = QCheckBox("KI (Ollama) einbeziehen, Modell:")
        self.with_ai.setChecked(auto_ai or config.load().get("ki") != "nein")
        row.addWidget(self.with_ai)
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.addItems([m for m, _ in RECOMMENDED_MODELS])
        self.model.setCurrentText(config.load().get("ollama_model") or RECOMMENDED_MODELS[0][0])
        row.addWidget(self.model, 1)
        lay.addLayout(row)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        lay.addWidget(self.log, 1)

        row = QHBoxLayout()
        self.btn_check = QPushButton("Status prüfen")
        self.btn_check.clicked.connect(self.check)
        self.btn_install = QPushButton("Fehlendes automatisch installieren")
        self.btn_install.clicked.connect(self.install)
        b = QPushButton("Schließen")
        b.clicked.connect(self.close)
        row.addWidget(self.btn_check)
        row.addWidget(self.btn_install)
        row.addStretch(1)
        row.addWidget(b)
        lay.addLayout(row)
        self.check()
        if auto_ai:
            self.install()

    def _run(self, fn, done):
        self.btn_check.setEnabled(False)
        self.btn_install.setEnabled(False)
        w = FuncWorker(fn)
        w.progress.connect(lambda _p, m: self.log.appendPlainText(m))
        w.result.connect(done)
        w.error.connect(lambda m: self.log.appendPlainText("FEHLER: " + m))
        w.finished.connect(self._finished)
        self.worker = w
        w.start()

    def _finished(self):
        self.btn_check.setEnabled(True)
        self.btn_install.setEnabled(True)
        self.worker = None

    def check(self):
        self._run(lambda _w: installer.status(), self._show_state)

    def _show_state(self, st: dict):
        rows = "".join(f"<tr><td>{k}</td><td>{'✅ ' + str(v) if v else '❌ fehlt'}</td></tr>"
                       for k, v in st.items())
        self.state.setText(f"<table cellspacing=4>{rows}</table>")

    def install(self):
        with_ai = self.with_ai.isChecked()
        model = self.model.currentText().strip() or None

        def job(w):
            installer.LOG = lambda m: w.progress.emit(0, str(m))
            try:
                installer.setup(auto=True, with_ai=with_ai, model=model, python_env=False)
            finally:
                installer.LOG = print
            return installer.status()

        def done(st):
            self._show_state(st)
            self.log.appendPlainText("\nFertig. Änderungen an der Texterkennung wirken sofort.")
            p = self.parent()
            if p is not None and hasattr(p, "ai_panel"):
                p.ai_panel.refresh()
        self._run(job, done)

    def closeEvent(self, ev):
        if self.worker and self.worker.isRunning():
            self.log.appendPlainText("Bitte warten, bis die Installation fertig ist …")
            ev.ignore()
            return
        super().closeEvent(ev)
