"""Maßketten: Maßzahlen gezielt aus ihrer Lage an der Maßlinie lesen.

Die Zahl steht **in einer Lücke der Maßlinie** („—— 6.70 ——“, Allplan-Standard) oder zwischen
zwei Maßbegrenzungen ohne Linie („✳74✳74✳“), mittig auf der Linie oder als Paar direkt darüber
und darunter („3.01“ / „3.00“). Tesseract scheitert auf dem ganzen Blatt oft daran, weil
Linienstücke und Sterne im OCR-Bild bleiben. Hier wird die Lücke gefunden, die Schrift darin
ohne Linie ausgeschnitten und nur mit Ziffern gelesen; eine Hochziffer („4.17⁵“) wird in voller
Größe angehängt.

Koordinaten in Bildpixeln; bw: 1 = Tinte.
"""
import re
from typing import List, Optional, Tuple

import numpy as np

from .model import Text

# Box (x, y, w, h) der Zahl in der Lücke, Box der vollen Ziffern, Box der Hochziffer oder None,
# Lage zur Maßlinie: 0 mittig darauf, -1 darüber, +1 darunter; Maßsegment (Zeile, x der Maßbegrenzung
# links, rechts, Mitte der Zahl) oder None, wenn keine Sterne auf der Zeile die Zahl einschließen
Box = Tuple[int, int, int, int]
Seg = Tuple[float, float, float, float]
Gap = Tuple[Box, Box, Optional[Box], int, Optional[Seg]]

# Maß in cm („25“, „150“) oder m („6.70“, „14.45“); die Hochziffer („4.17⁵“) wird getrennt gelesen
NUMBER = re.compile(r"^(?:\d{2,3}|\d{1,2}\.\d{2})$")
SUP = "⁰¹²³⁴⁵⁶⁷⁸⁹"
DIGIT_W = 0.77      # Ziffernbreite samt Abstand je Ziffernhöhe (serifenlose Planschrift)


def _ticks(bw: np.ndarray, px_per_mm: float):
    """Maßbegrenzungen: kurzer 45°-Strich („/“ oder „\“, je nach Leserichtung), durch dessen Mitte
    Maßlinie und Maßhilfslinie laufen („Stern“). Gibt (Liste (cx, cy), Maske der Sterne) zurück.

    Ziffern mit Schrägstrich („7“, „4“, „1“) haben kein Kreuz genau in der Strichmitte."""
    import cv2
    d = max(4, int(round(0.7 * px_per_mm)))
    k = np.eye(d, dtype=np.uint8)
    diag = cv2.morphologyEx(bw, cv2.MORPH_OPEN, k) | cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.fliplr(k))
    n, lab, st, cen = cv2.connectedComponentsWithStats(diag, connectivity=8)
    r = max(3, int(round(0.4 * px_per_mm)))
    H, W = bw.shape
    out, mask = [], np.zeros_like(bw)
    # kurze Stücke der Maßlinie zwischen Stern und Zahl („✳—1.25—✳“, kürzer als eine „Linie“)
    stub = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((1, max(5, int(px_per_mm))), np.uint8))
    R = int(3 * px_per_mm)
    for i in range(1, n):
        x, y, w, h, _ = st[i]
        if not (0.6 * px_per_mm <= max(w, h) <= 3.0 * px_per_mm) or abs(w - h) > 0.35 * max(w, h):
            continue
        cx, cy = int(round(cen[i][0])), int(round(cen[i][1]))
        if cx - r < 1 or cy - r < 1 or cx + r + 2 > W or cy + r + 2 > H:
            continue
        # waagrechter und senkrechter Strich durch die Mitte, je beidseits
        rows = bw[cy - 2:cy + 3, cx - r:cx + r + 1].all(axis=1)
        if not rows.any() or not bw[cy - r:cy + r + 1, cx - 1:cx + 2].any(axis=1).all():
            continue
        # der Schrägstrich läuft durch die Mitte: Tinte beidseits auf der Diagonale (nicht „4“)
        q = max(3, int(round(0.35 * px_per_mm)))
        if not any(bw[cy - sy * q - 1:cy - sy * q + 2, cx - q - 1:cx - q + 2].any()
                   and bw[cy + sy * q - 1:cy + sy * q + 2, cx + q - 1:cx + q + 2].any() for sy in (-1, 1)):
            continue
        out.append((cx, cy - 2 + float(np.nonzero(rows)[0].mean())))
        sl = (slice(y, y + h), slice(x, x + w))
        mask[sl] |= (lab[sl] == i).astype(np.uint8)
        mask[cy - r - 2:cy + r + 3, cx - 1:cx + 2] = 1
        mask[cy - 1:cy + 2, cx - r - 2:cx + r + 3] = 1
        # nur was am Stern hängt – der Querstrich einer „4“ daneben bleibt
        run = stub[cy - 2:cy + 3, max(0, cx - R):cx + R].any(axis=0)
        off = np.nonzero(~run)[0] + max(0, cx - R)
        a = int(off[off < cx].max()) + 1 if (off < cx).any() else max(0, cx - R)
        b = int(off[off > cx].min()) if (off > cx).any() else cx + R
        mask[cy - 2:cy + 3, a:b] |= stub[cy - 2:cy + 3, a:b]
    return out, cv2.dilate(mask, np.ones((3, 3), np.uint8))


