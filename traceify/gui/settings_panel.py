"""Einstellungsbereich (rechts): Modus, Vorlagen, Raster, Vektor, OCR, Maßstab, G-Code."""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QComboBox, QDoubleSpinBox,
                               QFormLayout, QGroupBox, QLabel, QPushButton,
                               QRadioButton, QScrollArea, QSpinBox, QVBoxLayout,
                               QWidget)

from ..core.ocr import available_languages, tesseract_available
from ..core.pipeline import ConvertSettings
from ..core.vectorize import MODE_CENTERLINE, MODE_OUTLINE
from ..export.gcode import COMP_LABELS, MACHINE_LASER, MACHINE_MILL, GcodeSettings

from ..gui_presets import PRESETS  # noqa: E402


def _spin(lo, hi, val, step=1, dec=None, suffix=""):
    w = QDoubleSpinBox() if dec is not None else QSpinBox()
    if dec is not None:
        w.setDecimals(dec)
    w.setRange(lo, hi)
    w.setSingleStep(step)
    w.setValue(val)
    if suffix:
        w.setSuffix(suffix)
    return w


class SettingsPanel(QScrollArea):
    convertRequested = Signal()
    previewBinaryRequested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setMinimumWidth(310)
        root = QWidget()
        lay = QVBoxLayout(root)
        self.setWidget(root)

        # ---- Modus ----
        g = QGroupBox("Konvertierung")
        f = QFormLayout(g)
        self.rb_cad = QRadioButton("CAD – Mittellinien (Linien, Bögen, Kreise)")
        self.rb_cnc = QRadioButton("CNC – Umrisse (geschlossene Konturen)")
        self.rb_cad.setChecked(True)
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_cad)
        self.mode_group.addButton(self.rb_cnc)
        f.addRow(self.rb_cad)
        f.addRow(self.rb_cnc)
        self.preset = QComboBox()
        self.preset.addItem("– Vorlage wählen –")
        self.preset.addItems(list(PRESETS))
        self.preset.currentTextChanged.connect(self.apply_preset)
        f.addRow("Vorlage:", self.preset)
        self.btn_convert = QPushButton("▶  Konvertieren")
        self.btn_convert.setMinimumHeight(36)
        self.btn_convert.setStyleSheet("font-weight:bold;")
        self.btn_convert.clicked.connect(self.convertRequested)
        f.addRow(self.btn_convert)
        lay.addWidget(g)

        # ---- Raster ----
        g = QGroupBox("Raster-Vorverarbeitung")
        f = QFormLayout(g)
        self.threshold = _spin(0, 254, 0)
        self.threshold.setSpecialValueText("automatisch")
        f.addRow("Schwellwert:", self.threshold)
        self.adaptive = QCheckBox("Adaptiv (ungleichmäßige Scans)")
        f.addRow(self.adaptive)
        self.invert = QCheckBox("Invertieren (helle Linien)")
        f.addRow(self.invert)
        self.deskew = QCheckBox("Schräglage automatisch begradigen")
        f.addRow(self.deskew)
        self.despeckle = _spin(0, 5000, 12, suffix=" px²")
        f.addRow("Flecken entfernen bis:", self.despeckle)
        self.fill_holes = _spin(0, 5000, 0, suffix=" px²")
        f.addRow("Löcher füllen bis:", self.fill_holes)
        self.smooth = _spin(0, 15, 0)
        self.smooth.setSpecialValueText("aus")
        f.addRow("Glätten:", self.smooth)
        self.thicken = _spin(0, 10, 0, suffix=" px")
        f.addRow("Lücken schließen:", self.thicken)
        b = QPushButton("Binärbild anzeigen")
        b.clicked.connect(self.previewBinaryRequested)
        f.addRow(b)
        lay.addWidget(g)

        # ---- Vektor ----
        g = QGroupBox("Vektorisierung")
        f = QFormLayout(g)
        self.tolerance = _spin(0.2, 20, 1.5, 0.1, 1, " px")
        f.addRow("Toleranz:", self.tolerance)
        self.arcs = QCheckBox("Bögen erkennen")
        self.arcs.setChecked(True)
        f.addRow(self.arcs)
        self.circles = QCheckBox("Kreise erkennen")
        self.circles.setChecked(True)
        f.addRow(self.circles)
        self.polylines = QCheckBox("Nur Polylinien ausgeben")
        f.addRow(self.polylines)
        self.min_length = _spin(0, 500, 6, 1, 1, " px")
        f.addRow("Min. Länge:", self.min_length)
        self.corner = _spin(10, 120, 40, 5, 0, " °")
        f.addRow("Eckenwinkel:", self.corner)
        self.snap = _spin(0, 20, 3, 0.5, 1, " px")
        f.addRow("Endpunkte fangen:", self.snap)
        self.contour_smooth = _spin(0, 10, 2)
        f.addRow("Umriss-Glättung:", self.contour_smooth)
        lay.addWidget(g)

        # ---- Linien & Farben ----
        g = QGroupBox("Linien, Farben, Symbole")
        f = QFormLayout(g)
        self.dashed = QCheckBox("Strichlinien erkennen (gestrichelt, Strichpunkt)")
        self.dashed.setChecked(True)
        f.addRow(self.dashed)
        self.widths = QCheckBox("Strichstärken messen und übernehmen")
        self.widths.setChecked(True)
        f.addRow(self.widths)
        self.thick = QCheckBox("Dicke Linien auf eigenen Layer (z. B. Wände)")
        self.thick.setChecked(True)
        f.addRow(self.thick)
        self.thick_ratio = _spin(1.2, 5.0, 1.7, 0.1, 1, " ×")
        f.addRow("Dick ab:", self.thick_ratio)
        self.walls_outline = QCheckBox("Wände als Umriss (Doppellinie) statt Mittellinie")
        self.walls_outline.setToolTip("Dicke Linien werden als geschlossene Umrisse auf den Layer "
                                      "WAENDE gelegt – wie gezeichnete Wände im CAD")
        f.addRow(self.walls_outline)
        self.straighten = QCheckBox("Linien gerade ausrichten (Schräglage ausgleichen)")
        self.straighten.setToolTip("Erkennt, wie schief der Scan liegt, richtet fast waagrechte/"
                                   "senkrechte Linien exakt aus und dreht die Schräglage beim "
                                   "Export heraus")
        self.straighten.setChecked(True)
        f.addRow(self.straighten)
        self.close_gaps = _spin(0.0, 5.0, 0.8, 0.1, 1, " mm")
        self.close_gaps.setSpecialValueText("aus")
        self.close_gaps.setToolTip("Linienenden, die knapp vor einem anderen Objekt enden, werden "
                                   "bis dorthin verlängert (Ecken und T-Stöße schließen)")
        f.addRow("Kleine Lücken schließen bis:", self.close_gaps)
        self.hatch = QCheckBox("Schraffur erkennen (Layer SCHRAFFUR)")
        self.hatch.setToolTip("Schräge Schraffurlinien (z. B. in Wänden) kommen auf einen eigenen "
                              "Layer und lassen sich im CAD mit einem Klick ausblenden")
        self.hatch.setChecked(True)
        f.addRow(self.hatch)
        self.hatch_areas = QCheckBox("Schraffur als Fläche exportieren (DXF-HATCH)")
        self.hatch_areas.setToolTip("Regelmäßige Schraffuren kommen im DXF/DWG als eine "
                                    "Schraffur-Fläche mit Winkel und Abstand statt als viele "
                                    "Einzellinien – im CAD als Ganzes änderbar")
        self.hatch_areas.setChecked(True)
        self.hatch.toggled.connect(self.hatch_areas.setEnabled)
        f.addRow(self.hatch_areas)
        self.color_layers = QCheckBox("Farben auf eigene Layer trennen")
        self.color_layers.setToolTip("Farbige Pläne: jede Farbe wird ein Layer (FARBE_ROT, …)")
        f.addRow(self.color_layers)
        self.color_count = _spin(0, 12, 0)
        self.color_count.setSpecialValueText("automatisch")
        f.addRow("Anzahl Farben:", self.color_count)
        self.symbols_auto = QCheckBox("Symbole aus der Bibliothek automatisch einsetzen")
        self.symbols_auto.setToolTip("Symbole, die du einmal festgelegt hast (Werkzeug „Symbol“), "
                                     "werden in neuen Plänen automatisch als CAD-Block erkannt.")
        f.addRow(self.symbols_auto)
        lay.addWidget(g)

        # ---- OCR ----
        g = QGroupBox("Texterkennung (OCR)")
        f = QFormLayout(g)
        self.ocr = QCheckBox("Texte erkennen")
        self.ocr.setChecked(True)
        f.addRow(self.ocr)
        self.ocr_lang = QComboBox()
        self.ocr_lang.setEditable(True)
        langs = available_languages()
        opts = ["deu+eng", "deu", "eng"] + [l for l in langs if l not in ("deu", "eng", "osd")]
        self.ocr_lang.addItems(opts)
        f.addRow("Sprache:", self.ocr_lang)
        self.ocr_conf = _spin(0, 100, 60, suffix=" %")
        f.addRow("Min. Sicherheit:", self.ocr_conf)
        self.ocr_vertical = QCheckBox("Auch senkrechten Text suchen")
        self.ocr_vertical.setChecked(True)
        f.addRow(self.ocr_vertical)
        self.ocr_upside = QCheckBox("Auch Text auf dem Kopf suchen")
        self.ocr_upside.setChecked(True)
        f.addRow(self.ocr_upside)
        self.ocr_free = QCheckBox("Schräge Texte nachlesen")
        self.ocr_free.setToolTip("Schrift in beliebigem Winkel, die die normale Erkennung "
                                 "nicht gefunden hat, wird geradegerückt und nachgelesen")
        self.ocr_free.setChecked(True)
        f.addRow(self.ocr_free)
        self.ocr_numbers = QCheckBox("Maßzahlen nachlesen (Kommas ergänzen)")
        self.ocr_numbers.setToolTip("Zahlen wie „24 85“ oder „251“ werden gezielt noch einmal "
                                    "gelesen; fehlende Kommas/Punkte werden ergänzt, die Ziffern "
                                    "bleiben unverändert")
        self.ocr_numbers.setChecked(True)
        f.addRow(self.ocr_numbers)
        if not tesseract_available():
            self.ocr.setChecked(False)
            self.ocr.setEnabled(False)
            f.addRow(QLabel("<i>Tesseract nicht gefunden – siehe README.</i>"))
        lay.addWidget(g)

        # ---- Maßstab ----
        g = QGroupBox("Maßstab")
        f = QFormLayout(g)
        self.scale_auto = QCheckBox("Aus Bild-DPI übernehmen")
        self.scale_auto.setChecked(True)
        f.addRow(self.scale_auto)
        self.mmpx = _spin(0.00001, 100000, 25.4 / 300, 0.01, 5, " mm/px")
        self.mmpx.setEnabled(False)
        self.scale_auto.toggled.connect(lambda on: self.mmpx.setEnabled(not on))
        f.addRow("Maßstab:", self.mmpx)
        self.auto_scale = QCheckBox("Maßstab aus Plan übernehmen (z. B. „M 1:100“)")
        self.auto_scale.setChecked(True)
        self.auto_scale.setToolTip("Steht im Plan „M 1:100“, wird in Originalgröße exportiert "
                                   "(1 cm auf dem Papier = 1 m). Nur ohne manuellen Maßstab.")
        f.addRow(self.auto_scale)
        self.pdf_dpi = _spin(0, 1200, 0, 50, 0, " dpi")
        self.pdf_dpi.setSpecialValueText("automatisch")
        self.pdf_dpi.setToolTip("Automatisch: gescannte PDFs in ihrer Originalauflösung "
                                "(schneller, keine Hochrechnung), sonst 300 dpi")
        f.addRow("PDF-Render-DPI:", self.pdf_dpi)
        lay.addWidget(g)

        # ---- PDF ----
        g = QGroupBox("Vektor-PDF")
        f = QFormLayout(g)
        self.pdf_vectors = QCheckBox("Vektordaten direkt übernehmen (wenn vorhanden)")
        self.pdf_vectors.setChecked(True)
        self.pdf_vectors.setToolTip("PDFs aus CAD-Programmen enthalten echte Linien – diese werden "
                                    "millimetergenau übernommen statt neu vektorisiert.")
        f.addRow(self.pdf_vectors)
        self.pdf_fills = QCheckBox("Gefüllte Flächen übernehmen")
        f.addRow(self.pdf_fills)
        self.pdf_colors = QCheckBox("Linienfarben übernehmen")
        self.pdf_colors.setChecked(True)
        f.addRow(self.pdf_colors)
        self.btn_calibrate = QPushButton("Maßstab per Länge kalibrieren …")
        f.addRow(self.btn_calibrate)
        lay.addWidget(g)

        # ---- G-Code ----
        g = QGroupBox("CNC / G-Code")
        f = QFormLayout(g)
        self.machine = QComboBox()
        self.machine.addItem("Fräse (Z-Zustellung)", MACHINE_MILL)
        self.machine.addItem("Laser / Plasma (M3/M5)", MACHINE_LASER)
        f.addRow("Maschine:", self.machine)
        self.feed = _spin(1, 50000, 800, 50, 0, " mm/min")
        f.addRow("Vorschub:", self.feed)
        self.plunge = _spin(1, 20000, 200, 10, 0, " mm/min")
        f.addRow("Eintauchen:", self.plunge)
        self.spindle = _spin(0, 60000, 12000, 500)
        f.addRow("Drehzahl / Leistung S:", self.spindle)
        self.safe_z = _spin(0, 100, 5, 0.5, 2, " mm")
        f.addRow("Sicherheitshöhe:", self.safe_z)
        self.depth = _spin(0, 100, 1, 0.1, 2, " mm")
        f.addRow("Frästiefe:", self.depth)
        self.step_down = _spin(0.01, 50, 0.5, 0.1, 2, " mm")
        f.addRow("Zustellung:", self.step_down)
        self.optimize = QCheckBox("Fahrwege optimieren")
        self.optimize.setChecked(True)
        f.addRow(self.optimize)
        self.tool_d = _spin(0, 50, 3, 0.5, 2, " mm")
        f.addRow("Fräser-Ø:", self.tool_d)
        self.comp = QComboBox()
        for key, label in COMP_LABELS.items():
            self.comp.addItem(label, key)
        self.comp.setToolTip("Radiuskorrektur: Werkzeugweg um den Fräserradius versetzen, damit "
                             "das Teil maßhaltig wird. „Automatisch“: Außenkonturen außen, Löcher "
                             "innen, Löcher zuerst.")
        f.addRow("Radiuskorrektur:", self.comp)
        self.climb = QCheckBox("Gleichlauf (sonst Gegenlauf)")
        self.climb.setChecked(True)
        f.addRow(self.climb)
        self.tabs = _spin(0, 20, 0)
        self.tabs.setSpecialValueText("keine")
        self.tabs.setToolTip("Haltestege je Außenkontur – das Teil bleibt mit der Platte verbunden")
        f.addRow("Haltestege:", self.tabs)
        self.tab_w = _spin(0.2, 50, 4, 0.5, 1, " mm")
        f.addRow("Steg-Breite:", self.tab_w)
        self.tab_h = _spin(0.1, 50, 1, 0.1, 2, " mm")
        f.addRow("Steg-Höhe:", self.tab_h)
        self.rapid = _spin(100, 50000, 3000, 100, 0, " mm/min")
        f.addRow("Eilgang (Zeitschätzung):", self.rapid)
        self.btn_preview = QPushButton("G-Code-Vorschau …")
        f.addRow(self.btn_preview)
        lay.addWidget(g)
        lay.addStretch(1)

    # ------------------------------------------------------------------
    def apply_preset(self, name: str):
        p = PRESETS.get(name)
        if not p:
            return
        (self.rb_cnc if p["mode"] == MODE_OUTLINE else self.rb_cad).setChecked(True)
        self.tolerance.setValue(p["tolerance"])
        self.arcs.setChecked(p["arcs"])
        self.circles.setChecked(p["circles"])
        self.polylines.setChecked(p["polylines"])
        self.despeckle.setValue(p["despeckle"])
        self.smooth.setValue(p["smooth"])
        if self.ocr.isEnabled():
            self.ocr.setChecked(p["ocr"])

    def settings(self) -> ConvertSettings:
        s = ConvertSettings()
        pp, v, o = s.preprocess, s.vectorize, s.ocr
        pp.threshold = self.threshold.value()
        pp.adaptive = self.adaptive.isChecked()
        pp.invert = self.invert.isChecked()
        pp.deskew = self.deskew.isChecked()
        pp.despeckle = self.despeckle.value()
        pp.fill_holes = self.fill_holes.value()
        pp.smooth = self.smooth.value()
        pp.thicken = self.thicken.value()
        v.mode = MODE_OUTLINE if self.rb_cnc.isChecked() else MODE_CENTERLINE
        v.tolerance = self.tolerance.value()
        v.detect_arcs = self.arcs.isChecked()
        v.detect_circles = self.circles.isChecked()
        v.output_polylines = self.polylines.isChecked()
        v.min_length = self.min_length.value()
        v.corner_angle = self.corner.value()
        v.snap_distance = self.snap.value()
        v.contour_smooth = self.contour_smooth.value()
        o.enabled = self.ocr.isChecked()
        o.language = self.ocr_lang.currentText().strip() or "eng"
        o.min_confidence = self.ocr_conf.value()
        o.vertical_text = self.ocr_vertical.isChecked()
        o.upside_down = self.ocr_upside.isChecked()
        o.free_angles = self.ocr_free.isChecked()
        o.fix_numbers = self.ocr_numbers.isChecked()
        s.scale = None if self.scale_auto.isChecked() else self.mmpx.value()
        s.auto_scale = self.auto_scale.isChecked()
        st = s.style
        st.detect_dashed = self.dashed.isChecked()
        st.measure_widths = self.widths.isChecked()
        st.thick_layer = self.thick.isChecked()
        st.thick_ratio = self.thick_ratio.value()
        st.walls_outline = self.walls_outline.isChecked()
        st.hatch_layer = self.hatch.isChecked()
        st.hatch_areas = self.hatch_areas.isChecked()
        st.straighten = self.straighten.isChecked()
        st.close_gaps_mm = self.close_gaps.value()
        st.color_layers = self.color_layers.isChecked()
        st.color_count = self.color_count.value()
        s.symbols_auto = self.symbols_auto.isChecked()
        s.pdf.enabled = self.pdf_vectors.isChecked()
        s.pdf.include_fills = self.pdf_fills.isChecked()
        s.pdf.keep_colors = self.pdf_colors.isChecked()
        return s

    def set_settings(self, s: ConvertSettings):
        pp, v, o = s.preprocess, s.vectorize, s.ocr
        self.threshold.setValue(pp.threshold)
        self.adaptive.setChecked(pp.adaptive)
        self.invert.setChecked(pp.invert)
        self.deskew.setChecked(pp.deskew)
        self.despeckle.setValue(pp.despeckle)
        self.fill_holes.setValue(pp.fill_holes)
        self.smooth.setValue(pp.smooth)
        self.thicken.setValue(pp.thicken)
        (self.rb_cnc if v.mode == MODE_OUTLINE else self.rb_cad).setChecked(True)
        self.tolerance.setValue(v.tolerance)
        self.arcs.setChecked(v.detect_arcs)
        self.circles.setChecked(v.detect_circles)
        self.polylines.setChecked(v.output_polylines)
        self.min_length.setValue(v.min_length)
        self.corner.setValue(v.corner_angle)
        self.snap.setValue(v.snap_distance)
        self.contour_smooth.setValue(v.contour_smooth)
        if self.ocr.isEnabled():
            self.ocr.setChecked(o.enabled)
        self.ocr_lang.setCurrentText(o.language)
        self.ocr_conf.setValue(o.min_confidence)
        self.ocr_vertical.setChecked(o.vertical_text)
        self.ocr_upside.setChecked(o.upside_down)
        self.ocr_free.setChecked(o.free_angles)
        self.ocr_numbers.setChecked(o.fix_numbers)
        self.scale_auto.setChecked(s.scale is None)
        self.auto_scale.setChecked(s.auto_scale)
        self.dashed.setChecked(s.style.detect_dashed)
        self.widths.setChecked(s.style.measure_widths)
        self.thick.setChecked(s.style.thick_layer)
        self.thick_ratio.setValue(s.style.thick_ratio)
        self.walls_outline.setChecked(s.style.walls_outline)
        self.hatch.setChecked(s.style.hatch_layer)
        self.hatch_areas.setChecked(s.style.hatch_areas)
        self.straighten.setChecked(s.style.straighten)
        self.close_gaps.setValue(s.style.close_gaps_mm)
        self.color_layers.setChecked(s.style.color_layers)
        self.color_count.setValue(s.style.color_count)
        self.symbols_auto.setChecked(s.symbols_auto)
        self.pdf_vectors.setChecked(s.pdf.enabled)
        self.pdf_fills.setChecked(s.pdf.include_fills)
        self.pdf_colors.setChecked(s.pdf.keep_colors)
        if s.scale:
            self.mmpx.setValue(s.scale)

    def set_manual_scale(self, mm_per_px: float):
        self.scale_auto.setChecked(False)
        self.mmpx.setValue(mm_per_px)

    def gcode_settings(self) -> GcodeSettings:
        return GcodeSettings(machine=self.machine.currentData(), feed_rate=self.feed.value(),
                             plunge_rate=self.plunge.value(), spindle_speed=self.spindle.value(),
                             safe_z=self.safe_z.value(), cut_depth=self.depth.value(),
                             step_down=self.step_down.value(),
                             optimize_order=self.optimize.isChecked(),
                             tool_diameter=self.tool_d.value(),
                             compensation=self.comp.currentData(),
                             climb=self.climb.isChecked(), tabs=self.tabs.value(),
                             tab_width=self.tab_w.value(), tab_height=self.tab_h.value(),
                             rapid_rate=self.rapid.value())


    # ------------------------------------------------------------------
    def set_value(self, name: str, value) -> str:
        """Setzt eine Einstellung per Namen (für den KI-Assistenten). Gibt Klartext zurück."""
        def b(v):
            return v if isinstance(v, bool) else str(v).lower() in ("1", "true", "ja", "an", "yes")

        def num(w, v):
            w.setValue(type(w.value())(float(v)))
            return w.value()

        n = name.lower().strip()
        if n == "modus":
            (self.rb_cnc if str(value).lower().startswith("u") else self.rb_cad).setChecked(True)
            return f"Modus: {'CNC-Umriss' if self.rb_cnc.isChecked() else 'CAD-Mittellinie'}"
        if n == "vorlage":
            match = next((k for k in PRESETS if k.lower() == str(value).lower()), None) or \
                next((k for k in PRESETS if str(value).lower() in k.lower()), None)
            if not match:
                raise ValueError(f"unbekannte Vorlage {value}")
            self.preset.setCurrentText(match)
            self.apply_preset(match)
            return f"Vorlage: {match}"
        checks = {"adaptiv": self.adaptive, "invertieren": self.invert, "begradigen": self.deskew,
                  "boegen": self.arcs, "kreise": self.circles, "nur_polylinien": self.polylines,
                  "ocr": self.ocr, "strichlinien": self.dashed, "strichstaerken": self.widths,
                  "dicke_linien_layer": self.thick, "farben_trennen": self.color_layers,
                  "waende_umriss": self.walls_outline, "schraffur_layer": self.hatch,
                  "schraffur_flaeche": self.hatch_areas,
                  "schraege_texte": self.ocr_free, "zahlen_nachlesen": self.ocr_numbers,
                  "gerade_ausrichten": self.straighten,
                  "massstab_aus_plan": self.auto_scale, "pdf_vektoren": self.pdf_vectors,
                  "symbole_automatisch": self.symbols_auto}
        if n in checks:
            checks[n].setChecked(b(value))
            return f"{name}: {'an' if checks[n].isChecked() else 'aus'}"
        nums = {"toleranz": self.tolerance, "schwellwert": self.threshold, "flecken": self.despeckle,
                "luecken_mm": self.close_gaps,
                "luecken_schliessen": self.thicken, "glaetten": self.smooth,
                "min_laenge": self.min_length, "eckenwinkel": self.corner,
                "vorschub": self.feed, "fraestiefe": self.depth, "zustellung": self.step_down,
                "fraeser_durchmesser": self.tool_d, "haltestege": self.tabs,
                "steg_breite": self.tab_w, "steg_hoehe": self.tab_h,
                "anzahl_farben": self.color_count}
        if n in nums:
            return f"{name}: {num(nums[n], value)}"
        if n == "ocr_sprache":
            self.ocr_lang.setCurrentText(str(value))
            return f"OCR-Sprache: {value}"
        if n == "massstab_mm_pro_px":
            self.set_manual_scale(float(value))
            return f"Maßstab: {float(value):.5f} mm/px"
        if n == "radiuskorrektur":
            v = str(value).lower().replace("ß", "ss").replace("ä", "ae").replace("ö", "oe") \
                .replace("ü", "ue")
            key = next((k for k in COMP_LABELS if v.startswith(k[:3])), None)
            if not key:
                raise ValueError(f"unbekannte Radiuskorrektur {value}")
            self.comp.setCurrentIndex(self.comp.findData(key))
            return f"Radiuskorrektur: {self.comp.currentText()}"
        if n == "maschine":
            self.machine.setCurrentIndex(1 if str(value).lower().startswith(("l", "p")) else 0)
            return f"Maschine: {self.machine.currentText()}"
        raise ValueError(f"unbekannte Einstellung {name}")
