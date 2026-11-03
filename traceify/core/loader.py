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


def load_pdf_page(path: str, page: int = 0, dpi: int = 300) -> Tuple[np.ndarray, float]:
    """Rendert eine PDF-Seite. Gibt (Graustufenbild, mm pro Pixel) zurück."""
    import pymupdf as fitz

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


def load(path: str, page: int = 0, dpi: int = 300) -> Tuple[np.ndarray, float]:
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