def _horizontal_gaps(bw: np.ndarray, px_per_mm: float) -> List[Gap]:
    """Schrift in Lücken waagrechter Linien (Box der Schrift, Box der vollen Ziffern).

    Die Lücke liegt zwischen zwei Linienstücken oder zwei Maßbegrenzungen („✳74✳74✳“: Allplan
    lässt die Maßlinie bei kurzen Maßen ganz weg)."""
    import cv2
    L = max(10, int(3.0 * px_per_mm))
    hor = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((1, L), np.uint8))
    n, _, st, _ = cv2.connectedComponentsWithStats(hor, connectivity=8)
    thin = max(3, int(round(0.6 * px_per_mm)))
    ticks, stars = _ticks(bw, px_per_mm)
    rt = 0.4 * px_per_mm
    segs = sorted([(y + h / 2.0, x, x + w) for x, y, w, h, _ in st[1:] if h <= thin]
                  + [(cy, cx - rt, cx + rt) for cx, cy in ticks])
    rest = bw & (hor == 0) & (stars == 0)
    H, W = bw.shape
    h_min, h_max = 1.2 * px_per_mm, 7.0 * px_per_mm
    out = []

    def seg(cy, x):
        """Maßsegment um x: nächste Sterne links und rechts auf der Zeile cy."""
        row = [tx for tx, ty in ticks if abs(ty - cy) <= 2.5]
        a = [tx for tx in row if tx < x]
        b = [tx for tx in row if tx > x]
        return (cy, max(a), min(b), x) if a and b else None
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
        end = None                                  # (Zeile, rechtes Ende) des Stücks vor der Lücke
        for a, b in zip(row, row[1:]):
            if end is None or a[2] > end[1]:
                end = (a[0], a[2])
            g0, g1 = int(end[1]), int(b[1])         # Lücke [g0, g1)
            cy = (end[0] + b[0]) / 2.0
            if not (1.5 * px_per_mm <= g1 - g0 <= 30 * px_per_mm):
                continue
            y0, y1 = max(0, int(cy - h_max)), min(H, int(cy + h_max) + 1)
            win = rest[y0:y1, g0:g1]
            k, _, cs, _ = cv2.connectedComponentsWithStats(win, connectivity=8)
            comps = [(x + g0, y + y0, w, h) for x, y, w, h, ar in cs[1:] if ar >= 2]
            # volle Ziffern: kreuzen die Linienmitte, Schrifthöhe
            full = [c for c in comps if c[1] <= cy <= c[1] + c[3] and h_min <= c[3] <= h_max]
            g = _number(full, comps, rest, g0, g1) if full else None
            if g is not None and abs(g[1][1] + g[1][3] / 2.0 - cy) <= 0.25 * g[1][3]:
                out.append(g + (0, seg(cy, g[1][0] + g[1][2] / 2.0)))   # mittig auf der Linie
                continue
            # zwei Zahlen direkt über und unter der Linie („3.01“ / „3.00“, Breite / Höhe einer
            # Öffnung): an der Linie trennen, sie berühren sich oft
            r = int(round(cy)) - y0
            win = win.copy()
            win[r - 1:r + 2] = 0
            k, _, cs, _ = cv2.connectedComponentsWithStats(win, connectivity=8)
            comps = [(x + g0, y + y0, w, h) for x, y, w, h, ar in cs[1:] if ar >= 2]
            for side in (-1, 1):
                full = [c for c in comps if h_min <= c[3] <= h_max
                        and 0 <= (cy - c[1] - c[3] if side < 0 else c[1] - cy) <= 0.25 * c[3] + 2]
                g = _number(full, comps, rest, g0, g1) if full else None
                if g is not None:
                    out.append(g + (side, seg(cy, g[1][0] + g[1][2] / 2.0)))
    return out


