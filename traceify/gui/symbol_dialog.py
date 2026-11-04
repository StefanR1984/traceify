"""Dialog: Symbol aus einem markierten Bereich festlegen und im Plan suchen."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QSlider, QVBoxLayout)

from .canvas import gray_to_qpixmap


class SymbolDialog(QDialog):
    def __init__(self, parent, crop: np.ndarray, default_name: str, ai_panel=None):
        super().__init__(parent)
        self.setWindowTitle("Symbol festlegen")
        self.ai_panel = ai_panel
        lay = QVBoxLayout(self)
        prev = QLabel()
        pm = gray_to_qpixmap(np.ascontiguousarray(crop))
        prev.setPixmap(pm.scaled(160, 160, Qt.KeepAspectRatio, Qt.FastTransformation)
                       if max(pm.width(), pm.height()) < 160 else
                       pm.scaled(220, 220, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        prev.setAlignment(Qt.AlignCenter)
        prev.setStyleSheet("background: white; border: 1px solid #bbb; padding: 6px;")
        lay.addWidget(prev)

        f = QFormLayout()
        row = QHBoxLayout()
        self.name = QLineEdit(default_name)
        row.addWidget(self.name, 1)
        self.btn_ai = QPushButton("✨ KI-Vorschlag")
        self.btn_ai.setToolTip("Lässt das KI-Bildmodell das Symbol benennen")
        self.btn_ai.clicked.connect(self._ask_ai)
        self.btn_ai.setEnabled(ai_panel is not None)
        row.addWidget(self.btn_ai)
        f.addRow("Name:", row)
        self.sim = QSlider(Qt.Horizontal)
        self.sim.setRange(50, 98)
        self.sim.setValue(72)
        self.sim_label = QLabel("72 %")
        self.sim.valueChanged.connect(lambda v: self.sim_label.setText(f"{v} %"))
        r2 = QHBoxLayout()
        r2.addWidget(self.sim, 1)
        r2.addWidget(self.sim_label)
        f.addRow("Ähnlichkeit ab:", r2)
        self.rotated = QCheckBox("Auch gedreht suchen (90°, 180°, 270°)")
        self.rotated.setChecked(True)
        f.addRow(self.rotated)
        self.save_lib = QCheckBox("In der Symbol-Bibliothek speichern (für weitere Pläne)")
        self.save_lib.setChecked(True)
        f.addRow(self.save_lib)
        lay.addLayout(f)
        lay.addWidget(QLabel("<small>Traceify sucht alle gleichen Symbole und ersetzt deren Linien "
                             "durch einen CAD-Block. Strg+Z macht es rückgängig.</small>"))
        self.crop = crop
        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.button(QDialogButtonBox.Ok).setText("Suchen und einsetzen")
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def _ask_ai(self):
        from ..ai.assistant import name_symbol
        panel = self.ai_panel
        client, model = panel.client, panel.model_name
        self.btn_ai.setEnabled(False)
        self.btn_ai.setText("… frage KI")
        crop = 255 - self.crop  # schwarz auf weiß

        def done(name):
            self.btn_ai.setText("✨ KI-Vorschlag")
            self.btn_ai.setEnabled(True)
            if name:
                self.name.setText(name)

        def err(msg):
            self.btn_ai.setText("✨ KI-Vorschlag")
            self.btn_ai.setEnabled(True)
            self.name.setToolTip(f"KI nicht verfügbar: {msg}")

        panel.run_bg(lambda _w: name_symbol(client, model, crop), done, err, busy=False)

    def values(self):
        rots = (0, 90, 180, 270) if self.rotated.isChecked() else (0,)
        return (self.name.text().strip() or "Symbol", self.sim.value() / 100.0, rots,
                self.save_lib.isChecked())
