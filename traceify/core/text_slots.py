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
    for i in range(1, n):
        x, y, w, h = (int(v) for v in st[i, :4])
        if max(w, h) > 30 * px_per_mm or min(w, h) < 0.7 * px_per_mm:
            continue
        if (m[y:y + h, x:x + w] > 0).sum() < 0.3 * px_per_mm * px_per_mm:
            continue
        out.append((x, y, w, h))
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
