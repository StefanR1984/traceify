"""Zeichenfläche: Rasterbild + Vektor-Overlay, Zoom, Auswahl, Zuschneiden."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QPainter, QPainterPath,
                           QPen, QPixmap, QTransform)
from PySide6.QtWidgets import (QGraphicsItem, QGraphicsPathItem,
                               QGraphicsPixmapItem, QGraphicsRectItem,
                               QGraphicsScene, QGraphicsSimpleTextItem,
                               QGraphicsView, QRubberBand)

from ..core.model import Arc, Circle, Line, Polyline, Text, layer_color


def gray_to_qpixmap(img: np.ndarray) -> QPixmap:
    img = np.ascontiguousarray(img)
    h, w = img.shape
    qimg = QImage(img.data, w, h, w, QImage.Format_Grayscale8).copy()
    return QPixmap.fromImage(qimg)


def entity_path(e) -> QPainterPath:
    p = QPainterPath()
    if isinstance(e, Line):
        p.moveTo(*e.p1)
        p.lineTo(*e.p2)
    elif isinstance(e, Circle):
        p.addEllipse(QPointF(*e.center), e.radius, e.radius)
    elif isinstance(e, Arc):
        r = e.radius
        rect = QRectF(e.center[0] - r, e.center[1] - r, 2 * r, 2 * r)
        span = (e.end_angle - e.start_angle) % 360
        p.arcMoveTo(rect, -e.start_angle)
        p.arcTo(rect, -e.start_angle, -span)
    elif isinstance(e, Polyline):
        if e.points:
            p.moveTo(*e.points[0])
            for pt in e.points[1:]:
                p.lineTo(*pt)
            if e.closed:
                p.closeSubpath()
    return p


class EntityItem(QGraphicsPathItem):
    def __init__(self, entity, width: float):
        super().__init__(entity_path(entity))
        self.entity = entity
        rgb = getattr(entity, "color", None) or layer_color(entity.layer)[1]
        self.base_pen = QPen(QColor(*rgb), width)
        self.base_pen.setCosmetic(True)
        self.base_pen.setCapStyle(Qt.RoundCap)
        lt = getattr(entity, "linetype", "CONTINUOUS")
        if lt in ("DASHED", "HIDDEN"):
            self.base_pen.setStyle(Qt.DashLine)
        elif lt == "DOT":
            self.base_pen.setStyle(Qt.DotLine)
        elif lt in ("DASHDOT", "CENTER"):
            self.base_pen.setStyle(Qt.DashDotLine)
        self.setPen(self.base_pen)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(2)

    def paint(self, painter, option, widget=None):
        pen = QPen(self.base_pen)
        if self.isSelected():
            pen.setColor(QColor(255, 120, 0))
            pen.setWidthF(self.base_pen.widthF() + 2)
        painter.setPen(pen)
        painter.drawPath(self.path())

    def shape(self):
        # großzügige Klickfläche
        from PySide6.QtGui import QPainterPathStroker
        st = QPainterPathStroker()
        st.setWidth(8 / max(0.05, self.scene().views()[0].transform().m11()) if self.scene()
                    and self.scene().views() else 8)
        return st.createStroke(self.path())


class TextEntityItem(QGraphicsSimpleTextItem):
    def __init__(self, entity: Text):
        super().__init__(entity.text)
        self.entity = entity
        rgb = getattr(entity, "color", None) or layer_color(entity.layer)[1]
        self.setBrush(QBrush(QColor(*rgb)))
        f = QFont("Sans Serif")
        f.setPixelSize(max(4, int(entity.height / 0.72)))
        self.setFont(f)
        h = self.boundingRect().height()
        # Einfügepunkt = links unten (Grundlinie); Text liegt darüber
        t = QTransform()
        t.translate(*entity.position)
        t.rotate(-entity.angle)
        t.translate(0, -h * 0.85)
        self.setTransform(t)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(3)

    def paint(self, painter, option, widget=None):
        if self.isSelected():
            painter.fillRect(self.boundingRect(), QColor(255, 120, 0, 90))
        super().paint(painter, option, widget)


class Canvas(QGraphicsView):
    cropSelected = Signal(int, int, int, int)
    measured = Signal(float, float, float, float)
    zoomChanged = Signal(float)
    mouseMoved = Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setBackgroundBrush(QColor(70, 72, 78))
        self.setMouseTracking(True)
        self.raster_item: QGraphicsPixmapItem | None = None
        self.bg_item: QGraphicsRectItem | None = None
        self.items_by_layer: dict[str, list] = {}
        self.line_width = 1.6
        self._crop_mode = False
        self._crop_origin = None
        self._rubber = QRubberBand(QRubberBand.Rectangle, self.viewport())
        self._panning = False
        self._pan_start = None
        self._measure_pts = None
        self._measure_item = None

    # ---- Inhalte ----
    def set_raster(self, img: np.ndarray | None, keep_view=False):
        sc = self.scene()
        if self.raster_item is not None:
            sc.removeItem(self.raster_item)
            self.raster_item = None
        if self.bg_item is not None:
            sc.removeItem(self.bg_item)
            self.bg_item = None
        if img is None:
            return
        h, w = img.shape
        self.bg_item = sc.addRect(0, 0, w, h, QPen(Qt.NoPen), QBrush(Qt.white))
        self.bg_item.setZValue(-1)
        self.raster_item = sc.addPixmap(gray_to_qpixmap(img))
        self.raster_item.setZValue(0)
        sc.setSceneRect(QRectF(-w * 0.05, -h * 0.05, w * 1.1, h * 1.1))
        if not keep_view:
            self.fit()

    def set_raster_opacity(self, op: float):
        if self.raster_item:
            self.raster_item.setOpacity(op)

    def set_entities(self, entities):
        self.clear_entities()
        for e in entities:
            it = TextEntityItem(e) if isinstance(e, Text) else EntityItem(e, self.line_width)
            self.scene().addItem(it)
            self.items_by_layer.setdefault(e.layer, []).append(it)

    def clear_entities(self):
        for items in self.items_by_layer.values():
            for it in items:
                if it.scene():
                    self.scene().removeItem(it)
        self.items_by_layer = {}

    def set_layer_visible(self, layer: str, vis: bool):
        for it in self.items_by_layer.get(layer, []):
            it.setVisible(vis)

    def set_vectors_visible(self, vis: bool):
        for items in self.items_by_layer.values():
            for it in items:
                it.setVisible(vis)

    def selected_entities(self):
        return [it.entity for it in self.scene().selectedItems() if hasattr(it, "entity")]

    def remove_entity_items(self, ents):
        ids = {id(e) for e in ents}
        for layer, items in self.items_by_layer.items():
            keep = []
            for it in items:
                if id(it.entity) in ids:
                    self.scene().removeItem(it)
                else:
                    keep.append(it)
            self.items_by_layer[layer] = keep

    # ---- Zoom / Navigation ----
    def fit(self):
        if self.raster_item:
            self.fitInView(self.raster_item.boundingRect(), Qt.KeepAspectRatio)
            self.zoomChanged.emit(self.transform().m11())

    def zoom(self, factor: float):
        cur = self.transform().m11()
        if 0.01 < cur * factor < 64:
            self.scale(factor, factor)
            self.zoomChanged.emit(self.transform().m11())

    def zoom_100(self):
        self.setTransform(QTransform())
        self.zoomChanged.emit(1.0)

    def wheelEvent(self, ev):
        self.zoom(1.25 if ev.angleDelta().y() > 0 else 0.8)

    def start_crop(self):
        self._crop_mode = True
        self.setDragMode(QGraphicsView.NoDrag)
        self.viewport().setCursor(Qt.CrossCursor)

    def cancel_crop(self):
        self._crop_mode = False
        self._rubber.hide()
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.viewport().unsetCursor()

    def start_measure(self):
        self._measure_pts = []
        self.setDragMode(QGraphicsView.NoDrag)
        self.viewport().setCursor(Qt.CrossCursor)

    def _end_measure(self):
        self._measure_pts = None
        if self._measure_item is not None:
            self.scene().removeItem(self._measure_item)
            self._measure_item = None
        self.setDragMode(QGraphicsView.RubberBandDrag)
        self.viewport().unsetCursor()

    def mousePressEvent(self, ev):
        if self._measure_pts is not None and ev.button() == Qt.LeftButton:
            p = self.mapToScene(ev.position().toPoint())
            self._measure_pts.append(p)
            if len(self._measure_pts) == 1:
                pen = QPen(QColor(0, 170, 255), 2)
                pen.setCosmetic(True)
                self._measure_item = self.scene().addLine(p.x(), p.y(), p.x(), p.y(), pen)
                self._measure_item.setZValue(10)
            else:
                a, b = self._measure_pts
                self._end_measure()
                self.measured.emit(a.x(), a.y(), b.x(), b.y())
            return
        if ev.button() == Qt.RightButton and self._measure_pts is not None:
            self._end_measure()
            return
        if ev.button() == Qt.MiddleButton or (ev.button() == Qt.LeftButton and
                                               ev.modifiers() & Qt.ShiftModifier and not self._crop_mode):
            self._panning = True
            self._pan_start = ev.position()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            return
        if self._crop_mode and ev.button() == Qt.LeftButton:
            self._crop_origin = ev.position().toPoint()
            self._rubber.setGeometry(self._crop_origin.x(), self._crop_origin.y(), 0, 0)
            self._rubber.show()
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        sp = self.mapToScene(ev.position().toPoint())
        self.mouseMoved.emit(sp.x(), sp.y())
        if self._measure_item is not None and self._measure_pts:
            a = self._measure_pts[0]
            self._measure_item.setLine(a.x(), a.y(), sp.x(), sp.y())
        if self._panning:
            d = ev.position() - self._pan_start
            self._pan_start = ev.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(d.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(d.y()))
            return
        if self._crop_mode and self._crop_origin is not None:
            from PySide6.QtCore import QRect
            self._rubber.setGeometry(QRect(self._crop_origin, ev.position().toPoint()).normalized())
            return
        super().mouseMoveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._panning:
            self._panning = False
            self.viewport().unsetCursor()
            return
        if self._crop_mode and self._crop_origin is not None:
            r = self._rubber.geometry()
            self._crop_origin = None
            a = self.mapToScene(r.topLeft())
            b = self.mapToScene(r.bottomRight())
            self.cancel_crop()
            x, y = int(max(0, a.x())), int(max(0, a.y()))
            w, h = int(b.x()) - x, int(b.y()) - y
            if w > 5 and h > 5:
                self.cropSelected.emit(x, y, w, h)
            return
        super().mouseReleaseEvent(ev)
