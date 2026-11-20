"""Laden von Rasterbildern und PDF-Seiten als Graustufen-Arrays."""
from __future__ import annotations

import os
from typing import List, Tuple

import cv2
import numpy as np

IMAGE_EXT = {".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif", ".webp"}
PDF_EXT = {".pdf"}
SUPPORTED_EXT = IMAGE_EXT | PDF_EXT


def is_supported(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in SUPPORTED_EXT


def pdf_page_count(path: str) -> int:
    import pymupdf as fitz

    with fitz.open(path) as doc:
        return doc.page_count


DEFAULT_PDF_DPI = 300


def native_dpi(path: str, page: int = 0) -> int:
    """Auflösung eines gescannten PDFs: ein Rasterbild, das fast die ganze Seite füllt.

    Gibt 0 zurück, wenn die Seite kein solcher Scan ist (Vektor-PDF, mehrere Bilder …).
    """
    import pymupdf as fitz

    try:
        with fitz.open(path) as doc:
            pg = doc.load_page(page)
            area = abs(pg.rect)
            best = 0.0
            for info in pg.get_images(full=True):
                xref, w_px, h_px = info[0], info[2], info[3]
                for r in pg.get_image_rects(xref):
                    if abs(r) >= 0.8 * area and r.width > 0 and r.height > 0:
                        best = max(best, w_px / (r.width / 72.0), h_px / (r.height / 72.0))
    except Exception:
        return 0
    return int(round(min(600.0, best))) if best >= 50 else 0


def resolve_dpi(path: str, page: int = 0, dpi: float = 0) -> int:
    """dpi <= 0 bedeutet automatisch: Scan-PDFs in ihrer Originalauflösung, sonst 300 dpi."""
    if dpi and dpi > 0:
        return int(round(float(dpi)))
    if path and path.lower().endswith(".pdf"):
        return native_dpi(path, page) or DEFAULT_PDF_DPI
    return DEFAULT_PDF_DPI


def load_pdf_page(path: str, page: int = 0, dpi: int = 0) -> Tuple[np.ndarray, float]:
    """Rendert eine PDF-Seite. Gibt (Graustufenbild, mm pro Pixel) zurück.

    dpi <= 0: automatisch (Scan-PDFs in Originalauflösung, siehe resolve_dpi).
    """
    import pymupdf as fitz

    dpi = resolve_dpi(path, page, dpi)  # PyMuPDF verlangt eine Ganzzahl
    with fitz.open(path) as doc:
        pg = doc.load_page(page)
        pix = pg.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)
        tiles = scan_tiles(pg)
    if tiles:
        img = _stitch_page(img, img, tiles, dpi)
    return img.copy(), 25.4 / dpi


STITCH_MARGIN_MM = 5.0


def scan_tiles(pg):
    """Mehrere gescannte Teile eines Plans nebeneinander auf der Seite (mit Fuge dazwischen)?

    Gibt (Achse, [Rechtecke in pt, in Reihenfolge]) zurück, sonst None. Seiten mit Vektor-
    zeichnung bleiben unberührt (dort passen sonst Vektoren und Bild nicht mehr aufeinander).
    """
    from .stitch import tile_order
    try:
        if sum(len(d.get("items", [])) for d in pg.get_drawings()) >= 15:
            return None
        rects = []
        for info in pg.get_images(full=True):
            for r in pg.get_image_rects(info[0]):
                if r.width > 0.1 * pg.rect.width or r.height > 0.1 * pg.rect.height:
                    rects.append((r.x0, r.y0, r.x1, r.y1))
    except Exception:
        return None
    found = tile_order(rects)
    return (found[0], [rects[i] for i in found[1]]) if found else None