def _number(full, comps, rest, g0: int, g1: int):
    """Aus den vollen Ziffern einer Lücke [g0, g1) die Zahl bilden: (Box, Box der Ziffern,
    Box der Hochziffer oder None) – oder None, wenn sie nicht frei in der Lücke steht."""
    from .ocr import _superscript_box
    top = max(c[3] for c in full)
    full = [c for c in full if c[3] >= 0.75 * top]             # ohne mitgefangene Hochziffer
    fx0, fy0 = min(c[0] for c in full), min(c[1] for c in full)
    fx1 = max(c[0] + c[2] for c in full)
    fy1 = max(c[1] + c[3] for c in full)
    fh = fy1 - fy0
    if fh > 1.3 * top or fx0 - g0 < 0.2 * fh or g1 - fx1 < 0.2 * fh:
        return None
    # dazu Punkt und Komma: kleine Teile am Fuß zwischen den Ziffern
    by1 = fy1
    for c in comps:
        if c[3] < 0.4 * fh and fx0 < c[0] and c[0] + c[2] < fx1 \
                and fy0 + 0.6 * fh <= c[1] and c[1] + c[3] <= fy1 + 0.3 * fh:
            by1 = max(by1, c[1] + c[3])
    fb = (fx0, fy0, fx1 - fx0, fh)
    sup = _superscript_box(rest, fb)
    return (fx0, fy0, fx1 - fx0, by1 - fy0), fb, sup[0] if sup else None


def line_gaps(bw: np.ndarray, px_per_mm: float) -> List[Tuple[Gap, int]]:
    """Schrift in Lücken waagrechter (k=0) und senkrechter Linien (k=1, liest von unten nach
    oben). Boxen im Originalbild."""
    out = [(g, 0) for g in _horizontal_gaps(bw, px_per_mm)]
    H = bw.shape[0]
    rot = np.ascontiguousarray(np.rot90(bw, -1))      # wie ocr.recognize, k=1
    for g in _horizontal_gaps(rot, px_per_mm):
        back = tuple(b and (b[1], H - (b[0] + b[2]), b[3], b[2]) for b in g[:3])
        out.append((back + g[3:], 1))
    return out


def _crop(bw: np.ndarray, gray: np.ndarray, box, k: int, height: int, side: int = 0) -> np.ndarray:
    """Schrift einer Box aus dem Graubild, auf height skaliert, lesbar gedreht. Tinte, die nicht
    in die Box reicht (Linienenden, Sterne, Nachbarzahlen im Rand), wird weiß – bei side ≠ 0 auch
    alles jenseits der Maßlinie (die zweite Zahl)."""
    import cv2
    x, y, w, h = box
    p = max(2, int(0.15 * (w if k else h)))
    x0, y0 = max(0, x - p), max(0, y - p)
    c = gray[y0:y + h + p, x0:x + w + p].copy()
    n, lab = cv2.connectedComponents(bw[y0:y + h + p, x0:x + w + p], connectivity=8)
    own = np.zeros(n, bool)
    own[np.unique(lab[y - y0:y - y0 + h, x - x0:x - x0 + w])] = True
    own[0] = False
    alien = ((lab > 0) & ~own[lab]).astype(np.uint8)
    c[(cv2.dilate(alien, np.ones((5, 5), np.uint8)) > 0) & ~own[lab]] = 255
    if side and k == 0:
        c[(y - y0 + h if side < 0 else 0):(None if side < 0 else y - y0)] = 255
    elif side:
        c[:, (x - x0 + w if side < 0 else 0):(None if side < 0 else x - x0)] = 255
    if k == 1:
        c = np.rot90(c, -1)
    f = height / max(1, c.shape[0])
    return cv2.resize(np.ascontiguousarray(c), (max(1, int(round(c.shape[1] * f))), height),
                      interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_CUBIC)


