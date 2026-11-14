"""Maßketten: Maßzahlen gezielt aus ihrer Lage an der Maßlinie lesen.

Erster Fall: die Zahl steht **in einer Lücke der Maßlinie** („—— 6.70 ——“, Allplan-Standard).
Tesseract scheitert auf dem ganzen Blatt oft daran, weil die Linienstücke links und rechts im
OCR-Bild bleiben (sie sind kürzer als die Schriftgrenze). Hier wird die Lücke gefunden, die
Schrift darin ohne Linie ausgeschnitten und nur mit Ziffern gelesen.

Koordinaten in Bildpixeln; bw: 1 = Tinte.
"""
import re
from typing import List, Tuple

import numpy as np

from .model import Text

# Box (x, y, w, h) der Schrift in der Lücke, Box der vollen Ziffern (für die Hochziffer)
Gap = Tuple[Tuple[int, int, int, int], Tuple[int, int, int, int]]

# Maß in cm („25“, „150“) oder m („6.70“, „14.45“, mit Hochziffer „4.175“)
NUMBER = re.compile(r"^(?:\d{1,3}|\d{1,2}[.,]\d{2,3})$")


def _horizontal_gaps(bw: np.ndarray, px_per_mm: float) -> List[Gap]:
    """Schrift in Lücken waagrechter Linien (Box der Schrift, Box der vollen Ziffern)."""
    import cv2
    L = max(10, int(3.0 * px_per_mm))
    hor = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((1, L), np.uint8))
    n, _, st, _ = cv2.connectedComponentsWithStats(hor, connectivity=8)
    thin = max(3, int(round(0.6 * px_per_mm)))
    segs = sorted((y + h / 2.0, x, x + w) for x, y, w, h, _ in st[1:] if h <= thin)
    rest = bw & (hor == 0)
    H, W = bw.shape
    h_min, h_max = 1.2 * px_per_mm, 7.0 * px_per_mm
    out = []
    # Linienstücke derselben Zeile (Mitte ± 1,5 px), nach x sortiert
    rows, cur = [], []
    for s in segs:
        if cur and s[0] - cur[-1][0] > 1.5:
            rows.append(cur)
            cur = []
        cur.append(s)
    if cur:
        rows.append(cur)
    for row in rows:
        row.sort(key=lambda s: s[1])
        for a, b in zip(row, row[1:]):
            g0, g1 = int(a[2]), int(b[1])          # Lücke [g0, g1)
            cy = (a[0] + b[0]) / 2.0
            if not (1.5 * px_per_mm <= g1 - g0 <= 30 * px_per_mm):
                continue
            y0, y1 = max(0, int(cy - h_max)), min(H, int(cy + h_max) + 1)
            win = rest[y0:y1, g0:g1]
            k, _, cs, _ = cv2.connectedComponentsWithStats(win, connectivity=8)
            comps = [(x + g0, y + y0, w, h) for x, y, w, h, ar in cs[1:] if ar >= 2]
            # volle Ziffern: kreuzen die Linienmitte, Schrifthöhe
            full = [c for c in comps if c[1] <= cy <= c[1] + c[3] and h_min <= c[3] <= h_max]
            if not full:
                continue
            fx0, fy0 = min(c[0] for c in full), min(c[1] for c in full)
            fx1 = max(c[0] + c[2] for c in full)
            fy1 = max(c[1] + c[3] for c in full)
            fh = fy1 - fy0
            # Schrift mittig auf der Linie, frei stehend in der Lücke
            if abs((fy0 + fy1) / 2.0 - cy) > 0.25 * fh or fx0 - g0 < 0.2 * fh or g1 - fx1 < 0.2 * fh:
                continue
            # dazu Punkt, Komma, Hochziffer: kleine Teile im Bereich der Zahl
            bx0, by0, bx1, by1 = fx0, fy0, fx1, fy1
            for c in comps:
                if c in full or c[3] > fh:
                    continue
                if fx0 - 0.3 * fh <= c[0] and c[0] + c[2] <= fx1 + 0.8 * fh \
                        and fy0 - 0.4 * fh <= c[1] and c[1] + c[3] <= fy1 + 0.4 * fh:
                    bx0, by0 = min(bx0, c[0]), min(by0, c[1])
                    bx1, by1 = max(bx1, c[0] + c[2]), max(by1, c[1] + c[3])
            out.append(((bx0, by0, bx1 - bx0, by1 - by0), (fx0, fy0, fx1 - fx0, fh)))
    return out


def line_gaps(bw: np.ndarray, px_per_mm: float) -> List[Tuple[Gap, int]]:
    """Schrift in Lücken waagrechter (k=0) und senkrechter Linien (k=1, liest von unten nach
    oben). Boxen im Originalbild."""
    out = [(g, 0) for g in _horizontal_gaps(bw, px_per_mm)]
    H = bw.shape[0]
    rot = np.ascontiguousarray(np.rot90(bw, -1))      # wie ocr.recognize, k=1
    for (b, f) in _horizontal_gaps(rot, px_per_mm):
        back = tuple((y, H - (x + w), h, w) for x, y, w, h in (b, f))
        out.append((back, 1))
    return out


