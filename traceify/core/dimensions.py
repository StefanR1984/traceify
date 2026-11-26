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
# links, rechts, Mitte der Zahl[, True bei kleinem Maß über engem Sternpaar]) oder None, wenn keine
# Sterne auf der Zeile die Zahl einschließen
Box = Tuple[int, int, int, int]
Seg = tuple
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
    hits = []                           # (zweiter Versuch?, Sterngröße, Bauteil, cx, cy, y der Waagrechten)
    for i in range(1, n):
        x, y, w, h, _ = st[i]
        if not (0.6 * px_per_mm <= max(w, h) <= 3.0 * px_per_mm) or abs(w - h) > 0.35 * max(w, h):
            continue
        cx, cy = int(round(cen[i][0])), int(round(cen[i][1]))
        if cx - r < 4 or cy - r < 4 or cx + r + 4 > W or cy + r + 4 > H:
            continue
        # Arme am Stern messen. Ohne Maßlinie („✳30✳“) ragen sie bei kleinen Sternen kaum über
        # den Schrägstrich hinaus, dessen Schwerpunkt oft 1 px neben dem Kreuz liegt: zweiter
        # Versuch mit kürzeren Armen, ±1 px, die Waagrechte höchstens 1 px vom Schwerpunkt (bei
        # „4“ und „2“ liegt der Schrägstrich über dem Querbalken bzw. Fuß) und alle Arme am Stern
        # selbst, nicht an der Nachbarziffer („4.17“)
        q0 = max(3, int(round(0.35 * px_per_mm)))
        rs, qs = max(3, min(r, int(0.35 * max(w, h)))), max(3, min(q0, int(0.3 * max(w, h))))
        for cx, rr, q, b in ((cx, r, q0, 2), (cx, rs, qs, 1), (cx - 1, rs, qs, 1), (cx + 1, rs, qs, 1)):
            # waagrechter und senkrechter Strich durch die Mitte, je beidseits
            rows = bw[cy - b:cy + b + 1, cx - rr:cx + rr + 1].all(axis=1)
            if not rows.any():
                continue
            # senkrecht um die gefundene Waagrechte: der Fuß einer „2“ hat darunter nichts
            yc = cy - b + int(round(np.nonzero(rows)[0].mean())) if b == 1 else cy
            m = max(rr, q) + 2
            wl = cv2.connectedComponents(bw[cy - m:cy + m + 1, cx - m:cx + m + 1], connectivity=8)[1]
            own = wl == wl[yc - cy + m, m] if b == 1 else wl > 0
            if not own[yc - cy + m - rr:yc - cy + m + rr + 1, m - 1:m + 2].any(axis=1).all():
                continue
            # der Schrägstrich läuft durch die Mitte: Tinte beidseits auf der Diagonale (nicht „4“)
            if any(own[m - sy * q - 1:m - sy * q + 2, m - q - 1:m - q + 2].any()
                   and own[m + sy * q - 1:m + sy * q + 2, m + q - 1:m + q + 2].any() for sy in (-1, 1)):
                hits.append((b == 1, max(w, h), i, cx, cy, cy - b + float(np.nonzero(rows)[0].mean())))
                break
    # zweiter Versuch nur in der Größe der sicher erkannten Sterne dieses Plans (± 15 %): sonst
    # trifft er Ziffern und Ecken größerer, fetter Schrift (1:200)
    sure = sorted(s for weak, s, *_ in hits if not weak)
    med = sure[len(sure) // 2] if len(sure) >= 5 else 0
    for weak, s, i, cx, cy, ty in hits:
        if weak and not 0.85 * med <= s <= 1.15 * med:
            continue
        x, y, w, h, _ = st[i]
        out.append((cx, ty))
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


def _weak_ticks(bw: np.ndarray, px_per_mm: float, ticks):
    """Sterne, die von Ziffern überdeckt sind („88⁵“ / „2.12⁵“ an einer Tür laufen durch den
    Stern) – die Formprüfung von _ticks scheitert dort am Zusammenhang mit den Ziffern. Gesucht
    wird nur auf Zeilen bekannter Sterne: Schrägstrich, waagrechter und senkrechter Strich durch
    denselben Punkt, Tinte beidseits auf der Diagonale. Findet auch Kreuzungen in Schraffuren –
    sie dienen nur als Ausgangspunkt für template_numbers, dessen Lage- und Längenprobe solche
    Fehlstellen aussortiert. Gibt eine Liste (cx, cy) zurück."""
    import cv2
    d = max(4, int(round(0.7 * px_per_mm)))
    k = np.eye(d, dtype=np.uint8)
    diag = cv2.morphologyEx(bw, cv2.MORPH_OPEN, k) | cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.fliplr(k))
    r = max(3, int(round(0.4 * px_per_mm)))
    q = max(3, int(round(0.35 * px_per_mm)))
    H, W = bw.shape
    dg = cv2.dilate(diag, np.ones((3, 3), np.uint8)).astype(bool)
    col = cv2.dilate(bw, np.ones((1, 3), np.uint8)).astype(bool)      # Spalten x-1 … x+1
    blob = cv2.dilate(bw, np.ones((3, 3), np.uint8)).astype(bool)

    def run(v):                                                       # v[x-r … x+r] alle wahr
        c = np.concatenate([[0], np.cumsum(~v)])
        o = np.zeros_like(v)
        o[r:W - r] = (c[2 * r + 1:] - c[:W - 2 * r]) == 0
        return o
    out = []
    for cy in sorted({int(round(cy)) for _, cy in ticks}):
        if cy - max(r, q) < 2 or cy + max(r, q) + 3 > H:
            continue
        ok = dg[cy] & col[cy - r:cy + r + 1].all(axis=0) & run(bw[cy - 1:cy + 2].any(axis=0).astype(bool))
        side = np.zeros(W, bool)
        for sy in (-1, 1):
            side[q:W - q] |= blob[cy - sy * q][:W - 2 * q] & blob[cy + sy * q][2 * q:]
        xs = np.nonzero(ok & side)[0]
        if not len(xs):
            continue
        for grp in np.split(xs, np.nonzero(np.diff(xs) > 2)[0] + 1):
            cx = float(grp.mean())
            if any(abs(cx - a) <= r and abs(cy - b) <= 3 for a, b in ticks):
                continue
            out.append((cx, float(cy)))
    return out


