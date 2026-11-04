"""Zeichenfläche: Rasterbild + Vektor-Overlay, Zoom, Auswahl und Werkzeuge.

Werkzeuge (set_tool):
  select  – Objekte wählen; bei genau einem Objekt erscheinen ziehbare Knoten
  erase   – Raster-Radierer (malt Weiß)
  pen     – Raster-Stift (malt Schwarz, z. B. Lücken in Linien schließen)
  region  – Bereich aufziehen (eigener Modus oder „ignorieren“)
  line, polyline, rect, circle, arc – neue Vektoren zeichnen (mit Fangpunkten)
  trim, extend – Stutzen und Dehnen
"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import (QBrush, QColor, QFont, QImage, QPainter, QPainterPath,
                           QPainterPathStroker, QPen, QPixmap, QTransform)
from PySide6.QtWidgets import (QGraphicsEllipseItem, QGraphicsItem, QGraphicsPathItem,
                               QGraphicsPixmapItem, QGraphicsRectItem,
                               QGraphicsScene, QGraphicsSimpleTextItem,
                               QGraphicsView, QRubberBand)

import math

from ..core import cad
from ..core.edit import entity_points, move_point
from ..core.model import Arc, Circle, Insert, Line, Polyline, Text, layer_color

TOOL_SELECT, TOOL_ERASE, TOOL_PEN, TOOL_REGION = "select", "erase", "pen", "region"
TOOL_SYMBOL = "symbol"
TOOL_LINE, TOOL_POLYLINE, TOOL_RECT = "line", "polyline", "rect"
TOOL_CIRCLE, TOOL_ARC, TOOL_TRIM, TOOL_EXTEND = "circle", "arc", "trim", "extend"
DRAW_TOOLS = (TOOL_LINE, TOOL_POLYLINE, TOOL_RECT, TOOL_CIRCLE, TOOL_ARC)
PICK_TOOLS = (TOOL_TRIM, TOOL_EXTEND)
SNAP_COLOR = QColor(255, 196, 0)


def snap_marker_path(kind: str, p, r: float) -> QPainterPath:
    """Fangsymbol wie in CAD üblich: □ Endpunkt, △ Mitte, ○ Zentrum, ✕ Schnitt, ⊾ Lot, ⧗ nächster."""
    x, y = p
    path = QPainterPath()
    if kind == cad.SNAP_END:
        path.addRect(QRectF(x - r, y - r, 2 * r, 2 * r))
    elif kind == cad.SNAP_MID:
        path.moveTo(x, y - r)
        path.lineTo(x + r, y + r)
        path.lineTo(x - r, y + r)
        path.closeSubpath()
    elif kind == cad.SNAP_CENTER:
        path.addEllipse(QPointF(x, y), r, r)
    elif kind == cad.SNAP_INTERSECTION:
        path.moveTo(x - r, y - r)
        path.lineTo(x + r, y + r)
        path.moveTo(x - r, y + r)
        path.lineTo(x + r, y - r)
    elif kind == cad.SNAP_PERP:
        path.moveTo(x - r, y - r)
        path.lineTo(x - r, y + r)
        path.lineTo(x + r, y + r)
        path.moveTo(x - r, y)
        path.lineTo(x, y)
        path.lineTo(x, y + r)
    else:
        path.moveTo(x - r, y - r)
        path.lineTo(x + r, y - r)
        path.lineTo(x - r, y + r)
        path.lineTo(x + r, y + r)
        path.closeSubpath()
    return path

REGION_COLORS = {"ignorieren": (110, 110, 110), "mittellinie": (40, 120, 255),
                 "umriss": (190, 40, 190), "nur_text": (230, 150, 0)}


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
        lw = getattr(entity, "lineweight", 0.0) or 0.0
        if lw >= 0.7 or entity.layer == "DICKE_LINIEN":
            width *= 2.0      # dicke Linien auch am Bildschirm hervorheben
        elif lw >= 0.45:
            width *= 1.4
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

    def refresh(self):
        self.prepareGeometryChange()
        self.setPath(entity_path(self.entity))

    def paint(self, painter, option, widget=None):
        pen = QPen(self.base_pen)
        if self.isSelected():
            pen.setColor(QColor(255, 120, 0))
            pen.setWidthF(self.base_pen.widthF() + 2)
        painter.setPen(pen)
        painter.drawPath(self.path())

    def shape(self):
        # großzügige Klickfläche
        st = QPainterPathStroker()
        st.setWidth(8 / max(0.05, self.scene().views()[0].transform().m11()) if self.scene()
                    and self.scene().views() else 8)
        return st.createStroke(self.path())


class InsertItem(QGraphicsPathItem):
    """Eingefügtes Symbol: alle Block-Objekte als ein auswählbares Element."""

    def __init__(self, entity: Insert, drawing_provider, width: float):
        super().__init__()
        self.entity = entity
        self.drawing_provider = drawing_provider
        pen = QPen(QColor(*(entity.color or layer_color(entity.layer)[1])), width * 1.2)
        pen.setCosmetic(True)
        self.base_pen = pen
        self.setPen(pen)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(2)
        self.refresh()
        self.setToolTip(f"Symbol: {entity.name}")

    def refresh(self):
        from ..core.symbols import explode_insert
        d = self.drawing_provider()
        path = QPainterPath()
        if d is not None:
            for e in explode_insert(d, self.entity):
                if isinstance(e, Text):
                    f = QFont("Sans Serif")
                    f.setPixelSize(max(4, int(e.height / 0.72)))
                    path.addText(QPointF(*e.position), f, e.text)
                else:
                    path.addPath(entity_path(e))
        self.prepareGeometryChange()
        self.setPath(path)

    def paint(self, painter, option, widget=None):
        pen = QPen(self.base_pen)
        if self.isSelected():
            pen.setColor(QColor(255, 120, 0))
            pen.setWidthF(self.base_pen.widthF() + 2)
        painter.setPen(pen)
        painter.drawPath(self.path())

    def shape(self):
        p = QPainterPath()
        p.addRect(self.path().boundingRect().adjusted(-3, -3, 3, 3))
        return p


class TextEntityItem(QGraphicsSimpleTextItem):
    def __init__(self, entity: Text):
        super().__init__(entity.text)
        self.entity = entity
        rgb = getattr(entity, "color", None) or layer_color(entity.layer)[1]
        self.setBrush(QBrush(QColor(*rgb)))
        f = QFont("Sans Serif")
        f.setPixelSize(max(4, int(entity.height / 0.72)))
        self.setFont(f)
        self.refresh()
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setZValue(3)

    def refresh(self):
        self.setText(self.entity.text)
        h = self.boundingRect().height()
        # Einfügepunkt = links unten (Grundlinie); Text liegt darüber
        t = QTransform()
        t.translate(*self.entity.position)
        t.rotate(-self.entity.angle)
        t.translate(0, -h * 0.85)
        self.setTransform(t)

    def paint(self, painter, option, widget=None):
        if self.isSelected():
            painter.fillRect(self.boundingRect(), QColor(255, 120, 0, 90))
        super().paint(painter, option, widget)


class NodeHandle(QGraphicsRectItem):
    """Ziehbarer Knoten eines Objekts (konstante Bildschirmgröße)."""

    def __init__(self, canvas: "Canvas", entity, index: int, pos):
        super().__init__(-5, -5, 10, 10)
        self.canvas, self.entity, self.index = canvas, entity, index
        self._dragging = False
        self.setPos(QPointF(*pos))
        self.setBrush(QBrush(QColor(255, 255, 255)))
        pen = QPen(QColor(232, 96, 28), 2)
        pen.setCosmetic(True)
        self.setPen(pen)
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIgnoresTransformations
                      | QGraphicsItem.ItemSendsGeometryChanges)
        self.setZValue(30)
        self.setCursor(Qt.SizeAllCursor)
        self.setToolTip("Knoten ziehen (Strg+Z macht es rückgängig)")

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionHasChanged and self._dragging:
            self.canvas._node_moved(self, value)
        return super().itemChange(change, value)

    def mousePressEvent(self, ev):
        self._dragging = True
        self.canvas.nodeEditStarted.emit()
        super().mousePressEvent(ev)

    def mouseReleaseEvent(self, ev):
        super().mouseReleaseEvent(ev)
        self._dragging = False
        self.canvas.nodeEditFinished.emit()


class RegionItem(QGraphicsRectItem):
    def __init__(self, index: int, region, label: str):
        super().__init__(region.x, region.y, region.w, region.h)
        self.index = index
        rgb = REGION_COLORS.get(region.mode, (100, 100, 100))
        pen = QPen(QColor(*rgb), 2, Qt.DashLine)
        pen.setCosmetic(True)
        self.setPen(pen)
        c = QColor(*rgb)
        c.setAlpha(45 if region.mode != "ignorieren" else 80)
        self.setBrush(QBrush(c))
        self.setZValue(1)
        t = QGraphicsSimpleTextItem(label, self)
        t.setBrush(QBrush(QColor(*rgb).darker(140)))
        t.setFlag(QGraphicsItem.ItemIgnoresTransformations, True)
        t.setPos(region.x + 2, region.y + 2)
        self.setToolTip(f"Bereich: {label} – Rechtsklick zum Ändern/Entfernen")


class Canvas(QGraphicsView):
    cropSelected = Signal(int, int, int, int)
    regionDrawn = Signal(int, int, int, int)
    symbolDrawn = Signal(int, int, int, int)
    regionMenuRequested = Signal(int, object)     # Index, globale Position
    brushStroke = Signal(list, str, int)          # Punkte, Werkzeug, Größe (px)
    measured = Signal(float, float, float, float)
    zoomChanged = Signal(float)
    mouseMoved = Signal(float, float)
    nodeEditStarted = Signal()
    nodeEditFinished = Signal()
    toolCancelled = Signal()
    entitiesDrawn = Signal(list)                  # neue Objekte (Bildpixel)
    trimRequested = Signal(object, float, float)  # Objekt, Klickpunkt
    extendRequested = Signal(object, float, float)
    drawInfo = Signal(str)

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
        self.item_by_id: dict[int, QGraphicsItem] = {}
        self.line_width = 1.6
        self.tool = TOOL_SELECT
        self.brush_size = 12
        self.node_connected = True
        self.entities_provider = lambda: []
        self.drawing_provider = lambda: None
        self._rect_purpose = None          # "crop" | "region"
        self._crop_origin = None
        self._rubber = QRubberBand(QRubberBand.Rectangle, self.viewport())
        self._panning = False
        self._pan_start = None
        self._measure_pts = None
        self._measure_item = None
        self._stroke = None
        self._stroke_item = None
        self._brush_cursor = None
        self.handles: list[NodeHandle] = []
        self.region_items: list[RegionItem] = []
        self.marker_items: list = []
        # Zeichnen
        self.snap_enabled = True
        self.snap_modes = set(cad.SNAP_LABELS)
        self.ortho_enabled = False
        self.ortho_angle = 0.0      # Schräglage des Scans (Grad, Bild) – Ortho folgt ihr
        self.mm_per_px_provider = lambda: 1.0
        self._snap_index = None
        self._draw_pts: list = []
        self._draw_cur = None
        self._draw_preview = None
        self._snap_item = None
        self._snap_label = None
        self._hover_item = None
        self._typed = ""
        self.scene().selectionChanged.connect(self.refresh_handles)

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

    def update_raster(self, img: np.ndarray):
        """Nur die Pixel austauschen (Ansicht, Deckkraft und Vektoren bleiben)."""
        if self.raster_item is None or img.shape[:2] != (int(self.raster_item.pixmap().height()),
                                                         int(self.raster_item.pixmap().width())):
            op = self.raster_item.opacity() if self.raster_item else 1.0
            self.set_raster(img, keep_view=True)
            self.set_raster_opacity(op)
        else:
            self.raster_item.setPixmap(gray_to_qpixmap(img))

    def set_raster_opacity(self, op: float):
        if self.raster_item:
            self.raster_item.setOpacity(op)

    def set_entities(self, entities):
        self._snap_index = None
        self.clear_entities()
        for e in entities:
            if isinstance(e, Text):
                it = TextEntityItem(e)
            elif isinstance(e, Insert):
                it = InsertItem(e, self.drawing_provider, self.line_width)
            else:
                it = EntityItem(e, self.line_width)
            self.scene().addItem(it)
            self.items_by_layer.setdefault(e.layer, []).append(it)
            self.item_by_id[id(e)] = it

    def clear_entities(self):
        self.clear_handles()
        for items in self.items_by_layer.values():
            for it in items:
                if it.scene():
                    self.scene().removeItem(it)
        self.items_by_layer = {}
        self.item_by_id = {}

    def add_entities(self, ents):
        """Neue Objekte ergänzen, ohne die ganze Szene neu aufzubauen."""
        self._snap_index = None
        for e in ents:
            if isinstance(e, Text):
                it = TextEntityItem(e)
            elif isinstance(e, Insert):
                it = InsertItem(e, self.drawing_provider, self.line_width)
            else:
                it = EntityItem(e, self.line_width)
            self.scene().addItem(it)
            self.items_by_layer.setdefault(e.layer, []).append(it)
            self.item_by_id[id(e)] = it

    def refresh_entities(self, ents):
        self._snap_index = None
        for e in ents:
            it = self.item_by_id.get(id(e))
            if it is not None:
                it.refresh()

    def set_layer_visible(self, layer: str, vis: bool):
        for it in self.items_by_layer.get(layer, []):
            it.setVisible(vis)

    def set_vectors_visible(self, vis: bool):
        for items in self.items_by_layer.values():
            for it in items:
                it.setVisible(vis)

    def selected_entities(self):
        return [it.entity for it in self.scene().selectedItems() if hasattr(it, "entity")]

    def select_entities(self, ents):
        ids = {id(e) for e in ents}
        self.scene().clearSelection()
        for e_id in ids:
            it = self.item_by_id.get(e_id)
            if it is not None:
                it.setSelected(True)

    def remove_entity_items(self, ents):
        self._snap_index = None
        self.clear_handles()
        ids = {id(e) for e in ents}
        for layer, items in self.items_by_layer.items():
            keep = []
            for it in items:
                if id(it.entity) in ids:
                    self.scene().removeItem(it)
                    self.item_by_id.pop(id(it.entity), None)
                else:
                    keep.append(it)
            self.items_by_layer[layer] = keep

    # ---- Knoten ----
    def clear_handles(self):
        for h in self.handles:
            if h.scene():
                self.scene().removeItem(h)
        self.handles = []

    def refresh_handles(self):
        if any(h._dragging for h in self.handles):
            return
        self.clear_handles()
        if self.tool != TOOL_SELECT:
            return
        sel = self.selected_entities()
        if len(sel) != 1 or isinstance(sel[0], Text):
            return
        e = sel[0]
        pts = entity_points(e)
        if not pts or len(pts) > 400:
            return
        for i, p in enumerate(pts):
            h = NodeHandle(self, e, i, p)
            self.scene().addItem(h)
            self.handles.append(h)

    def _node_moved(self, handle: NodeHandle, pos):
        changed = move_point(self.entities_provider(), handle.entity, handle.index,
                             (pos.x(), pos.y()), self.node_connected)
        self.refresh_entities(changed)
        pts = entity_points(handle.entity)
        for h in self.handles:
            if h is not handle and h.index < len(pts):
                h.setPos(QPointF(*pts[h.index]))

    # ---- Problemstellen ----
    def set_markers(self, problems):
        for it in self.marker_items:
            if it.scene():
                self.scene().removeItem(it)
        self.marker_items = []
        for i, p in enumerate(problems or []):
            col = QColor(220, 40, 40) if p.kind == "fehlt" else QColor(150, 60, 200)
            pen = QPen(col, 2, Qt.DashLine)
            pen.setCosmetic(True)
            pad = 6
            it = self.scene().addRect(QRectF(p.x - pad, p.y - pad, p.w + 2 * pad, p.h + 2 * pad),
                                      pen, QBrush(QColor(col.red(), col.green(), col.blue(), 28)))
            it.setZValue(25)
            it.setToolTip(f"Problemstelle {i + 1}: "
                          + ("Tinte ohne Vektor – fehlt im Ergebnis" if p.kind == "fehlt"
                             else "Vektor ohne Tinte – vermutlich überflüssig")
                          + f" ({p.size} px)")
            self.marker_items.append(it)

    def zoom_to_rect(self, x, y, w, h, margin: float = 4.0):
        cx, cy = x + w / 2, y + h / 2
        size = max(w, h) * margin + 60
        self.fitInView(QRectF(cx - size / 2, cy - size / 2, size, size), Qt.KeepAspectRatio)
        self.zoomChanged.emit(self.transform().m11())

    # ---- Bereiche ----
    def set_regions(self, regions, labels):
        for it in self.region_items:
            if it.scene():
                self.scene().removeItem(it)
        self.region_items = []
        for i, r in enumerate(regions):
            it = RegionItem(i, r, labels.get(r.mode, r.mode))
            self.scene().addItem(it)
            self.region_items.append(it)

    def contextMenuEvent(self, ev):
        if self.tool in DRAW_TOOLS + PICK_TOOLS:
            return
        sp = self.mapToScene(ev.pos())
        for it in reversed(self.region_items):
            if it.isVisible() and it.rect().contains(sp):
                self.regionMenuRequested.emit(it.index, ev.globalPos())
                return
        super().contextMenuEvent(ev)

    # ---- Werkzeuge ----
    def set_tool(self, tool: str, size: int | None = None):
        if size:
            self.brush_size = int(size)
        if tool != self.tool or tool not in DRAW_TOOLS:
            self.cancel_drawing()
        self._clear_hover()
        self.tool = tool
        self._rect_purpose = {TOOL_REGION: "region", TOOL_SYMBOL: "symbol"}.get(tool)
        self._remove_brush_cursor()
        if tool == TOOL_SELECT:
            self.setDragMode(QGraphicsView.RubberBandDrag)
            self.viewport().unsetCursor()
            self.refresh_handles()
        else:
            self.clear_handles()
            self.setDragMode(QGraphicsView.NoDrag)
            if tool in DRAW_TOOLS + PICK_TOOLS:
                self.scene().clearSelection()
                self.viewport().setCursor(Qt.CrossCursor)
                self.setFocus()
            else:
                self.viewport().setCursor(Qt.CrossCursor if tool in (TOOL_REGION, TOOL_SYMBOL)
                                          else Qt.BlankCursor)

    def set_brush_size(self, size: int):
        self.brush_size = int(size)
        if self._brush_cursor is not None:
            c = self._brush_cursor.rect().center()
            self._place_brush_cursor(c)

    def _place_brush_cursor(self, sp):
        r = self.brush_size / 2
        if self._brush_cursor is None:
            self._brush_cursor = QGraphicsEllipseItem()
            pen = QPen(QColor(232, 96, 28), 1.5)
            pen.setCosmetic(True)
            self._brush_cursor.setPen(pen)
            self._brush_cursor.setZValue(40)
            self.scene().addItem(self._brush_cursor)
        self._brush_cursor.setRect(QRectF(sp.x() - r, sp.y() - r, 2 * r, 2 * r))

    def _remove_brush_cursor(self):
        if self._brush_cursor is not None and self._brush_cursor.scene():
            self.scene().removeItem(self._brush_cursor)
        self._brush_cursor = None

    def clear_stroke(self):
        if self._stroke_item is not None and self._stroke_item.scene():
            self.scene().removeItem(self._stroke_item)
        self._stroke_item = None

    def event(self, ev):
        # Esc/Enter/Ziffern beim Zeichnen gehören der Zeichenfläche, nicht den Fenster-Kürzeln
        from PySide6.QtCore import QEvent
        if ev.type() == QEvent.ShortcutOverride and self.tool in DRAW_TOOLS and self._draw_pts:
            if ev.key() in (Qt.Key_Escape, Qt.Key_Return, Qt.Key_Enter, Qt.Key_Backspace) or \
                    (ev.text() and (ev.text().isdigit() or ev.text() in ".,;")):
                ev.accept()
                return True
        return super().event(ev)

    def keyPressEvent(self, ev):
        if self.tool in DRAW_TOOLS and self._draw_key(ev):
            return
        if ev.key() == Qt.Key_Escape and self.tool in DRAW_TOOLS and self._draw_pts:
            self.cancel_drawing()
            self.drawInfo.emit("Abgebrochen – nächster Startpunkt.")
            return
        if ev.key() == Qt.Key_Escape:
            if self._measure_pts is not None:
                self._end_measure()
            if self._rect_purpose == "crop":
                self.cancel_crop()
            self.toolCancelled.emit()
            return
        super().keyPressEvent(ev)

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
        self._rect_purpose = "crop"
        self.clear_handles()
        self.setDragMode(QGraphicsView.NoDrag)
        self.viewport().setCursor(Qt.CrossCursor)

    def cancel_crop(self):
        self._rubber.hide()
        self._crop_origin = None
        if self.tool in (TOOL_REGION, TOOL_SYMBOL):
            self._rect_purpose = "region" if self.tool == TOOL_REGION else "symbol"
            return
        self._rect_purpose = None
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
        self.set_tool(self.tool)

    def mousePressEvent(self, ev):
        sp = self.mapToScene(ev.position().toPoint())
        if self._measure_pts is not None and ev.button() == Qt.LeftButton:
            self._measure_pts.append(sp)
            if len(self._measure_pts) == 1:
                pen = QPen(QColor(0, 170, 255), 2)
                pen.setCosmetic(True)
                self._measure_item = self.scene().addLine(sp.x(), sp.y(), sp.x(), sp.y(), pen)
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
                                               ev.modifiers() & Qt.ShiftModifier and
                                               not self._rect_purpose and
                                               self.tool not in DRAW_TOOLS):
            self._panning = True
            self._pan_start = ev.position()
            self.viewport().setCursor(Qt.ClosedHandCursor)
            return
        if self._rect_purpose and ev.button() == Qt.LeftButton:
            self._crop_origin = ev.position().toPoint()
            self._rubber.setGeometry(self._crop_origin.x(), self._crop_origin.y(), 0, 0)
            self._rubber.show()
            return
        if self.tool in DRAW_TOOLS:
            self.setFocus()
            if ev.button() == Qt.LeftButton:
                p = self._resolve_point(sp, ev.modifiers())
                self._draw_click(p)
            elif ev.button() == Qt.RightButton:
                self._draw_finish()
            return
        if self.tool in PICK_TOOLS:
            if ev.button() == Qt.LeftButton:
                p = (sp.x(), sp.y())
                e = cad.pick(self._snap_candidates(p, self._pick_radius()), p, self._pick_radius())
                if e is not None:
                    (self.trimRequested if self.tool == TOOL_TRIM
                     else self.extendRequested).emit(e, p[0], p[1])
                    self._clear_hover()
                else:
                    self.drawInfo.emit("Dort ist kein Objekt – bitte direkt auf eine Linie klicken.")
            return
        if self.tool in (TOOL_ERASE, TOOL_PEN) and ev.button() == Qt.LeftButton:
            self._stroke = [(sp.x(), sp.y())]
            self.clear_stroke()
            self._stroke_item = QGraphicsPathItem()
            col = QColor(255, 255, 255, 230) if self.tool == TOOL_ERASE else QColor(0, 0, 0, 230)
            pen = QPen(col, self.brush_size, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            self._stroke_item.setPen(pen)
            self._stroke_item.setZValue(5)
            path = QPainterPath(sp)
            path.lineTo(sp + QPointF(0.01, 0.01))
            self._stroke_item.setPath(path)
            self.scene().addItem(self._stroke_item)
            return
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        sp = self.mapToScene(ev.position().toPoint())
        self.mouseMoved.emit(sp.x(), sp.y())
        if self.tool in (TOOL_ERASE, TOOL_PEN):
            self._place_brush_cursor(sp)
        if self.tool in DRAW_TOOLS and not self._panning:
            self._draw_move(self._resolve_point(sp, ev.modifiers()))
        if self.tool in PICK_TOOLS and not self._panning:
            self._update_hover(sp)
        if self._measure_item is not None and self._measure_pts:
            a = self._measure_pts[0]
            self._measure_item.setLine(a.x(), a.y(), sp.x(), sp.y())
        if self._panning:
            d = ev.position() - self._pan_start
            self._pan_start = ev.position()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(d.x()))
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - int(d.y()))
            return
        if self._rect_purpose and self._crop_origin is not None:
            self._rubber.setGeometry(QRect(self._crop_origin, ev.position().toPoint()).normalized())
            return
        if self._stroke is not None:
            self._stroke.append((sp.x(), sp.y()))
            path = self._stroke_item.path()
            path.lineTo(sp)
            self._stroke_item.setPath(path)
            return
        super().mouseMoveEvent(ev)

    def leaveEvent(self, ev):
        self._remove_brush_cursor()
        super().leaveEvent(ev)

    def mouseReleaseEvent(self, ev):
        if self._panning:
            self._panning = False
            self.set_tool(self.tool) if self.tool != TOOL_SELECT else self.viewport().unsetCursor()
            return
        if self._stroke is not None and ev.button() == Qt.LeftButton:
            pts, self._stroke = self._stroke, None
            self.brushStroke.emit(pts, self.tool, int(self.brush_size))
            return
        if self._rect_purpose and self._crop_origin is not None:
            purpose = self._rect_purpose
            r = self._rubber.geometry()
            a = self.mapToScene(r.topLeft())
            b = self.mapToScene(r.bottomRight())
            self.cancel_crop()
            x, y = int(max(0, a.x())), int(max(0, a.y()))
            w, h = int(b.x()) - x, int(b.y()) - y
            if w > 5 and h > 5:
                {"crop": self.cropSelected, "region": self.regionDrawn,
                 "symbol": self.symbolDrawn}[purpose].emit(x, y, w, h)
            return
        super().mouseReleaseEvent(ev)

    # ================================================================ Zeichnen
    def _snap_candidates(self, p, radius):
        if self._snap_index is None:
            self._snap_index = cad.SnapIndex(self.entities_provider())
        return self._snap_index.query(p, radius)

    def _px(self, screen_px: float) -> float:
        """Bildschirmpixel → Szenenpixel (zoomunabhängige Größen)."""
        return screen_px / max(1e-6, self.transform().m11())

    def _pick_radius(self):
        return self._px(8)

    def _resolve_point(self, sp, modifiers):
        """Mausposition → Punkt nach Fang bzw. Ortho; zeigt den Fangmarker."""
        raw = (sp.x(), sp.y())
        last = self._draw_pts[-1] if self._draw_pts else None
        if self.tool == TOOL_ARC and len(self._draw_pts) == 2:
            last = None
        snap = None
        if self.snap_enabled and self.snap_modes:
            r = self._px(12)
            snap = cad.find_snap(self._snap_candidates(raw, r), raw, r, self.snap_modes, last)
        self._show_snap(snap)
        if snap is not None:
            return snap.point
        ortho = self.ortho_enabled != bool(modifiers & Qt.ShiftModifier)
        if ortho and last is not None and self.tool in (TOOL_LINE, TOOL_POLYLINE):
            return cad.ortho(last, raw, self.ortho_angle)
        return raw

    def _show_snap(self, snap):
        if snap is None:
            for it in (self._snap_item, self._snap_label):
                if it is not None and it.scene():
                    self.scene().removeItem(it)
            self._snap_item = self._snap_label = None
            return
        if self._snap_item is None:
            pen = QPen(SNAP_COLOR, 2)
            pen.setCosmetic(True)
            self._snap_item = QGraphicsPathItem()
            self._snap_item.setPen(pen)
            self._snap_item.setZValue(60)
            self.scene().addItem(self._snap_item)
            self._snap_label = QGraphicsSimpleTextItem()
            self._snap_label.setBrush(QBrush(SNAP_COLOR))
            self._snap_label.setFlag(QGraphicsItem.ItemIgnoresTransformations)
            self._snap_label.setZValue(60)
            self.scene().addItem(self._snap_label)
        self._snap_item.setPath(snap_marker_path(snap.kind, snap.point, self._px(6)))
        self._snap_label.setText(cad.SNAP_LABELS.get(snap.kind, ""))
        self._snap_label.setPos(snap.point[0] + self._px(10), snap.point[1] + self._px(8))

    def _ensure_preview(self):
        if self._draw_preview is None:
            pen = QPen(QColor(0, 200, 255), 1.6, Qt.DashLine)
            pen.setCosmetic(True)
            self._draw_preview = QGraphicsPathItem()
            self._draw_preview.setPen(pen)
            self._draw_preview.setZValue(50)
            self.scene().addItem(self._draw_preview)
        return self._draw_preview

    def _shape_entities(self, pts, cur):
        """Was entstünde mit den gesetzten Punkten plus cur (für Vorschau und Abschluss)."""
        t = self.tool
        allp = list(pts) + ([cur] if cur is not None else [])
        if t == TOOL_LINE and len(allp) >= 2:
            return [Line(allp[0], allp[1])]
        if t == TOOL_POLYLINE and len(allp) >= 2:
            return [Polyline(allp, False)]
        if t == TOOL_RECT and len(allp) >= 2:
            (x0, y0), (x1, y1) = allp[0], allp[1]
            return [Polyline([(x0, y0), (x1, y0), (x1, y1), (x0, y1)], True)]
        if t == TOOL_CIRCLE and len(allp) >= 2:
            r = math.dist(allp[0], allp[1])
            return [Circle(allp[0], r)] if r > 1e-6 else []
        if t == TOOL_ARC:
            if len(allp) == 2:
                return [Line(allp[0], allp[1])]
            if len(allp) >= 3:
                a = cad.arc_from_3_points(allp[0], allp[2], allp[1])
                return [a] if a else [Line(allp[0], allp[1])]
        return []

    def _draw_move(self, p):
        self._draw_cur = p
        if not self._draw_pts:
            self.drawInfo.emit(self._hint())
            return
        path = QPainterPath()
        for e in self._shape_entities(self._draw_pts, p):
            path.addPath(entity_path(e))
        self._ensure_preview().setPath(path)
        self.drawInfo.emit(self._measure_text(self._draw_pts[-1] if self.tool != TOOL_ARC
                                              else self._draw_pts[0], p))

    def _measure_text(self, a, b):
        k = self.mm_per_px_provider() or 1.0
        d = math.dist(a, b) * k
        ang = math.degrees(math.atan2(-(b[1] - a[1]), b[0] - a[0])) % 360
        if self.tool == TOOL_CIRCLE:
            base = f"Radius {d:.2f} mm  (Ø {2 * d:.2f})"
        elif self.tool == TOOL_RECT:
            base = f"Breite {abs(b[0] - a[0]) * k:.2f} × Höhe {abs(b[1] - a[1]) * k:.2f} mm"
        else:
            base = f"Länge {d:.2f} mm   Winkel {ang:.1f}°"
        typed = f"   Eingabe: {self._typed}▏ (Enter)" if self._typed else ""
        return base + typed

    def _hint(self):
        return {TOOL_LINE: "Linie: Startpunkt klicken.",
                TOOL_POLYLINE: "Polylinie: Startpunkt klicken.",
                TOOL_RECT: "Rechteck: erste Ecke klicken.",
                TOOL_CIRCLE: "Kreis: Mittelpunkt klicken.",
                TOOL_ARC: "Bogen: Startpunkt klicken."}.get(self.tool, "")

    def _draw_click(self, p):
        t = self.tool
        if self._draw_pts and math.dist(p, self._draw_pts[-1]) < 1e-6:
            return
        if t == TOOL_POLYLINE and len(self._draw_pts) >= 2 and \
                math.dist(p, self._draw_pts[0]) < 1e-6:
            self._emit([Polyline(list(self._draw_pts), True)])
            return
        self._draw_pts.append(p)
        n = len(self._draw_pts)
        if t == TOOL_LINE and n == 2:
            self._emit(self._shape_entities(self._draw_pts, None))
            self._draw_pts = [p]                      # weiterzeichnen ab Endpunkt
            self.drawInfo.emit("Linie: nächster Punkt – oder Rechtsklick/Esc zum Beenden.")
        elif t in (TOOL_RECT, TOOL_CIRCLE) and n == 2:
            self._emit(self._shape_entities(self._draw_pts, None))
            self.cancel_drawing()
        elif t == TOOL_ARC and n == 3:
            ents = self._shape_entities(self._draw_pts, None)
            if ents and isinstance(ents[0], Arc):
                self._emit(ents)
                self.cancel_drawing()
            else:
                self._draw_pts.pop()
                self.drawInfo.emit("Die drei Punkte liegen auf einer Geraden – anderen Punkt wählen.")
        elif t == TOOL_ARC and n == 2:
            self.drawInfo.emit("Bogen: Punkt auf dem Bogen klicken.")
        elif t == TOOL_POLYLINE and n >= 2:
            self.drawInfo.emit("Polylinie: weitere Punkte – Rechtsklick/Enter = fertig, "
                               "Klick auf den Startpunkt = schließen.")

    def _draw_finish(self):
        if self.tool == TOOL_POLYLINE and len(self._draw_pts) >= 2:
            self._emit([Polyline(list(self._draw_pts), False)])
        self.cancel_drawing()
        self.drawInfo.emit(self._hint())

    def _emit(self, ents):
        self._typed = ""
        if ents:
            self.entitiesDrawn.emit(ents)

    def cancel_drawing(self):
        self._draw_pts = []
        self._typed = ""
        if self._draw_preview is not None and self._draw_preview.scene():
            self.scene().removeItem(self._draw_preview)
        self._draw_preview = None
        self._show_snap(None)

    def _draw_key(self, ev) -> bool:
        """Längen-/Radiuseingabe per Tastatur. True = Taste verbraucht."""
        txt = ev.text()
        key = ev.key()
        if self._draw_pts and txt and (txt.isdigit() or txt in ".,;") and \
                not ev.modifiers() & (Qt.ControlModifier | Qt.AltModifier):
            self._typed += "." if txt == "," else txt
        elif key == Qt.Key_Backspace and self._typed:
            self._typed = self._typed[:-1]
        elif key in (Qt.Key_Return, Qt.Key_Enter):
            if self._typed:
                self._apply_typed()
            elif self.tool == TOOL_POLYLINE:
                self._draw_finish()
            return True
        else:
            return False
        if self._draw_cur is not None:
            self._draw_move(self._draw_cur)
        return True

    def _apply_typed(self):
        k = self.mm_per_px_provider() or 1.0
        txt, self._typed = self._typed, ""
        try:
            if self.tool == TOOL_RECT and ";" in txt:
                w, h = (float(v) / k for v in txt.split(";")[:2])
                a = self._draw_pts[0]
                cur = self._draw_cur or (a[0] + 1, a[1] + 1)
                sx = 1 if cur[0] >= a[0] else -1
                sy = 1 if cur[1] >= a[1] else -1
                self._draw_click((a[0] + sx * w, a[1] + sy * h))
                return
            val = float(txt.split(";")[0]) / k
        except ValueError:
            self.drawInfo.emit(f"„{txt}“ ist keine Zahl.")
            return
        if val <= 0 or not self._draw_pts:
            return
        base = self._draw_pts[0] if self.tool in (TOOL_CIRCLE, TOOL_ARC, TOOL_RECT) \
            else self._draw_pts[-1]
        toward = self._draw_cur or (base[0] + 1, base[1])
        self._draw_click(cad.point_at_distance(base, toward, val))

    # ---- Stutzen / Dehnen: Objekt unter der Maus hervorheben
    def _update_hover(self, sp):
        p = (sp.x(), sp.y())
        r = self._pick_radius()
        e = cad.pick(self._snap_candidates(p, r), p, r)
        if e is None:
            self._clear_hover()
            self.drawInfo.emit("Stutzen: Teilstück anklicken, das wegfallen soll."
                               if self.tool == TOOL_TRIM else
                               "Dehnen: Linie nahe dem Ende anklicken, das verlängert werden soll.")
            return
        if self._hover_item is None:
            col = QColor(255, 60, 60) if self.tool == TOOL_TRIM else QColor(60, 220, 120)
            pen = QPen(col, 4)
            pen.setCosmetic(True)
            self._hover_item = QGraphicsPathItem()
            self._hover_item.setPen(pen)
            self._hover_item.setZValue(45)
            self.scene().addItem(self._hover_item)
        if self.tool == TOOL_TRIM:
            _removed, added = cad.trim(self._trim_context(e), e, p)
            keep = QPainterPath()
            for a in added:
                keep.addPath(entity_path(a))
            full = entity_path(e)
            # rot = das wegfallende Stück (Differenz annähernd über Strichpfade)
            stroker = QPainterPathStroker()
            stroker.setWidth(self._px(3))
            gone = stroker.createStroke(full).subtracted(stroker.createStroke(keep))
            self._hover_item.setPen(QPen(Qt.NoPen))
            self._hover_item.setBrush(QBrush(QColor(255, 60, 60, 220)))
            self._hover_item.setPath(gone)
        else:
            self._hover_item.setPath(entity_path(e))

    def _trim_context(self, e):
        """Objekte, die e schneiden können (über den Index, nicht die ganze Zeichnung)."""
        b = cad._bbox(e, 1.0)
        if b is None:
            return [e]
        cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
        r = max(b[2] - b[0], b[3] - b[1]) / 2 * 1.5 + 1
        return self._snap_candidates((cx, cy), r)

    def _clear_hover(self):
        if self._hover_item is not None and self._hover_item.scene():
            self.scene().removeItem(self._hover_item)
        self._hover_item = None