def read_gap_numbers(bw: np.ndarray, gray: np.ndarray, px_per_mm: float, s, run_lines=None):
    """Maßzahlen in Lücken der Maßlinie lesen. Gibt (Texte, Boxen x, y, w, h) zurück."""
    from . import textlines
    from .ocr import NUM_WHITELIST, SUPERSCRIPT
    gaps = line_gaps(bw, px_per_mm)
    if not gaps:
        return [], []
    LH = textlines.LINE_H
    crops = []
    for (b, _, sup, side, _s), k in gaps:
        c = _crop(bw, gray, b, k, LH, side)
        if sup is not None:
            # Hochziffer („4.17⁵“) in voller Größe dahinter: so liest Tesseract sie sicher
            c = np.hstack([c[:, :-2], _crop(bw, gray, sup, k, LH, side)])
        crops.append(c)
    res = (run_lines or textlines._tesseract_lines)(crops, s, NUM_WHITELIST)
    cand = []                       # (Text oder None, Rohlesung, Konfidenz) je Lücke
    for ((b, fb, sup, _, sg), k), (t, conf) in zip(gaps, res):
        raw = t = (t or "").replace(" ", "").replace(",", ".")
        high = ""
        if sup is not None and NUMBER.match(t[:-1]):      # letzte Ziffer ist die Hochziffer
            t, high = t[:-1], t[-1].translate(SUPERSCRIPT)
        ok = conf >= 75 and bool(NUMBER.match(t))
        if ok:
            # passt die Länge der Zahl zur Box? (sonst: Teil einer Zahl oder zwei aufeinander)
            w, h = (fb[2], fb[3]) if k == 0 else (fb[3], fb[2])
            want = h * DIGIT_W * (len(t) - 0.5 * t.count(".") - 0.15)
            ok = 0.75 <= w / want <= 1.25
        cand.append([t + high if ok else None, raw, conf])
    check_lengths(cand, [g for g, _ in gaps], [k for _, k in gaps])
    texts, boxes = [], []
    for ((b, fb, sup, side, sg), k), (t, _, _) in zip(gaps, cand):
        if t is None:
            continue
        if sup is not None and t[-1] not in SUP:          # war keine (Pfeilspitze, Linienrest)
            sup = None
        x, y, w, h = b
        if sup is not None:                               # Box mit Hochziffer
            x1, y1 = max(x + w, sup[0] + sup[2]), max(y + h, sup[1] + sup[3])
            x, y = min(x, sup[0]), min(y, sup[1])
            b = (x, y, x1 - x, y1 - y)
            w, h = b[2], b[3]
        height = float(fb[3] if k == 0 else fb[2])
        if k == 0:
            txt = Text(t, (float(x), float(fb[1] + fb[3])), height, 0.0)
        else:
            txt = Text(t, (float(fb[0] + fb[2]), float(y + h)), height, 90.0)
        if sg is not None and side == 0 and _mid(sg):
            txt.dim = _dim(txt, sg, k, bw.shape[0])
        texts.append(txt)
        boxes.append(b)
    return texts, boxes


def _mid(sg: Seg) -> bool:
    """Steht die Zahl in der Mitte ihres Maßsegments? (Sonst fehlt ein Stern dazwischen.)"""
    return abs(sg[3] - (sg[1] + sg[2]) / 2.0) <= 0.12 * (sg[2] - sg[1])


def _dim(t: Text, sg: Seg, k: int, H: int) -> Tuple[float, float, float]:
    """Maßlinie des Segments als Text.dim (in Texthöhen relativ zur Einfügung)."""
    cy, a, b = sg[:3]
    p0, p1 = ((a, cy), (b, cy)) if k == 0 else ((cy, H - a), (cy, H - b))   # k=1: zurückdrehen
    r = np.radians(t.angle)
    u, n = (np.cos(r), -np.sin(r)), (-np.sin(r), -np.cos(r))
    x, y, h = t.position[0], t.position[1], t.height

    def along(p, v):
        return float(((p[0] - x) * v[0] + (p[1] - y) * v[1]) / h)
    return along(p0, u), along(p1, u), along(p0, n)


def metres(t: str) -> Optional[float]:
    """Maßzahl in Meter: „6.70“ → 6.70, „74“ (cm) → 0.74, „88⁵“ → 0.885, „2.12⁵“ → 2.125."""
    plain = t.rstrip(SUP)
    high = t[len(plain):]
    if not NUMBER.match(plain) or len(high) > 1:
        return None
    v = float(plain) if "." in plain else float(plain) / 100
    if high:
        v += SUP.index(high) / 1000
    return v


