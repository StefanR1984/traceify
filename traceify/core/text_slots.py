"""Stellen mit unerkannter Schrift für das Nachlesen per KI und Regeln für die Übernahme.

Die OCR findet auf Plänen vor allem Maßzahlen nicht, die an Linien kleben oder von Türbögen und
Schraffur gekreuzt werden. Hier werden lange waagrechte/senkrechte Linien aus dem Bild genommen,
die übrige Tinte in Schriftgröße zu Wörtern gruppiert, und alles, was schon sicher gelesen ist,
ausgespart. Die KI liest jede Stelle zweimal mit verschiedenem Rand (`read_unrecognized` in
`traceify.ai.assistant`); übernommen wird nur, was beide Male gleich gelesen wurde und von der
Länge her in die Stelle passt – das Bildmodell erfindet sonst auf Schraffur und Linien gern Maße.

Koordinaten in Bildpixeln, Boxen (x, y, w, h).
"""
import re
from typing import List, Optional, Tuple

import numpy as np

from .model import Text

Box = Tuple[int, int, int, int]

# Maß in cm („24“, „88⁵“, „14⁷⁵“) oder m („2.40“, „2.83⁵“) – so schreibt Allplan
DIM = re.compile(r"^(?:\d{1,3}(?:⁵|⁷⁵|²⁵)?|\d{1,2}\.\d{2}⁵?)$")
LETTER = re.compile(r"[A-Za-zÄÖÜäöüß]")
SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹"
_SUPT = str.maketrans("0123456789", SUP)
_EDGE = " -—–_*.|/\\~¬'\"`:;"


def is_sure(t: Text) -> bool:
    """Gilt eine OCR-Lesung als sicher (wird von der KI nie überschrieben)?"""
    s = t.text.strip()
    return bool(DIM.match(s)) or (bool(LETTER.search(s)) and len(s) >= 4)


def find_slots(gray: np.ndarray, texts: List[Text], px_per_mm: float,
               line_mm: float = 3.0) -> List[Box]:
    """Wortgroße Tintengruppen ohne sichere Lesung. Lange Linien (≥ line_mm) zählen nicht."""
    import cv2
    from .benchmark import text_box
    bw = (gray < 128).astype(np.uint8)
    k = max(3, int(line_mm * px_per_mm))
    lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((1, k), np.uint8)) \
        | cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((k, 1), np.uint8))
    rest = bw & (1 - lines)
    n, lab, st, _ = cv2.connectedComponentsWithStats(rest, connectivity=8)
    size = np.maximum(st[:, 2], st[:, 3])
    keep = (size >= 0.5 * px_per_mm) & (size <= 4 * px_per_mm)
    keep[0] = False
    m = keep[lab].astype(np.uint8)
    for t in texts:
        if is_sure(t):
            x, y, w, h = text_box(t, pad=0.2)
            m[max(0, y):y + h, max(0, x):x + w] = 0
    # Zeichen eines Worts zusammenfassen (Abstand ~0,3 mm, waagrecht wie senkrecht geschrieben)
    g = cv2.dilate(m, np.ones((int(0.3 * px_per_mm) | 1, int(0.6 * px_per_mm) | 1), np.uint8))
    n, _, st, _ = cv2.connectedComponentsWithStats(g, connectivity=8)
    out = []
    for x, y, w, h in merge_row([tuple(int(v) for v in st[i, :4]) for i in range(1, n)]):
        # 60 mm: zusammengefasste Zeilen („STAHLBETONTREPPENHAUS“ ~40 mm)
        if max(w, h) > 60 * px_per_mm or min(w, h) < 0.7 * px_per_mm:
            continue
        if (m[y:y + h, x:x + w] > 0).sum() < 0.3 * px_per_mm * px_per_mm:
            continue
        out.append((x, y, w, h))
    return out


def merge_row(boxes: List[Box]) -> List[Box]:
    """Wortteile auf derselben Zeile zusammenfassen. Aus Punkten gedruckte Schrift (Plan 03)
    zerfällt beim Gruppieren in Stücke („STAHL“ | „LBET“ | „ONT“, „TREPPENANLA“ + halbes „GE“
    1,1 Höhen daneben) – die KI las dann nur „TREPPENANLA“. Zwei Teile gehören zusammen, wenn
    das kleinere senkrecht in der Zeile des größeren liegt (±20 % von dessen Höhe, Mitten ≤ 0,2
    Höhen versetzt, höchstens 2,5-mal so hoch) und die Lücke ≤ 1,2 × dessen Höhe ist; Ketten
    verbinden (Union-Find).
    shortcut: nur waagrecht – senkrechte Wörter bleiben in Stücken, falls das vorkommt."""
    if not boxes:
        return []
    b = np.array(boxes, float)
    x0, y0, x1, y1 = b[:, 0], b[:, 1], b[:, 0] + b[:, 2], b[:, 1] + b[:, 3]
    h = b[:, 3]
    root = list(range(len(b)))

    def find(i):
        while root[i] != i:
            root[i] = root[root[i]]
            i = root[i]
        return i

    for i in range(len(b) - 1):
        j = np.arange(i + 1, len(b))
        big = h[j] >= h[i]                        # Zeile des größeren Teils
        H = np.maximum(h[i], h[j])
        ty = np.where(big, y0[j], y0[i])
        sy0, sy1 = np.where(big, y0[i], y0[j]), np.where(big, y1[i], y1[j])
        inrow = (sy0 >= ty - 0.2 * H) & (sy1 <= ty + 1.2 * H)             & (np.abs((y0[j] + y1[j]) - (y0[i] + y1[i])) / 2 <= 0.2 * H)             & (H <= 2.5 * np.minimum(h[i], h[j]))     # kein hohes Symbol als Brücke zwischen Zeilen
        gap = np.maximum(x0[i], x0[j]) - np.minimum(x1[i], x1[j])
        for k in j[inrow & (gap <= 1.2 * H)]:
            root[find(int(k))] = find(i)
    groups = {}
    for i, bx in enumerate(boxes):
        groups.setdefault(find(i), []).append(bx)
    out = []
    for g in groups.values():
        gx0, gy0 = min(q[0] for q in g), min(q[1] for q in g)
        gx1, gy1 = max(q[0] + q[2] for q in g), max(q[1] + q[3] for q in g)
        if gy1 - gy0 > 1.6 * max(g, key=lambda q: q[2])[3]:
            out += g                               # über Zeichnungsteile gekettet: einzeln lassen
        else:
            out.append((gx0, gy0, gx1 - gx0, gy1 - gy0))
    return out


