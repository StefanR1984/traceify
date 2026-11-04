"""Symbole erkennen und als CAD-Blöcke einsetzen.

1. Ein Rechteck um ein Beispielsymbol (z. B. Steckdose) definiert die Vorlage:
   – ein Rasterausschnitt (für die Suche) und
   – die Vektoren darin (werden zum Block, bezogen auf die Rechteckmitte).
2. Die Vorlage wird per Kreuzkorrelation im ganzen Plan gesucht, optional um 90/180/270° gedreht.
3. An jeder Fundstelle werden die Einzelvektoren durch EINEN Block-Verweis (Insert) ersetzt.

Eine Bibliothek im Benutzerordner (Symbole/) merkt sich Vorlagen für spätere Zeichnungen.
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
from dataclasses import asdict, dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .model import Arc, Circle, Drawing, Insert, Line, Polyline, Text


# ------------------------------------------------------------------ Transformation
def _rot(p, theta_deg, scale=1.0):
    """Sichtbar gegen den Uhrzeigersinn drehen (Bildkoordinaten, y nach unten)."""
    t = math.radians(theta_deg)
    c, s = math.cos(t), math.sin(t)
    x, y = p[0] * scale, p[1] * scale
    return (x * c + y * s, -x * s + y * c)


def transform_entity(e, rotation: float, scale: float, dx: float, dy: float):
    """Kopie von e: um (0,0) drehen/skalieren, dann verschieben (Bildkoordinaten)."""
    e = copy.copy(e)
    T = lambda p: (lambda q: (q[0] + dx, q[1] + dy))(_rot(p, rotation, scale))  # noqa: E731
    if isinstance(e, Line):
        e.p1, e.p2 = T(e.p1), T(e.p2)
    elif isinstance(e, Circle):
        e.center, e.radius = T(e.center), e.radius * scale
    elif isinstance(e, Arc):
        e.center, e.radius = T(e.center), e.radius * scale
        e.start_angle = (e.start_angle - rotation) % 360
        e.end_angle = (e.end_angle - rotation) % 360
    elif isinstance(e, Polyline):
        e.points = [T(p) for p in e.points]
    elif isinstance(e, Text):
        e.position = T(e.position)
        e.height *= scale
        e.angle = (e.angle + rotation) % 360
    return e


def explode_insert(d: Drawing, ins: Insert) -> list:
    out = []
    for e in d.blocks.get(ins.name, []):
        t = transform_entity(e, ins.rotation, ins.scale, ins.position[0], ins.position[1])
        t.layer = ins.layer          # aufgelöst auf dem Layer des Verweises (Sichtbarkeit, Export)
        if ins.color and not getattr(t, "color", None):
            t.color = ins.color
        out.append(t)
    return out


def _anchor(e):
    if isinstance(e, Line):
        return ((e.p1[0] + e.p2[0]) / 2, (e.p1[1] + e.p2[1]) / 2)
    if isinstance(e, (Circle, Arc)):
        return e.center
    if isinstance(e, Polyline) and e.points:
        xs = [p[0] for p in e.points]
        ys = [p[1] for p in e.points]
        return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    if isinstance(e, (Text, Insert)):
        return e.position
    return (0.0, 0.0)


def _inside(p, x, y, w, h, pad=0.0):
    return x - pad <= p[0] <= x + w + pad and y - pad <= p[1] <= y + h + pad


# ------------------------------------------------------------------ Vorlage
@dataclass
class SymbolTemplate:
    name: str
    image: np.ndarray        # uint8, 255 = Tinte (Ausschnitt)
    entities: list           # Block-Geometrie relativ zur Mitte

    @property
    def size(self):
        return self.image.shape[1], self.image.shape[0]


def make_template(name: str, bw: np.ndarray, d: Drawing, x: int, y: int, w: int,
                  h: int) -> SymbolTemplate:
    """Vorlage aus einem Rechteck: Rasterausschnitt + Vektoren darin (relativ zur Mitte)."""
    H, W = bw.shape[:2]
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(W, int(x + w)), min(H, int(y + h))
    img = (bw[y0:y1, x0:x1] > 0).astype(np.uint8) * 255
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ents = [transform_entity(e, 0, 1, -cx, -cy) for e in d.entities
            if not isinstance(e, Insert) and _inside(_anchor(e), x0, y0, x1 - x0, y1 - y0)]
    for e in ents:
        e.layer = "SYMBOL"   # Layer innerhalb des Blocks
    return SymbolTemplate(name, img, ents)


# ------------------------------------------------------------------ Suche
@dataclass
class Match:
    cx: float
    cy: float
    rotation: float
    score: float
    w: int
    h: int


def find_matches(bw: np.ndarray, tpl: SymbolTemplate, threshold: float = 0.72,
                 rotations=(0, 90, 180, 270), max_matches: int = 2000) -> List[Match]:
    """Sucht die Vorlage im Binärbild (normierte Kreuzkorrelation, leicht weichgezeichnet)."""
    src = cv2.GaussianBlur((bw > 0).astype(np.float32), (5, 5), 0)
    found: List[Match] = []
    for rot in rotations:
        t = np.ascontiguousarray(np.rot90(tpl.image, k=int(rot // 90) % 4)) if rot else tpl.image
        th, tw = t.shape
        if th < 4 or tw < 4 or th > src.shape[0] or tw > src.shape[1]:
            continue
        tf = cv2.GaussianBlur((t > 0).astype(np.float32), (5, 5), 0)
        if tf.std() < 1e-6:
            continue
        res = cv2.matchTemplate(src, tf, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(res >= threshold)
        for yy, xx in zip(ys, xs):
            found.append(Match(xx + tw / 2, yy + th / 2, float(rot), float(res[yy, xx]), tw, th))
    # Nicht-Maximum-Unterdrückung: pro Ort nur den besten Treffer
    found.sort(key=lambda m: -m.score)
    keep: List[Match] = []
    for m in found:
        r = 0.5 * min(m.w, m.h)
        if all(math.hypot(m.cx - k.cx, m.cy - k.cy) > r for k in keep):
            keep.append(m)
            if len(keep) >= max_matches:
                break
    return keep


def apply_matches(d: Drawing, tpl: SymbolTemplate, matches: List[Match]) -> int:
    """Ersetzt Vektoren an den Fundstellen durch Block-Verweise. Gibt die Anzahl zurück."""
    if not matches:
        return 0
    d.blocks[tpl.name] = tpl.entities
    remove = set()
    inserts = []
    for m in matches:
        x, y = m.cx - m.w / 2, m.cy - m.h / 2
        for e in d.entities:
            if isinstance(e, Insert):
                continue
            if _inside(_anchor(e), x, y, m.w, m.h, pad=1.0):
                remove.add(id(e))
        inserts.append(Insert(tpl.name, (float(m.cx), float(m.cy)), m.rotation % 360))
    # vorhandene Verweise an derselben Stelle nicht doppeln
    existing = [e for e in d.entities if isinstance(e, Insert)]
    inserts = [i for i in inserts if all(math.dist(i.position, e.position) > 2 for e in existing)]
    d.entities = [e for e in d.entities if id(e) not in remove] + inserts
    return len(inserts)


# ------------------------------------------------------------------ Bibliothek
def library_dir() -> str:
    from ..installer import user_data_dir
    p = os.path.join(user_data_dir(), "Symbole")
    os.makedirs(p, exist_ok=True)
    return p


def _safe(name: str) -> str:
    return re.sub(r"[^\w\-äöüÄÖÜß ]+", "_", name).strip() or "Symbol"


def _ent_to_dict(e) -> dict:
    d = asdict(e)
    d["_typ"] = type(e).__name__
    return d


def _ent_from_dict(d: dict):
    typ = d.pop("_typ")
    cls = {"Line": Line, "Arc": Arc, "Circle": Circle, "Polyline": Polyline, "Text": Text}[typ]
    for k in ("p1", "p2", "center", "position"):
        if k in d and d[k] is not None:
            d[k] = tuple(d[k])
    if "points" in d:
        d["points"] = [tuple(p) for p in d["points"]]
    if d.get("color"):
        d["color"] = tuple(d["color"])
    return cls(**d)


def save_template(tpl: SymbolTemplate, folder: Optional[str] = None) -> str:
    folder = folder or library_dir()
    base = os.path.join(folder, _safe(tpl.name))
    ok, buf = cv2.imencode(".png", tpl.image)
    if ok:
        buf.tofile(base + ".png")
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump({"name": tpl.name, "entities": [_ent_to_dict(e) for e in tpl.entities]}, f,
                  ensure_ascii=False, indent=1)
    return base


def load_library(folder: Optional[str] = None) -> List[SymbolTemplate]:
    folder = folder or library_dir()
    out = []
    for fn in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not fn.endswith(".json"):
            continue
        base = os.path.join(folder, fn[:-5])
        try:
            with open(base + ".json", encoding="utf-8") as f:
                data = json.load(f)
            img = cv2.imdecode(np.fromfile(base + ".png", np.uint8), cv2.IMREAD_GRAYSCALE)
            if img is None:
                continue
            out.append(SymbolTemplate(data["name"], (img > 127).astype(np.uint8) * 255,
                                      [_ent_from_dict(e) for e in data["entities"]]))
        except Exception:
            continue
    return out


def apply_library(d: Drawing, bw: np.ndarray, library: List[SymbolTemplate],
                  threshold: float = 0.75) -> Tuple[int, dict]:
    total, per = 0, {}
    for tpl in library:
        n = apply_matches(d, tpl, find_matches(bw, tpl, threshold))
        if n:
            per[tpl.name] = n
            total += n
    return total, per
