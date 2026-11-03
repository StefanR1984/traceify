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
from ..export.gcode import MACHINE_LASER, MACHINE_MILL, GcodeSettings

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
        self.pdf_dpi = _spin(72, 1200, 300, 50, 0, " dpi")
        f.addRow("PDF-Render-DPI:", self.pdf_dpi)
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
        s.scale = None if self.scale_auto.isChecked() else self.mmpx.value()
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
        self.scale_auto.setChecked(s.scale is None)
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
                             optimize_order=self.optimize.isChecked())


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
                  "ocr": self.ocr}
        if n in checks:
            checks[n].setChecked(b(value))
            return f"{name}: {'an' if checks[n].isChecked() else 'aus'}"
        nums = {"toleranz": self.tolerance, "schwellwert": self.threshold, "flecken": self.despeckle,
                "luecken_schliessen": self.thicken, "glaetten": self.smooth,
                "min_laenge": self.min_length, "eckenwinkel": self.corner,
                "vorschub": self.feed, "fraestiefe": self.depth, "zustellung": self.step_down}
        if n in nums:
            return f"{name}: {num(nums[n], value)}"
        if n == "ocr_sprache":
            self.ocr_lang.setCurrentText(str(value))
            return f"OCR-Sprache: {value}"
        if n == "massstab_mm_pro_px":
            self.set_manual_scale(float(value))
            return f"Maßstab: {float(value):.5f} mm/px"
        if n == "maschine":
            self.machine.setCurrentIndex(1 if str(value).lower().startswith(("l", "p")) else 0)
            return f"Maschine: {self.machine.currentText()}"
        raise ValueError(f"unbekannte Einstellung {name}")