def _variants(raw: str) -> List[str]:
    """Lesarten einer unsicheren Ziffernfolge: wie gelesen, Hochziffer als volle Ziffer gelesen
    („875“ → „87⁵“), Punkt verloren („245“ → „2.45“)."""
    sup = SUP
    out = [raw]
    d = raw.replace(".", "")
    if d.isdigit() and 3 <= len(d) <= 5:
        out += [raw[:-1] + sup[int(raw[-1])]] if len(raw) == 3 or "." in raw[:-1] else []
        out += [d[:-2] + "." + d[-2:]]
        out += [d[:-3] + "." + d[-3:-1] + sup[int(d[-1])]] if len(d) >= 4 else []
    return [v for v in dict.fromkeys(out) if metres(v) is not None]


def check_lengths(cand: list, gaps: list, ks: list) -> Optional[float]:
    """Maßzahlen gegen die Länge ihres Maßsegments prüfen (cand wird geändert).

    Der Maßstab (Pixel je Meter) ergibt sich aus den sicheren Lesungen selbst: richtige Maße
    stimmen auf ±1 % überein. Damit gilt je Segment, in dessen Mitte die Zahl steht:
    - unsichere Lesung (Konfidenz, Breite, Muster), Segment ≥ 1 m: genau eine Lesart passt auf
      ±1 % aufs Segment → nehmen („14.40“ mit Konfidenz 69, „1875“ → „1.87⁵“);
    - sichere Lesung, aber Segment kürzer als 0,67 × die Zahl → kann nicht stimmen → verwerfen.
    Ein zu langes Segment beweist nichts: Hat die Erkennung Sterne verpasst, umfasst es mehrere
    Teilmaße, und die Zahl kann zufällig mittig stehen („43⁵“ in 1,25 m). Teilmaße einer Kette
    ergeben so von selbst das Gesamtmaß. Zahlen über/unter der Linie (Breite und Höhe einer
    Öffnung) bleiben ungeprüft. Gibt den Maßstab zurück (oder None)."""
    rows = []                                   # (Index, Länge px, Lage in der Mitte)
    for i, (g, k) in enumerate(zip(gaps, ks)):
        sg = g[4]
        if sg is None or g[3] != 0:
            continue
        rows.append((i, sg[2] - sg[1], _mid(sg)))
    q = sorted(L / metres(cand[i][0]) for i, L, mid in rows if mid and cand[i][0] and metres(cand[i][0]))
    if len(q) < 5:
        return None
    r = q[len(q) // 2]
    if sum(abs(v / r - 1) <= 0.03 for v in q) < max(5, 0.5 * len(q)):
        return None                             # kein einheitlicher Maßstab (Skizze, Fehlerkennung)
    for i, L, mid in rows:
        if not mid:
            continue
        c = cand[i]
        if c[0] is not None:
            v = metres(c[0])
            if L < 0.67 * v * r:
                c[0] = None
            continue
        if c[2] < 50 or L < r:              # unter 1 m trennt 1 px schon 2 cm („85“ / „88⁵“)
            continue
        fit = [t for t in _variants(c[1]) if abs(L - metres(t) * r) <= max(1.5, 0.01 * L)]
        if len(fit) == 1:
            c[0] = fit[0]
    return r


_NUMLIKE = re.compile(r"^[0-9.,:;°\"'’”⁰¹²³⁴⁵⁶⁷⁸⁹ ]+$")


def merge(texts: list, boxes: list, new_texts: list, new_boxes: list) -> None:
    """Lückenzahlen in die OCR-Ergebnisse übernehmen (texts/boxes parallel, werden geändert).

    Liegt dort noch nichts: dazu. Liegt dort eine andere Zahlenlesung („144“, „6 03“): die
    Lückenzahl ersetzt sie – sie ist aus dem sauberen Ausschnitt gelesen und trägt ggf. ihre
    Maßlinie (DIMENSION). Wörter bleiben."""
    from .ocr import _overlap
    for t, b in zip(new_texts, new_boxes):
        hit = [i for i, o in enumerate(boxes) if _overlap(b, o) > 0.3]
        if any(not _NUMLIKE.match(texts[i].text) for i in hit):
            continue
        if t.dim is None and any(texts[i].text == t.text for i in hit):
            continue                                # gleiche Lesung schon da
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