def _stitch_page(gray: np.ndarray, img: np.ndarray, tiles, dpi: int) -> np.ndarray:
    """Teile aus der gerenderten Seite schneiden, Versatz am Graubild bestimmen, zusammensetzen."""
    import logging
    from .stitch import chain_offsets, compose, edge_specks
    axis, rects = tiles
    f = dpi / 72.0
    boxes = [tuple(int(round(v * f)) for v in r) for r in rects]
    boxes = [(max(0, x0), max(0, y0), min(gray.shape[1], x1), min(gray.shape[0], y1))
             for x0, y0, x1, y1 in boxes]
    g_parts = [gray[y0:y1, x0:x1].copy() for x0, y0, x1, y1 in boxes]
    i_parts = [img[y0:y1, x0:x1].copy() for x0, y0, x1, y1 in boxes]
    band = max(3, int(round(1.0 / 25.4 * dpi)))  # Scankante: 1 mm an der Fuge (Punkte entfernt das Entflecken)
    sides = ("left", "right") if axis == "x" else ("top", "bottom")
    for i in range(len(boxes)):
        for side, use in ((sides[0], i > 0), (sides[1], i < len(boxes) - 1)):
            if use:
                m = edge_specks(g_parts[i], side, band)
                g_parts[i][m] = 255
                i_parts[i][m] = 255
    q = 1 if axis == "x" else 0  # Querlage aus der Seite als Rückfall
    dy0 = [boxes[i + 1][q] - boxes[i][q] for i in range(len(boxes) - 1)]
    offs, kinds = chain_offsets(g_parts, axis, dy0)
    logging.getLogger("traceify").info("Seite aus %d Scanteilen zusammengesetzt (%s, %s)",
                                       len(boxes), ", ".join(kinds), offs)
    out = compose(i_parts, offs)
    m = int(round(STITCH_MARGIN_MM / 25.4 * dpi))
    pad = ((m, m), (m, m)) + ((0, 0),) * (out.ndim - 2)
    return np.pad(out, pad, constant_values=255)


def load_image(path: str) -> Tuple[np.ndarray, float]:
    """Lädt ein Rasterbild. Gibt (Graustufenbild, mm pro Pixel) zurück.

    Die DPI wird – falls im Bild hinterlegt – aus den Metadaten gelesen,
    sonst wird 300 dpi angenommen.
    """
    from PIL import Image

    with Image.open(path) as im:
        dpi = im.info.get("dpi", (300, 300))[0] or 300
        if im.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            im = im.convert("RGBA")
            bg.paste(im, mask=im.split()[-1])
            im = bg
        gray = np.array(im.convert("L"))
    return gray, 25.4 / float(dpi)


def load_color(path: str, page: int = 0, dpi: int = 0):
    """Farbbild (BGR, uint8) oder None, wenn die Quelle keine Farbe hat."""
    ext = os.path.splitext(path)[1].lower()
    if ext in PDF_EXT:
        import pymupdf as fitz
        dpi = resolve_dpi(path, page, dpi)
        with fitz.open(path) as doc:
            pg = doc.load_page(page)
            pix = pg.get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
            rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
            tiles = scan_tiles(pg)
        if tiles:  # gleiche Zusammensetzung wie load_pdf_page (Versatz am Graubild)
            rgb = _stitch_page(cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY), rgb, tiles, dpi)
        return np.ascontiguousarray(rgb[..., ::-1])
    if ext in IMAGE_EXT:
        from PIL import Image
        with Image.open(path) as im:
            if im.mode in ("1", "L", "LA", "I", "I;16", "F"):
                return None
            if im.mode in ("RGBA", "P", "LA"):
                im = im.convert("RGBA")
                bg = Image.new("RGB", im.size, (255, 255, 255))
                bg.paste(im, mask=im.split()[-1])
                im = bg
            rgb = np.array(im.convert("RGB"))
        if (np.abs(rgb[..., 0].astype(int) - rgb[..., 1]) < 4).all() and \
                (np.abs(rgb[..., 1].astype(int) - rgb[..., 2]) < 4).all():
            return None  # eigentlich Graustufen
        return np.ascontiguousarray(rgb[..., ::-1])
    return None


def load(path: str, page: int = 0, dpi: int = 0) -> Tuple[np.ndarray, float]:
    ext = os.path.splitext(path)[1].lower()
    if ext in PDF_EXT:
        return load_pdf_page(path, page, dpi)
    if ext in IMAGE_EXT:
        return load_image(path)
    raise ValueError(f"Nicht unterstütztes Format: {ext}")


def page_count(path: str) -> int:
    return pdf_page_count(path) if path.lower().endswith(".pdf") else 1


def save_image(path: str, img: np.ndarray) -> None:
    ok, buf = cv2.imencode(os.path.splitext(path)[1] or ".png", img)
    if not ok:
        raise IOError("Bild konnte nicht gespeichert werden")
    buf.tofile(path)


def list_inputs(folder: str, recursive: bool = False) -> List[str]:
    out = []
    for root, _dirs, files in os.walk(folder):
        for f in sorted(files):
            if is_supported(f):
                out.append(os.path.join(root, f))
        if not recursive:
            break
    return out