def _horizontal_gaps(bw: np.ndarray, px_per_mm: float, keep: Optional[list] = None, tk=None) -> List[Gap]:
    """Schrift in Lücken waagrechter Linien (Box der Schrift, Box der vollen Ziffern).

    Die Lücke liegt zwischen zwei Linienstücken oder zwei Maßbegrenzungen („✳74✳74✳“: Allplan
    lässt die Maßlinie bei kurzen Maßen ganz weg). tk: (Sterne, Maske) beider Richtungen und (Sterne,
    Maske) dieser Richtung aus line_gaps, sonst _ticks."""
    import cv2
    L = max(10, int(3.0 * px_per_mm))
    hor = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((1, L), np.uint8))
    n, _, st, _ = cv2.connectedComponentsWithStats(hor, connectivity=8)
    thin = max(3, int(round(0.6 * px_per_mm)))
    ticks, stars = _ticks(bw, px_per_mm) if tk is None else tk[:2]
    if keep is not None:                            # für template_numbers: eigene Sterne, Fremdtinte
        keep.append((ticks, stars | hor) if tk is None else (tk[2], tk[3] | hor))
    # Stern als Lückenende: nur die Mitte ± 0,15 mm – die Sterne sind aus rest entfernt, und die
    # Ziffern kleiner Maße („✳28✳“) reichen oft bis an die Arme
    rt = 0.15 * px_per_mm
    segs = sorted([(y + h / 2.0, x, x + w) for x, y, w, h, _ in st[1:] if h <= thin]
                  + [(cy, cx - rt, cx + rt) for cx, cy in ticks])
    rest = bw & (hor == 0) & (stars == 0)
    H, W = bw.shape
    h_min, h_max = 0.8 * px_per_mm, 7.0 * px_per_mm    # Allplan-cm-Maße sind 1 mm hoch
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
            # senkrechte Wand-/Hilfslinien durch die Zahl abziehen (länger als jede Ziffer, Rand = Papier),
            # sonst ist die Ziffer daran zu hoch und fehlt in der Zahl
            win = win & (cv2.morphologyEx(win, cv2.MORPH_OPEN, np.ones((int(4.0 * px_per_mm), 1), np.uint8),
                                          borderType=cv2.BORDER_CONSTANT, borderValue=0) == 0)
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
    # Partner eines Sterns, den _ticks nicht fand (sitzt auf einer Wand-/Hilfslinie): nur für kleine Maße über
    # dem Paar, die Längenprobe sortiert Kreuzungen in Schraffuren aus
    return out + _close_pairs(rest, ticks, out, _weak_ticks(bw, px_per_mm, ticks))


