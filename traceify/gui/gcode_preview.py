"""G-Code-Vorschau: Werkzeugwege, Eilgänge, Haltestege, Animation und Zeitschätzung."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QFileDialog, QGraphicsScene,
                               QGraphicsView, QHBoxLayout, QLabel, QMessageBox,
                               QPlainTextEdit, QPushButton, QSlider, QTabWidget,
                               QVBoxLayout, QWidget)

from ..export.gcode import MACHINE_MILL, generate_gcode, plan

COL_CUT = QColor(232, 96, 28)
COL_TAB = QColor(40, 170, 90)
COL_RAPID = QColor(140, 150, 165)
COL_DONE = QColor(30, 30, 30)


def _arc_points(prev, m, step_deg=6.0):
    cx, cy = prev.x + m.i, prev.y + m.j
    r = math.hypot(m.i, m.j)
    a0 = math.atan2(prev.y - cy, prev.x - cx)
    a1 = math.atan2(m.y - cy, m.x - cx)
    if m.cw:
        sweep = -(((a0 - a1) % (2 * math.pi)) or 2 * math.pi)
    else:
        sweep = ((a1 - a0) % (2 * math.pi)) or 2 * math.pi
    n = max(4, int(abs(math.degrees(sweep)) / step_deg))
    return [(cx + r * math.cos(a0 + sweep * k / n), cy + r * math.sin(a0 + sweep * k / n))
            for k in range(1, n + 1)]


class PreviewView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing)
        self.setBackgroundBrush(QColor(248, 249, 251))
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale(1, -1)  # CAD: y nach oben

    def wheelEvent(self, ev):
        f = 1.25 if ev.angleDelta().y() > 0 else 0.8
        self.scale(f, f)

    def fit(self):
        r = self.scene().itemsBoundingRect()
        if not r.isEmpty():
            self.fitInView(r.adjusted(-5, -5, 5, 5), Qt.KeepAspectRatio)


class GcodePreviewDialog(QDialog):
    def __init__(self, parent, drawing, settings, visible_layers=None, default_path=""):
        super().__init__(parent)
        self.setWindowTitle("G-Code-Vorschau")
        self.resize(1100, 760)
        self.drawing, self.settings, self.visible = drawing, settings, visible_layers
        self.default_path = default_path
        self.res = plan(drawing, settings, visible_layers)
        self.gcode = generate_gcode(drawing, settings, visible_layers, result=self.res)

        lay = QVBoxLayout(self)
        self.info = QLabel()
        self.info.setWordWrap(True)
        lay.addWidget(self.info)
        tabs = QTabWidget()
        lay.addWidget(tabs, 1)

        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        self.view = PreviewView()
        v.addWidget(self.view, 1)
        row = QHBoxLayout()
        self.btn_play = QPushButton("▶ Abspielen")
        self.btn_play.clicked.connect(self.toggle_play)
        row.addWidget(self.btn_play)
        self.slider = QSlider(Qt.Horizontal)
        row.addWidget(self.slider, 1)
        self.pos_label = QLabel("")
        self.pos_label.setMinimumWidth(240)
        row.addWidget(self.pos_label)
        v.addLayout(row)
        legend = QLabel('<span style="color:#e8601c">━ Schnitt</span> &nbsp; '
                        '<span style="color:#28aa5a">━ Haltesteg</span> &nbsp; '
                        '<span style="color:#8c96a5">┅ Eilgang</span> &nbsp; '
                        '<span style="color:#1e1e1e">━ erledigt</span> &nbsp; '
                        "Mausrad = Zoom, Ziehen = verschieben")
        v.addWidget(legend)
        tabs.addTab(w, "Werkzeugwege")

        self.text = QPlainTextEdit(self.gcode)
        self.text.setReadOnly(True)
        self.text.setFont(QFont("Consolas", 9))
        tabs.addTab(self.text, f"G-Code ({self.gcode.count(chr(10))} Zeilen)")

        bb = QDialogButtonBox()
        b_save = bb.addButton("G-Code speichern …", QDialogButtonBox.AcceptRole)
        b_save.clicked.connect(self.save)
        bb.addButton("Schließen", QDialogButtonBox.RejectRole).clicked.connect(self.reject)
        lay.addWidget(bb)

        self._build_scene()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.slider.setRange(0, max(1, len(self.res.moves) - 1))
        self.slider.setValue(self.slider.maximum())
        self.slider.valueChanged.connect(self._show_progress)
        self._show_progress(self.slider.maximum())
        self._update_info()
        QTimer.singleShot(0, self.view.fit)

    # ------------------------------------------------------------ Szene
    def _build_scene(self):
        sc = self.view.scene()
        sc.clear()
        self.segments = []   # (move_index, QPainterPath, kind)
        moves = self.res.moves
        mill = self.settings.machine == MACHINE_MILL
        pen_rapid = QPen(COL_RAPID, 0.8, Qt.DashLine)
        pen_rapid.setCosmetic(True)
        for k in range(1, len(moves)):
            a, b = moves[k - 1], moves[k]
            if b.kind in ("plunge", "on", "off") or (b.kind == "retract" and not b.tab):
                continue
            path = QPainterPath(QPointF(a.x, a.y))
            if b.kind == "arc":
                for x, y in _arc_points(a, b):
                    path.lineTo(x, y)
            else:
                path.lineTo(b.x, b.y)
            if b.kind == "rapid" and not b.tab:
                it = sc.addPath(path, pen_rapid)
                kind = "rapid"
            else:
                kind = "tab" if b.tab else "cut"
                pen = QPen(COL_TAB if b.tab else COL_CUT, 2.0 if mill else 1.5)
                pen.setCosmetic(True)
                pen.setCapStyle(Qt.RoundCap)
                it = sc.addPath(path, pen)
            it.setZValue(1 if kind != "rapid" else 0)
            self.segments.append((k, it, kind))
        # Werkzeugposition
        r = max(0.6, self.settings.tool_diameter / 2) if mill else 0.6
        self.tool = sc.addEllipse(-r, -r, 2 * r, 2 * r, QPen(QColor(0, 120, 220), 0),
                                  QBrush(QColor(0, 120, 220, 110)))
        self.tool.setZValue(5)

    def _show_progress(self, idx):
        moves = self.res.moves
        idx = max(0, min(idx, len(moves) - 1))
        for k, it, kind in self.segments:
            pen = it.pen()
            if kind == "rapid":
                it.setVisible(k <= idx or idx == len(moves) - 1)
                continue
            base = COL_TAB if kind == "tab" else COL_CUT
            done = k <= idx and idx < len(moves) - 1
            pen.setColor(COL_DONE if done else base)
            it.setPen(pen)
        m = moves[idx]
        self.tool.setPos(m.x, m.y)
        self.pos_label.setText(f"X {m.x:8.2f}  Y {m.y:8.2f}  Z {m.z:6.2f}   "
                               f"({idx}/{len(moves) - 1})")

    def toggle_play(self):
        if self.timer.isActive():
            self.timer.stop()
            self.btn_play.setText("▶ Abspielen")
            return
        if self.slider.value() >= self.slider.maximum():
            self.slider.setValue(0)
        self.btn_play.setText("⏸ Pause")
        self.timer.start(16)

    def _tick(self):
        step = max(1, len(self.res.moves) // 600)  # ganze Animation ca. 10 s
        v = self.slider.value() + step
        if v >= self.slider.maximum():
            v = self.slider.maximum()
            self.timer.stop()
            self.btn_play.setText("▶ Abspielen")
        self.slider.setValue(v)

    def _update_info(self):
        r, s = self.res, self.settings
        t = r.time_min
        tt = f"{int(t // 60)} h {int(t % 60)} min" if t >= 60 else f"{t:.1f} min"
        txt = (f"<b>{len(r.paths)}</b> Wege · <b>{r.passes}</b> Durchgang/-gänge · "
               f"Schnittweg <b>{r.cut_length / 1000:.2f} m</b> · Eilgang {r.rapid_length / 1000:.2f} m"
               f" · geschätzte Zeit <b>{tt}</b>")
        if s.machine == MACHINE_MILL:
            txt += (f"<br>Fräser Ø {s.tool_diameter:g} mm · Korrektur: {s.compensation} · "
                    f"Tiefe {s.cut_depth:g} mm in {s.step_down:g}-mm-Schritten")
        if s.tabs:
            txt += f" · {s.tabs} Haltestege je Außenkontur"
        if r.warnings:
            txt += "<br><span style='color:#c0392b'>⚠ " + "<br>⚠ ".join(r.warnings) + "</span>"
        self.info.setText(txt)

    def save(self):
        f, _ = QFileDialog.getSaveFileName(self, "G-Code speichern", self.default_path,
                                           "G-Code (*.nc *.gcode *.tap *.ngc)")
        if not f:
            return
        try:
            with open(f, "w", encoding="ascii", errors="replace") as fh:
                fh.write(self.gcode)
        except OSError as exc:
            QMessageBox.critical(self, "Fehler", str(exc))
            return
        self.saved_path = f
        self.accept()
