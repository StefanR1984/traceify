"""Gescannte Planteile zusammensetzen.

Ein großer Plan wird oft in zwei (oder mehr) Teilen gescannt und nebeneinander auf eine
PDF-Seite gelegt – dazwischen bleibt eine weiße Fuge, und die Teile sind meist um einige
Pixel gegeneinander versetzt. Hier wird die Anordnung erkannt (`tile_order`) und der Versatz
bestimmt (`align`): echte Überlappung per Kreuzkorrelation mehrerer Bänder, sonst Stoß an Stoß
mit der Höhenlage aus dem Zeilenprofil (waagrechte Linien laufen über die Fuge weiter).
"""
from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np

MIN_OVERLAP_SCORE = 0.8   # Schraffur ähnelt sich auch ohne echte Überlappung (~0,67)
MIN_PROFILE_SCORE = 0.5


def tile_order(rects: Sequence[Tuple[float, float, float, float]]) -> Optional[Tuple[str, List[int]]]:
    """Liegen die Bildrechtecke (x0, y0, x1, y1) als Reihe ("x") oder Spalte ("y") nebeneinander,
    ohne sich zu überdecken? Gibt (Achse, Reihenfolge) zurück, sonst None."""
    if len(rects) < 2:
        return None
    r = np.asarray(rects, float)
    w, h = r[:, 2] - r[:, 0], r[:, 3] - r[:, 1]
    if (w <= 0).any() or (h <= 0).any():
        return None
    for axis, a0, a1, b0, b1, size, cross in (("x", 0, 2, 1, 3, w, h), ("y", 1, 3, 0, 2, h, w)):
        order = list(np.argsort(r[:, a0]))
        ok = True
        for i, j in zip(order, order[1:]):
            gap = r[j, a0] - r[i, a1]
            shared = min(r[i, b1], r[j, b1]) - max(r[i, b0], r[j, b0])
            if gap < -0.02 * min(size[i], size[j]) or gap > 0.1 * min(size[i], size[j]) \
                    or shared < 0.7 * max(cross[i], cross[j]):
                ok = False
                break
        if ok:
            return axis, [int(i) for i in order]
    return None


def _ink(img: np.ndarray) -> np.ndarray:
    return cv2.GaussianBlur(255 - img, (0, 0), 1.5).astype(np.float32)