def read_gap_numbers(bw: np.ndarray, gray: np.ndarray, px_per_mm: float, s, run_lines=None):
    """Maßzahlen in Lücken der Maßlinie lesen. Gibt (Texte, Boxen x, y, w, h) zurück."""
    import cv2

    from . import textlines
    from .ocr import NUM_WHITELIST, SUPERSCRIPT, _superscript_box
    gaps = line_gaps(bw, px_per_mm)
    if not gaps:
        return [], []
    crops = []
    for (b, _), k in gaps:
        x, y, w, h = b
        p = max(2, int(0.15 * h))
        c = gray[max(0, y - p):y + h + p, max(0, x - p):x + w + p]
        if k == 1:
            c = np.rot90(c, -1)
        f = textlines.LINE_H / max(1, c.shape[0])
        crops.append(cv2.resize(np.ascontiguousarray(c),
                                (max(1, int(round(c.shape[1] * f))), textlines.LINE_H),
                                interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_CUBIC))
    res = (run_lines or textlines._tesseract_lines)(crops, s, NUM_WHITELIST)
    rot = np.ascontiguousarray(np.rot90(bw, -1))
    H = bw.shape[0]
    texts, boxes = [], []
    for ((b, fb), k), (t, conf) in zip(gaps, res):
        t = (t or "").replace(" ", "")
        if conf < 60 or not NUMBER.match(t):
            continue
        # Hochziffer („4.17⁵“): als normale Ziffer mitgelesen → hochstellen
        if k == 0:
            sup = _superscript_box(bw, fb)
        else:
            fx, fy, fw, fh = fb                           # Box ins gedrehte Bild
            sup = _superscript_box(rot, (H - (fy + fh), fx, fh, fw))
        if sup is not None and sum(ch.isdigit() for ch in t) == sup[1] + 1 and "." in t[:-1]:
            t = t[:-1] + t[-1].translate(SUPERSCRIPT)
        x, y, w, h = b
        height = float(fb[3] if k == 0 else fb[2])
        if k == 0:
            texts.append(Text(t, (float(x), float(fb[1] + fb[3])), height, 0.0))
        else:
            texts.append(Text(t, (float(fb[0] + fb[2]), float(y + h)), height, 90.0))
        boxes.append(b)
    return texts, boxes


_NUMLIKE = re.compile(r"^[0-9.,:;°\"'’”⁰¹²³⁴⁵⁶⁷⁸⁹ ]+$")


def merge(texts: list, boxes: list, new_texts: list, new_boxes: list) -> None:
    """Lückenzahlen in die OCR-Ergebnisse übernehmen (texts/boxes parallel, werden geändert).

    Liegt dort noch nichts: dazu. Liegt dort eine andere Zahlenlesung („144“, „6 03“): die
    Lückenzahl ersetzt sie – sie ist aus dem sauberen Ausschnitt gelesen. Wörter bleiben."""
    from .ocr import _overlap
    for t, b in zip(new_texts, new_boxes):
        hit = [i for i, o in enumerate(boxes) if _overlap(b, o) > 0.3]
        if any(not _NUMLIKE.match(texts[i].text) or texts[i].text == t.text for i in hit):
            continue
        for i in sorted(hit, reverse=True):
            del texts[i], boxes[i]
        texts.append(t)
        boxes.append(b)


def _self_check() -> None:
    import cv2
    img = np.zeros((200, 600), np.uint8)
    cv2.line(img, (10, 100), (250, 100), 1, 2)
    cv2.line(img, (350, 100), (590, 100), 1, 2)
    cv2.putText(img, "6.70", (262, 112), cv2.FONT_HERSHEY_SIMPLEX, 0.8, 1, 2)
    g = line_gaps(img, 10.0)
    assert len(g) == 1 and g[0][1] == 0, g
    x, y, w, h = g[0][0][0]
    assert 255 <= x <= 265 and x + w <= 350 and y < 100 < y + h, g
    T, B = [Text("144", (0, 0), 10), Text("Bad", (0, 0), 10)], [(0, 0, 50, 20), (100, 0, 50, 20)]
    merge(T, B, [Text("14.45", (0, 0), 10), Text("2.10", (0, 0), 10)], [(2, 0, 60, 20), (100, 0, 40, 20)])
    assert [t.text for t in T] == ["Bad", "14.45"], [t.text for t in T]
    assert NUMBER.match("14.45") and NUMBER.match("150") and not NUMBER.match("9295")


if __name__ == "__main__":
    _self_check()
    print("ok")
