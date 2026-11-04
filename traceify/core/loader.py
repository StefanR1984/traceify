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
    return img.copy(), 25.4 / dpi


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
            pix = doc.load_page(page).get_pixmap(dpi=dpi, colorspace=fitz.csRGB, alpha=False)
            rgb = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3)
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