def _overlap(a: np.ndarray, b: np.ndarray) -> Optional[Tuple[int, int]]:
    """Echte Überlappung: Randstreifen von b in a suchen (in mehreren Bändern); jeder sichere
    Fund wird über die ganze Überlappung gegengeprüft – ein Band mit nur einer waagrechten
    Linie passt überall auf ihr, regelmäßige Raster passen auch versetzt.
    Gibt (dx, dy) von b gegen a zurück."""
    ha, wa = a.shape
    hb, wb = b.shape
    k = min(48, wb // 4)  # schmal: auch kleine Überlappungen finden
    search = min(wa, max(k + 8, int(0.35 * wa)))
    area = _ink(a[:, wa - search:])
    bb = _ink(b)
    margin = max(10, int(0.03 * hb))
    bands = np.linspace(margin, hb - margin, 7).astype(int)
    cands = set()
    for y0, y1 in zip(bands, bands[1:]):
        tpl = bb[y0:y1, :k]
        if tpl.std() < 1.0 or y1 - y0 < 20:
            continue
        lo = max(0, y0 - margin)
        sub = area[lo:min(ha, y1 + margin)]
        if sub.shape[0] < tpl.shape[0]:
            continue
        res = cv2.matchTemplate(sub, tpl, cv2.TM_CCOEFF_NORMED)
        _, score, _, (x, y) = cv2.minMaxLoc(res)
        if score >= MIN_OVERLAP_SCORE:
            cands.add((wa - search + x, lo + y - y0))
    best, found = MIN_OVERLAP_SCORE, None
    for dx, dy in sorted(cands):
        ov = wa - dx
        ya, yb = max(0, dy), max(0, -dy)
        n = min(ha - ya, hb - yb)
        if n < 20 or ov < 4:
            continue
        pa, pb = _ink(a[ya:ya + n, dx:]), bb[yb:yb + n, :ov]
        # waagrechte Linien laufen auch beim Stoß weiter – nur der Rest zählt
        pa = pa - pa.mean(1, keepdims=True)
        pb = pb - pb.mean(1, keepdims=True)
        if pa.std() < 1.0 or pb.std() < 1.0:
            continue
        c = float(np.corrcoef(pa.ravel(), pb.ravel())[0, 1])
        if c >= best:
            best, found = c, (dx, dy)
    return found


def _abut_dy(a: np.ndarray, b: np.ndarray) -> Optional[int]:
    """Höhenversatz beim Stoß: Zeilenprofil der Randstreifen beider Teile vergleichen."""
    h = min(a.shape[0], b.shape[0])
    edge = 50
    pa = _ink(a[:h, -edge - 8:-8]).mean(1)
    pb = _ink(b[:h, 8:edge + 8]).mean(1)
    rng = max(20, int(0.04 * h))
    if h <= 4 * rng or pa.std() < 0.5 or pb.std() < 0.5:
        return None
    best, best_dy = -1.0, 0
    for dy in range(-rng, rng + 1):
        x, y = pa[rng:h - rng], pb[rng - dy:h - rng - dy]
        c = float(np.corrcoef(x, y)[0, 1])
        if c > best:
            best, best_dy = c, dy
    return best_dy if best >= MIN_PROFILE_SCORE else None


def align(a: np.ndarray, b: np.ndarray, axis: str = "x", dy0: int = 0) -> Tuple[int, int, str]:
    """Lage von Teil b gegen Teil a (beide Graubilder, b rechts bzw. unter a).

    Gibt (dx, dy, Art) zurück: Art „überlappt“ oder „stoß“. ``dy0`` ist der Querversatz aus
    der Seitenlage, falls nichts Besseres gefunden wird.
    """
    if axis == "y":
        dx, dy, how = align(np.ascontiguousarray(a.T), np.ascontiguousarray(b.T), "x", dy0)
        return dy, dx, how
    ov = _overlap(a, b)
    if ov is not None:
        return ov[0], ov[1], "überlappt"
    dy = _abut_dy(a, b)
    # Profil: Zeile i von a entspricht Zeile i - dy von b → b beginnt auf Zeile dy von a
    return a.shape[1], (dy if dy is not None else dy0), "stoß"


def edge_specks(gray: np.ndarray, side: str, band: int) -> np.ndarray:
    """Maske der Tinte, die ganz im Randstreifen (``band`` px) an der Fuge liegt – die
    Scankante (gepunktete Linie, Schatten). Linien, die über die Fuge laufen, reichen tiefer
    ins Bild und bleiben. ``side``: "left", "right", "top", "bottom"."""
    if side in ("top", "bottom"):
        return edge_specks(gray.T, "left" if side == "top" else "right", band).T
    h, w = gray.shape
    band = min(band, w // 4)
    width = min(w, 3 * band)
    sub = gray[:, w - width:] if side == "right" else gray[:, :width]
    bw = (sub < 128).astype(np.uint8)
    n, lab, st, _ = cv2.connectedComponentsWithStats(bw, connectivity=8)
    x0, x1 = st[:, cv2.CC_STAT_LEFT], st[:, cv2.CC_STAT_LEFT] + st[:, cv2.CC_STAT_WIDTH]
    inside = (x0 >= width - band) if side == "right" else (x1 <= band)
    inside[0] = False
    out = np.zeros(gray.shape, bool)
    if side == "right":
        out[:, w - width:] = inside[lab]
    else:
        out[:, :width] = inside[lab]
    return out


def compose(parts: Sequence[np.ndarray], offsets: Sequence[Tuple[int, int]], fill=255) -> np.ndarray:
    """Teile an ihren Versätzen (dx, dy) auf eine gemeinsame Fläche legen; spätere Teile
    überdecken frühere."""
    xs = [dx for dx, _ in offsets]
    ys = [dy for _, dy in offsets]
    x0, y0 = min(xs), min(ys)
    w = max(dx + p.shape[1] for p, (dx, _) in zip(parts, offsets)) - x0
    h = max(dy + p.shape[0] for p, (_, dy) in zip(parts, offsets)) - y0
    out = np.full((h, w) + parts[0].shape[2:], fill, dtype=parts[0].dtype)
    for p, (dx, dy) in zip(parts, offsets):
        out[dy - y0:dy - y0 + p.shape[0], dx - x0:dx - x0 + p.shape[1]] = p
    return out


def chain_offsets(parts: Sequence[np.ndarray], axis: str = "x",
                  dy0: Sequence[int] = ()) -> Tuple[List[Tuple[int, int]], List[str]]:
    """Versätze aller Teile (in Reihenfolge) gegen das erste; Graubilder."""
    offs, kinds = [(0, 0)], []
    for i in range(1, len(parts)):
        dx, dy, how = align(parts[i - 1], parts[i], axis, dy0[i - 1] if i - 1 < len(dy0) else 0)
        px, py = offs[-1]
        offs.append((px + dx, py + dy))
        kinds.append(how)
    return offs, kinds
