"""Hauptfenster von Traceify."""
from __future__ import annotations

import math
import os
import traceback

import numpy as np
from PySide6.QtCore import QSettings, Qt, QThread, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (QApplication, QComboBox, QDockWidget, QFileDialog,
                               QInputDialog, QLabel, QListWidget, QListWidgetItem,
                               QMainWindow, QMessageBox, QProgressBar, QSlider,
                               QSpinBox, QToolBar, QVBoxLayout, QWidget)

from .. import __version__
from ..api import load_settings, save_settings
from ..core import loader, preprocess
from ..core.model import Drawing, layer_color
from ..core.pipeline import convert_source
from ..export import export
from .batch_dialog import BatchDialog
from .canvas import Canvas
from .ai_panel import AiPanel, FuncWorker, describe_action
from .settings_panel import SettingsPanel

UI_STATE_VERSION = 4  # erhöhen, wenn sich Leisten/Docks ändern – alte Anordnung wird verworfen

FILE_FILTER = ("Bilder & PDF (*.png *.jpg *.jpeg *.bmp *.tif *.tiff *.gif *.webp *.pdf);;"
               "Alle Dateien (*)")


class ConvertWorker(QThread):
    progress = Signal(int, str)
    done = Signal(object)
    failed = Signal(str)

    def __init__(self, gray, settings, scale, source, path="", page=0, pdf_dpi=300,
                 allow_vectors=True, color=None):
        super().__init__()
        self.args = (gray, settings, scale, source, path, page, pdf_dpi, allow_vectors, color)

    def run(self):
        try:
            gray, s, scale, src, path, page, dpi, allow, color = self.args
            res = convert_source(path, page, s, gray, scale, dpi, src,
                                 progress=lambda p, m: self.progress.emit(p, m),
                                 allow_vectors=allow, color=color)
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
        self.color_img = None
        self.raster_modified = False
        self.is_vector_pdf = False
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
        self.canvas.regionDrawn.connect(self.on_region_drawn)
        self.canvas.symbolDrawn.connect(self.on_symbol_drawn)
        self.canvas.drawing_provider = lambda: self.drawing
        self.canvas.regionMenuRequested.connect(self.on_region_menu)
        self.canvas.brushStroke.connect(self.on_brush_stroke)
        self.canvas.nodeEditStarted.connect(self.on_node_edit_started)
        self.canvas.nodeEditFinished.connect(self.on_node_edit_finished)
        self.canvas.toolCancelled.connect(lambda: self.set_tool("select"))
        self.canvas.entities_provider = lambda: self.drawing.entities if self.drawing else []
        self.canvas.mm_per_px_provider = lambda: (self.drawing.scale if self.drawing
                                                  else self.img_scale)
        self.canvas.entitiesDrawn.connect(self.on_entities_drawn)
        self.canvas.trimRequested.connect(self.on_trim)
        self.canvas.extendRequested.connect(self.on_extend)
        self.canvas.drawInfo.connect(lambda t: self.statusBar().showMessage(t))
        self.regions = []
        self.canvas.measured.connect(self.on_measured)
        self.canvas.mouseMoved.connect(self.on_mouse)
        self.canvas.scene().selectionChanged.connect(self.update_status)

        self.panel = SettingsPanel()
        self.panel.convertRequested.connect(self.run_convert)
        self.panel.previewBinaryRequested.connect(self.preview_binary)
        self.panel.btn_calibrate.clicked.connect(self.start_calibrate)
        self.panel.btn_preview.clicked.connect(self.gcode_preview)
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

        self.user_layers = set()   # Layer mit selbst gezeichneten Objekten
        self._build_actions()
        self._build_menus()
        self._build_toolbar()
        self.canvas.snap_enabled = self.a_snap.isChecked()
        self.canvas.ortho_enabled = self.a_ortho_mode.isChecked()
        self.on_snap_modes()

        self.progress = QProgressBar()
        self.progress.setMaximumWidth(220)
        self.progress.setVisible(False)
        self.pos_label = QLabel("")
        from PySide6.QtWidgets import QPushButton
        self.quality_btn = QPushButton("")
        self.quality_btn.setFlat(True)
        self.quality_btn.setVisible(False)
        self.quality_btn.clicked.connect(lambda: self.a_markers.trigger())
        self.statusBar().addPermanentWidget(self.quality_btn)
        self.statusBar().addPermanentWidget(self.pos_label)
        self.quality = None
        self.quality_stale = False
        self._problem_idx = -1
        self.statusBar().addPermanentWidget(self.progress)
        self.statusBar().showMessage("Datei öffnen (Strg+O) oder hierher ziehen.")
        self.setAcceptDrops(True)

        geo = self.qs.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        st = self.qs.value("state")
        if st is not None:
            self.restoreState(st, UI_STATE_VERSION)
        self.update_actions()
        self._autostart_ollama()
        from .. import config as _cfg
        self.a_update_auto.setChecked(_cfg.load().get("update_check") is not False)
        self.update_button = None
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2500, lambda: self.check_updates(manual=False))

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
        self.a_dwg = A("Als DWG exportieren …", lambda: self.export_dialog(".dwg"),
                       tip="Über den kostenlosen ODA File Converter")
        self.a_svg = A("Als SVG exportieren …", lambda: self.export_dialog(".svg"))
        self.a_preview = A("G-Code-Vorschau …", self.gcode_preview, "Ctrl+Shift+G",
                           "Werkzeugwege ansehen, abspielen, Zeit schätzen")
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

        # Werkzeuge (exklusiv)
        self.a_tool_select = A("Auswählen / Knoten bearbeiten", lambda: self.set_tool("select"),
                               "Esc", "Objekte wählen; bei einem Objekt Knoten ziehen",
                               checkable=True)
        self.a_tool_erase = A("Radierer", lambda: self.set_tool("erase"), "E",
                              "Flecken, Stempel, Lochungen im Rasterbild wegradieren",
                              checkable=True)
        self.a_tool_pen = A("Stift", lambda: self.set_tool("pen"), "P",
                            "Lücken in Linien im Rasterbild nachziehen", checkable=True)
        self.a_tool_region = A("Bereich festlegen", lambda: self.set_tool("region"), "R",
                               "Rechteck aufziehen: eigener Modus oder ignorieren",
                               checkable=True)
        self.a_tool_symbol = A("Symbol festlegen und suchen", lambda: self.set_tool("symbol"), "Y",
                               "Rechteck um ein Beispielsymbol ziehen – alle gleichen werden "
                               "als CAD-Block eingesetzt", checkable=True)
        self.a_symbol_lib = A("Symbol-Bibliothek anwenden", self.apply_symbol_library,
                              tip="Alle gespeicherten Symbole in diesem Plan suchen")
        self.a_symbol_folder = A("Symbol-Bibliothek öffnen (Ordner)", self.open_symbol_folder)
        # Zeichnen (Vektoren)
        self.a_draw_line = A("Linie", lambda: self.set_tool("line"), "N",
                             "Linien zeichnen – Fangpunkte, Länge per Tastatur (mm + Enter)",
                             checkable=True)
        self.a_draw_poly = A("Polylinie", lambda: self.set_tool("polyline"), "Shift+N",
                             "Zusammenhängenden Linienzug zeichnen; Klick auf den Start schließt",
                             checkable=True)
        self.a_draw_rect = A("Rechteck", lambda: self.set_tool("rect"), "Shift+K",
                             "Zwei Ecken klicken – oder „Breite;Höhe“ eintippen", checkable=True)
        self.a_draw_circle = A("Kreis", lambda: self.set_tool("circle"), "K",
                               "Mittelpunkt, dann Radius (klicken oder eintippen)", checkable=True)
        self.a_draw_arc = A("Bogen (3 Punkte)", lambda: self.set_tool("arc"), "A",
                            "Startpunkt, Endpunkt, dann ein Punkt auf dem Bogen", checkable=True)
        self.a_trim = A("Stutzen", lambda: self.set_tool("trim"), "T",
                        "Teilstück zwischen zwei Schnittpunkten entfernen", checkable=True)
        self.a_extend = A("Dehnen", lambda: self.set_tool("extend"), "D",
                          "Linie bis zum nächsten Objekt verlängern", checkable=True)
        self.a_snap = A("Fangpunkte", self.toggle_snap, "F3",
                        "Endpunkt, Mitte, Zentrum, Schnittpunkt … einrasten", checkable=True)
        self.a_snap.setChecked(self.qs.value("snap_on", "true") != "false")
        self.a_ortho_mode = A("Ortho (nur waagrecht/senkrecht)", self.toggle_ortho, "F7",
                              "Beim Zeichnen nur waagrecht/senkrecht – Umschalt kehrt es "
                              "vorübergehend um", checkable=True)
        self.a_ortho_mode.setChecked(self.qs.value("ortho_on", "false") == "true")
        self.snap_mode_actions = {}
        saved_modes = self.qs.value("snap_modes", "")
        from ..core.cad import SNAP_LABELS
        for key, label in SNAP_LABELS.items():
            a = QAction(label, self, checkable=True)
            a.setChecked(not saved_modes or key in str(saved_modes).split(","))
            a.toggled.connect(self.on_snap_modes)
            self.snap_mode_actions[key] = a

        self.tool_group = QActionGroup(self)
        for a in (self.a_tool_select, self.a_tool_erase, self.a_tool_pen, self.a_tool_region,
                  self.a_tool_symbol, self.a_draw_line, self.a_draw_poly, self.a_draw_rect,
                  self.a_draw_circle, self.a_draw_arc, self.a_trim, self.a_extend):
            self.tool_group.addAction(a)
        self.a_tool_select.setChecked(True)
        self.a_regions_clear = A("Alle Bereiche entfernen", self.clear_regions)

        # Vektor-Bearbeitung
        self.a_corner = A("Ecke schließen (2 Linien)", self.edit_close_corner, "C",
                          "Zwei markierte Linien bis zum Schnittpunkt verlängern/kürzen")
        self.a_ortho = A("Gerade ausrichten (waagrecht/senkrecht)", self.edit_orthogonalize, "O",
                         "Fast waagrechte/senkrechte Linien exakt ausrichten – Auswahl oder alles")
        self.a_gaps = A("Lücken schließen …", self.edit_snap_gaps, "L",
                        "Nahe Endpunkte zusammenführen – Auswahl oder alles")
        self.a_join = A("Zu Polylinie verbinden", self.edit_join, "J")
        self.a_explode = A("In Einzellinien auflösen", self.edit_explode, "X")
        self.a_connected = A("Verbundene Knoten mitziehen", self.toggle_connected, checkable=True)
        self.a_connected.setChecked(True)

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
        self.a_report = A("Problem melden …", self.report_problem,
                          tip="Fehlerbericht auf GitHub – Version und Umgebung werden mitgeschickt")
        self.a_idea = A("Idee vorschlagen …", lambda: self.report_problem("idee"))
        self.a_log = A("Protokolldatei öffnen", self.open_log)
        self.a_update = A("Nach Updates suchen …", lambda: self.check_updates(manual=True))
        self.a_update_auto = A("Beim Start nach Updates suchen", self.toggle_update_auto,
                               checkable=True)
        self.a_quality = A("Qualität prüfen", self.check_quality, "Ctrl+Shift+Q",
                           "Vergleicht Vektoren mit dem Scan: Abdeckung, Genauigkeit, Problemstellen")
        self.a_markers = A("Problemstellen anzeigen", self.toggle_markers, "Q", checkable=True)
        self.a_next_problem = A("Nächste Problemstelle", self.next_problem, "F8")
        self.a_help = A("Kurzanleitung", self.show_help, "F1")
        self.a_about = A("Über Traceify", self.show_about)

    def _build_menus(self):
        m = self.menuBar().addMenu("&Datei")
        for a in (self.a_open, None, self.a_dxf, self.a_dwg, self.a_svg, self.a_nc,
                  self.a_preview, None,
                  self.a_save_set, self.a_load_set, None, self.a_quit):
            m.addSeparator() if a is None else m.addAction(a)
        dm = m.addMenu("DXF-Version")
        for v in ("R12", "R2000", "R2007", "R2010", "R2013", "R2018"):
            a = QAction(v, self, checkable=True)
            a.setChecked(v == self.dxf_version)
            a.triggered.connect(lambda _=False, v=v, menu=dm: self.set_dxf_version(v, menu))
            dm.addAction(a)

        m = self.menuBar().addMenu("&Bearbeiten")
        for a in (self.a_undo, None, self.a_tool_select, self.a_select_all, self.a_select_layer,
                  self.a_delete, None, self.a_corner, self.a_ortho, self.a_gaps, self.a_join,
                  self.a_explode, None, self.a_connected):
            m.addSeparator() if a is None else m.addAction(a)

        m = self.menuBar().addMenu("&Zeichnen")
        for a in (self.a_draw_line, self.a_draw_poly, self.a_draw_rect, self.a_draw_circle,
                  self.a_draw_arc, None, self.a_trim, self.a_extend, None, self.a_snap,
                  self.a_ortho_mode):
            m.addSeparator() if a is None else m.addAction(a)
        sm = m.addMenu("Fangarten")
        for a in self.snap_mode_actions.values():
            sm.addAction(a)

        m = self.menuBar().addMenu("&Raster")
        for a in (self.a_tool_erase, self.a_tool_pen, None, self.a_tool_region,
                  self.a_regions_clear, None, self.a_rot_l, self.a_rot_r, self.a_crop,
                  self.a_deskew, self.a_invert):
            m.addSeparator() if a is None else m.addAction(a)

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
        m.addAction(self.a_tool_symbol)
        m.addAction(self.a_symbol_lib)
        m.addAction(self.a_symbol_folder)
        m.addSeparator()
        m.addAction(self.a_quality)
        m.addAction(self.a_markers)
        m.addAction(self.a_next_problem)

        m.addSeparator()
        m.addAction(self.a_components)

        m = self.menuBar().addMenu("&KI")
        for a in (self.a_ai_show, None, self.a_ai_suggest, self.a_ai_texts, self.a_ai_review):
            m.addSeparator() if a is None else m.addAction(a)
        m.addSeparator()
        m.addAction(self.a_components)

        m = self.menuBar().addMenu("&Hilfe")
        m.addAction(self.a_help)
        m.addSeparator()
        m.addAction(self.a_report)
        m.addAction(self.a_idea)
        m.addAction(self.a_log)
        m.addSeparator()
        m.addAction(self.a_update)
        m.addAction(self.a_update_auto)
        m.addAction(self.a_about)

    def _build_toolbar(self):
        short = {self.a_open: "Öffnen", self.a_convert: "▶ Konvertieren", self.a_dxf: "DXF",
                 self.a_nc: "G-Code", self.a_svg: "SVG", self.a_crop: "Zuschneiden",
                 self.a_rot_l: "⟲ 90°", self.a_rot_r: "⟳ 90°", self.a_fit: "Einpassen",
                 self.a_show_bin: "Binärbild", self.a_batch: "Stapel …",
                 self.a_ai_suggest: "✨ KI-Analyse", self.a_ai_show: "KI-Chat",
                 self.a_preview: "Vorschau"}
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
        tb.addAction(self.a_preview)
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
        self._build_edit_toolbar()
        tb.addSeparator()
        tb.addAction(self.a_ai_suggest)
        tb.addAction(self.a_ai_show)

    def _build_edit_toolbar(self):
        for a, t in {self.a_tool_select: "↖ Auswahl", self.a_tool_erase: "Radierer",
                     self.a_tool_pen: "Stift", self.a_tool_region: "▭ Bereich",
                     self.a_tool_symbol: "⌘ Symbol",
                     self.a_corner: "Ecke", self.a_ortho: "Ausrichten",
                     self.a_gaps: "Lücken", self.a_join: "Verbinden",
                     self.a_explode: "Auflösen", self.a_delete: "Löschen",
                     self.a_undo: "↶ Zurück"}.items():
            a.setIconText(t)
        self.addToolBarBreak()
        tb = QToolBar("Bearbeiten")
        tb.setObjectName("toolbar_edit")
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        self.addToolBar(tb)
        for a in (self.a_tool_select, self.a_tool_erase, self.a_tool_pen):
            tb.addAction(a)
        tb.addWidget(QLabel(" Pinsel "))
        self.brush_spin = QSpinBox()
        self.brush_spin.setRange(1, 300)
        self.brush_spin.setValue(int(self.qs.value("brush_size", 12)))
        self.brush_spin.setSuffix(" px")
        self.brush_spin.valueChanged.connect(self.on_brush_size)
        tb.addWidget(self.brush_spin)
        tb.addAction(self.a_tool_region)
        tb.addAction(self.a_tool_symbol)
        tb.addSeparator()
        for a in (self.a_corner, self.a_ortho, self.a_gaps, self.a_join, self.a_explode,
                  self.a_delete):
            tb.addAction(a)
        tb.addSeparator()
        tb.addAction(self.a_undo)

        for a, t in {self.a_draw_line: "╱ Linie", self.a_draw_poly: "Polylinie",
                     self.a_draw_rect: "▭ Rechteck", self.a_draw_circle: "◯ Kreis",
                     self.a_draw_arc: "◠ Bogen", self.a_trim: "✂ Stutzen",
                     self.a_extend: "⇥ Dehnen", self.a_snap: "⌖ Fang",
                     self.a_ortho_mode: "┼ Ortho"}.items():
            a.setIconText(t)
        tb = QToolBar("Zeichnen")
        tb.setObjectName("toolbar_draw")
        tb.setToolButtonStyle(Qt.ToolButtonTextOnly)
        tb.setOrientation(Qt.Vertical)
        self.addToolBar(Qt.LeftToolBarArea, tb)
        for a in (self.a_draw_line, self.a_draw_poly, self.a_draw_rect, self.a_draw_circle,
                  self.a_draw_arc, None, self.a_trim, self.a_extend, None, self.a_snap,
                  self.a_ortho_mode):
            tb.addSeparator() if a is None else tb.addAction(a)
        tb.addWidget(QLabel(" Layer:"))
        self.draw_layer = QComboBox()
        self.draw_layer.setEditable(True)
        self.draw_layer.setMinimumContentsLength(8)
        self.draw_layer.setMaximumWidth(120)
        self.draw_layer.setToolTip("Layer für neu gezeichnete Objekte (eintippen = neuer Layer)")
        self.draw_layer.addItem(self.qs.value("draw_layer", "GEZEICHNET"))
        tb.addWidget(self.draw_layer)

    def update_actions(self):
        has_img = self.gray is not None
        has_vec = self.drawing is not None and bool(self.drawing.entities)
        busy = self.worker is not None
        for a in (self.a_convert, self.a_rot_l, self.a_rot_r, self.a_crop, self.a_deskew,
                  self.a_invert, self.a_calib, self.a_show_bin, self.a_ai_suggest,
                  self.a_tool_erase, self.a_tool_pen, self.a_tool_region, self.a_regions_clear):
            a.setEnabled(has_img and not busy)
        for a in (self.a_corner, self.a_ortho, self.a_gaps, self.a_join, self.a_explode,
                  self.a_quality, self.a_markers, self.a_next_problem, self.a_tool_symbol,
                  self.a_symbol_lib):
            a.setEnabled(has_vec and not busy)
        for a in (self.a_draw_line, self.a_draw_poly, self.a_draw_rect, self.a_draw_circle,
                  self.a_draw_arc):
            a.setEnabled(has_img and not busy)
        for a in (self.a_trim, self.a_extend):
            a.setEnabled(has_vec and not busy)
        for a in (self.a_dxf, self.a_dwg, self.a_svg, self.a_nc, self.a_preview, self.a_delete,
                  self.a_select_all,
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
        try:
            self.color_img = loader.load_color(path, page, self.panel.pdf_dpi.value())
        except Exception:
            self.color_img = None
        self.path, self.page = path, page
        self.gray, self.img_scale = gray, scale
        self.binary = None
        self.drawing = None
        self.user_layers = set()
        self.undo_stack.clear()
        self.quality = None
        self._show_quality()
        self.canvas.set_markers([])
        self.a_markers.setChecked(False)
        self.regions = []
        self.canvas.set_regions([], {})
        self.set_tool("select")
        self.raster_modified = False
        self.is_vector_pdf = False
        if path.lower().endswith(".pdf"):
            from ..core.pdf_vector import has_vectors
            self.is_vector_pdf = has_vectors(path, page, self.panel.settings().pdf)
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
            + ("Vektor-PDF erkannt – Linien und Texte werden direkt übernommen. "
               if self.is_vector_pdf and self.panel.pdf_vectors.isChecked() else "")
            + "Jetzt Einstellungen prüfen und »Konvertieren« (F5).")
        self.update_actions()

    def on_page_changed(self, v):
        if self.path:
            self.open_file(self.path, v - 1)

    # --------------------------------------------------------- Konvertieren
    def run_convert(self):
        if self.gray is None or self.worker:
            return
        s = self.panel.settings()
        from dataclasses import asdict
        s.regions = [asdict(r) for r in self.regions]
        self.worker = ConvertWorker(self.gray, s, self.img_scale,
                                    os.path.basename(self.path or ""), self.path or "",
                                    self.page, self.panel.pdf_dpi.value(),
                                    allow_vectors=not self.raster_modified,
                                    color=self.color_img if s.style.color_layers else None)
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
        old = self.drawing
        if old is not None and old.entities:
            self.undo_stack.append(("drawing", old))
        self.drawing = res.drawing
        if old is not None and self.user_layers:
            # Selbst Gezeichnetes überlebt das Neu-Konvertieren (eigene Layer)
            auto = set(self.drawing.layers())
            keep = [e for e in old.entities if e.layer in self.user_layers and e.layer not in auto]
            self.drawing.entities.extend(keep)
        self.binary = res.binary
        self.canvas.set_entities(self.drawing.entities)
        self.canvas.set_vectors_visible(self.a_show_vec.isChecked())
        self.opacity.setValue(self.opacity.value())
        self.canvas.set_raster_opacity(self.opacity.value() / 100)
        if self.a_show_bin.isChecked():
            self.canvas.set_raster(255 - self.binary, keep_view=True)
            self.canvas.set_raster_opacity(self.opacity.value() / 100)
        self.refresh_layers()
        self.text_boxes = list(getattr(res, "text_boxes", []) or [])
        self.check_quality(silent=True)
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
                pm.fill(QColor(*layer_color(layer)[1]))
                it.setIcon(QIcon(pm))
                self.layer_list.addItem(it)
            cur = self.draw_layer.currentText()
            for layer in self.drawing.layers():
                if self.draw_layer.findText(layer) < 0:
                    self.draw_layer.addItem(layer)
            self.draw_layer.setCurrentText(cur)
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
                f"<br>Auflösung: {d.scale:.5f} mm/px")
        if d.meta.get("massstab"):
            txt += f"<br>Zeichnungsmaßstab: <b>{d.meta['massstab']}</b> ({d.meta.get('massstab_quelle', '')})"
        if d.meta.get("quelle"):
            txt += f"<br>Quelle: {d.meta['quelle']}"
        counts = d.symbol_counts()
        if counts:
            txt += "<br><br><b>Symbole</b><br>" + "<br>".join(
                f"{k}: <b>{v}</b>" for k, v in counts.items())
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
        self._mark_quality_stale()
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
        if kind == "raster_only":
            self.gray, self.color_img = data[0], data[1]
            self.binary = None
            self._show_current_raster()
            self.update_actions()
            return
        if kind == "entities" and self.drawing:
            self.drawing.entities = data[0]
        elif kind == "drawing":
            self.drawing = data[0]
        elif kind == "raster":
            self.gray, self.drawing, self.color_img = data
            self.binary = None
            self.a_show_bin.setChecked(False)
            self.canvas.set_raster(self.gray)
        self.canvas.set_entities(self.drawing.entities if self.drawing else [])
        self.canvas.set_raster_opacity(self.opacity.value() / 100 if self.drawing else 1.0)
        self.refresh_layers()
        self.update_actions()

    # --------------------------------------------------------------- Symbole
    def _current_binary(self):
        if self.binary is not None and self.binary.shape == self.gray.shape:
            return self.binary
        return preprocess.to_binary(self.gray, self.panel.settings().preprocess)

    def on_symbol_drawn(self, x, y, w, h):
        from ..core import symbols as S
        from .symbol_dialog import SymbolDialog
        if not self.drawing or self.gray is None:
            return
        bw = self._current_binary()
        H, W = bw.shape
        crop = bw[max(0, y):min(H, y + h), max(0, x):min(W, x + w)]
        if crop.size == 0 or not crop.any():
            self.statusBar().showMessage("Im markierten Rechteck ist nichts zu sehen.")
            return
        n = len(self.drawing.symbol_counts()) + 1
        dlg = SymbolDialog(self, 255 - crop, f"Symbol {n}", self.ai_panel)
        if not dlg.exec():
            return
        name, thr, rots, save = dlg.values()
        tpl = S.make_template(name, bw, self.drawing, x, y, w, h)
        if not tpl.entities:
            QMessageBox.information(self, "Symbol", "Im Rechteck liegen keine Vektoren – bitte "
                                    "zuerst konvertieren oder das Rechteck größer ziehen.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            matches = S.find_matches(bw, tpl, thr, rots)
            self._snapshot()
            count = S.apply_matches(self.drawing, tpl, matches)
            if save:
                S.save_template(tpl)
        finally:
            QApplication.restoreOverrideCursor()
        if not count:
            self.undo_stack.pop()
        self.canvas.set_entities(self.drawing.entities)
        self.canvas.set_vectors_visible(self.a_show_vec.isChecked())
        self.refresh_layers()
        self.update_actions()
        self.statusBar().showMessage(f"„{name}“: {count} Stück gefunden und als Block eingesetzt"
                                     + (" (in der Bibliothek gespeichert)" if save else "")
                                     + ". Strg+Z = zurück.")

    def apply_symbol_library(self):
        from ..core import symbols as S
        if not self.drawing:
            return
        lib = S.load_library()
        if not lib:
            QMessageBox.information(self, "Symbol-Bibliothek",
                                    "Die Bibliothek ist noch leer. Lege Symbole mit dem Werkzeug "
                                    "„Symbol“ (Y) fest.")
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            self._snapshot()
            n, per = S.apply_library(self.drawing, self._current_binary(), lib)
        finally:
            QApplication.restoreOverrideCursor()
        if not n:
            self.undo_stack.pop()
        self.canvas.set_entities(self.drawing.entities)
        self.refresh_layers()
        self.statusBar().showMessage(f"Bibliothek: {n} Symbole eingesetzt"
                                     + (" – " + ", ".join(f"{k} ×{v}" for k, v in per.items())
                                        if per else "."))

    def open_symbol_folder(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from ..core.symbols import library_dir
        QDesktopServices.openUrl(QUrl.fromLocalFile(library_dir()))

    # -------------------------------------------------------------- Qualität
    def check_quality(self, silent=False):
        from ..core.quality import assess
        from ..core.vectorize import MODE_OUTLINE
        if not self.drawing or self.gray is None:
            return
        bw = self.binary if self.binary is not None and self.binary.shape == self.gray.shape \
            else preprocess.to_binary(self.gray, self.panel.settings().preprocess)
        ignore = [r for r in self.regions if r.mode == "ignorieren"]
        if ignore:
            bw = bw.copy()
            for r in ignore:
                bw[r.slices(bw.shape)] = 0
        try:
            self.quality = assess(bw, self.drawing.expanded(), mm_per_px=self.img_scale,
                                  extra_boxes=getattr(self, "text_boxes", None),
                                  fill_closed=self.panel.settings().vectorize.mode == MODE_OUTLINE)
        except Exception:
            import logging
            logging.getLogger("traceify").exception("Qualitätsprüfung")
            self.quality = None
            return
        self.quality_stale = False
        self._problem_idx = -1
        self._show_quality()
        if self.a_markers.isChecked():
            self.canvas.set_markers(self.quality.problems)
        if not silent:
            self.statusBar().showMessage("Qualität: " + self.quality.summary())

    def _show_quality(self):
        q = self.quality
        if q is None:
            self.quality_btn.setVisible(False)
            return
        col = {"gruen": "#1a8a4a", "gelb": "#d4a017", "rot": "#c0392b"}[q.rating]
        if self.quality_stale:
            col = "#999999"
        txt = {"gruen": "gut", "gelb": "prüfen", "rot": "Probleme"}[q.rating]
        n = len(q.problems)
        self.quality_btn.setText(f"● Qualität: {txt}" + (f" ({n})" if n else "")
                                 + (" – veraltet" if self.quality_stale else ""))
        self.quality_btn.setStyleSheet(f"color: {col}; font-weight: bold;")
        self.quality_btn.setToolTip(q.summary() + "\nKlick: Problemstellen ein/aus · F8: nächste"
                                    + ("\nNach Änderungen: Werkzeuge → Qualität prüfen"
                                       if self.quality_stale else ""))
        self.quality_btn.setVisible(True)

    def toggle_markers(self, on):
        if on and (self.quality is None or self.quality_stale):
            self.check_quality(silent=True)
        self.canvas.set_markers(self.quality.problems if on and self.quality else [])
        if on and self.quality and not self.quality.problems:
            self.statusBar().showMessage("Keine Problemstellen gefunden.")

    def next_problem(self):
        if self.quality is None or self.quality_stale:
            self.check_quality(silent=True)
        if not self.quality or not self.quality.problems:
            self.statusBar().showMessage("Keine Problemstellen.")
            return
        if not self.a_markers.isChecked():
            self.a_markers.setChecked(True)
            self.toggle_markers(True)
        self._problem_idx = (self._problem_idx + 1) % len(self.quality.problems)
        p = self.quality.problems[self._problem_idx]
        self.canvas.zoom_to_rect(p.x, p.y, p.w, p.h)
        what = "fehlt im Ergebnis (Tinte ohne Vektor)" if p.kind == "fehlt" else \
            "vermutlich überflüssig (Vektor ohne Tinte)"
        self.statusBar().showMessage(f"Problemstelle {self._problem_idx + 1}/"
                                     f"{len(self.quality.problems)}: {what}. F8 = weiter.")

    # ------------------------------------------------------------ Werkzeuge
    def set_tool(self, tool):
        acts = {"select": self.a_tool_select, "erase": self.a_tool_erase,
                "pen": self.a_tool_pen, "region": self.a_tool_region,
                "symbol": self.a_tool_symbol, "line": self.a_draw_line,
                "polyline": self.a_draw_poly, "rect": self.a_draw_rect,
                "circle": self.a_draw_circle, "arc": self.a_draw_arc,
                "trim": self.a_trim, "extend": self.a_extend}
        if tool != "select" and self.gray is None:
            tool = "select"
        if tool in ("trim", "extend") and not (self.drawing and self.drawing.entities):
            tool = "select"
        if tool == "symbol" and not self.drawing:
            tool = "select"
            self.statusBar().showMessage("Symbole: zuerst konvertieren (F5), dann ein Symbol "
                                         "mit einem Rechteck markieren.")
            self.a_tool_select.setChecked(True)
            self.canvas.set_tool("select")
            return
        acts[tool].setChecked(True)
        self.canvas.set_tool(tool, self.brush_spin.value())
        msg = {"select": "Auswahl: Objekte anklicken oder Rahmen ziehen. Bei einem Objekt "
                         "erscheinen Knoten zum Ziehen.",
               "erase": "Radierer: über das Rasterbild malen (Pinselgröße in der Leiste). "
                        "Esc = zurück zur Auswahl.",
               "pen": "Stift: Lücken in Linien nachziehen. Esc = zurück zur Auswahl.",
               "region": "Bereich: Rechteck aufziehen und Behandlung wählen. "
                         "Rechtsklick auf einen Bereich = ändern/entfernen. Esc = fertig.",
               "symbol": "Symbol: Rechteck eng um EIN Beispielsymbol ziehen (z. B. eine "
                         "Steckdose). Esc = fertig.",
               "line": "Linie: Startpunkt klicken. Länge eintippen + Enter, Umschalt = Ortho, "
                       "F3 = Fang an/aus.",
               "polyline": "Polylinie: Punkte klicken, Rechtsklick/Enter = fertig.",
               "rect": "Rechteck: erste Ecke klicken, dann zweite – oder „Breite;Höhe“ "
                       "eintippen.",
               "circle": "Kreis: Mittelpunkt klicken, dann Radius klicken oder eintippen.",
               "arc": "Bogen: Startpunkt, Endpunkt, dann einen Punkt auf dem Bogen.",
               "trim": "Stutzen: Teilstück anklicken, das wegfallen soll (rot markiert).",
               "extend": "Dehnen: Linie nahe dem Ende anklicken, das verlängert werden soll."}[tool]
        self.statusBar().showMessage(msg)

    # -------------------------------------------------------------- Zeichnen
    def toggle_snap(self, on):
        self.canvas.snap_enabled = bool(on)
        self.qs.setValue("snap_on", "true" if on else "false")
        self.statusBar().showMessage("Fangpunkte " + ("an." if on else "aus."))

    def toggle_ortho(self, on):
        self.canvas.ortho_enabled = bool(on)
        self.qs.setValue("ortho_on", "true" if on else "false")
        self.statusBar().showMessage("Ortho " + ("an." if on else "aus."))

    def on_snap_modes(self, *_):
        modes = {k for k, a in self.snap_mode_actions.items() if a.isChecked()}
        self.canvas.snap_modes = modes
        self.qs.setValue("snap_modes", ",".join(sorted(modes)) or "-")

    def _ensure_drawing(self):
        if self.drawing is None and self.gray is not None:
            h, w = self.gray.shape[:2]
            self.drawing = Drawing(w, h, self.img_scale, [], self.path or "")
            self.canvas.set_raster_opacity(self.opacity.value() / 100)
        return self.drawing

    def _current_draw_layer(self):
        name = (self.draw_layer.currentText() or "GEZEICHNET").strip().upper().replace(" ", "_")
        self.qs.setValue("draw_layer", name)
        return name or "GEZEICHNET"

    def on_entities_drawn(self, ents):
        if self._ensure_drawing() is None:
            return
        layer = self._current_draw_layer()
        self.user_layers.add(layer)
        if self.draw_layer.findText(layer) < 0:
            self.draw_layer.addItem(layer)
        for e in ents:
            e.layer = layer
        self._mark_quality_stale()
        self.undo_stack.append(("entities", list(self.drawing.entities)))
        self.drawing.entities.extend(ents)
        self.canvas.add_entities(ents)
        self.refresh_layers()
        self.update_actions()

    def on_trim(self, entity, x, y):
        from ..core import cad
        if not self.drawing:
            return
        removed, added = cad.trim(self.drawing.entities, entity, (x, y))
        if not removed:
            self.statusBar().showMessage("Dieses Objekt lässt sich nicht stutzen.")
            return
        self._mark_quality_stale()
        self.undo_stack.append(("entities", list(self.drawing.entities)))
        ids = {id(e) for e in removed}
        self.drawing.entities = [e for e in self.drawing.entities if id(e) not in ids] + added
        self.canvas.remove_entity_items(removed)
        self.canvas.add_entities(added)
        self.refresh_layers()
        self.update_actions()
        self.statusBar().showMessage("Gestutzt (Strg+Z = zurück). Nächstes Teilstück anklicken "
                                     "oder Esc.")

    def on_extend(self, entity, x, y):
        import copy
        from ..core import cad
        from ..core.model import Line
        if not self.drawing:
            return
        if not isinstance(entity, Line):
            self.statusBar().showMessage("Dehnen geht bei einzelnen Linien – Polylinien vorher "
                                         "auflösen (X).")
            return
        snap = list(self.drawing.entities)
        snap[next(i for i, e in enumerate(snap) if e is entity)] = copy.copy(entity)
        if not cad.extend(self.drawing.entities, entity, (x, y)):
            self.statusBar().showMessage("In dieser Richtung liegt kein Objekt, bis zu dem die "
                                         "Linie reichen könnte.")
            return
        self._mark_quality_stale()
        self.undo_stack.append(("entities", snap))
        self.canvas.refresh_entities([entity])
        self.update_actions()
        self.statusBar().showMessage("Gedehnt (Strg+Z = zurück).")

    def on_brush_size(self, v):
        self.qs.setValue("brush_size", int(v))
        self.canvas.set_brush_size(v)

    def _show_current_raster(self):
        if self.a_show_bin.isChecked():
            self.binary = preprocess.to_binary(self.gray, self.panel.settings().preprocess)
            self.canvas.update_raster(255 - self.binary)
        else:
            self.canvas.update_raster(self.gray)

    def on_brush_stroke(self, pts, tool, size):
        import cv2
        if self.gray is None or not pts:
            self.canvas.clear_stroke()
            return
        self.undo_stack.append(("raster_only", self.gray, self.color_img))
        g = self.gray.copy()
        arr = np.round(np.asarray(pts, dtype=float)).astype(np.int32).reshape(-1, 1, 2)
        col = 255 if tool == "erase" else 0
        r = max(1, int(round(size / 2)))
        if len(arr) == 1:
            cv2.circle(g, tuple(int(v) for v in arr[0, 0]), r, col, -1)
        else:
            cv2.polylines(g, [arr], False, col, thickness=max(1, int(size)))
            cv2.circle(g, tuple(int(v) for v in arr[0, 0]), r, col, -1)
            cv2.circle(g, tuple(int(v) for v in arr[-1, 0]), r, col, -1)
        self.gray = g
        if self.color_img is not None:
            c = self.color_img.copy()
            cc = (col, col, col)
            if len(arr) == 1:
                cv2.circle(c, tuple(int(v) for v in arr[0, 0]), r, cc, -1)
            else:
                cv2.polylines(c, [arr], False, cc, thickness=max(1, int(size)))
                cv2.circle(c, tuple(int(v) for v in arr[0, 0]), r, cc, -1)
                cv2.circle(c, tuple(int(v) for v in arr[-1, 0]), r, cc, -1)
            self.color_img = c
        self.binary = None
        self.raster_modified = True
        self._show_current_raster()
        self.canvas.clear_stroke()
        self.statusBar().showMessage(("Radiert" if tool == "erase" else "Nachgezogen")
                                     + " – zum Übernehmen neu konvertieren (F5). Strg+Z = zurück.")
        self.update_actions()

    # -------------------------------------------------------------- Bereiche
    def _region_labels(self):
        from ..core.pipeline import REGION_MODES
        return REGION_MODES

    def _update_regions(self):
        self.canvas.set_regions(self.regions, self._region_labels())
        if self.regions:
            self.statusBar().showMessage(f"{len(self.regions)} Bereich(e) – wirken beim nächsten "
                                         "Konvertieren (F5).")

    def _region_mode_menu(self, current=None, with_delete=False):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        acts = {}
        for mode, label in self._region_labels().items():
            a = menu.addAction(label)
            a.setCheckable(True)
            a.setChecked(mode == current)
            acts[a] = mode
        if with_delete:
            menu.addSeparator()
            acts[menu.addAction("Bereich entfernen")] = None
        return menu, acts

    def on_region_drawn(self, x, y, w, h):
        from PySide6.QtGui import QCursor
        from ..core.pipeline import Region
        menu, acts = self._region_mode_menu()
        chosen = menu.exec(QCursor.pos())
        if chosen in acts:
            self.regions.append(Region(x, y, w, h, acts[chosen]))
            self._update_regions()

    def on_region_menu(self, index, gpos):
        if not (0 <= index < len(self.regions)):
            return
        menu, acts = self._region_mode_menu(self.regions[index].mode, with_delete=True)
        chosen = menu.exec(gpos)
        if chosen not in acts:
            return
        if acts[chosen] is None:
            del self.regions[index]
        else:
            self.regions[index].mode = acts[chosen]
        self._update_regions()

    def clear_regions(self):
        self.regions = []
        self._update_regions()
        self.statusBar().showMessage("Alle Bereiche entfernt.")

    # ------------------------------------------------------ Vektor-Bearbeitung
    def _mark_quality_stale(self):
        if self.quality is not None and not self.quality_stale:
            self.quality_stale = True
            self._show_quality()

    def _snapshot(self):
        self._mark_quality_stale()
        import copy
        self.undo_stack.append(("entities", copy.deepcopy(self.drawing.entities)))
        self.update_actions()

    def _targets(self, types):
        sel = [e for e in self.canvas.selected_entities() if isinstance(e, types)]
        if sel:
            return sel, True
        return [e for e in self.drawing.entities if isinstance(e, types)
                and e.layer in self.visible_layers()], False

    def on_node_edit_started(self):
        if self.drawing:
            # Schnappschuss VOR der Änderung: Objekte bleiben identisch, Koordinaten kopiert
            import copy
            snap = copy.deepcopy(self.drawing.entities)
            self.undo_stack.append(("entities", snap))
            self.update_actions()

    def on_node_edit_finished(self):
        self.statusBar().showMessage("Knoten verschoben (Strg+Z = zurück).")

    def toggle_connected(self, on):
        self.canvas.node_connected = bool(on)

    def edit_close_corner(self):
        from ..core.edit import close_corner
        from ..core.model import Line
        sel = [e for e in self.canvas.selected_entities() if isinstance(e, Line)]
        if len(sel) != 2:
            self.statusBar().showMessage("Bitte genau zwei Linien markieren (Strg+Klick).")
            return
        self._snapshot()
        if not close_corner(*sel):
            self.undo_stack.pop()
            self.statusBar().showMessage("Die Linien sind parallel – keine Ecke möglich.")
            return
        self.canvas.refresh_entities(sel)
        self.canvas.refresh_handles()
        self.statusBar().showMessage("Ecke geschlossen.")

    def edit_orthogonalize(self):
        from ..core.edit import orthogonalize
        from ..core.model import Line
        if not self.drawing:
            return
        targets, is_sel = self._targets(Line)
        self._snapshot()
        n = orthogonalize(targets, tol_deg=3.0, join_tol=max(1.5, self.panel.snap.value()))
        if not n:
            self.undo_stack.pop()
        self.canvas.refresh_entities(targets)
        self.statusBar().showMessage(f"{n} Linien exakt ausgerichtet"
                                     + (" (Auswahl)." if is_sel else " (alle sichtbaren)."))

    def edit_snap_gaps(self):
        from ..core.edit import snap_gaps
        from ..core.model import Line, Polyline
        if not self.drawing:
            return
        dist, ok = QInputDialog.getDouble(self, "Lücken schließen",
                                          "Endpunkte zusammenführen bis Abstand (Pixel):",
                                          6.0, 0.5, 500.0, 1)
        if not ok:
            return
        targets, is_sel = self._targets((Line, Polyline))
        self._snapshot()
        n = snap_gaps(targets, dist)
        self.canvas.refresh_entities(targets)
        self.statusBar().showMessage(f"{n} Lücken geschlossen"
                                     + (" (Auswahl)." if is_sel else " (alle sichtbaren)."))

    def edit_join(self):
        from ..core.edit import join_lines
        from ..core.model import Line
        if not self.drawing:
            return
        lines = [e for e in self.canvas.selected_entities() if isinstance(e, Line)]
        if len(lines) < 2:
            self.statusBar().showMessage("Bitte mindestens zwei verbundene Linien markieren.")
            return
        self._snapshot()
        polys = join_lines(lines, tol=max(0.5, self.panel.snap.value() / 2))
        ids = {id(e) for e in lines}
        self.drawing.entities = [e for e in self.drawing.entities if id(e) not in ids] + polys
        self.canvas.set_entities(self.drawing.entities)
        self.canvas.select_entities(polys)
        self.refresh_layers()
        self.statusBar().showMessage(f"{len(lines)} Linien zu {len(polys)} Polylinie(n) verbunden.")

    def edit_explode(self):
        from ..core.edit import explode
        from ..core.model import Polyline
        if not self.drawing:
            return
        polys = [e for e in self.canvas.selected_entities() if isinstance(e, Polyline)]
        if not polys:
            self.statusBar().showMessage("Bitte Polylinien markieren.")
            return
        self._snapshot()
        new = [ln for p in polys for ln in explode(p)]
        ids = {id(e) for e in polys}
        self.drawing.entities = [e for e in self.drawing.entities if id(e) not in ids] + new
        self.canvas.set_entities(self.drawing.entities)
        self.canvas.select_entities(new)
        self.refresh_layers()
        self.statusBar().showMessage(f"{len(polys)} Polylinie(n) in {len(new)} Linien aufgelöst.")

    # ---------------------------------------------------------------- Raster
    def _raster_edit(self, new_gray, msg, keep_regions=False, color_fn=None):
        if not keep_regions and self.regions:
            self.regions = []
            self.canvas.set_regions([], {})
            msg += " (Bereiche entfernt)"
        self.undo_stack.append(("raster", self.gray, self.drawing, self.color_img))
        self.raster_modified = True  # Vektor-PDF-Koordinaten passen nicht mehr
        if self.color_img is not None:
            try:  # gleiche Änderung auf das Farbbild (für die Farbtrennung)
                self.color_img = np.ascontiguousarray(color_fn(self.color_img)) if color_fn \
                    else None
            except Exception:
                self.color_img = None
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
            self._raster_edit(preprocess.rotate90(self.gray, d), "Gedreht",
                              color_fn=lambda c: preprocess.rotate90(c, d))

    def start_crop(self):
        if self.gray is not None:
            self.statusBar().showMessage("Rechteck mit der Maus aufziehen …")
            self.canvas.start_crop()

    def on_crop(self, x, y, w, h):
        H, W = self.gray.shape
        w, h = min(w, W - x), min(h, H - y)
        if w > 5 and h > 5:
            self._raster_edit(preprocess.crop(self.gray, x, y, w, h), f"Zugeschnitten auf {w}×{h} px",
                              color_fn=lambda c: preprocess.crop(c, x, y, w, h))

    def deskew_now(self):
        bw = preprocess.to_binary(self.gray, self.panel.settings().preprocess)
        a = preprocess.estimate_skew(bw)
        if abs(a) < 0.05:
            self.statusBar().showMessage("Keine Schräglage erkannt.")
            return
        self._raster_edit(preprocess.rotate(self.gray, a, border=255), f"Um {a:.2f}° begradigt",
                          color_fn=lambda c: preprocess.rotate(c, a, border=(255, 255, 255)))

    def invert_now(self):
        self._raster_edit(255 - self.gray, "Invertiert", keep_regions=True,
                          color_fn=lambda c: 255 - c)

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
        if ext == ".dwg" and not self._ensure_oda():
            return
        names = {".dxf": "DXF (*.dxf)", ".dwg": "DWG (*.dwg)", ".svg": "SVG (*.svg)",
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
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                export(self.drawing, f, self.panel.gcode_settings(), self.dxf_version,
                       self.visible_layers())
            finally:
                QApplication.restoreOverrideCursor()
        except Exception as exc:
            import logging
            logging.getLogger("traceify").exception("Export fehlgeschlagen")
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
        self.check_quality(silent=True)
        q = self.quality
        extra = ""
        if q:
            extra = (f" Die automatische Prüfung meldet: {q.summary()}. "
                     + ("Größte Problemstellen (Bildpixel x,y,b,h): " + "; ".join(
                         f"{p.kind} {p.x},{p.y},{p.w},{p.h}" for p in q.problems[:8]) + "."
                        if q.problems else ""))
        self.ai_chat("Bewerte das Vektorisierungs-Ergebnis im Bild (Original blass, erkannte "
                     "Vektoren farbig). Was fehlt, was ist falsch, was ist überflüssig?" + extra
                     + " Schlage konkrete Verbesserungen vor und führe sinnvolle "
                     "Einstellungsänderungen plus 'konvertieren' als Aktionen aus.", True,
                     overlay=True, echo=True)

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
                elif kind == "gcode_vorschau":
                    from PySide6.QtCore import QTimer
                    QTimer.singleShot(0, self.gcode_preview)
                    msg = "G-Code-Vorschau geöffnet"
                elif kind == "exportieren":
                    export_fmt = "." + str(a.get("format", "dxf")).lower().lstrip(".")
                    if export_fmt not in (".dxf", ".dwg", ".svg", ".nc"):
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

    def gcode_preview(self):
        if not self.drawing or not self.drawing.entities:
            self.statusBar().showMessage("Erst konvertieren – dann gibt es Werkzeugwege.")
            return
        from .gcode_preview import GcodePreviewDialog
        s = self.panel.settings().scale
        if s:
            self.drawing.scale = s
        base = os.path.splitext(os.path.basename(self.path or "zeichnung"))[0]
        start = os.path.join(self.qs.value("export_dir", os.path.dirname(self.path or "")),
                             base + ".nc")
        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            try:
                dlg = GcodePreviewDialog(self, self.drawing, self.panel.gcode_settings(),
                                         self.visible_layers(), start)
            finally:
                QApplication.restoreOverrideCursor()
        except Exception as exc:
            import logging
            logging.getLogger("traceify").exception("G-Code-Vorschau")
            QMessageBox.critical(self, "G-Code-Vorschau", str(exc))
            return
        if dlg.exec() and getattr(dlg, "saved_path", None):
            self.qs.setValue("export_dir", os.path.dirname(dlg.saved_path))
            self.statusBar().showMessage(f"Gespeichert: {dlg.saved_path}")

    # ------------------------------------------------------- DWG / Support
    def _ensure_oda(self) -> bool:
        from ..export.dwg import ODA_DOWNLOAD_URL, available
        if available():
            return True
        r = QMessageBox.question(
            self, "DWG-Export",
            "Für den DWG-Export nutzt Traceify den kostenlosen <b>ODA File Converter</b> "
            "der Open Design Alliance. Er ist nicht installiert.<br><br>"
            "Download-Seite jetzt öffnen? Nach der Installation funktioniert der DWG-Export "
            "sofort.<br><br>Alternativ: als DXF exportieren – jedes CAD-Programm öffnet DXF "
            "und kann es als DWG speichern.")
        if r == QMessageBox.Yes:
            from PySide6.QtCore import QUrl
            from PySide6.QtGui import QDesktopServices
            QDesktopServices.openUrl(QUrl(ODA_DOWNLOAD_URL))
        return False

    def report_problem(self, kind="fehler"):
        import json
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from .. import support
        what, ok = QInputDialog.getMultiLineText(
            self, "Problem melden" if kind == "fehler" else "Idee vorschlagen",
            ("Was ist passiert? (Version, Umgebung, Einstellungen und das Ende der "
             "Protokolldatei werden automatisch angehängt – du siehst alles vor dem Absenden "
             "auf GitHub.)") if kind == "fehler" else "Was wünschst du dir?")
        if not ok:
            return
        settings_json = json.dumps(self.panel.settings().to_dict(), ensure_ascii=False)
        url = support.issue_url(kind, "", what.strip(), settings_json)
        QDesktopServices.openUrl(QUrl(url))
        self.statusBar().showMessage("GitHub wurde im Browser geöffnet – dort prüfen und absenden.")

    def open_log(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from .. import support
        p = support.log_path()
        if not os.path.exists(p):
            open(p, "a").close()
        QDesktopServices.openUrl(QUrl.fromLocalFile(p))

    def toggle_update_auto(self, on):
        from .. import config
        config.save({"update_check": bool(on)})

    def check_updates(self, manual=False):
        from .. import update

        def job(_w):
            return update.check(force=manual)

        def done(info):
            if info is None:
                if manual:
                    QMessageBox.information(self, "Updates",
                                            f"Traceify {__version__} ist aktuell.")
                return
            self._show_update(info, manual)

        w = FuncWorker(job)
        w.result.connect(done)
        w.finished.connect(lambda: self.ai_workers.remove(w) if w in self.ai_workers else None)
        self.ai_workers.append(w)
        w.start()

    def _show_update(self, info, ask_now):
        from PySide6.QtWidgets import QPushButton
        if self.update_button is None:
            self.update_button = QPushButton()
            self.update_button.setStyleSheet("color: #E8601C; font-weight: bold;")
            self.statusBar().addPermanentWidget(self.update_button)
        self.update_button.setText(f"⬆ Update {info.version} verfügbar")
        try:
            self.update_button.clicked.disconnect()
        except (RuntimeError, TypeError):
            pass
        self.update_button.clicked.connect(lambda: self._update_dialog(info))
        if ask_now:
            self._update_dialog(info)

    def _update_dialog(self, info):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from .. import config
        box = QMessageBox(self)
        box.setWindowTitle("Update verfügbar")
        box.setText(f"<b>Traceify {info.version}</b> ist verfügbar (installiert: {__version__}).")
        box.setInformativeText("Setup herunterladen? Danach einfach ausführen – Einstellungen "
                               "bleiben erhalten.")
        box.setDetailedText(info.notes or "")
        b_dl = box.addButton("Herunterladen", QMessageBox.AcceptRole)
        b_page = box.addButton("Release-Seite", QMessageBox.ActionRole)
        b_skip = box.addButton("Diese Version überspringen", QMessageBox.RejectRole)
        box.addButton("Später", QMessageBox.RejectRole)
        box.exec()
        if box.clickedButton() is b_dl:
            QDesktopServices.openUrl(QUrl(info.setup_url or info.url))
        elif box.clickedButton() is b_page:
            QDesktopServices.openUrl(QUrl(info.url))
        elif box.clickedButton() is b_skip:
            config.save({"update_skip": info.version})
            if self.update_button:
                self.update_button.setVisible(False)

    def show_help(self):
        QMessageBox.information(self, "Kurzanleitung", (
            "<b>1. Öffnen</b> – Bild oder PDF öffnen bzw. ins Fenster ziehen.<br>"
            "<b>2. Vorbereiten</b> – ggf. drehen, zuschneiden, begradigen (Menü Raster). "
            "Mit »Binärbild anzeigen« prüfen, ob alle Linien schwarz erfasst werden.<br>"
            "<b>3. Modus/Vorlage</b> – CAD-Mittellinien für Zeichnungen und Pläne, "
            "CNC-Umrisse für Logos und Schneidteile.<br>"
            "<b>4. Konvertieren</b> (F5) – Ergebnis erscheint farbig über dem Bild.<br>"
            "<b>Vorher bereinigen</b> – Radierer (E) und Stift (P) im Rasterbild, Bereiche (R) "
            "mit eigenem Modus oder „ignorieren“.<br>"
            "<b>5. Bereinigen</b> – Objekte anklicken oder per Rahmen markieren, Entf löscht, "
            "Knoten ziehen, Ecke schließen (C), gerade ausrichten (O), Lücken schließen (L), "
            "Strg+Z macht rückgängig. Layer links ein-/ausblenden (nur sichtbare werden "
            "exportiert).<br>"
            "<b>Zeichnen</b> – Leiste links: Linie (N), Polylinie (Umschalt+N), Rechteck "
            "(Umschalt+K), Kreis (K), Bogen (A). Fangpunkte F3, Ortho F7 (oder Umschalt "
            "halten). Länge/Radius in mm eintippen + Enter, Rechteck „Breite;Höhe“. Esc bricht "
            "die Form ab, Rechtsklick beendet den Linienzug.<br>"
            "<b>Stutzen</b> (T) entfernt das angeklickte Teilstück bis zu den Schnittpunkten, "
            "<b>Dehnen</b> (D) verlängert eine Linie bis zum nächsten Objekt.<br>"
            "<b>6. Maßstab</b> – automatisch aus der DPI oder per »Maßstab kalibrieren« an "
            "einer bekannten Strecke.<br>"
            "<b>7. Export</b> – DXF (Strg+E), DWG, G-Code (Strg+G) oder SVG.<br><br>"
            "<b>Qualität</b> – die Ampel unten rechts zeigt, ob alles erfasst ist; Q markiert "
            "Problemstellen, F8 springt hin.<br>"
            "<b>Symbole</b> – Werkzeug Symbol (Y): Rechteck um ein Beispiel ziehen, alle gleichen "
            "werden als CAD-Block eingesetzt.<br><br>"
            "<b>Vektor-PDFs</b> aus CAD-Programmen werden automatisch erkannt und direkt "
            "übernommen. Steht „M 1:100“ im Plan, wird in Originalgröße exportiert.<br><br>"
            "Navigation: Mausrad = Zoom, mittlere Maustaste oder Umschalt+Ziehen = "
            "Verschieben (beim Zeichnen nur mittlere Maustaste), Strg+0 = Einpassen."))

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
        self.qs.setValue("state", self.saveState(UI_STATE_VERSION))
        if self.worker:
            self.worker.wait(10000)
        super().closeEvent(ev)