def _strip(bl: np.ndarray, r: int, h: float) -> np.ndarray:
    """Maske der Linien, die eine Zahl kreuzen: die waagrechte Maßlinie um Zeile r (ohne die Spalten, in
    denen ein Ziffernstrich sie quert – Tinte darüber und darunter) und senkrechte Striche länger als jede
    Ziffer (Hilfslinien, Wände). bl: Tinte (bool), Linie waagrecht."""
    import cv2
    L = max(10, int(1.5 * h))
    hor = cv2.morphologyEx(bl.astype(np.uint8), cv2.MORPH_OPEN, np.ones((1, L), np.uint8)).astype(bool)
    band = np.zeros_like(hor)
    band[max(0, r - 3):r + 4] = True
    hor &= band
    rows = np.nonzero(hor.any(axis=1))[0]
    if len(rows):
        r0, r1 = rows.min(), rows.max()
        hor &= ~(bl[max(0, r0 - 2):r0].any(axis=0) & bl[r1 + 1:r1 + 3].any(axis=0))[None, :]
    vl = int(1.6 * h)
    if bl.shape[0] <= vl:
        return hor
    # Rand = Papier, sonst gilt eine Ziffer am Rand als lang
    vert = cv2.morphologyEx((bl & ~hor).astype(np.uint8), cv2.MORPH_OPEN, np.ones((vl, 1), np.uint8),
                            borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(bool)
    return hor | vert


def _close_pairs(rest: np.ndarray, ticks, found: List[Gap], weak=()) -> List[Gap]:
    """Kleine Maße über zwei eng liegenden Sternen („24“ über „✳✳“): Die Zahl passt nicht
    dazwischen und steht darüber, oft breiter als das Paar und in Nachbarschrift, oder direkt
    daneben über der verlängerten Maßlinie. Gesucht werden Ziffern in Schrifthöhe der übrigen
    Maßzahlen, das Wort, das der Paarmitte bzw. dem Paarende am nächsten liegt.
    Zählt nur, wenn die Zahl zum Sternabstand passt (check_lengths). weak: schwache Sterne (_weak_ticks) –
    nur als Partner eines sicheren Sterns, dem auf dieser Seite bis 2,5 h kein sicherer folgt."""
    import cv2
    hs = sorted(g[1][3] for g in found if g[3] == 0)
    if len(hs) < 3:
        return []
    h = hs[len(hs) // 2]                        # Ziffernhöhe der Maßzahlen in diesem Plan
    H, W = rest.shape
    rows = {}
    for x, y in sorted(ticks, key=lambda t: t[1]):
        key = next((k for k in rows if abs(k - y) <= 2.5), y)
        rows.setdefault(key, []).append(x)
    out = []
    pairs = []
    for cy, xs in rows.items():
        xs.sort()
        pairs += [(cy, a, b) for a, b in zip(xs, xs[1:])]
        # Maß von 1–2 cm („1⁵“ an der Wand): beide Sterne verschmelzen zu einem, Länge 0
        pairs += [(cy, a, a) for a in xs]
        for wx, wy in weak:
            if abs(wy - cy) > 2.5:
                continue
            for a in xs:
                lo, hi = sorted((a, wx))
                if 0.3 * h <= hi - lo <= 2.5 * h and not any(lo < x < hi or 0 < abs(x - a) <= 2.5 * h
                                                            and (x - a) * (wx - a) > 0 for x in xs):
                    pairs.append((cy, lo, hi))
    for cy, a, b in pairs:
        # zwei Ziffern hätten dazwischen keinen Platz (bis 2,5 h: „12⁵“ ist breiter als 2 Ziffern)
        if a != b and not 0.3 * h <= b - a <= 2.5 * h:
            continue
        c = (a + b) / 2.0
        x0, x1 = max(0, int(a - 3 * h)), min(W, int(b + 3 * h))
        y0, y1 = max(0, int(cy - 2.4 * h)), int(cy) - 1
        win = rest[y0:y1, x0:x1]
        # Maßhilfslinien laufen senkrecht durchs Fenster und kleben an der Zahl daneben („12“ → Ziffer
        # 2,3 h hoch, fällt aus der Wortbildung): Striche länger als jede Ziffer abziehen
        vl = int(1.6 * h)
        if win.shape[0] > vl:
            # Rand = Papier, sonst gilt eine Ziffer am Fensterrand („1“ bis zur Maßlinie) als lang
            win = win & (cv2.morphologyEx(win, cv2.MORPH_OPEN, np.ones((vl, 1), np.uint8),
                                          borderType=cv2.BORDER_CONSTANT, borderValue=0) == 0)
        n, _, st, _ = cv2.connectedComponentsWithStats(win, connectivity=8)
        comps = [(x + x0, y + y0, w, hh) for x, y, w, hh, ar in st[1:] if ar >= 2]
        # Wörter: Ziffern einer Zeile mit kleinem Abstand
        words: list = []
        for q in sorted((q for q in comps if 0.75 * h <= q[3] <= 1.3 * h), key=lambda q: q[0]):
            for wd in words:
                p = wd[-1]
                if abs(q[1] + q[3] - p[1] - p[3]) <= 0.2 * h and q[0] - (p[0] + p[2]) < 0.4 * h:
                    wd.append(q)
                    break
            else:
                words.append([q])
        # die Zahl steht mittig über dem Paar oder – Allplan verlängert dafür die Maßlinie –
        # direkt daneben über der Linie; die nächste gewinnt
        best = None
        for wd in words:
            wx0, wx1 = wd[0][0], wd[-1][0] + wd[-1][2]
            if abs((wx0 + wx1) / 2.0 - c) <= 0.6 * h:
                dd = abs((wx0 + wx1) / 2.0 - c)
            elif -0.2 * h <= wx0 - b <= 1.5 * h:
                dd = h + wx0 - b
            elif -0.2 * h <= a - wx1 <= 1.5 * h:
                dd = h + a - wx1
            else:
                continue
            dd += abs(cy - max(q[1] + q[3] for q in wd))
            if best is None or dd < best[0]:
                best = (dd, wd)
        if best is None:
            continue
        word = best[1]
        gx0 = word[0][0] - int(0.3 * h)
        gx1 = word[-1][0] + word[-1][2] + int(0.3 * h)
        g = _number(word, comps, rest, gx0, gx1)
        if g is None:
            continue
        out.append(g + (-1, (cy, a, b, g[1][0] + g[1][2] / 2.0, True)))
    # ein Wort, das schon ein echtes Paar hat, nicht zusätzlich als Einzelstern
    taken = {g[1] for g in out if g[4][1] != g[4][2]}
    return [g for g in out if g[4][1] != g[4][2] or g[1] not in taken]


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


def _join_ticks(own: list, other: list, d: float = 3.0) -> list:
    """Sterne der eigenen Richtung plus die der anderen, die nicht schon dabei sind (Abstand > d)."""
    return list(own) + [p for p in other if all(abs(p[0] - q[0]) > d or abs(p[1] - q[1]) > d for q in own)]


def line_gaps(bw: np.ndarray, px_per_mm: float, keep: Optional[list] = None) -> List[Tuple[Gap, int]]:
    """Schrift in Lücken waagrechter (k=0) und senkrechter Linien (k=1, liest von unten nach
    oben). Boxen im Originalbild. keep sammelt je Richtung (Sterne, Maske Sterne + Linien)."""
    H = bw.shape[0]
    rot = np.ascontiguousarray(np.rot90(bw, -1))      # wie ocr.recognize, k=1
    # Sterne beider Richtungen teilen: _ticks verlangt beide Linien beidseits des Sterns, am
    # Kettenende oder an einseitiger Hilfslinie findet ihn nur die Richtung, in der die
    # durchgehende Linie waagrecht liegt – die Lückensuche der anderen braucht ihn aber auch
    t0, s0 = _ticks(bw, px_per_mm)
    t1, s1 = _ticks(rot, px_per_mm)
    t0r = [(H - 1 - y, x) for x, y in t0]            # Original → gedreht
    t1o = [(y, H - 1 - x) for x, y in t1]            # gedreht → Original
    # template_numbers (Türmaße) bleibt bei den eigenen Sternen – mit den geteilten verlor es „88⁵“
    out = [(g, 0) for g in _horizontal_gaps(bw, px_per_mm, keep,
                                            (_join_ticks(t0, t1o), s0 | np.rot90(s1, 1), t0, s0))]
    for g in _horizontal_gaps(rot, px_per_mm, keep,
                              (_join_ticks(t1, t0r), s1 | np.ascontiguousarray(np.rot90(s0, -1)), t1, s1)):
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
    # Maßlinie, die an die Ziffern stößt oder durch sie läuft (Lücke schmaler als die Zahl), und kreuzende
    # Hilfslinien weiß – an „—1.35—“ scheitert Tesseract. `_strip` nimmt nur Läufe länger als jede Ziffer;
    # gesucht in einem um eine Ziffernhöhe größeren Fenster.
    hd = h if k == 0 else w
    e = int(hd)
    Y0, X0 = (max(0, y - e), x0) if k == 0 else (y0, max(0, x - e))
    bl = bw[Y0:(y + h + e if k == 0 else y + h + p), X0:(x + w + p if k == 0 else x + w + e)] > 0
    if k:
        bl = bl.T
    o = (y - Y0) if k == 0 else (x - X0)
    mid = bl[o + int(0.25 * hd):o + int(0.75 * hd) + 1]
    if mid.size and mid.shape[1]:
        m = _strip(bl, o + int(0.25 * hd) + int(np.argmax(mid.mean(axis=1))), hd)
        if k:
            m = m.T
        sub = m[y0 - Y0:y0 - Y0 + c.shape[0], x0 - X0:x0 - X0 + c.shape[1]]
        c[:sub.shape[0], :sub.shape[1]][sub] = 255
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
    keep: list = []
    gaps = line_gaps(bw, px_per_mm, keep)
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
        # Punkt am Rand = Rest von Maßlinie/Pfeilspitze („2.45.“), nie Hochziffer oder Teil der Zahl
        raw = t = (t or "").replace(" ", "").replace(",", ".").strip(".")
        high = ""
        two = sup is not None and (sup[2] if k == 0 else sup[3]) > 0.9 * (sup[3] if k == 0 else sup[2])
        if two and NUMBER.match(t[:-2]) and t[-2:].isdigit():   # „14⁷⁵“: zweistellige Hochziffer
            t, high = t[:-2], t[-2:].translate(SUPERSCRIPT)
        elif sup is not None and (NUMBER.match(t[:-1]) or len(t) == 2 and t.isdigit() and sg is not None
                                  and len(sg) == 5):      # letzte Ziffer ist die Hochziffer („9⁵“ nur über Sternpaar)
            # einstellige Hochziffer an Maßen ist immer ⁵ (halbe Zentimeter); klein gedruckt liest
            # Tesseract sie oft als 9, 2, 6 oder 1
            t, high = t[:-1], "⁵"
        # einstellig („5“) nur über engem Sternpaar: dort prüft check_lengths die Länge
        ok = conf >= 75 and bool(NUMBER.match(t) or sg is not None and len(sg) == 5 and re.fullmatch(r"\d", t))
        if ok:
            # passt die Länge der Zahl zur Box? (sonst: Teil einer Zahl oder zwei aufeinander)
            w, h = (fb[2], fb[3]) if k == 0 else (fb[3], fb[2])
            # die „1“ ist in vielen Schriften schmal (Allplan: „81“, „41“, „1.01“ lagen bei 0,70–0,75 und
            # fielen durch), in anderen nicht – beide Sollbreiten gelten
            n = len(t) - 0.5 * t.count(".") - 0.15
            ok = any(0.75 <= w / (h * DIGIT_W * m) <= 1.25 for m in {n, n - 0.3 * t.count("1")})
        cand.append([t + high if ok else None, raw, conf])
    r = check_lengths(cand, [g for g, _ in gaps], [k for _, k in gaps])
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
    if r:
        _door_numbers(bw, px_per_mm, gaps, cand, keep, r, texts, boxes)
    return texts, boxes


def _door_numbers(bw, px_per_mm, gaps, cand, keep, r, texts, boxes) -> None:
    """Türmaße (template_numbers) in beiden Richtungen lesen und an texts/boxes anhängen, wo
    noch keine Lückenzahl steht."""
    from .ocr import _overlap
    tpl, heights = digit_templates(bw, gaps, cand)
    if len(tpl) < 8 or "5" not in tpl or not heights:
        return
    H = bw.shape[0]
    found = []
    for k, (ticks, alien) in enumerate(keep):
        img = bw if k == 0 else np.ascontiguousarray(np.rot90(bw, -1))
        # Seiten eines Sterns, an denen schon eine gelesene Maßzahl ihr Segment füllt
        done = [(sg[j], sg[0], dr) for (g, kk), c in zip(gaps, cand) for sg in [g[4]]
                if kk == k and c[0] and sg is not None and g[3] == 0 for j, dr in ((1, 1), (2, -1))]
        weak = _weak_ticks(img, px_per_mm, ticks)       # von Ziffern überdeckte Sterne
        for t, (x, y, w, h), hs, sc, key in template_numbers(img, ticks, alien, px_per_mm, tpl, heights, r,
                                                             done, weak):
            if k == 0:
                found.append((sc, Text(t, (float(x), float(y + h)), float(hs), 0.0), (x, y, w, h), (k, key)))
            else:                                    # zurückdrehen wie line_gaps
                b = (y, H - (x + w), h, w)
                found.append((sc, Text(t, (float(b[0] + b[2]), float(b[1] + b[3])), float(hs), 90.0), b, (k, key)))
    n0, keys = len(boxes), []
    for sc, t, b, key in sorted(found, key=lambda f: -f[0]):
        # Breite und Höhe derselben Tür überlappen sich oft – nur gegen Fremdes prüfen
        if not any(_overlap(b, o) > 0.3 and (i < n0 or keys[i - n0] != key) for i, o in enumerate(boxes)):
            texts.append(t)
            boxes.append(b)
            keys.append(key)


TPL_H = 32          # Höhe der Ziffern-Schablonen


def digit_templates(bw: np.ndarray, gaps: list, cand: list):
    """Ziffern-Schablonen aus den sicher gelesenen Maßzahlen dieses Plans (gleiche Schrift):
    ({Ziffer: Mittelbild, Höhe TPL_H, Werte 0..1}, vorkommende Ziffernhöhen in px)."""
    import cv2
    samples, hs = {}, []
    for ((_b, fb, _sup, side, _sg), k), c in zip(gaps, cand):
        if c[0] is None or side != 0:
            continue
        plain = c[0].rstrip(SUP).replace(".", "")
        x, y, w, h = fb
        win = bw[y:y + h, x:x + w]
        win = np.ascontiguousarray(np.rot90(win, -1) if k else win)
        _, _, st, _ = cv2.connectedComponentsWithStats(win, connectivity=8)
        full = sorted((q for q in st[1:] if q[3] >= 0.75 * win.shape[0]), key=lambda q: q[0])
        if len(full) != len(plain):                  # verschmolzene oder zerrissene Ziffern
            continue
        hs.append(win.shape[0])
        for ch, (cx, cy, cw, chh, _) in zip(plain, full):
            samples.setdefault(ch, []).append(win[cy:cy + chh, cx:cx + cw].astype(np.float32))
    tpl = {}
    for ch, L in samples.items():
        w = max(2, int(round(np.median([q.shape[1] * TPL_H / q.shape[0] for q in L]))))
        tpl[ch] = np.mean([cv2.resize(q, (w, TPL_H), interpolation=cv2.INTER_AREA) for q in L], axis=0)
    groups = []                                      # Höhengruppen (Türmaße sind oft kleiner)
    for h in sorted(hs):
        if not groups or h > 1.15 * groups[-1][0]:
            groups.append([h, 0])
        groups[-1][1] += 1
    return tpl, [h for h, n in groups if n >= 2]     # kleinste Höhe der Gruppe: Unschärfe macht größer


def _scaled(t: np.ndarray, hs: float) -> np.ndarray:
    import cv2
    w = max(2, int(round(t.shape[1] * hs / TPL_H)))
    return (cv2.resize(t, (w, max(3, int(round(hs)))), interpolation=cv2.INTER_AREA) > 0.4).astype(np.float32)


def _match(I: np.ndarray, W: np.ndarray, t: np.ndarray) -> np.ndarray:
    """Überdeckung Schablone/Tinte an jeder Stelle: Tinte auf der Schablone geteilt durch
    (Schablone + Tinte daneben). Wo W = 0 ist (bekannte Fremdtinte: Stern, Linie), zählt nichts."""
    import cv2
    bg = 1 - cv2.dilate(t, np.ones((3, 3), np.uint8))
    Iw = I * W
    vis = cv2.matchTemplate(W, t, cv2.TM_CCORR)
    sc = cv2.matchTemplate(Iw, t, cv2.TM_CCORR) / (vis + cv2.matchTemplate(Iw, bg, cv2.TM_CCORR) + 1e-3)
    sc[vis < 0.5 * t.sum()] = -1                     # Schablone überwiegend verdeckt
    return sc


def _digit_maps(I, W, tp):
    """Je Ziffer der Wert an jeder Zellenlage (Zelle = breiteste Ziffer, Ziffer mittig; ±1 px Spiel)."""
    import cv2
    cw = max(t.shape[1] for t in tp.values())
    hh = next(iter(tp.values())).shape[0]
    M = np.full((10, I.shape[0] - hh + 1, I.shape[1] - cw + 1), -1.0, np.float32)
    for ch, tb in tp.items():
        t = np.zeros((hh, cw), np.float32)
        pad = (cw - tb.shape[1]) // 2
        t[:, pad:pad + tb.shape[1]] = tb
        if cv2.matchTemplate(I, t, cv2.TM_CCORR).max() < 0.5 * tb.sum():
            continue                                 # nirgends genug Tinte für diese Ziffer (Zeit)
        M[int(ch)] = cv2.dilate(_match(I, W, t), np.ones((3, 3), np.uint8))
    return M, cw


def _read_band(M, pitch: float, dot: bool):
    """Beste Ziffernfolge je Startstelle im Format „dd“ oder „d.dd“ (feste Ziffernbreite):
    (Mittelwert, kleinster Ziffernwert, beste Ziffer, Abstand zur zweitbesten, Zellenlagen)."""
    offs = [int(round(o * pitch)) for o in ((0, 1.5, 2.5) if dot else (0, 1))]
    srt = np.sort(M, axis=0)
    best, marg, arg = srt[-1], srt[-1] - srt[-2], M.argmax(axis=0)
    W = best.shape[1] - offs[-1]
    if W <= 0:
        return None
    cells = np.stack([best[:, o:o + W] for o in offs])
    return cells.mean(axis=0), cells.min(axis=0), arg, marg, offs


def _sup5(I, W, t5, hs, xe: int, top: int) -> float:
    """Hochgestellte 5 rechts oben an der Zahl (xe = rechtes Ende, top = Oberkante): bester Wert."""
    x0, y0 = int(xe - 0.1 * hs), int(top - 0.4 * hs)
    x1, y1 = int(xe + 0.85 * hs), int(top + 0.6 * hs)
    best = -1.0
    if x0 < 0 or y0 < 0 or x1 > I.shape[1] or y1 > I.shape[0]:
        return best
    for f in (0.5, 0.6, 0.7):
        t = _scaled(t5, max(5.0, f * hs))
        if t.shape[0] < y1 - y0 and t.shape[1] < x1 - x0:
            best = max(best, float(_match(I[y0:y1, x0:x1], W[y0:y1, x0:x1], t).max()))
    return best


def template_numbers(bw: np.ndarray, ticks, alien: np.ndarray, px_per_mm: float, tpl: dict,
                     heights, r: float, done=(), extra=()) -> list:
    """Türmaße an einer Maßbegrenzung per Schablonenabgleich lesen: Breite direkt über der
    Maßlinie („88⁵“, „1.01“), Höhe direkt darunter („2.12⁵“). Die Zahlen berühren sich, laufen
    über den zweiten Stern und in Wände – Tesseract liest dort nichts, und der zweite Stern wird
    nicht als Stern erkannt. Darum von einem bekannten Stern aus (nach beiden Seiten):

    - Ziffern der Planschrift (tpl aus digit_templates) über der Linie abgleichen;
    - die gelesene Breite muss zur Lage passen: Zahl mittig zwischen dem Stern und der Stelle
      im Abstand Breite × r (px je Meter), dort ein Strich quer durch die Maßlinie;
    - dann die Höhe unter der Linie im Format „d.dd“; der vermutete zweite Stern zählt nicht mit.

    alien: bekannte Fremdtinte (Sterne, Linien); done: (x, Zeile, Seite ±1) – Sternseiten, die
    schon ein gelesenes Maß haben und nicht abgesucht werden; extra: zusätzliche, unsichere
    Ausgangspunkte (_weak_ticks), zählen nicht als „Stern dazwischen“. Gibt (Text, Box x y w h, Ziffernhöhe, Wert)
    und Schlüssel des Sternpaars – Breite und Höhe einer Tür dürfen sich überlappen) zurück;
    nur deutliche Treffer (Überdeckung und Abstand zur zweitbesten Ziffer)."""
    import cv2
    H, Wd = bw.shape
    I = bw.astype(np.float32)
    Wt = (alien == 0).astype(np.float32)
    rr = max(3, int(round(0.4 * px_per_mm)))
    e = np.eye(max(4, int(round(0.7 * px_per_mm))), dtype=np.uint8)
    out = []
    T = np.array(ticks, float).reshape(-1, 2)
    open_ = {}                                       # Stern → noch offene Seiten
    row = -9
    for tx, cy in sorted(list(ticks) + list(extra), key=lambda t: t[1]):
        sides = [dr for dr in (1, -1) if not any(x == tx and abs(y - cy) <= 2.5 and q == dr for x, y, q in done)]
        if int(round(cy)) - row > 1:                 # Sterne einer Kette (±1 px) teilen sich die Zeile
            row = int(round(cy))
        if sides:
            open_[int(round(tx)), row] = sides

    def emit(s, x0, top, w, hs, sc, key):
        if _sup5(I, Wt, tpl["5"], hs, x0 + w, top) >= 0.75:
            out.append((s + "⁵", (x0, top - int(0.3 * hs), w + int(0.5 * hs), hs + int(0.3 * hs)), hs, sc, key))
        else:
            out.append((s, (x0, top, w, hs), hs, sc, key))
    for hs in heights:
        tp = {ch: _scaled(t, hs) for ch, t in tpl.items()}
        pitch = DIGIT_W * hs
        ext = int(1.7 * r) + 2 * hs
        rows = {}                                    # Zeile → Sterne; Nachbarn teilen sich den Abgleich
        for tx, cy in open_:
            rows.setdefault(cy, []).append(tx)
        found = {}                                   # (tx, cy) → bester Treffer über der Linie
        for cy, xs in rows.items():
            ya, yb = cy - 5 - hs, cy + 1             # Fuß der Ziffern 0–4 px über der Linienmitte
            if ya < hs or yb + 2 * hs >= H:
                continue
            # abzusuchende Abschnitte: je offener Seite vom Stern aus, überlappende zusammen
            runs = []
            for a, b, tx in sorted((min(tx - dr * 2 * hs, tx + dr * ext), max(tx - dr * 2 * hs, tx + dr * ext), tx)
                                   for tx in xs for dr in open_[tx, cy]):
                if runs and a <= runs[-1][1]:
                    runs[-1][1] = max(runs[-1][1], b)
                    runs[-1][2].add(tx)
                else:
                    runs.append([a, b, {tx}])
            for xa, xb, run in runs:
                xa, xb = max(0, xa), min(Wd, xb)
                up = slice(ya, cy - hs // 2 - 2), slice(xa, xb)
                if (I[up] * Wt[up]).sum() < 0.12 * hs * hs:
                    continue                         # nichts ganz über der Linie (Zahl auf der Linie: Zeit)
                M, cw = _digit_maps(I[ya:yb, xa:xb], Wt[ya:yb, xa:xb], tp)
                for dot in (False, True):
                    rb = _read_band(M, pitch, dot)
                    if rb is None:
                        continue
                    sc, mn, arg, marg, offs = rb
                    for y, x in zip(*np.nonzero((sc >= 0.75) & (mn >= 0.65)
                                                & (sc == cv2.dilate(sc, np.ones((3, 5), np.uint8))))):
                        s = "".join(str(int(arg[y, x + o])) for o in offs)
                        s = s[0] + "." + s[1:] if dot else s
                        v = metres(s)
                        m = min(float(marg[y, x + o]) for o in offs)
                        if not v or v < 0.4 or (m < 0.09 and sc[y, x] < 0.85):
                            continue
                        left = (slice(ya + y, ya + y + hs), slice(max(0, xa + x - cw), xa + x))
                        if (I[left] * Wt[left]).mean() > 0.4:
                            continue                                     # Zahlenhaufen, Schrift davor
                        mid = xa + x + (offs[-1] + cw) / 2.0             # Mitte der Ziffern
                        for tx in run:
                            dr = 1 if mid > tx else -1
                            far = tx + dr * v * r
                            fi = int(round(far))
                            if dr not in open_[tx, cy] or abs(mid - (tx + far) / 2.0) > 0.2 * hs + 2 or not 3 <= fi < Wd - 3:
                                continue
                            if not bw[cy - rr:cy + rr + 1, fi - 2:fi + 3].any(axis=1).all():
                                continue                                 # kein Strich am anderen Ende
                            lo, hi = min(tx, far) + 3, max(tx, far) - 3
                            if ((abs(T[:, 1] - cy) <= 2.5) & (T[:, 0] > lo) & (T[:, 0] < hi)).any():
                                continue                                 # Sterne dazwischen
                            if (tx, cy) not in found or sc[y, x] > found[tx, cy][0]:
                                found[tx, cy] = (float(sc[y, x]), s, xa + int(x), ya + int(y), offs[-1] + cw, far)
        for (tx, cy), best in found.items():
            sc0, s, x0, top, w, far = best
            emit(s, x0, top, w, hs, sc0, (tx, cy, hs))
            # Höhe unter der Linie; sie ragt bei kleiner Schrift bis über die Linie
            a, b = sorted((tx, int(round(far))))
            xa, xb = a - 2 * hs, b + 4 * hs
            ya, yb = cy - int(0.5 * hs), cy + hs + 7
            if xa < 0 or xb >= Wd:
                continue
            Wb = Wt[ya:yb, xa:xb].copy()
            fx, fy = int(round(far)) - xa, cy - ya
            cv2.line(Wb, (fx, fy - rr - 2), (fx, fy + rr + 2), 0, 3)        # zweiter Stern: Strich
            sl = (slice(max(0, fy - 3 * rr), fy + 3 * rr), slice(max(0, fx - 3 * rr), fx + 3 * rr))
            win = np.ascontiguousarray(bw[ya:yb, xa:xb][sl])
            dg = cv2.morphologyEx(win, cv2.MORPH_OPEN, e) | cv2.morphologyEx(win, cv2.MORPH_OPEN, np.fliplr(e))
            Wb[sl][cv2.dilate(dg, np.ones((3, 3), np.uint8)) > 0] = 0      # … und Schrägstrich
            Wb[fy - 1:fy + 2, a - xa:b - xa] = 0                           # Maßlinie dazwischen
            M, cw = _digit_maps(I[ya:yb, xa:xb], Wb, tp)
            rb = _read_band(M, pitch, True)
            if rb is None:
                continue
            sc, mn, arg, marg, offs = rb
            y, x = np.unravel_index(int(np.argmax(sc)), sc.shape)
            if sc[y, x] >= 0.8 and mn[y, x] >= 0.7 and min(marg[y, x + o] for o in offs) >= 0.05:
                s = "".join(str(int(arg[y, x + o])) for o in offs)
                emit(s[0] + "." + s[1:], xa + int(x), ya + int(y), offs[-1] + cw, hs, float(sc[y, x]),
                     (tx, cy, hs))
    return out


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


def scale_from_dims(texts, mm_per_px: float) -> Optional[float]:
    """Zeichnungsmaßstab N (für 1:N) aus den Maßzahlen mit erkannter Maßlinie (Text.dim):
    Länge der Maßlinie in Papier-mm gegen den Wert in Metern. Nur wenn mindestens fünf Maße auf
    ±3 % übereinstimmen und das Ergebnis auf ±3 % ein üblicher Maßstab ist, sonst None."""
    import math
    from .scale_detect import COMMON
    q = sorted(math.dist(*t.dim_points()) / metres(t.text) for t in texts
               if getattr(t, "dim", None) and metres(t.text))
    if len(q) < 5 or mm_per_px <= 0:
        return None
    r = q[len(q) // 2]                          # Pixel je Meter
    if sum(abs(v / r - 1) <= 0.03 for v in q) < max(5, 0.5 * len(q)):
        return None
    n = 1000.0 / (r * mm_per_px)
    best = min(COMMON, key=lambda c: abs(c / n - 1))
    return float(best) if abs(best / n - 1) <= 0.03 else None


def metres(t: str) -> Optional[float]:
    """Maßzahl in Meter: „6.70“ → 6.70, „74“ (cm) → 0.74, „88⁵“ → 0.885, „2.12⁵“ → 2.125."""
    plain = t.rstrip(SUP)
    high = t[len(plain):]
    if not (NUMBER.match(plain) or re.fullmatch(r"\d", plain)) or len(high) > 2:
        return None
    v = float(plain) if "." in plain else float(plain) / 100
    if high:                                    # Millimeter: „⁵“ = 5 mm, „⁷⁵“ = 7,5 mm
        v += int("".join(str(SUP.index(c)) for c in high)) / 10 ** (2 + len(high))
    return v


def _variants(raw: str) -> List[str]:
    """Lesarten einer unsicheren Ziffernfolge: wie gelesen, Hochziffer als volle Ziffer gelesen
    („875“ → „87⁵“; als Hochziffer an Maßen gibt es nur ⁵, „1119“ → „1.11⁵“), Punkt verloren
    („245“ → „2.45“)."""
    raw = raw.strip(".")                        # Punkt am Rand = Rest von Maßlinie/Pfeilspitze („2.45.“)
    out = [raw]
    d = raw.replace(".", "")
    if d.isdigit() and 3 <= len(d) <= 5:
        out += [raw[:-1] + "⁵"] if len(raw) == 3 or "." in raw[:-1] else []
        out += [d[:-2] + "." + d[-2:]]
        out += [d[:-3] + "." + d[-3:-1] + "⁵"] if len(d) >= 4 else []
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
        if sg is None or (g[3] != 0 and len(sg) < 5):
            continue
        rows.append((i, sg[2] - sg[1], _mid(sg) and len(sg) < 5))
    q = sorted(L / metres(cand[i][0]) for i, L, mid in rows if mid and cand[i][0] and metres(cand[i][0]))
    r = q[len(q) // 2] if len(q) >= 5 else None
    if r is not None and sum(abs(v / r - 1) <= 0.03 for v in q) < max(5, 0.5 * len(q)):
        r = None                                # kein einheitlicher Maßstab (Skizze, Fehlerkennung)
    # kleines Maß über zwei engen Sternen: nur, wenn es zum Abstand passt (1 px ≈ 2 cm Spiel)
    for i, (g, k) in enumerate(zip(gaps, ks)):
        sg, c = g[4], cand[i]
        if sg is None or len(sg) < 5:
            continue
        L = sg[2] - sg[1]
        ts = [c[0]] if c[0] else _variants(c[1]) if c[2] >= 50 else []
        if L == 0:                              # verschmolzenes Paar: nur „1⁵“–„3⁵“, „15“ ist dort „1⁵“
            ts = [t[0] + "⁵" for t in ts if t and re.fullmatch(r"[1-3][5⁵]", t)]
        fits = [t for t in ts if r is not None and abs(L - metres(t) * r) <= (3.5 if L == 0 else max(2.5, 0.1 * L))]
        c[0] = fits[0] if len(fits) == 1 else None
        if c[0] and c[0][-1] in SUP and c[0][-1] != "⁵":
            c[0] = c[0][:-1]                    # halbe Zentimeter: fast immer ⁵, sonst Nachbarschrift
    if r is None:
        return None
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


_SPACED = re.compile(r"^(\d) (\d\d)[°⁵]$")         # „2 75°“: Punkt als Lücke, Hochziffer als „°“
_DIM_M = re.compile(r"^\d{1,2}\.\d{2}[⁰¹²³⁴⁵⁶⁷⁸⁹]?$")


def _stacked(t: Text, o: Text) -> bool:
    """o steht direkt über oder unter t (gleiche Richtung, fast gleicher Anfang)."""
    import math
    if abs((t.angle - o.angle + 180) % 360 - 180) > 2:
        return False
    a = math.radians(t.angle)
    dx, dy = o.position[0] - t.position[0], o.position[1] - t.position[1]
    x = (dx * math.cos(a) - dy * math.sin(a)) / t.height
    y = (-dx * math.sin(a) - dy * math.cos(a)) / t.height
    return abs(x) <= 1.5 and 0.8 <= abs(y) <= 2.0


def tidy_numbers(texts: list) -> int:
    """Allplan-Maße, deren Dezimalpunkt im Scan verloren ging (texts wird geändert).

    - „2 75°“ → „2.75⁵“ (Punkt als Lücke gelesen, Hochziffer als Gradzeichen);
    - Türmaß-Paar „1.01“ über „2.40“ (Breite/Höhe der Öffnung): eine dreistellige Zahl direkt
      über/unter einem Maß „d.dd“ wird „d.dd“, wenn das Paar eine Tür ergibt – Breite 0,55–1,5 m,
      Höhe 1,9–3,0 m. Andere dreistellige Zahlen (Höhen, Nummern) bleiben.
    Gibt die Zahl der Änderungen zurück."""
    n = 0
    for t in texts:
        m = _SPACED.match(t.text)
        if m:
            t.text = f"{m.group(1)}.{m.group(2)}⁵"
            n += 1
    for t in texts:
        if not re.fullmatch(r"\d{3}", t.text):
            continue
        v = int(t.text) / 100
        for o in texts:
            # beide Richtungen: die OCR-Höhe einer Zahl ist oft zu klein („101“ 9,6 statt 14 px)
            if o is t or not _DIM_M.match(o.text) or not (_stacked(t, o) or _stacked(o, t)):
                continue
            w = metres(o.text)
            if w is not None and (0.55 <= v <= 1.5 and 1.9 <= w <= 3.0 or 0.55 <= w <= 1.5 and 1.9 <= v <= 3.0):
                t.text = f"{t.text[0]}.{t.text[1:]}"
                n += 1
                break
    return n


_NUMLIKE = re.compile(r"^[0-9.,:;°\"'’”⁰¹²³⁴⁵⁶⁷⁸⁹ ]+$")


def _garbage(s: str, lex) -> bool:
    """Fehllesung statt Wort? Ziffern mit Fremdzeichen („+42“, „S69“, „962%“, „sve 9“) oder höchstens drei
    Buchstaben („Las“, „ar,“) – ohne Wort darin: Planbegriff, ≥ 4 Buchstaben oder Abkürzung in Großbuchstaben
    („0.21a Flur“, „Bad“, „WC“ bleiben)."""
    toks = re.findall(r"[A-Za-zÄÖÜäöüß]{2,}", s)
    if not re.search(r"\d", s) and sum(map(len, toks)) > 3:
        return False
    return not any(w in lex or len(w) >= 4 or w.isupper() for w in toks)


def merge(texts: list, boxes: list, new_texts: list, new_boxes: list) -> None:
    """Lückenzahlen in die OCR-Ergebnisse übernehmen (texts/boxes parallel, werden geändert).

    Liegt dort noch nichts: dazu. Liegt dort eine andere Zahlenlesung („144“, „6 03“): die
    Lückenzahl ersetzt sie – sie ist aus dem sauberen Ausschnitt gelesen und trägt ggf. ihre
    Maßlinie (DIMENSION). Wörter bleiben."""
    from .ocr import _overlap
    lex = None
    for t, b in zip(new_texts, new_boxes):
        hit = [i for i, o in enumerate(boxes) if _overlap(b, o) > 0.3]
        if any(not _NUMLIKE.match(texts[i].text) for i in hit):
            if t.dim is None:
                continue
            if lex is None:
                from .lexicon import Lexicon
                lex = Lexicon()
            # mittig in der Maßlinie gelesen: Unsinn der Seiten-OCR („Las“, „sve 9“, „962%“) weicht
            if not all(_NUMLIKE.match(texts[i].text) or _garbage(texts[i].text, lex) for i in hit):
                continue
        if t.dim is None and any(texts[i].text == t.text for i in hit):
            continue                                # gleiche Lesung schon da
        # die Seiten-OCR las Meter mit Punkt, die Lücke nur einen Teil („4.25“ gegen „25“, „7.58⁵“ gegen „758⁵“):
        # Seitenlesung bleibt. Ohne Punkt nicht – dort ist die Mehrziffer meist Hochziffer/Sternstrich („425“ = 42⁵)
        if "." not in t.text and any("." in texts[i].text and NUMBER.match(texts[i].text.rstrip(SUP))
                                     and _subseq(t.text.rstrip(SUP), texts[i].text.rstrip(SUP)) for i in hit):
            continue
        # die OCR fand dieselbe Zahl samt Hochziffer („2.83⁵“), die Lücke nicht: Hochziffer behalten
        t.text = next((texts[i].text for i in hit if texts[i].text.rstrip(SUP) == t.text), t.text)
        for i in sorted(hit, reverse=True):
            if not _split_off(texts[i], boxes[i], t.text):
                del texts[i], boxes[i]
        texts.append(t)
        boxes.append(b)


def _subseq(a: str, b: str) -> bool:
    """a echt kürzer als b und eine Teilfolge davon („25“ in „4.25“)."""
    it = iter(b)
    return len(a) < len(b) and all(c in it for c in a)


def _split_off(o: Text, box, num: str) -> bool:
    """Hat die OCR zwei Maße als eine Zeile gelesen („25 1.01“) und ist num eines davon am Rand:
    o behält den Rest (Lage um den Anteil verschoben). Gibt zurück, ob o bleibt."""
    import math
    toks = o.text.split()
    if len(toks) < 2 or num not in (toks[0], toks[-1]):
        return False
    first = toks[0] == num
    rest = toks[1:] if first else toks[:-1]
    if not all(NUMBER.match(x.rstrip(SUP)) for x in rest):
        return False
    if first:                                   # Anfang verschiebt sich um den abgetrennten Teil
        a = math.radians(o.angle)
        L = (box[2] if abs(math.cos(a)) >= 0.5 else box[3]) * (len(num) + 1) / len(o.text)
        o.position = (o.position[0] + L * math.cos(a), o.position[1] - L * math.sin(a))
    o.text = " ".join(rest)
    return True


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
