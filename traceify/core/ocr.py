"""Texterkennung (OCR) mit Tesseract.

Erkannte Texte werden als echte CAD-Texte ausgegeben und ihre Bereiche
vor der Vektorisierung aus dem Binärbild entfernt, damit Buchstaben nicht
als Linien-Wirrwarr im DXF landen.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from typing import List, Tuple

import numpy as np

from .model import Text

_ALNUM = re.compile(r"[0-9A-Za-zÄÖÜäöüß]")


@dataclass
class OcrSettings:
    enabled: bool = True
    language: str = "deu+eng"
    min_confidence: int = 60
    vertical_text: bool = True     # zusätzlich um 90° gedrehte Texte suchen
    max_height_ratio: float = 0.08  # Textzeilen höher als 8 % der Bildhöhe ignorieren
    erase_padding: int = 2


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
    """Eigener Sprachdaten-Ordner (vom Installer), falls vorhanden."""
    import os
    from .. import config
    from ..installer import bundled_tesseract
    exe, bd = bundled_tesseract()
    d = bd if (exe and bd) else config.load().get("tessdata_dir")
    if d and os.path.isdir(d) and any(f.endswith(".traineddata") for f in os.listdir(d)):
        return f'--tessdata-dir "{d}"'
    return ""


def _setup():
    import pytesseract
    cmd = _tesseract_cmd()
    if cmd:
        pytesseract.pytesseract.tesseract_cmd = cmd
    return pytesseract


def tesseract_available() -> bool:
    return _tesseract_cmd() is not None


def available_languages() -> List[str]:
    try:
        pt = _setup()
        return sorted(l for l in pt.get_languages(config=_tess_config()) if l != "osd")
    except Exception:
        return []


def _usable_lang(lang: str) -> str:
    have = set(available_languages())
    if not have:
        return lang
    parts = [p for p in lang.split("+") if p in have]
    return "+".join(parts) or ("eng" if "eng" in have else sorted(have)[0])


def _run(gray: np.ndarray, s: OcrSettings):
    pytesseract = _setup()
    data = pytesseract.image_to_data(gray, lang=_usable_lang(s.language),
                                     config=(_tess_config() + " --psm 11").strip(),
                                     output_type=pytesseract.Output.DICT)
    words = []
    for i, txt in enumerate(data["text"]):
        txt = (txt or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1
        if not txt or conf < s.min_confidence or not _ALNUM.search(txt):
            continue
        x, y, w, h = (data[k][i] for k in ("left", "top", "width", "height"))
        if h > max(gray.shape[0] * s.max_height_ratio, 80) or h < 5:
            continue
        if len(txt) == 1 and conf < 85:  # Einzelzeichen sind oft Fehlerkennungen
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        words.append((key, x, y, w, h, txt))
    return _group_lines(words)


def _group_lines(words):
    """Fasst Wörter derselben Zeile zu einem Text zusammen (wenn nah genug)."""
    lines = {}
    for key, x, y, w, h, txt in words:
        lines.setdefault(key, []).append((x, y, w, h, txt))
    out = []
    for ws in lines.values():
        ws.sort()
        cur = [ws[0]]
        for wd in ws[1:]:
            px, py, pw, ph, _ = cur[-1]
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
        res.append((x0, y0, x1 - x0, y1 - y0, " ".join(g[4] for g in grp)))
    return res


def recognize(gray: np.ndarray, s: OcrSettings) -> Tuple[List[Text], List[Tuple[int, int, int, int]]]:
    """Gibt (Texte, Boxen zum Ausradieren) zurück. Boxen: (x, y, w, h) in Bildpixeln."""
    if not s.enabled or not tesseract_available():
        return [], []
    H, W = gray.shape
    texts, boxes = [], []
    # Waagrechter und senkrechter Durchgang gleichzeitig (Tesseract läuft als eigener Prozess)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_h = ex.submit(_run, gray, s)
        # Von unten nach oben laufender Text wird durch Drehung im
        # Uhrzeigersinn waagrecht. Original (x, y) -> gedreht (H-1-y, x)
        f_v = ex.submit(_run, np.ascontiguousarray(np.rot90(gray, -1)), s) \
            if s.vertical_text else None
        horizontal = f_h.result()
        vertical = f_v.result() if f_v is not None else []
    for x, y, w, h, txt in horizontal:
        texts.append(Text(txt, (float(x), float(y + h)), float(h) * 0.8, 0.0))
        boxes.append((x, y, w, h))

    if s.vertical_text:
        for x, y, w, h, txt in vertical:
            ox, oy, ow, oh = y, H - (x + w), h, w
            if any(_overlap((ox, oy, ow, oh), b) > 0.3 for b in boxes):
                continue
            # Text läuft von unten nach oben; Basislinie liegt rechts
            texts.append(Text(txt, (float(ox + ow), float(oy + oh)), float(h) * 0.8, 90.0))
            boxes.append((ox, oy, ow, oh))
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
