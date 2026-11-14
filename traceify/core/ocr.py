"""Texterkennung (OCR) mit Tesseract.

Erkannte Texte werden als echte CAD-Texte ausgegeben und ihre Bereiche
vor der Vektorisierung aus dem Binärbild entfernt, damit Buchstaben nicht
als Linien-Wirrwarr im DXF landen.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np

from .model import Text

_ALNUM = re.compile(r"[0-9A-Za-zÄÖÜäöüß]")


@dataclass
class OcrSettings:
    enabled: bool = True
    language: str = "deu+eng"
    min_confidence: int = 60
    vertical_text: bool = True     # zusätzlich um 90° gedrehte Texte suchen
    upside_down: bool = True       # auch auf dem Kopf stehende Texte (180°/270°) suchen
    free_angles: bool = True       # übrig gebliebene Schrift in beliebigem Winkel nachlesen
    max_height_ratio: float = 0.08  # Textzeilen höher als 8 % der Bildhöhe ignorieren
    max_char_mm: float = 15.0      # größere Objekte (Linien, Flächen) vor der OCR ausblenden
    despeckle: int = 3             # Flecken entfernen nur bis zu dieser Fläche (px²) – kleiner als
                                   # bei den Linien, damit Dezimalpunkte und Kommas erhalten bleiben
    erase_padding: int = 2
    fix_numbers: bool = True       # Maßzahlen nachlesen: fehlende/falsche Kommas ergänzen
    dictionary: bool = True        # verstümmelte Wörter mit dem Wörterbuch für Planbegriffe
                                   # korrigieren (Zahlen bleiben unverändert)


def _tesseract_cmd():
    """Pfad zu tesseract: config.json, sonst PATH, sonst übliche Orte."""
    import os
    from .. import config
    from ..installer import bundled_tesseract
    b, _ = bundled_tesseract()
    if b:
        return b
    cfg = config.load()
    c = cfg.get("tesseract_cmd")
    if c and os.path.isfile(c):
        return c
    w = shutil.which("tesseract")
    if w:
        return w
    for c in (r"C:\Program Files\Tesseract-OCR\tesseract.exe",
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR",
                           "tesseract.exe"),
              "/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
        if os.path.isfile(c):
            return c
    return None


def _tess_config() -> str:
    """Eigener Sprachdaten-Ordner (vom Installer), falls vorhanden.

    Der Ordner wird über TESSDATA_PREFIX übergeben und nicht über „--tessdata-dir "…"“:
    pytesseract zerlegt die Optionen unter Windows ohne Anführungszeichen-Auswertung, so dass
    Tesseract den Pfad samt Anführungszeichen bekam („"D:\\…\\tessdata"/deu.traineddata“ ließ
    sich nicht öffnen). Mit der Umgebungsvariable gibt es das Problem nicht, auch nicht bei
    Leerzeichen im Pfad. Tesseract 5 erwartet dort den tessdata-Ordner selbst.
    Rückgabe: zusätzliche Optionen für den Aufruf (derzeit immer leer)."""
    import os
    from .. import config
    from ..installer import bundled_tesseract
    exe, bd = bundled_tesseract()
    d = bd if (exe and bd) else config.load().get("tessdata_dir")
    if d and os.path.isdir(d) and any(f.endswith(".traineddata") for f in os.listdir(d)):
        os.environ["TESSDATA_PREFIX"] = d
    return ""


_NO_WINDOW = 0x08000000   # CREATE_NO_WINDOW


def _setup():
    import os
    import pytesseract
    cmd = _tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    _tess_config()
    if os.name == "nt":
        pp = pytesseract.pytesseract
        if not getattr(pp, "_traceify_kein_fenster", False):
            orig = pp.subprocess_args

            def subprocess_args(*a, **kw):
                args = orig(*a, **kw)
                args["creationflags"] = args.get("creationflags", 0) | _NO_WINDOW
                return args

            pp.subprocess_args = subprocess_args      # kein kurz aufblitzendes cmd-Fenster
            pp._traceify_kein_fenster = True
    return pytesseract


def tesseract_available() -> bool:
    return _tesseract_cmd() is not None


_LANG_CACHE: dict = {}


def available_languages() -> List[str]:
    """Von Tesseract gefundene Sprachen (ohne „osd“). Leer, wenn Tesseract fehlt/nicht läuft."""
    import os
    import subprocess
    cmd = _tesseract_cmd()
    if not cmd:
        return []
    _tess_config()
    key = (cmd, os.environ.get("TESSDATA_PREFIX", ""))
    if key not in _LANG_CACHE:
        try:
            kw = {"creationflags": _NO_WINDOW} if os.name == "nt" else {}
            r = subprocess.run([cmd, "--list-langs"], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=30, **kw)
            langs = [l.strip() for l in r.stdout.decode("utf-8", "replace").splitlines()]
            _LANG_CACHE[key] = sorted(l for l in langs if re.fullmatch(r"[A-Za-z_]+", l)
                                      and l != "osd")
        except Exception:
            return []
    return list(_LANG_CACHE[key])


def _usable_lang(lang: str) -> str:
    have = set(available_languages())
    if not have:
        return lang
    parts = [p for p in lang.split("+") if p in have]
    return "+".join(parts) or ("eng" if "eng" in have else sorted(have)[0])


_WORDISH = re.compile(r"[0-9A-Za-zÄÖÜäöüß]{2,}|\d")
_ODD = re.compile(r"[<>|{}\[\]~\\@#$^*«»¢£¥©®§¶]")   # in Plänen praktisch nie, bei Schraffur oft


def plausible(txt: str) -> bool:
    """Grober Filter gegen Zeichensalat aus Schraffuren und Linien („Mm“, „om>Z“, „%y“)."""
    t = txt.strip()
    if not t or not _WORDISH.search(t) or _ODD.search(t):
        return False
    alnum = sum(c.isalnum() for c in t)
    if alnum < 0.6 * len(t.replace(" ", "")):
        return False
    letters = [c for c in t if c.isalpha()]
    if len(letters) == len(t) and len(t) <= 3:
        # kurze reine Buchstabenfolgen nur als Großbuchstaben-Kürzel (WC, KG, HK, BR)
        # oder als ganzes Wort mit Großbuchstaben am Anfang (Bad, Gang)
        return t.isupper() or (t[0].isupper() and t[1:].islower() and len(t) == 3)
    return True


_NUMERIC = re.compile(r"^[0-9.,]+$")
_DECIMAL = re.compile(r"^\d{1,6}[.,]\d{1,3}$")
NUM_WHITELIST = "-c tessedit_char_whitelist=0123456789.,"


def _run(gray: np.ndarray, s: OcrSettings, run_lines=None, detail=None):
    pytesseract = _setup()
    data = pytesseract.image_to_data(gray, lang=_usable_lang(s.language),
                                     config=(_tess_config() + " --psm 11").strip(),
                                     output_type=pytesseract.Output.DICT)
    raw = []
    for i, txt in enumerate(data["text"]):
        txt = (txt or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1
        if not txt or conf < 0:
            continue
        x, y, w, h = (data[k][i] for k in ("left", "top", "width", "height"))
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        raw.append((key, x, y, w, h, txt, conf))
    if s.fix_numbers:
        raw = fix_superscripts(gray, raw, s, run_lines)
        raw = fix_numbers(gray if detail is None else detail, raw, s, run_lines)
    units = _unit_words(raw)
    words = []
    for i, (key, x, y, w, h, txt, conf) in enumerate(raw):
        if i in units and conf >= 50 and 5 <= h:
            words.append((key, x, y, w, h, txt, conf))     # „qm“, „m²“ hinter einer Zahl
            continue
        if s.dictionary and 35 <= conf < s.min_confidence:
            # unsicher gelesen, aber eindeutig ein Planbegriff („Heizraurn“ → „Heizraum“)
            hit = _plan_lexicon().best(txt)
            if hit is not None and hit[1] <= 0.2 and len(hit[0]) >= 5:
                from .lexicon import _case_like
                txt, conf = _case_like(txt, hit[0]), float(s.min_confidence)
        if conf < s.min_confidence or not _ALNUM.search(txt) or not plausible(txt):
            continue
        if h > max(gray.shape[0] * s.max_height_ratio, 80) or h < 5:
            continue
        if len(txt) <= 2 and conf < 85:  # Einzelzeichen/Kürzel sind oft Fehlerkennungen
            continue
        words.append((key, x, y, w, h, txt, conf))
    return _group_lines(words)


_PLAN_LEX = None


def _plan_lexicon():
    global _PLAN_LEX
    if _PLAN_LEX is None:
        from .lexicon import Lexicon
        _PLAN_LEX = Lexicon()
    return _PLAN_LEX


_UNITS = {"qm", "m²", "m2", "m³", "m3", "cm", "mm", "m", "dm", "km", "kg", "kN", "°", "%",
          "lfm", "Stk", "St"}


def _unit_words(raw) -> set:
    """Indizes von Einheiten („qm“, „m²“ …) direkt hinter einer Zahl auf derselben Zeile.

    Solche kurzen Wörter fallen sonst durch den Zeichensalat-Filter."""
    out = set()
    nums = [(k, x, y, w, h) for k, x, y, w, h, t, c in raw
            if c >= 30 and re.search(r"\d[.,]?$", t)]
    for i, (k, x, y, w, h, t, c) in enumerate(raw):
        if t not in _UNITS:
            continue
        for k2, x2, y2, w2, h2 in nums:
            hh = max(h, h2)
            if abs((y + h / 2) - (y2 + h2 / 2)) < 0.5 * hh and \
                    -0.2 * hh <= x - (x2 + w2) <= 1.0 * hh:
                out.add(i)
                break
    return out


def _number_candidates(raw):
    """Maßzahlen, bei denen ein Komma/Punkt fehlen oder falsch sein kann.

    - zwei Zahlen dicht nebeneinander auf einer Zeile („24 85“ statt „24,85“)
    - eine Zahl mit drei oder mehr Ziffern („251“ statt „2,51“)
    - eine Zahl mit Trennzeichen (Komma und Punkt werden oft verwechselt)
    Gibt Listen von Indizes in raw zurück."""
    idx = sorted(range(len(raw)), key=lambda i: (raw[i][0], raw[i][1]))
    out, used = [], set()
    for a, b in zip(idx, idx[1:]):
        ka, xa, ya, wa, ha, ta, ca = raw[a]
        kb, xb, yb, wb, hb, tb, cb = raw[b]
        if a in used or not (_NUMERIC.match(ta) and _NUMERIC.match(tb)) or ca < 30 or cb < 30:
            continue
        hh = max(ha, hb)
        same_row = abs((ya + ha / 2) - (yb + hb / 2)) < 0.4 * hh and 0.6 < ha / max(1, hb) < 1.6
        if ka == kb and same_row and -0.2 * hh <= xb - (xa + wa) <= 0.9 * hh \
                and not any(c in ta + tb.rstrip(".,") for c in ".,") \
                and len(ta) + len(tb) <= 8:
            out.append([a, b])
            used.update((a, b))
    for i, (_, _, _, _, _, t, c) in enumerate(raw):
        if i in used or c < 30 or not _NUMERIC.match(t):
            continue
        digits = sum(ch.isdigit() for ch in t)
        if (digits >= 3 and digits <= 7) or (_DECIMAL.match(t) and digits >= 2):
            out.append([i])
    return out


def fix_numbers(gray: np.ndarray, raw, s: OcrSettings, run_lines=None):
    """Maßzahlen gezielt nachlesen (nur Ziffern, Komma, Punkt) und Trennzeichen ergänzen.

    Übernommen wird eine Nachlesung nur, wenn sie **dieselben Ziffern** in derselben
    Reihenfolge enthält und genau ein Trennzeichen hat – an den Ziffern ändert sich also
    nie etwas, nur Komma/Punkt kommen dazu oder werden richtiggestellt."""
    from . import textlines
    import cv2
    cands = _number_candidates(raw)
    if not cands:
        return raw
    crops = []
    for grp in cands:
        x0 = min(raw[i][1] for i in grp)
        y0 = min(raw[i][2] for i in grp)
        x1 = max(raw[i][1] + raw[i][3] for i in grp)
        y1 = max(raw[i][2] + raw[i][4] for i in grp)
        pad = max(2, int(0.35 * (y1 - y0)))     # Komma ragt unter die Grundlinie
        H, W = gray.shape
        c = gray[max(0, y0 - pad):min(H, y1 + pad), max(0, x0 - pad):min(W, x1 + pad)]
        c = cv2.normalize(c, None, 0, 255, cv2.NORM_MINMAX)   # Graustufen voll ausnutzen
        f = textlines.LINE_H / max(1, c.shape[0])
        c = cv2.resize(c, (max(1, int(round(c.shape[1] * f))), textlines.LINE_H),
                       interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_CUBIC)
        crops.append(c)
    run_lines = run_lines or textlines._tesseract_lines
    res = run_lines(crops, s, NUM_WHITELIST)
    drop, add = set(), []
    for grp, (txt, conf) in zip(cands, res):
        t = (txt or "").replace(" ", "")
        old = "".join(raw[i][5] for i in grp)
        if conf < 50 or not _DECIMAL.match(t) or \
                re.sub(r"\D", "", t) != re.sub(r"\D", "", old) or t == old:
            continue
        x0 = min(raw[i][1] for i in grp)
        y0 = min(raw[i][2] for i in grp)
        x1 = max(raw[i][1] + raw[i][3] for i in grp)
        y1 = max(raw[i][2] + raw[i][4] for i in grp)
        drop.update(grp)
        add.append((raw[grp[0]][0], x0, y0, x1 - x0, y1 - y0, t,
                    max(conf, max(raw[i][6] for i in grp))))
    if not drop:
        return raw
    return [r for i, r in enumerate(raw) if i not in drop] + add


SUPERSCRIPT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
# Zahl, dahinter evtl. ein Zeichen, als das Tesseract eine Hochziffer liest („36°“, „10.61"“)
_NUM_TAIL = re.compile(r"^(\d+(?:[.,]\d+)?)([°\"'’”*^?]?)$")


def _superscript_box(bw: np.ndarray, box):
    """Sucht hinter einer Zahl (Box x, y, w, h) eine kleine, hochgestellte Ziffer.

    Gibt (Box der Hochziffer, Zahl voller Ziffern links davon) oder None zurück.
    bw: 1 = Tinte."""
    import cv2
    x, y, w, h = box
    H, W = bw.shape
    x0, y0 = max(0, x - 2), max(0, int(y - 0.3 * h))
    x1, y1 = min(W, int(x + w + 0.8 * h)), min(H, int(y + 1.1 * h))
    if x1 <= x0 or y1 <= y0:
        return None
    n, _, st, _ = cv2.connectedComponentsWithStats(bw[y0:y1, x0:x1], connectivity=8)
    comps = [(cx + x0, cy + y0, cw, ch) for cx, cy, cw, ch, a in st[1:] if a >= 3]
    full = [c for c in comps if c[3] >= 0.75 * h and c[3] <= 1.3 * h and c[0] < x + w]
    if not full:
        return None
    last = max(full, key=lambda c: c[0])
    sups = [c for c in comps
            if 0.3 * h <= c[3] <= 0.75 * h and c[2] <= 0.7 * h        # klein
            and c[1] + c[3] <= y + 0.72 * h and c[1] <= y + 0.25 * h  # oben, nicht am Fuß
            and c[0] >= last[0] + 0.5 * last[2]]                       # hinter der letzten Ziffer
    if not sups:
        return None
    sup = min(sups, key=lambda c: c[0])
    # danach darf direkt keine weitere volle Ziffer folgen (sonst ist es etwas anderes)
    if any(c[0] > sup[0] and c[0] - (sup[0] + sup[2]) < 0.4 * h and c[3] >= 0.75 * h
           for c in comps):
        return None
    return sup, sum(1 for c in full if c[0] < sup[0])


def fix_superscripts(gray: np.ndarray, raw, s: OcrSettings, run_lines=None):
    """Maße mit hochgestellter Ziffer (Allplan: „2.38⁵“ = 2,385 m) richtig lesen.

    Tesseract liest die kleine Ziffer als „°“ oder „"“, als normale Ziffer oder gar nicht.
    Hinter jeder gelesenen Zahl wird nach einer kleinen, oben stehenden Komponente gesucht
    und diese einzeln als Ziffer gelesen. Die Hauptziffern bleiben unverändert."""
    import cv2
    from . import textlines
    bw = (gray < 128).astype(np.uint8)
    cands = []
    for i, (key, x, y, w, h, txt, conf) in enumerate(raw):
        m = _NUM_TAIL.match(txt)
        if conf < 30 or not m or h < 8:
            continue
        # geht die Zahl direkt weiter („6“ + „819“ bei „6,19“), ist das keine Hochziffer
        if any(j != i and x + w - 0.2 * h <= r[1] <= x + w + 1.0 * h
               and r[2] < y + h and r[2] + r[4] > y for j, r in enumerate(raw)):
            continue
        found = _superscript_box(bw, (x, y, w, h))
        if found is None:
            continue
        sup, n_full = found
        main, tail = m.group(1), m.group(2)
        digits = sum(ch.isdigit() for ch in main)
        if not tail and digits == n_full + 1:
            main = main[:-1]                  # Hochziffer als normale Ziffer mitgelesen
        elif digits != n_full or not main[-1:].isdigit():
            continue                          # Ziffern verschmolzen o. Ä. – nichts riskieren
        if not main or not main[-1].isdigit():
            continue
        cands.append((i, main, sup))
    if not cands:
        return raw
    crops = []
    for _, _, (sx, sy, sw, sh) in cands:
        p = max(2, int(0.35 * sh))
        c = gray[max(0, sy - p):sy + sh + p, max(0, sx - p):sx + sw + p]
        f = textlines.LINE_H / max(1, c.shape[0])
        crops.append(cv2.resize(c, (max(1, int(round(c.shape[1] * f))), textlines.LINE_H),
                                interpolation=cv2.INTER_CUBIC))
    res = (run_lines or textlines._tesseract_lines)(crops, s, NUM_WHITELIST)
    out, drop = list(raw), set()
    for (i, main, (sx, sy, sw, sh)), (t, c) in zip(cands, res):
        t = (t or "").strip()
        if len(t) != 1 or not t.isdigit() or c < 50:
            continue
        key, x, y, w, h, _, conf = raw[i]
        x1, y1 = max(x + w, sx + sw), max(y + h, sy + sh)
        # Zahl + kleine hochgestellte Ziffer ist ein starkes Muster: unsichere Lesung reicht
        out[i] = (key, x, y, x1 - x, y1 - y, main + t.translate(SUPERSCRIPT),
                  max(conf, float(s.min_confidence)) if conf >= 40 else conf)
        for j, r in enumerate(raw):           # die Hochziffer als eigenes Wort entfernen
            if j != i and _overlap((r[1], r[2], r[3], r[4]), (sx, sy, sw, sh)) > 0.5 \
                    and len(r[5]) <= 2:
                drop.add(j)
    return [r for j, r in enumerate(out) if j not in drop]


def _group_lines(words):
    """Fasst Wörter derselben Zeile zu einem Text zusammen (wenn nah genug)."""
    lines = {}
    for key, x, y, w, h, txt, conf in words:
        lines.setdefault(key, []).append((x, y, w, h, txt, conf))
    out = []
    for ws in lines.values():
        ws.sort()
        cur = [ws[0]]
        for wd in ws[1:]:
            px, py, pw, ph = cur[-1][:4]
            if wd[0] - (px + pw) < 1.5 * max(ph, wd[3]):
                cur.append(wd)
            else:
                out.append(cur)
                cur = [wd]
        out.append(cur)
    res = []
    for grp in out:
        x0 = min(g[0] for g in grp)
        y0 = min(g[1] for g in grp)
        x1 = max(g[0] + g[2] for g in grp)
        y1 = max(g[1] + g[3] for g in grp)
        txt = " ".join(g[4] for g in grp)
        # Güte: mittlere Sicherheit, gewichtet mit der Zahl erkannter Zeichen
        score = sum(g[5] * len(g[4]) for g in grp)
        res.append((x0, y0, x1 - x0, y1 - y0, txt, score))
    return _merge_rows(res)


def _merge_rows(items, gap: float = 0.8):
    """Texte auf derselben Zeile, die Tesseract getrennt hat (andere Zeilennummer, z. B.
    „NFL“ und „13,12“), zusammenfassen: gleiche Höhe, gleiche Grundlinie, Lücke höchstens
    gap × Schrifthöhe."""
    items = sorted(items, key=lambda t: (t[0], t[1]))
    out = []
    for it in items:
        x, y, w, h, txt, score = it
        for j, (X, Y, W_, H_, T, S) in enumerate(out):
            hh = max(h, H_)
            if not (0.75 <= h / max(1, H_) <= 1.33):
                continue
            if abs((y + h) - (Y + H_)) > 0.25 * hh or abs(y - Y) > 0.35 * hh:
                continue
            g = x - (X + W_)
            if -0.1 * hh <= g <= gap * hh:
                x0, y0 = min(X, x), min(Y, y)
                x1, y1 = max(X + W_, x + w), max(Y + H_, y + h)
                out[j] = (x0, y0, x1 - x0, y1 - y0, T + " " + txt, S + score)
                break
        else:
            out.append(it)
    return out


def text_layer(ink: np.ndarray, px_per_mm: float, max_char_mm: float) -> np.ndarray:
    """Nur Objekte in Schriftgröße behalten (ink: 255 = Tinte).

    Lange Linien, Wände und Schraffurflächen führen bei Tesseract zu Zeichensalat und
    verdecken echte Texte – sie werden vor der Erkennung ausgeblendet.
    """
    import cv2
    lim = max(12.0, max_char_mm * px_per_mm)
    n, lab, st, _ = cv2.connectedComponentsWithStats((ink > 0).astype(np.uint8), connectivity=8)
    keep = np.zeros(n, bool)
    w, h, a = st[:, 2], st[:, 3], st[:, 4]
    big, small = np.maximum(w, h), np.minimum(w, h)
    # Schriftgröße – oder ein zusammenhängend geschriebenes Wort (Handschrift): mäßig lang
    # und nicht linienartig dünn
    wordlike = (big <= 4 * lim) & (small >= 0.15 * big) & (small <= lim)
    solid = (a >= 0.85 * w * h) & (small > lim / 3)
    keep[((big <= lim) | wordlike) & ~solid] = True
    keep[0] = False
    return np.where(keep[lab], 255, 0).astype(np.uint8)


def ocr_zoom(px_per_mm: float) -> int:
    """Vergrößerung für grobe Scans (unter ~130 dpi), damit Tesseract etwa 300 dpi sieht."""
    return max(2, int(round(11.8 / px_per_mm))) if 0 < px_per_mm < 5 else 1


def recognize(gray: np.ndarray, s: OcrSettings, px_per_mm: float = 0.0, zoom: int = 1,
              detail: Optional[np.ndarray] = None
              ) -> Tuple[List[Text], List[Tuple[int, int, int, int]]]:
    """Gibt (Texte, Boxen zum Ausradieren) zurück. Boxen: (x, y, w, h) in Bildpixeln.

    gray: Schwarz-auf-Weiß-Bild. px_per_mm: seine Auflösung (0 = unbekannt) – damit werden
    Linien und Flächen vor der OCR ausgeblendet. zoom: um diesen Faktor vergrößertes Bild;
    Texte und Boxen werden auf das Original zurückgerechnet. detail: dasselbe Bild in
    Graustufen (schwarz auf weiß, gleiche Größe) – darin sind feine Kommas und Punkte noch
    erhalten; Maßzahlen werden daraus nachgelesen.
    """
    if not s.enabled or not tesseract_available():
        return [], []
    src = gray
    if px_per_mm > 0:
        src = 255 - text_layer(255 - gray, px_per_mm, s.max_char_mm)
    H, W = src.shape
    # Drehungen im Uhrzeigersinn: k=0 waagrecht, k=1 von unten nach oben laufender Text,
    # k=2 auf dem Kopf, k=3 von oben nach unten
    ks = [0] + ([1] if s.vertical_text else []) + ([2, 3] if s.upside_down else [])
    if not s.vertical_text and s.upside_down:
        ks = [0, 2]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(ks)) as ex:
        if detail is not None and detail.shape != src.shape:
            detail = None
        futs = {k: ex.submit(_run, np.ascontiguousarray(np.rot90(src, -k)), s, None,
                             None if detail is None
                             else np.ascontiguousarray(np.rot90(detail, -k)))
                for k in ks}
        found = {k: f.result() for k, f in futs.items()}
    cands = []
    for k, items in found.items():
        for x, y, w, h, txt, score in items:
            # Box zurück ins Originalbild drehen
            if k == 0:
                ox, oy, ow, oh = x, y, w, h
            elif k == 1:                       # gedreht (H-1-y, x)
                ox, oy, ow, oh = y, H - (x + w), h, w
            elif k == 2:
                ox, oy, ow, oh = W - (x + w), H - (y + h), w, h
            else:                              # gegen Uhrzeigersinn zurück
                ox, oy, ow, oh = W - (y + h), x, h, w
            cands.append((score, k, ox, oy, ow, oh, txt, h))
    # Überlappende Treffer aus verschiedenen Richtungen: der bessere gewinnt
    cands.sort(key=lambda c: -c[0])
    texts, boxes, sure, scores = [], [], [], []
    for score, k, ox, oy, ow, oh, txt, th in cands:
        if any(_overlap((ox, oy, ow, oh), b) > 0.3 for b in boxes):
            continue
        boxes.append((ox, oy, ow, oh))
        scores.append(score)
        if score >= 88:
            sure.append(txt)
        X, Y, Wd, Hd = ox / zoom, oy / zoom, ow / zoom, oh / zoom
        height = th / zoom * 0.8
        if k == 0:
            texts.append(Text(txt, (X, Y + Hd), height, 0.0))
        elif k == 1:   # läuft von unten nach oben; Basislinie rechts
            texts.append(Text(txt, (X + Wd, Y + Hd), height, 90.0))
        elif k == 2:   # auf dem Kopf; Basislinie oben, Start rechts
            texts.append(Text(txt, (X + Wd, Y), height, 180.0))
        else:          # läuft von oben nach unten; Basislinie links
            texts.append(Text(txt, (X, Y), height, 270.0))
    lex = None
    if s.dictionary:
        # Wörterbuch: Planbegriffe + Wörter, die in diesem Plan sicher gelesen wurden
        from .lexicon import Lexicon, correct, from_texts
        lex = Lexicon()
        lex.add_own(from_texts(sure))
        for t, sc in zip(texts, scores):
            # sicher gelesen: nur Formverwechslungen (i/l, rn/m) und fehlende Umlaute
            t.text = correct(t.text, lex, sure=sc >= 80)[0]
    if s.free_angles and px_per_mm > 0:
        # schräge Beschriftungen u. Ä., die keine der vier Richtungen gefunden hat
        from . import textlines
        layer = 255 - src
        found_c = textlines.find_candidates(layer, px_per_mm, boxes,
                                            max_char_mm=min(12.0, s.max_char_mm))
        tt, bb = textlines.read_candidates(found_c, layer, s, lexicon=lex, gray=detail)
        for t, b in zip(tt, bb):
            if any(_overlap(b, o) > 0.3 for o in boxes):
                continue
            t.position = (t.position[0] / zoom, t.position[1] / zoom)
            t.height /= zoom
            texts.append(t)
            boxes.append(b)
    if s.fix_numbers and px_per_mm > 0:
        # Maßzahlen in Lücken der Maßlinie gezielt lesen
        from . import dimensions
        tt, bb = dimensions.read_gap_numbers((gray < 128).astype(np.uint8),
                                             gray if detail is None else detail, px_per_mm, s)
        for t in tt:
            t.position = (t.position[0] / zoom, t.position[1] / zoom)
            t.height /= zoom
        dimensions.merge(texts, boxes, tt, bb)
    if zoom != 1:
        boxes = [(x // zoom, y // zoom, -(-w // zoom), -(-h // zoom)) for x, y, w, h in boxes]
    return texts, boxes


def _overlap(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    ix = max(0, min(ax + aw, bx + bw) - max(ax, bx))
    iy = max(0, min(ay + ah, by + bh) - max(ay, by))
    inter = ix * iy
    return inter / max(1, min(aw * ah, bw * bh))


def erase_boxes(bw: np.ndarray, boxes, pad: int = 2) -> np.ndarray:
    out = bw.copy()
    H, W = out.shape
    for x, y, w, h in boxes:
        out[max(0, y - pad):min(H, y + h + pad), max(0, x - pad):min(W, x + w + pad)] = 0
    return out
