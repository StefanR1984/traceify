"""Hauptfenster von Traceify."""
from __future__ import annotations

import math
import os
import traceback

import numpy as np
from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (QApplication, QDockWidget, QFileDialog,
                               QInputDialog, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QProgressBar, QSlider,
                               QSpinBox, QToolBar, QVBoxLayout, QWidget)

from .. import __version__
from ..api import load_settings, save_settings
from ..core import loader, preprocess
from ..core.model import LAYER_COLORS, Drawing
from ..core.pipeline import convert
from ..export import export
from .batch_dialog import BatchDialog
from .canvas import Canvas
from .ai_panel import AiPanel, FuncWorker, describe_action
from .settings_panel import SettingsPanel

FILE_FILTER = ("Bilder & PDF (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif *.webp *.pdf);;"
               "Alle Dateien (*)")


class ConvertWorker(QThread):
    progress = Signal(int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, gray, settings, scale, source):
        super().__init__()
        self.args = (gray, settings, scale, source)

    def run(self):
        try:
            gray, s, scale, src = self.args
            res = convert(gray, s, scale, src, progress=lambda p, m: self.progress.emit(p, m))
            self.done.emit(res)
        except Exception:
            self.failed.emit(traceback.format_exc())


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Traceify")
        self.resize(1400, 900)
        self.qs = QSettings("Traceify", "Traceify")
        self.path = None
        self.page = 0
        self.gray: np.ndarray | None = None
        self.img_scale = 25.4 / 300
        self.binary = None
        self.drawing: Drawing | None = None
        self.undo_stack = []      # ("entities", liste) | ("raster", gray, drawing)
        self.worker = None
        self.dxf_version = self.qs.value("dxf_version", "R2010")
        self.show_binary = False

        self.canvas = Canvas()
        self.setCentralWidget(self.canvas)
        self.canvas.cropSelected.connect(self.on_crop)
        self.canvas.measured.connect(self.on_measured)
        self.canvas.mouseMoved.connect(self.on_mouse)
        self.canvas.scene().selectionChanged.connect(self.update_status)

        self.panel = SettingsPanel()
        self.panel.convertRequested.connect(self.run_convert)
        self.panel.previewBinaryRequested.connect(self.preview_binary)
        self.panel.btn_calibrate.clicked.connect(self.start_calibrate)
        dock = QDockWidget("Einstellungen", self)
        dock.setObjectName("dock_settings")
        dock.setWidget(self.panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.dock_settings = dock

        self.layer_list = QListWidget()
        self.layer_list.itemChanged.connect(self.on_layer_toggled)
        lw = QWidget()
        ll = QVBoxLayout(lw)
        ll.setContentsMargins(4, 4, 4, 4)
        ll.addWidget(self.layer_list)
        ll.addWidget(QLabel("Raster-Deckkraft:"))
        self.opacity = QSlider(Qt.Horizontal)
        self.opacity.setRange(0, 100)
        self.opacity.setValue(45)
        self.opacity.valueChanged.connect(lambda v: self.canvas.set_raster_opacity(v / 100))
        ll.addWidget(self.opacity)
        self.stats_label = QLabel("")
        self.stats_label.setWordWrap(True)
        ll.addWidget(self.stats_label)
        dock = QDockWidget("Layer", self)
        dock.setObjectName("dock_layers")
        dock.setWidget(lw)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)
        self.dock_layers = dock

        self.ai_panel = AiPanel()
        self.ai_panel.suggestRequested.connect(self.ai_suggest)
        self.ai_panel.correctTextsRequested.connect(self.ai_correct_texts)
        self.ai_panel.reviewRequested.connect(self.ai_review)
        self.ai_panel.chatRequested.connect(self.ai_chat)
        self.ai_panel.actionsConfirmed.connect(self.execute_actions)
        dock = QDockWidget("KI-Assistent", self)
        dock.setObjectName("dock_ai")
        dock.setWidget(self.ai_panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)
        self.tabifyDockWidget(self.dock_settings, dock)
        self.dock_settings.raise_()
        self.dock_ai = dock
        self.ai_workers = []

        self._build_actions()
        self._build_menus()
        self._build_toolbar()

        self.progress = QProgressBar()
        self.progress.setMaximumWidth(220)
        self.progress.setVisible(False)
        self.pos_label = QLabel("")
        self.statusBar().addPermanentWidget(self.pos_label)
        self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().showMessage("Datei öffnen (Strg+O) oder hierher ziehen.")
        self.setAcceptDrops(True)

        geo = self.qs.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        st = self.qs.value("state")
        if st is not None:
            self.restoreState(st)
        self.update_actions()
        self._autostart_ollama()

    # ------------------------------------------------------------------ UI
    def _act(self, text, slot, shortcut=None, tip=None, checkable=False):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        if tip:
            a.setStatusTip(tip)
            a.setToolTip(tip)
        a.setCheckable(checkable)
        a.triggered.connect(slot)
        return a

    def _build_actions(self):
        A = self._act
        self.a_open = A("Öffnen …", self.open_dialog, QKeySequence.Open, "Bild oder PDF öffnen")
        self.a_convert = A("Konvertieren", self.run_convert, "F5", "Aktuelles Bild vektorisieren")
        self.a_dxf = A("Als DXF exportieren …", lambda: self.export_dialog(".dxf"),
                       "Ctrl+E", "Für AutoCAD, LibreCAD, Fusion, SolidWorks …")
        self.a_svg = A("Als SVG exportieren …", lambda: self.export_dialog(".svg"))
        self.a_nc = A("Als G-Code exportieren …", lambda: self.export_dialog(".nc"),
                      "Ctrl+G", "Werkzeugwege für CNC-Fräse, Laser, Plasma")
        self.a_save_set = A("Einstellungen speichern …", self.save_settings)
        self.a_load_set = A("Einstellungen laden …", self.load_settings)
        self.a_quit = A("Beenden", self.close, QKeySequence.Quit)

        self.a_undo = A("Rückgängig", self.undo, QKeySequence.Undo)
        self.a_delete = A("Auswahl löschen", self.delete_selected, QKeySequence.Delete,
                          "Markierte Objekte entfernen")
        self.a_select_all = A("Alles auswählen", self.select_all, QKeySequence.SelectAll)
        self.a_select_layer = A("Ganzen Layer der Auswahl auswählen", self.select_layer)

        self.a_rot_l = A("90° nach links drehen", lambda: self.rotate(-1))
        self.a_rot_r = A("90° nach rechts drehen", lambda: self.rotate(1))
        self.a_crop = A("Zuschneiden …", self.start_crop, "Ctrl+K",
                        "Rechteck aufziehen, um den Bildausschnitt festzulegen")
        self.a_deskew = A("Schräglage jetzt begradigen", self.deskew_now)
        self.a_invert = A("Farben invertieren", self.invert_now)

        self.a_fit = A("Einpassen", self.canvas.fit, "Ctrl+0")
        self.a_zoom_in = A("Vergrößern", lambda: self.canvas.zoom(1.25), QKeySequence.ZoomIn)
        self.a_zoom_out = A("Verkleinern", lambda: self.canvas.zoom(0.8), QKeySequence.ZoomOut)
        self.a_zoom_100 = A("100 %", self.canvas.zoom_100, "Ctrl+1")
        self.a_show_vec = A("Vektoren anzeigen", self.canvas.set_vectors_visible, "V",
                            checkable=True)
        self.a_show_vec.setChecked(True)
        self.a_show_bin = A("Binärbild statt Original", self.toggle_binary, "B",
                            checkable=True)

        self.a_batch = A("Stapelkonvertierung …", self.open_batch, "Ctrl+B",
                         "Viele Dateien / PDF-Seiten auf einmal umwandeln")
        self.a_calib = A("Maßstab kalibrieren …", self.start_calibrate)
        self.a_components = A("Komponenten prüfen / installieren …", self.open_components)
        self.a_ai_suggest = A("Bild analysieren && Einstellungen wählen", self.ai_suggest,
                              "Ctrl+Shift+A")
        self.a_ai_texts = A("Erkannte Texte mit KI prüfen", self.ai_correct_texts)
        self.a_ai_review = A("Ergebnis bewerten && verbessern", self.ai_review)
        self.a_ai_show = A("KI-Assistent anzeigen", self.show_ai, "Ctrl+Shift+K")
        self.a_help = A("Kurzanleitung", self.show_help, "F1")
        self.a_about = A("Über Traceify", self.show_about)

    def _build_menus(self):
        m = self.menuBar().addMenu("&Datei")
        for a in (self.a_open, None, self.a_dxf, self.a_svg, self.a_nc, None,
                  self.a_save_set, self.a_load_set, None, self.a_quit):
            m.addSeparator() if a is None else m.addAction(a)
        dm = m.addMenu("DXF-Version")
        for v in ("R12", "R2000", "R2007", "R2010", "R2013", "R2018"):
            a = QAction(v, self, checkable=True)
            a.setChecked(v == self.dxf_version)
            a.triggered.connect(lambda _=False, v=v, menu=dm: self.set_dxf_version(v, menu))
            dm.addAction(a)

        m = self.menuBar().addMenu("&Bearbeiten")
        for a in (self.a_undo, None, self.a_select_all, self.a_select_layer, self.a_delete):
            m.addSeparator() if a is None else m.addAction(a)

        m = self.menuBar().addMenu("&Raster")
        for a in (self.a_rot_l, self.a_rot_r, self.a_crop, self.a_deskew, self.a_invert):
            m.addAction(a)

        m = self.menuBar().addMenu("&Ansicht")
        for a in (self.a_fit, self.a_zoom_100, self.a_zoom_in, self.a_zoom_out, None,
                  self.a_show_vec, self.a_show_bin):
            m.addSeparator() if a is None else m.addAction(a)
        m.addSeparator()
        m.addAction(self.dock_settings.toggleViewAction())
        m.addAction(self.dock_layers.toggleViewAction())
        m.addAction(self.dock_ai.toggleViewAction())

        m = self.menuBar().addMenu("&Werkzeuge")
        m.addAction(self.a_batch)
        m.addAction(self.a_calib)

        m.addSeparator()
        m.addAction(self.a_components)

        m = self.menuBar().addMenu("&KI")
        for a in (self.a_ai_show, None, self.a_ai_suggest, self.a_ai_texts, self.a_ai_review):
            m.addSeparator() if a is None else m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_components)

        m = self.menuBar().addMenu("&Hilfe")
        m.addAction(self.a_help)
        m.addAction(self.a_about)

    def _build_toolbar(self):
        short = {self.a_open: "Öffnen", self.a_convert: "▶ Konvertieren", self.a_dxf: "DXF",
                 self.a_nc: "G-Code", self.a_svg: "SVG", self.a_crop: "Zuschneiden",
                 self.a_rot_l: "⟲ 90°", self.a_rot_r: "⟳ 90°", self.a_fit: "Einpassen",
                 self.a_show_bin: "Binärbild", self.a_batch: "Stapel …",
                 self.a_ai_suggest: "✨ KI-Analyse", self.a_ai_show: "KI-Chat"}
        for a, t in short.items():
            a.setIconText(t)
        tb = QToolBar("Werkzeuge")
        tb.setObjectName("toolbar_main")
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(tb)
        tb.addAction(self.a_open)
        tb.addSeparator()
        tb.addWidget(QLabel(" Seite "))
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setEnabled(False)
        self.page_spin.valueChanged.connect(self.on_page_changed)
        tb.addWidget(self.page_spin)
        self.page_total = QLabel(" / 1 ")
        tb.addWidget(self.page_total)
        tb.addSeparator()
        tb.addAction(self.a_convert)
        tb.addSeparator()
        tb.addAction(self.a_dxf)
        tb.addAction(self.a_nc)
        tb.addAction(self.a_svg)
        tb.addSeparator()
        tb.addAction(self.a_crop)
        tb.addAction(self.a_rot_l)
        tb.addAction(self.a_rot_r)
        tb.addSeparator()
        tb.addAction(self.a_fit)
        tb.addAction(self.a_show_bin)
        tb.addSeparator()
        tb.addAction(self.a_batch)
        tb.addSeparator()
        tb.addAction(self.a_ai_suggest)
        tb.addAction(self.a_ai_show)

    def update_actions(self):
        has_img = self.gray is not None
        has_vec = self.drawing is not None and bool(self.drawing.entities)
        busy = self.worker is not None
        for a in (self.a_convert, self.a_rot_l, self.a_rot_r, self.a_crop, self.a_deskew,
                  self.a_invert, self.a_calib, self.a_show_bin, self.a_ai_suggest):
            a.setEnabled(has_img and not busy)
        for a in (self.a_dxf, self.a_svg, self.a_nc, self.a_delete, self.a_select_all,
                  self.a_select_layer, self.a_ai_texts, self.a_ai_review):
            a.setEnabled(has_vec and not busy)
        self.panel.btn_convert.setEnabled(has_img and not busy)
        self.a_undo.setEnabled(bool(self.undo_stack) and not busy)

    # --------------------------------------------------------------- Datei
    def dragEnterEvent(self, ev):
        if ev.mimeData().hasUrls():
            ev.acceptProposedAction()

    def dropEvent(self, ev):
        urls = [u.toLocalFile() for u in ev.mimeData().urls()]
        files = [u for u in urls if loader.is_supported(u)]
        if files:
            self.open_file(files[0])

    def open_dialog(self):
        start = self.qs.value("last_dir", os.path.expanduser("~"))
        f, _ = QFileDialog.getOpenFileName(self, "Datei öffnen", start, FILE_FILTER)
        if f:
            self.open_file(f)

    def open_file(self, path: str, page: int = 0):
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            n = loader.page_count(path)
            gray, scale = loader.load(path, page, self.panel.pdf_dpi.value())
        except Exception as exc:
            QMessageBox.critical(self, "Fehler", f"Datei konnte nicht geöffnet werden:\n{exc}")
            return
        finally:
            QApplication.restoreOverrideCursor()
        self.qs.setValue("last_dir", os.path.dirname(path))
        self.path, self.page = path, page
        self.gray, self.img_scale = gray, scale
        self.binary = None
        self.drawing = None
        self.undo_stack.clear()
        self.page_spin.blockSignals(True)
        self.page_spin.setMaximum(n)
        self.page_spin.setValue(page + 1)
        self.page_spin.setEnabled(n > 1)
        self.page_spin.blockSignals(False)
        self.page_total.setText(f" / {n} ")
        self.a_show_bin.setChecked(False)
        self.canvas.clear_entities()
        self.canvas.set_raster(gray)
        self.canvas.set_raster_opacity(1.0)
        self.refresh_layers()
        self.setWindowTitle(f"Traceify – {os.path.basename(path)}"
                            + (f" (Seite {page + 1}/{n})" if n > 1 else ""))
        dpi = 25.4 / scale
        self.statusBar().showMessage(
            f"{os.path.basename(path)}: {gray.shape[1]} × {gray.shape[0]} px, {dpi:.0f} dpi "
            f"→ {gray.shape[1] * scale:.1f} × {gray.shape[0] * scale:.1f} mm. "
            "Jetzt Einstellungen prüfen und »Konvertieren« (F5).")
        self.update_actions()

    def on_page_changed(self, v):
        if self.path:
            self.open_file(self.path, v - 1)

    # --------------------------------------------------------- Konvertieren
    def run_convert(self):
        if self.gray is None or self.worker:
            return
        s = self.panel.settings()
        self.worker = ConvertWorker(self.gray, s, self.img_scale,
                                    os.path.basename(self.path or ""))
        self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(self.on_converted)
        self.worker.failed.connect(self.on_failed)
        self.progress.setVisible(True)
        self.progress.setValue(0)
        self.update_actions()
        self.worker.start()

    def on_progress(self, p, msg):
        self.progress.setValue(p)
        self.statusBar().showMessage(msg)

    def _worker_finished(self):
        if self.worker:
            self.worker.wait()
        self.worker = None
        self.progress.setVisible(False)
        self.update_actions()

    def on_failed(self, tb):
        self._worker_finished()
        QMessageBox.critical(self, "Konvertierung fehlgeschlagen", tb[-2000:])

    def on_converted(self, res):
        self._worker_finished()
        if self.drawing is not None and self.drawing.entities:
            self.undo_stack.append(("drawing", self.drawing))
        self.drawing = res.drawing
        self.binary = res.binary
        self.canvas.set_entities(self.drawing.entities)
        self.canvas.set_vectors_visible(self.a_show_vec.isChecked())
        self.opacity.setValue(self.opacity.value())
        self.canvas.set_raster_opacity(self.opacity.value() / 100)
        if self.a_show_bin.isChecked():
            self.canvas.set_raster(255 - self.binary, keep_view=True)
            self.canvas.set_raster_opacity(self.opacity.value() / 100)
        self.refresh_layers()
        pend = getattr(self, "_pending_export", None)
        if pend:
            self._pending_export = None
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: self.export_dialog(pend))
        st = self.drawing.stats()
        self.statusBar().showMessage(
            "Fertig: " + ", ".join(f"{v} {k}" for k, v in st.items() if v) +
            ". Objekte anklicken und mit Entf löschen; Export über Strg+E / Strg+G.")
        self.update_actions()

    def preview_binary(self):
        if self.gray is None:
            return
        s = self.panel.settings()
        self.binary = preprocess.to_binary(self.gray, s.preprocess)
        self.a_show_bin.setChecked(True)
        self.canvas.set_raster(255 - self.binary, keep_view=True)
        self.canvas.set_raster_opacity(1.0 if not self.drawing else self.opacity.value() / 100)

    def toggle_binary(self, on):
        if self.gray is None:
            return
        if on:
            if self.binary is None or self.binary.shape != self.gray.shape:
                self.binary = preprocess.to_binary(self.gray, self.panel.settings().preprocess)
            self.canvas.set_raster(255 - self.binary, keep_view=True)
        else:
            self.canvas.set_raster(self.gray, keep_view=True)
        self.canvas.set_raster_opacity(self.opacity.value() / 100 if self.drawing else 1.0)

    # --------------------------------------------------------------- Layer
    def refresh_layers(self):
        self.layer_list.blockSignals(True)
        self.layer_list.clear()
        if self.drawing:
            counts = {}
            for e in self.drawing.entities:
                counts[e.layer] = counts.get(e.layer, 0) + 1
            for layer in self.drawing.layers():
                it = QListWidgetItem(f"{layer}  ({counts[layer]})")
                it.setData(Qt.UserRole, layer)
                it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                it.setCheckState(Qt.Checked)
                pm = QPixmap(14, 14)
                pm.fill(QColor(*LAYER_COLORS.get(layer, (7, (0, 0, 0)))[1]))
                it.setIcon(QIcon(pm))
                self.layer_list.addItem(it)
        self.layer_list.blockSignals(False)
        self.update_status()

    def visible_layers(self):
        out = set()
        for i in range(self.layer_list.count()):
            it = self.layer_list.item(i)
            if it.checkState() == Qt.Checked:
                out.add(it.data(Qt.UserRole))
        return out

    def on_layer_toggled(self, it):
        self.canvas.set_layer_visible(it.data(Qt.UserRole), it.checkState() == Qt.Checked)

    def update_status(self):
        if not self.drawing:
            self.stats_label.setText("")
            return
        d = self.drawing
        sel = len(self.canvas.selected_entities())
        txt = "<br>".join(f"{k}: <b>{v}</b>" for k, v in d.stats().items())
        txt += (f"<br><br>Größe: {d.width * d.scale:.1f} × {d.height * d.scale:.1f} mm"
                f"<br>Maßstab: {d.scale:.5f} mm/px")
        if sel:
            txt += f"<br><br><b>{sel} ausgewählt</b> (Entf = löschen)"
        self.stats_label.setText(txt)

    def on_mouse(self, x, y):
        if self.gray is not None:
            s = self.drawing.scale if self.drawing else self.img_scale
            h = self.gray.shape[0]
            self.pos_label.setText(f"X {x * s:8.2f} mm   Y {(h - y) * s:8.2f} mm ")

    # ------------------------------------------------------------ Bearbeiten
    def delete_selected(self):
        sel = self.canvas.selected_entities()
        if not sel or not self.drawing:
            return
        self.undo_stack.append(("entities", list(self.drawing.entities)))
        ids = {id(e) for e in sel}
        self.drawing.entities = [e for e in self.drawing.entities if id(e) not in ids]
        self.canvas.remove_entity_items(sel)
        self.refresh_layers()
        self.statusBar().showMessage(f"{len(sel)} Objekte gelöscht (Strg+Z zum Rückgängigmachen).")
        self.update_actions()

    def select_all(self):
        for items in self.canvas.items_by_layer.values():
            for it in items:
                if it.isVisible():
                    it.setSelected(True)

    def select_layer(self):
        layers = {e.layer for e in self.canvas.selected_entities()}
        for l in layers:
            for it in self.canvas.items_by_layer.get(l, []):
                it.setSelected(True)

    def undo(self):
        if not self.undo_stack:
            return
        kind, *data = self.undo_stack.pop()
        if kind == "entities" and self.drawing:
            self.drawing.entities = data[0]
        elif kind == "drawing":
            self.drawing = data[0]
        elif kind == "raster":
            self.gray, self.drawing = data
            self.binary = None
            self.a_show_bin.setChecked(False)
            self.canvas.set_raster(self.gray)
        self.canvas.set_entities(self.drawing.entities if self.drawing else [])
        self.canvas.set_raster_opacity(self.opacity.value() / 100 if self.drawing else 1.0)
        self.refresh_layers()
        self.update_actions()

    # ---------------------------------------------------------------- Raster
    def _raster_edit(self, new_gray, msg):
        self.undo_stack.append(("raster", self.gray, self.drawing))
        self.gray = new_gray
        self.drawing = None
        self.binary = None
        self.a_show_bin.setChecked(False)
        self.canvas.clear_entities()
        self.canvas.set_raster(self.gray)
        self.canvas.set_raster_opacity(1.0)
        self.refresh_layers()
        self.statusBar().showMessage(msg + " – bitte neu konvertieren (F5).")
        self.update_actions()

    def rotate(self, d):
        if self.gray is not None:
            self._raster_edit(preprocess.rotate90(self.gray, d), "Gedreht")

    def start_crop(self):
        if self.gray is not None:
            self.statusBar().showMessage("Rechteck mit der Maus aufziehen …")
            self.canvas.start_crop()

    def on_crop(self, x, y, w, h):
        H, W = self.gray.shape
        w, h = min(w, W - x), min(h, H - y)
        if w > 5 and h > 5:
            self._raster_edit(preprocess.crop(self.gray, x, y, w, h), f"Zugeschnitten auf {w}×{h} px")

    def deskew_now(self):
        bw = preprocess.to_binary(self.gray, self.panel.settings().preprocess)
        a = preprocess.estimate_skew(bw)
        if abs(a) < 0.05:
            self.statusBar().showMessage("Keine Schräglage erkannt.")
            return
        self._raster_edit(preprocess.rotate(self.gray, a, border=255), f"Um {a:.2f}° begradigt")

    def invert_now(self):
        self._raster_edit(255 - self.gray, "Invertiert")

    # ----------------------------------------------------------- Maßstab
    def start_calibrate(self):
        if self.gray is None:
            return
        self.statusBar().showMessage("Maßstab: Anfangs- und Endpunkt einer bekannten Strecke "
                                     "anklicken (Rechtsklick = Abbruch).")
        self.canvas.start_measure()

    def on_measured(self, x1, y1, x2, y2):
        px = math.hypot(x2 - x1, y2 - y1)
        if px < 2:
            return
        cur = self.drawing.scale if self.drawing else (self.panel.settings().scale or self.img_scale)
        mm, ok = QInputDialog.getDouble(self, "Maßstab kalibrieren",
                                        f"Gemessene Strecke: {px:.1f} px.\nWahre Länge in mm:",
                                        px * cur, 0.0001, 1e7, 3)
        if not ok or mm <= 0:
            return
        scale = mm / px
        self.panel.set_manual_scale(scale)
        if self.drawing:
            self.drawing.scale = scale
            self.update_status()
        self.statusBar().showMessage(f"Maßstab gesetzt: {scale:.5f} mm/px")

    # ---------------------------------------------------------------- Export
    def set_dxf_version(self, v, menu):
        self.dxf_version = v
        self.qs.setValue("dxf_version", v)
        for a in menu.actions():
            a.setChecked(a.text() == v)

    def export_dialog(self, ext):
        if not self.drawing or not self.drawing.entities:
            return
        names = {".dxf": "DXF (*.dxf)", ".svg": "SVG (*.svg)",
                 ".nc": "G-Code (*.nc *.gcode *.tap *.ngc)"}
        base = os.path.splitext(os.path.basename(self.path or "zeichnung"))[0]
        if self.page_spin.maximum() > 1:
            base += f"_S{self.page + 1:03d}"
        start = os.path.join(self.qs.value("export_dir", os.path.dirname(self.path or "")), base + ext)
        f, _ = QFileDialog.getSaveFileName(self, "Exportieren", start, names[ext])
        if not f:
            return
        if not os.path.splitext(f)[1]:
            f += ext
        # Maßstab aus den Einstellungen übernehmen, falls nachträglich geändert
        s = self.panel.settings().scale
        if s:
            self.drawing.scale = s
        try:
            export(self.drawing, f, self.panel.gcode_settings(), self.dxf_version,
                   self.visible_layers())
        except Exception as exc:
            QMessageBox.critical(self, "Export fehlgeschlagen", str(exc))
            return
        self.qs.setValue("export_dir", os.path.dirname(f))
        self.statusBar().showMessage(f"Gespeichert: {f}")

    def save_settings(self):
        f, _ = QFileDialog.getSaveFileName(self, "Einstellungen speichern", "traceify.json",
                                           "JSON (*.json)")
        if f:
            save_settings(self.panel.settings(), f)

    def load_settings(self):
        f, _ = QFileDialog.getOpenFileName(self, "Einstellungen laden", "", "JSON (*.json)")
        if f:
            try:
                self.panel.set_settings(load_settings(f))
            except Exception as exc:
                QMessageBox.critical(self, "Fehler", str(exc))

    # ---------------------------------------------------------------- Werkzeuge
    def open_batch(self):
        dlg = BatchDialog(self, self.panel.settings, self.panel.gcode_settings,
                          lambda: self.dxf_version, self.panel.pdf_dpi.value)
        dlg.exec()

    def open_components(self, auto_ai: bool = False):
        from .components_dialog import ComponentsDialog
        ComponentsDialog(self, auto_ai=bool(auto_ai)).exec()

    def _autostart_ollama(self):
        from .. import config, installer
        ki = config.load().get("ki")
        if ki is None and installer.FROZEN and not installer.ollama_running():
            # Erster Start der installierten Version: einmal nach der KI fragen
            from PySide6.QtCore import QTimer
            QTimer.singleShot(800, self._ask_first_ai)
            return
        if ki != "ja":
            return

        def job(_w):
            return installer.start_ollama()
        w = FuncWorker(job)
        w.result.connect(lambda ok: self.ai_panel.refresh())
        w.finished.connect(lambda: self.ai_workers.remove(w) if w in self.ai_workers else None)
        self.ai_workers.append(w)
        w.start()

    def _ask_first_ai(self):
        from .. import config
        r = QMessageBox.question(
            self, "KI-Funktionen einrichten?",
            "Traceify kann eine lokale KI (Ollama) nutzen: Bilder analysieren, Einstellungen "
            "wählen, Texte prüfen und Aufträge im Chat ausführen. Alles läuft auf deinem "
            "Rechner.\n\nDafür werden Ollama und ein KI-Modell (ca. 3–4 GB) heruntergeladen.\n\n"
            "Jetzt einrichten? (Später jederzeit über Menü KI → Komponenten möglich.)")
        if r == QMessageBox.Yes:
            config.save({"ki": "ja"})
            self.open_components(auto_ai=True)
        else:
            config.save({"ki": "nein"})

    # ================================================================ KI
    def show_ai(self):
        self.dock_ai.show()
        self.dock_ai.raise_()

    def _ai_ready(self, need_image=True) -> bool:
        if need_image and self.gray is None:
            QMessageBox.information(self, "KI", "Bitte zuerst eine Datei öffnen.")
            return False
        if not self.ai_panel.model_name:
            QMessageBox.information(self, "KI", "Bitte im KI-Assistenten ein Modell wählen.")
            return False
        return True

    def _ai_run(self, fn, done, status_msg):
        self.show_ai()
        self.statusBar().showMessage(status_msg)
        self.ai_panel.run_bg(fn, done)

    def ai_suggest(self):
        if not self._ai_ready():
            return
        from ..ai import suggest_settings
        from ..gui_presets import PRESETS
        panel, gray = self.ai_panel, self.gray
        model = panel.model_name
        panel.say("system", "Analysiere das Bild …")

        def done(sug):
            preset = sug.get("vorlage")
            if preset in PRESETS:
                self.panel.preset.setCurrentText(preset)
                self.panel.apply_preset(preset)
            if sug.get("modus"):
                self.panel.set_value("modus", sug["modus"])
            self.panel.set_value("invertieren", bool(sug.get("invertieren")))
            self.panel.set_value("adaptiv", bool(sug.get("ungleichmaessig_beleuchtet")))
            self.panel.set_value("begradigen", bool(sug.get("schraeg")))
            if sug.get("verrauscht"):
                self.panel.despeckle.setValue(max(self.panel.despeckle.value(), 40))
            if "enthaelt_text" in sug and self.panel.ocr.isEnabled():
                self.panel.ocr.setChecked(bool(sug["enthaelt_text"]) and
                                          not self.panel.rb_cnc.isChecked())
            flags = [t for k, t in (("schraeg", "begradigen"), ("verrauscht", "entrauschen"),
                                    ("ungleichmaessig_beleuchtet", "adaptiver Schwellwert"),
                                    ("invertieren", "invertieren"), ("enthaelt_text", "OCR an"))
                     if sug.get(k)]
            import html as _h
            panel.say("ki", f"Erkannt: <b>{_h.escape(str(sug.get('art', '?')))}</b> → Vorlage "
                            f"<b>{_h.escape(str(preset))}</b>"
                            + (f" ({', '.join(flags)})" if flags else "") + "<br>"
                            + _h.escape(str(sug.get("begruendung", ""))))
            self.statusBar().showMessage("KI-Einstellungen übernommen – konvertiere …")
            self.run_convert()

        self._ai_run(lambda _w: suggest_settings(panel.client, model, gray), done,
                     "KI analysiert das Bild …")

    def ai_correct_texts(self):
        if not self._ai_ready() or not self.drawing:
            return
        from ..ai import correct_texts
        from ..core.model import Text
        if not self.drawing.by_type(Text):
            self.ai_panel.say("system", "Keine erkannten Texte vorhanden (OCR aktivieren und "
                                        "neu konvertieren).")
            return
        panel, gray, drawing = self.ai_panel, self.gray, self.drawing
        model = panel.model_name
        panel.say("system", f"Prüfe {len(drawing.by_type(Text))} Texte einzeln mit {model} …")

        def job(w):
            return correct_texts(panel.client, model, gray, drawing,
                                 lambda i, n, t: w.progress.emit(i, f"{i}/{n} {t}"),
                                 lambda: w.stop_requested)

        def done(fixes):
            if not fixes:
                panel.say("ki", "Alle Texte sehen korrekt aus – keine Änderungen.")
                return
            self._review_text_fixes(fixes)
        w = self.ai_panel.run_bg(job, done)
        w.progress.connect(lambda _i, m: self.statusBar().showMessage("KI liest Texte: " + m))
        self.show_ai()

    def _review_text_fixes(self, fixes):
        from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QTableWidget,
                                       QTableWidgetItem)
        dlg = QDialog(self)
        dlg.setWindowTitle("KI-Textkorrekturen")
        dlg.resize(620, 420)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Häkchen = Korrektur übernehmen. Neue Texte sind editierbar."))
        tab = QTableWidget(len(fixes), 3)
        tab.setHorizontalHeaderLabels(["Bisher (OCR)", "Neu (KI)", "KI sicher"])
        for r, f in enumerate(fixes):
            a = QTableWidgetItem(f.old)
            a.setFlags(a.flags() & ~Qt.ItemIsEditable)
            a.setFlags(a.flags() | Qt.ItemIsUserCheckable)
            a.setCheckState(Qt.Checked if f.sure else Qt.Unchecked)
            tab.setItem(r, 0, a)
            tab.setItem(r, 1, QTableWidgetItem(f.new))
            c = QTableWidgetItem("ja" if f.sure else "nein")
            c.setFlags(c.flags() & ~Qt.ItemIsEditable)
            tab.setItem(r, 2, c)
        tab.resizeColumnsToContents()
        tab.horizontalHeader().setStretchLastSection(True)
        lay.addWidget(tab)
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        lay.addWidget(bb)
        if dlg.exec() != QDialog.Accepted:
            return
        self.undo_stack.append(("entities", [self._clone(e) for e in self.drawing.entities]))
        n = 0
        for r, f in enumerate(fixes):
            if tab.item(r, 0).checkState() == Qt.Checked:
                f.entity.text = tab.item(r, 1).text()
                n += 1
        self.canvas.set_entities(self.drawing.entities)
        self.refresh_layers()
        self.ai_panel.say("ki", f"{n} Texte korrigiert (Strg+Z macht es rückgängig).")
        self.update_actions()

    @staticmethod
    def _clone(e):
        import copy
        return copy.copy(e)

    def ai_review(self):
        if not self._ai_ready() or not self.drawing:
            return
        self.ai_chat("Bewerte das Vektorisierungs-Ergebnis im Bild (Original blass, erkannte "
                     "Vektoren farbig). Was fehlt, was ist falsch, was ist überflüssig? Schlage "
                     "konkrete Verbesserungen vor und führe sinnvolle Einstellungsänderungen plus "
                     "'konvertieren' als Aktionen aus.", True, overlay=True, echo=True)

    def ai_chat(self, text, with_image, overlay=False, echo=False):
        if not self._ai_ready(need_image=False):
            return
        from ..ai import describe_state, encode_image, render_overlay
        panel = self.ai_panel
        if echo:
            panel.say("du", text)
        ctx = describe_state(self.path, self.gray, self.drawing, self.panel.settings(),
                             self.visible_layers() if self.drawing else None)
        img = None
        if with_image and self.gray is not None:
            # Mit Ergebnis: Original + Vektoren überlagert, sonst nur das Original
            src = render_overlay(self.gray, self.drawing) if self.drawing else self.gray
            img = encode_image(src)
        assistant = panel.assistant
        self._ai_run(lambda _w: assistant.ask(text, ctx, img),
                     lambda data: (self.statusBar().showMessage("KI hat geantwortet."),
                                   panel.show_answer(data, self.execute_actions)),
                     "KI denkt nach …")

    # ------------------------------------------------------- KI-Aktionen
    def execute_actions(self, actions):
        import html as _h
        convert_after = False
        export_fmt = None
        for a in actions:
            kind = str(a.get("aktion", "")).lower()
            try:
                if kind == "einstellung":
                    msg = self.panel.set_value(str(a.get("name", "")), a.get("wert"))
                elif kind == "konvertieren":
                    convert_after = True
                    msg = "Konvertierung gestartet"
                elif kind == "layer_loeschen":
                    msg = self._ai_delete(lambda e, L=str(a.get("layer", "")).upper(): e.layer == L,
                                          f"Layer {a.get('layer')} gelöscht")
                elif kind == "layer_sichtbar":
                    L = str(a.get("layer", "")).upper()
                    vis = bool(a.get("sichtbar", True))
                    for i in range(self.layer_list.count()):
                        it = self.layer_list.item(i)
                        if it.data(Qt.UserRole) == L:
                            it.setCheckState(Qt.Checked if vis else Qt.Unchecked)
                    msg = f"Layer {L} {'eingeblendet' if vis else 'ausgeblendet'}"
                elif kind == "kurze_objekte_loeschen":
                    msg = self._ai_delete_short(float(a.get("max_mm", 1.0)))
                elif kind == "text_ersetzen":
                    msg = self._ai_replace_text(str(a.get("alt", "")), str(a.get("neu", "")))
                elif kind == "drehen":
                    self.rotate(-1 if str(a.get("richtung", "")).startswith("l") else 1)
                    msg = "Bild gedreht"
                elif kind == "begradigen":
                    self.deskew_now()
                    msg = "Begradigt"
                elif kind == "exportieren":
                    export_fmt = "." + str(a.get("format", "dxf")).lower().lstrip(".")
                    if export_fmt not in (".dxf", ".svg", ".nc"):
                        export_fmt = ".dxf"
                    msg = f"Export {export_fmt.upper()[1:]} vorbereitet"
                else:
                    msg = None
                    self.ai_panel.say("fehler", f"Unbekannte Aktion: {_h.escape(kind)}")
                if msg:
                    self.ai_panel.say("aktion", _h.escape(msg))
            except Exception as exc:
                self.ai_panel.say("fehler", f"{_h.escape(describe_action(a))}: {_h.escape(str(exc))}")
        if convert_after:
            if export_fmt:
                self._pending_export = export_fmt
            self.run_convert()
        elif export_fmt:
            self.export_dialog(export_fmt)

    def _ai_delete(self, pred, msg):
        if not self.drawing:
            raise ValueError("noch kein Ergebnis vorhanden")
        sel = [e for e in self.drawing.entities if pred(e)]
        if not sel:
            return msg + " (nichts gefunden)"
        self.undo_stack.append(("entities", list(self.drawing.entities)))
        ids = {id(e) for e in sel}
        self.drawing.entities = [e for e in self.drawing.entities if id(e) not in ids]
        self.canvas.remove_entity_items(sel)
        self.refresh_layers()
        self.update_actions()
        return f"{msg}: {len(sel)} Objekte"

    def _ai_delete_short(self, max_mm):
        from ..core.model import Line, Polyline
        d = self.drawing
        if not d:
            raise ValueError("noch kein Ergebnis vorhanden")

        def length(e):
            if isinstance(e, Line):
                return math.dist(e.p1, e.p2) * d.scale
            if isinstance(e, Polyline):
                pts = e.points + ([e.points[0]] if e.closed else [])
                return sum(math.dist(a, b) for a, b in zip(pts, pts[1:])) * d.scale
            return None
        return self._ai_delete(lambda e: (length(e) is not None and length(e) < max_mm),
                               f"Objekte unter {max_mm} mm gelöscht")

    def _ai_replace_text(self, old, new):
        from ..core.model import Text
        if not self.drawing:
            raise ValueError("noch kein Ergebnis vorhanden")
        hits = [t for t in self.drawing.by_type(Text) if t.text == old] or \
               [t for t in self.drawing.by_type(Text) if old and old.lower() in t.text.lower()]
        if not hits:
            return f"Text „{old}“ nicht gefunden"
        self.undo_stack.append(("entities", [self._clone(e) for e in self.drawing.entities]))
        for t in hits:
            t.text = new if t.text == old else t.text.replace(old, new)
        self.canvas.set_entities(self.drawing.entities)
        self.refresh_layers()
        return f"{len(hits)} Text(e) ersetzt"

    def show_help(self):
        QMessageBox.information(self, "Kurzanleitung", (
            "<b>1. Öffnen</b> – Bild oder PDF öffnen bzw. ins Fenster ziehen.<br>"
            "<b>2. Vorbereiten</b> – ggf. drehen, zuschneiden, begradigen (Menü Raster). "
            "Mit »Binärbild anzeigen« prüfen, ob alle Linien schwarz erfasst werden.<br>"
            "<b>3. Modus/Vorlage</b> – CAD-Mittellinien für Zeichnungen und Pläne, "
            "CNC-Umrisse für Logos und Schneidteile.<br>"
            "<b>4. Konvertieren</b> (F5) – Ergebnis erscheint farbig über dem Bild.<br>"
            "<b>5. Bereinigen</b> – Objekte anklicken oder per Rahmen markieren, Entf löscht, "
            "Strg+Z macht rückgängig. Layer links ein-/ausblenden (nur sichtbare werden "
            "exportiert).<br>"
            "<b>6. Maßstab</b> – automatisch aus der DPI oder per »Maßstab kalibrieren« an "
            "einer bekannten Strecke.<br>"
            "<b>7. Export</b> – DXF (Strg+E), G-Code (Strg+G) oder SVG.<br><br>"
            "Navigation: Mausrad = Zoom, mittlere Maustaste oder Umschalt+Ziehen = "
            "Verschieben, Strg+0 = Einpassen."))

    def show_about(self):
        QMessageBox.about(self, "Über Traceify",
                          f"<b>Traceify {__version__}</b><br>Raster- und PDF-Zeichnungen in "
                          "DXF, SVG und G-Code umwandeln.<br><br>Verwendet OpenCV, scikit-image, "
                          "ezdxf, PyMuPDF, Tesseract OCR, Ollama und Qt (PySide6).<br><br>"
                          "Freie Software unter der GNU AGPL v3.<br>"
                          '<a href="https://github.com/StefanR1984/traceify">'
                          "github.com/StefanR1984/traceify</a>")

    def closeEvent(self, ev):
        self.qs.setValue("geometry", self.saveGeometry())
        self.qs.setValue("state", self.saveState())
        if self.worker:
            self.worker.wait(10000)
        super().closeEvent(ev)
