"""Nachlesen von Schrift, die die normale OCR nicht gefunden hat.

Tesseract liest ganze Seiten nur waagrecht (Traceify dreht zusätzlich um 90/180/270°).
Schräg gesetzte Beschriftungen und Handschrift bleiben dabei oft liegen. Hier werden
schriftähnliche Gruppen von Zeichen gesucht, in jeder beliebigen Lage:

1. Objekte in Schriftgröße (``ocr.text_layer``), außerhalb schon erkannter Texte
2. benachbarte, ähnlich große Zeichen zu Wörtern/Zeilen gruppieren; zusammenhängend
   geschriebene Wörter (Handschrift) zählen auch einzeln
3. Lage und Winkel jeder Gruppe bestimmen, Ausschnitt geraderücken
4. alle Ausschnitte untereinander auf ein Blatt setzen und in **einem** Tesseract-Aufruf
   lesen – einmal so, einmal um 180° gedreht; die sicherere Lesart gewinnt
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List, Tuple

import cv2
import numpy as np

from .model import Text

LINE_H = 44        # Höhe der geradegerückten Ausschnitte für Tesseract (px)
GAP = 26           # Abstand zwischen den Ausschnitten auf dem Leseblatt


@dataclass
class Candidate:
    center: Tuple[float, float]
    angle: float         # Richtung der Zeile im Bild, Grad (0 = nach rechts, y nach unten)
    length: float        # Ausdehnung entlang der Zeile (px)
    height: float        # Ausdehnung quer dazu (px)
    n: int               # Anzahl Zeichen-Objekte
    pixels: np.ndarray   # (k, 2) Tinte der Gruppe (x, y)


def _union_find(n):
    par = list(range(n))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            par[ra] = rb
    return find, union


def find_candidates(layer: np.ndarray, px_per_mm: float, skip_boxes=(),
                    min_char_mm: float = 1.2, max_char_mm: float = 12.0,
                    max_candidates: int = 400) -> List[Candidate]:
    """Schriftähnliche Gruppen in einem Bild, das nur noch Objekte in Schriftgröße enthält
    (255 = Tinte). skip_boxes: bereits erkannte Textbereiche (x, y, w, h)."""
    m = (layer > 0).astype(np.uint8)
    for (x, y, w, h) in skip_boxes or ():
        m[max(0, y - 2):y + h + 2, max(0, x - 2):x + w + 2] = 0
    n, lab, st, cen = cv2.connectedComponentsWithStats(m, connectivity=8)
    if n <= 1:
        return []
    lo, hi = min_char_mm * px_per_mm, max_char_mm * px_per_mm
    W, H = st[:, 2], st[:, 3]
    size = np.maximum(W, H)
    # Zeichen: mindestens so groß wie ein kleiner Buchstabe; Punkte/i-Tüpfel kommen über
    # die Nachbarschaft mit (unten), zählen aber nicht als eigene Zeichen
    idx = [i for i in range(1, n) if size[i] >= 0.5 * lo]
    if not idx:
        return []
    pos = {i: k for k, i in enumerate(idx)}
    find, union = _union_find(len(idx))
    cell = int(hi) + 1
    grid = {}
    for i in idx:
        grid.setdefault((int(cen[i, 0] // cell), int(cen[i, 1] // cell)), []).append(i)
    for i in idx:
        gx, gy = int(cen[i, 0] // cell), int(cen[i, 1] // cell)
        xi, yi, wi, hi_ = st[i, :4]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in grid.get((gx + dx, gy + dy), ()):
                    if j <= i:
                        continue
                    si, sj = size[i], size[j]
                    small, big = min(si, sj), max(si, sj)
                    if big > 3.0 * small and small >= lo:
                        continue
                    xj, yj, wj, hj = st[j, :4]
                    gx_ = max(0, max(xi, xj) - min(xi + wi, xj + wj))
                    gy_ = max(0, max(yi, yj) - min(yi + hi_, yj + hj))
                    if math.hypot(gx_, gy_) <= 0.7 * max(small, 0.5 * big):
                        union(pos[i], pos[j])
    groups = {}
    for i in idx:
        groups.setdefault(find(pos[i]), []).append(i)

    out = []
    for g in groups.values():
        chars = [i for i in g if size[i] >= lo]
        if not chars:
            continue
        # zusammenhängend geschriebenes Wort (Handschrift) oder mehrere Zeichen
        if len(chars) < 2:
            i = chars[0]
            if size[i] < 2.2 * min(W[i], H[i]) or size[i] > 4 * hi:
                continue
        ys, xs = [], []
        for i in g:
            x0, y0, w, h = st[i, :4]
            yy, xx = np.nonzero(lab[y0:y0 + h, x0:x0 + w] == i)
            ys.append(yy + y0)
            xs.append(xx + x0)
        P = np.column_stack([np.concatenate(xs), np.concatenate(ys)]).astype(np.float32)
        (cx, cy), (rw, rh), ang = cv2.minAreaRect(P)
        if rw < rh:
            rw, rh, ang = rh, rw, ang + 90.0
        if rh < lo or rh > hi or rw < 1.5 * rh:
            continue
        if _dashes(st, chars):
            continue
        out.append(Candidate((float(cx), float(cy)), float(ang) % 180.0, float(rw), float(rh),
                             len(chars), P))
    out.sort(key=lambda c: -c.length)
    return out[:max_candidates]


def _dashes(st, chars) -> bool:
    """Gruppe aus lauter gleichartigen Strichen (Strichlinie, Fliesen-Schraffur)?"""
    if len(chars) < 3:
        return False
    asp = [max(st[i, 2], st[i, 3]) / max(1, min(st[i, 2], st[i, 3])) for i in chars]
    return float(np.median(asp)) > 3.5


def _straighten(c: Candidate, ink: np.ndarray, flip: bool) -> np.ndarray:
    """Ausschnitt der Gruppe, waagrecht gedreht und auf LINE_H Höhe gebracht."""
    pad = 0.35 * c.height
    a = c.angle + (180.0 if flip else 0.0)
    scale = LINE_H / (c.height + 2 * pad)
    M = cv2.getRotationMatrix2D(c.center, a, scale)
    out_w = int((c.length + 2 * pad) * scale) + 2
    M[0, 2] += out_w / 2 - c.center[0]
    M[1, 2] += LINE_H / 2 - c.center[1]
    mask = np.zeros(ink.shape, np.uint8)
    pts = c.pixels.astype(np.int32)
    mask[pts[:, 1], pts[:, 0]] = 255
    crop = cv2.warpAffine(mask, M, (out_w, LINE_H), flags=cv2.INTER_LINEAR, borderValue=0)
    return 255 - crop


def read_candidates(cands: List[Candidate], ink: np.ndarray, s, run_ocr=None
                    ) -> Tuple[List[Text], List[Tuple[int, int, int, int]]]:
    """Liest alle Kandidaten (beide Leserichtungen) und gibt Texte und Boxen zurück."""
    from .ocr import plausible
    if not cands:
        return [], []
    run_ocr = run_ocr or _tesseract_lines
    best = [None] * len(cands)
    for flip in (False, True):
        crops = [_straighten(c, ink, flip) for c in cands]
        for k, (txt, conf) in enumerate(run_ocr(crops, s)):
            txt = (txt or "").strip()
            if not txt or conf < max(s.min_confidence, 70) or not plausible(txt):
                continue
            n_al = sum(ch.isalnum() for ch in txt)
            if n_al <= 3 and conf < 85:
                continue
            # Zeichenzahl muss zur Länge der Gruppe passen (Schrift ist etwa 0,4–1 × so
            # breit wie hoch) – sonst hat Tesseract in Strichen „Buchstaben“ gesehen
            expect = cands[k].length / max(1.0, cands[k].height)
            if not (0.35 * expect <= len(txt) <= 3.0 * expect + 1):
                continue
            score = conf * sum(ch.isalnum() for ch in txt)
            if best[k] is None or score > best[k][0]:
                best[k] = (score, txt, flip)
    texts, boxes = [], []
    for c, b in zip(cands, best):
        if b is None:
            continue
        _, txt, flip = b
        a = c.angle + (180.0 if flip else 0.0)          # Leserichtung im Bild
        r = math.radians(a)
        ux, uy = math.cos(r), math.sin(r)               # entlang der Zeile
        nx, ny = -uy, ux                                # nach „unten“ (zur Grundlinie)
        bx = c.center[0] - ux * c.length / 2 + nx * c.height / 2
        by = c.center[1] - uy * c.length / 2 + ny * c.height / 2
        texts.append(Text(txt, (float(bx), float(by)), float(c.height) * 0.8, (-a) % 360.0))
        x0, y0 = c.pixels.min(axis=0)
        x1, y1 = c.pixels.max(axis=0)
        boxes.append((int(x0), int(y0), int(x1 - x0) + 1, int(y1 - y0) + 1))
    return texts, boxes


def _tesseract_lines(crops: List[np.ndarray], s) -> List[Tuple[str, float]]:
    """Alle Ausschnitte untereinander auf ein Blatt, ein Tesseract-Aufruf, Zuordnung per y."""
    from .ocr import _setup, _tess_config, _usable_lang
    pt = _setup()
    width = max(c.shape[1] for c in crops) + 2 * GAP
    height = GAP + len(crops) * (LINE_H + GAP)
    sheet = np.full((height, width), 255, np.uint8)
    rows = []
    y = GAP
    for c in crops:
        sheet[y:y + LINE_H, GAP:GAP + c.shape[1]] = c
        rows.append((y, y + LINE_H))
        y += LINE_H + GAP
    data = pt.image_to_data(sheet, lang=_usable_lang(s.language),
                            config=(_tess_config() + " --psm 6").strip(),
                            output_type=pt.Output.DICT)
    words = [[] for _ in crops]
    for i, t in enumerate(data["text"]):
        t = (t or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1
        if not t or conf < 0:
            continue
        cy = data["top"][i] + data["height"][i] / 2
        k = int((cy - GAP / 2) // (LINE_H + GAP))
        if 0 <= k < len(crops):
            words[k].append((data["left"][i], t, conf))
    out = []
    for ws in words:
        if not ws:
            out.append(("", -1.0))
            continue
        ws.sort()
        txt = " ".join(w[1] for w in ws)
        conf = sum(w[2] * len(w[1]) for w in ws) / max(1, sum(len(w[1]) for w in ws))
        out.append((txt, conf))
    return out
