"""Dialog für die Stapelkonvertierung."""
from __future__ import annotations

import os

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFileDialog,
                               QFormLayout, QHBoxLayout, QLineEdit, QListWidget,
                               QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QVBoxLayout, QWidget)

from ..api import batch_convert
from ..core import loader


class BatchWorker(QThread):
    progress = Signal(int, int, str)
    itemDone = Signal(object)
    finishedWith = Signal(list)

    def __init__(self, sources, out_dir, formats, settings, gcode, dxf_version, pdf_dpi,
                 ai=False, rules=""):
        super().__init__()
        self.args = (sources, out_dir, formats, settings, gcode, dxf_version, pdf_dpi)
        self.ai, self.rules = ai, rules
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        sources, out_dir, formats, settings, gcode, ver, dpi = self.args
        res = batch_convert(sources, out_dir, formats, settings, gcode, dxf_version=ver,
                            pdf_dpi=dpi, progress=lambda i, n, m: self.progress.emit(i, n, m),
                            should_stop=lambda: self._stop, ai=self.ai, rules=self.rules,
                            on_item=lambda it: self.itemDone.emit(it))
        self.finishedWith.emit(res)


class BatchDialog(QDialog):
    def __init__(self, parent, settings_getter, gcode_getter, dxf_version_getter, pdf_dpi_getter):
        super().__init__(parent)
        self.setWindowTitle("Stapelkonvertierung")
        self.resize(640, 560)
        self._get = (settings_getter, gcode_getter, dxf_version_getter, pdf_dpi_getter)
        self.worker = None

        lay = QVBoxLayout(self)
        self.files = QListWidget()
        lay.addWidget(self.files)
        row = QHBoxLayout()
        for text, fn in (("Dateien hinzufügen …", self.add_files),
                         ("Ordner hinzufügen …", self.add_folder),
                         ("Liste leeren", self.files.clear)):
            b = QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
        lay.addLayout(row)
        self.recursive = QCheckBox("Unterordner einbeziehen")
        lay.addWidget(self.recursive)

        form = QFormLayout()
        out_row = QHBoxLayout()
        self.out_dir = QLineEdit(os.path.join(os.path.expanduser("~"), "Traceify-Ausgabe"))
        b = QPushButton("…")
        b.setFixedWidth(32)
        b.clicked.connect(self.pick_out)
        out_row.addWidget(self.out_dir)
        out_row.addWidget(b)
        w = QWidget()
        w.setLayout(out_row)
        form.addRow("Zielordner:", w)
        fmt_row = QHBoxLayout()
        self.f_dxf = QCheckBox("DXF")
        self.f_dxf.setChecked(True)
        self.f_svg = QCheckBox("SVG")
        self.f_nc = QCheckBox("G-Code (.nc)")
        self.f_dwg = QCheckBox("DWG")
        from ..export.dwg import available as oda_available
        if not oda_available():
            self.f_dwg.setEnabled(False)
            self.f_dwg.setToolTip("Benötigt den kostenlosen ODA File Converter")
        for c in (self.f_dxf, self.f_dwg, self.f_svg, self.f_nc):
            fmt_row.addWidget(c)
        w = QWidget()
        w.setLayout(fmt_row)
        form.addRow("Formate:", w)
        lay.addLayout(form)

        from PySide6.QtWidgets import QGroupBox
        g = QGroupBox("KI (Ollama) – optional")
        gl = QVBoxLayout(g)
        self.ai = QCheckBox("KI sieht sich jede Datei an und wählt die Einstellungen")
        gl.addWidget(self.ai)
        self.rules = QPlainTextEdit()
        self.rules.setPlaceholderText(
            "Regeln in Klartext, z. B.:\n"
            "Grundrisse als DXF mit Maßstab aus dem Plan und dicken Wänden auf eigenem Layer.\n"
            "Logos als CNC-Umriss, G-Code mit 2 mm Frästiefe, 3 mm Fräser, außen korrigiert.\n"
            "Handschriftliche Notizen und Fotos überspringen.")
        self.rules.setMaximumHeight(90)
        self.rules.setEnabled(False)
        self.ai.toggled.connect(self.rules.setEnabled)
        gl.addWidget(self.rules)
        lay.addWidget(g)

        self.bar = QProgressBar()
        lay.addWidget(self.bar)
        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        lay.addWidget(self.log)

        self.buttons = QDialogButtonBox()
        self.btn_start = self.buttons.addButton("Start", QDialogButtonBox.AcceptRole)
        self.btn_stop = self.buttons.addButton("Abbrechen", QDialogButtonBox.RejectRole)
        self.btn_close = self.buttons.addButton("Schließen", QDialogButtonBox.DestructiveRole)
        self.btn_start.clicked.connect(self.start)
        self.btn_stop.clicked.connect(self.stop)
        self.btn_close.clicked.connect(self.close)
        self.btn_stop.setEnabled(False)
        lay.addWidget(self.buttons)

    def add_files(self):
        fs, _ = QFileDialog.getOpenFileNames(
            self, "Dateien wählen", "", "Bilder & PDF (*.png *.jpg *.jpeg *.bmp *.tif *.tiff "
            "*.gif *.webp *.pdf)")
        for f in fs:
            self.files.addItem(f)

    def add_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Ordner wählen")
        if d:
            for f in loader.list_inputs(d, self.recursive.isChecked()):
                self.files.addItem(f)

    def pick_out(self):
        d = QFileDialog.getExistingDirectory(self, "Zielordner wählen", self.out_dir.text())
        if d:
            self.out_dir.setText(d)

    def start(self):
        sources = [self.files.item(i).text() for i in range(self.files.count())]
        fmts = [e for c, e in ((self.f_dxf, ".dxf"), (self.f_dwg, ".dwg"), (self.f_svg, ".svg"),
                               (self.f_nc, ".nc"))
                if c.isChecked()]
        if not sources:
            QMessageBox.information(self, "Stapel", "Bitte zuerst Dateien hinzufügen.")
            return
        if not fmts:
            QMessageBox.information(self, "Stapel", "Bitte mindestens ein Format wählen.")
            return
        sg, gg, vg, dg = self._get
        self.log.clear()
        use_ai = self.ai.isChecked()
        if use_ai:
            from ..ai import default_client
            client, _ = default_client()
            if not client.available():
                QMessageBox.warning(self, "Stapel", "Ollama ist nicht erreichbar – bitte im "
                                    "KI-Assistenten starten oder KI hier abwählen.")
                return
        self.worker = BatchWorker(sources, self.out_dir.text(), fmts, sg(), gg(), vg(), dg(),
                                  ai=use_ai, rules=self.rules.toPlainText().strip())
        self.worker.itemDone.connect(self.on_item)
        self.worker.progress.connect(self.on_progress)
        self.worker.finishedWith.connect(self.on_done)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.worker.start()

    def stop(self):
        if self.worker:
            self.worker.stop()
            self.log.appendPlainText("… wird nach der aktuellen Datei abgebrochen")

    def on_progress(self, i, n, msg):
        self.bar.setMaximum(max(1, n))
        self.bar.setValue(i)
        if msg != "Fertig":
            self.log.appendPlainText(f"[{i + 1}/{n}] {msg}")

    def on_item(self, it):
        if it.note:
            self.log.appendPlainText("   " + it.note)
        if it.error:
            self.log.appendPlainText(f"   FEHLER: {it.error}")

    def on_done(self, results):
        ok = [r for r in results if not r.error and not r.skipped]
        skipped = sum(1 for r in results if r.skipped)
        self.log.appendPlainText(f"\nFertig: {len(ok)} von {len(results)} erfolgreich"
                                 + (f", {skipped} übersprungen" if skipped else "")
                                 + f" → {self.out_dir.text()}")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.worker = None

    def closeEvent(self, ev):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(30000)
        super().closeEvent(ev)