def slot_crop(gray: np.ndarray, box: Box, px_per_mm: float, pad_mm: float) -> np.ndarray:
    """Ausschnitt um eine Stelle; hohe, schmale Stellen werden lesbar gedreht (von unten nach
    oben geschrieben, wie senkrechte Maße)."""
    x, y, w, h = box
    p = int(pad_mm * px_per_mm)
    c = gray[max(0, y - p):y + h + p, max(0, x - p):x + w + p]
    if vertical(box):
        c = np.rot90(c, 1)
    return np.ascontiguousarray(c)


def vertical(box: Box) -> bool:
    return box[3] > 1.3 * box[2]


def normalize(raw: str) -> str:
    """KI-Antwort aufräumen: „2.83^5“ → „2.83⁵“, Ränder und einzelne Fremdzeichen weg
    („r 30 *“ → „30“, „- 1.95⁵ —“ → „1.95⁵“)."""
    s = re.sub(r"\^\{?(\d+)\}?", lambda m: m.group(1).translate(_SUPT), raw or "")
    s = s.replace(",", ".").strip(_EDGE)
    tok = s.split()
    core = [t.strip("*-—_.") for t in tok]
    dims = [t for t in core if DIM.match(t)]
    if len(dims) == 1 and all(len(t) <= 1 for t, c in zip(tok, core) if c != dims[0]):
        return dims[0]
    if len(core) == 1:
        m = re.fullmatch(r"[a-z]?(\d[\d.%s]*)[a-z*]?" % SUP, core[0])
        if m and DIM.match(m.group(1)):
            return m.group(1)
    return s


def _length(s: str) -> float:
    """Länge eines Texts in Zeichenbreiten (Punkt, Leerzeichen, Hochziffer schmal)."""
    return len(s) - 0.6 * (s.count(".") + s.count(" ")) - 0.4 * sum(c in SUP for c in s)


def plausible(s: str, box: Box) -> bool:
    """Passt die Lesung zur Stelle? Maße ohne einstellige Zahlen (die liest die KI oft aus
    Bruchstücken), Länge zur Größe der Stelle."""
    if not s:
        return False
    if DIM.match(s):
        if len(s.rstrip(SUP)) == 1:
            return False
    elif not LETTER.search(s):
        return False
    else:
        tok = s.split()
        # „22T“, „b.54“: Ziffern und Buchstaben in einem Wort sind Bruchstücke, kein Raumstempel
        if any(LETTER.search(t) and re.search(r"\d", t) for t in tok):
            return False
        # kurze Buchstabenfolgen nur als Abkürzung in Großbuchstaben („WC“, „TRH“), nicht „qrr“
        if all(LETTER.search(t) for t in tok) and len(s.replace(" ", "")) < 4 and not s.isupper():
            return False
        # einzelne Buchstaben liest das Modell aus Linienkreuzungen (Plan 03: H, F, T, K)
        if len(s.replace(" ", "")) < 2:
            return False
    w, h = (box[3], box[2]) if vertical(box) else (box[2], box[3])
    r = _length(s) * h * 0.55 / max(1, w)
    return 0.35 <= r <= 1.6


def accept(first: str, second: str, box: Box) -> Optional[str]:
    """Übernahmeregel: beide Lesungen gleich und plausibel → Text, sonst None."""
    a, b = normalize(first), normalize(second)
    return a if a and a == b and plausible(a, box) else None


def replaced(texts: List[Text], box: Box) -> List[Text]:
    """Unsichere OCR-Lesungen in der Stelle, die eine KI-Lesung ersetzt."""
    from .benchmark import text_box
    x, y, w, h = box
    out = []
    for t in texts:
        if is_sure(t):
            continue
        bx, by, bw, bh = text_box(t)
        cx, cy = bx + bw / 2, by + bh / 2
        if x <= cx <= x + w and y <= cy <= y + h:
            out.append(t)
    return out


def _self_check() -> None:
    assert normalize("r 30 *") == "30" and normalize("- 1.95^5 —") == "1.95⁵"
    assert normalize("21^{25}") == "21²⁵" and normalize("1.13 Büro") == "1.13 Büro"
    assert accept("2.40", "2.40", (0, 0, 40, 14)) == "2.40"
    assert accept("2.40", "2.48", (0, 0, 40, 14)) is None
    assert accept("6", "6", (0, 0, 9, 14)) is None                  # einstellig
    assert accept("13.06", "13.06", (0, 0, 300, 14)) is None        # viel zu lang für den Text
    assert accept("22T", "22T", (0, 0, 30, 14)) is None and accept("qrr", "qrr", (0, 0, 25, 14)) is None
    assert accept("WC", "WC", (0, 0, 18, 14)) == "WC"


_self_check()
