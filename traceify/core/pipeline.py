"""Gesamte Konvertierung: Graustufenbild (oder Vektor-PDF) -> Drawing."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Callable, Optional

import numpy as np

from . import ocr as ocr_mod
from .model import Drawing, Text
from .pdf_vector import PdfVectorSettings, has_vectors, import_page
from .preprocess import PreprocessSettings, to_binary
from .scale_detect import find_scale, format_scale
from .vectorize import VectorizeSettings, vectorize


def _make(cls, d: dict):
    """Dataclass aus dict – unbekannte Schlüssel (ältere/neuere Versionen) ignorieren."""
    names = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in (d or {}).items() if k in names})


@dataclass
class ConvertSettings:
    preprocess: PreprocessSettings = field(default_factory=PreprocessSettings)
    vectorize: VectorizeSettings = field(default_factory=VectorizeSettings)
    ocr: ocr_mod.OcrSettings = field(default_factory=ocr_mod.OcrSettings)
    pdf: PdfVectorSettings = field(default_factory=PdfVectorSettings)
    scale: Optional[float] = None  # mm pro Pixel; None = aus DPI
    auto_scale: bool = True        # „M 1:N“ im Plan erkennen und in Originalgröße ausgeben

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ConvertSettings":
        return cls(
            preprocess=_make(PreprocessSettings, d.get("preprocess")),
            vectorize=_make(VectorizeSettings, d.get("vectorize")),
            ocr=_make(ocr_mod.OcrSettings, d.get("ocr")),
            pdf=_make(PdfVectorSettings, d.get("pdf")),
            scale=d.get("scale"),
            auto_scale=d.get("auto_scale", True),
        )


@dataclass
class ConvertResult:
    drawing: Drawing
    binary: np.ndarray        # vorverarbeitetes Binärbild (Zeichnung weiß)
    text_boxes: list


def apply_auto_scale(d: Drawing, settings: ConvertSettings) -> None:
    """Erkannten Zeichnungsmaßstab anwenden (nur ohne manuell gesetzten Maßstab)."""
    if settings.scale is not None or not settings.auto_scale:
        return
    n = find_scale(t.text for t in d.by_type(Text))
    if n and n != 1:
        d.scale *= n
        d.meta["massstab"] = format_scale(n)
        d.meta["massstab_quelle"] = "aus Plan erkannt"


def convert(gray: np.ndarray, settings: ConvertSettings, dpi_scale: float = 25.4 / 300,
            source: str = "", progress: Optional[Callable[[int, str], None]] = None) -> ConvertResult:
    def step(p, msg):
        if progress:
            progress(p, msg)

    step(5, "Vorverarbeitung …")
    bw = to_binary(gray, settings.preprocess)

    texts, boxes = [], []
    if settings.ocr.enabled:
        step(25, "Texterkennung (OCR) …")
        ocr_src = 255 - bw  # sauberes Schwarz-auf-Weiß-Bild für Tesseract
        texts, boxes = ocr_mod.recognize(ocr_src, settings.ocr)
        bw_vec = ocr_mod.erase_boxes(bw, boxes, settings.ocr.erase_padding)
    else:
        bw_vec = bw

    step(55, "Vektorisierung …")
    ents = vectorize(bw_vec, settings.vectorize)

    scale = settings.scale or dpi_scale
    d = Drawing(width=gray.shape[1], height=gray.shape[0], scale=scale,
                entities=ents + texts, source=source)
    apply_auto_scale(d, settings)
    step(100, "Fertig")
    return ConvertResult(d, bw, boxes)


def convert_pdf_vectors(path: str, page: int, dpi: int, settings: ConvertSettings,
                        gray: Optional[np.ndarray] = None,
                        progress: Optional[Callable[[int, str], None]] = None) -> ConvertResult:
    """Vektor-PDF direkt übernehmen (keine Rastervektorisierung)."""
    if progress:
        progress(20, "Lese Vektordaten aus dem PDF …")
    d = import_page(path, page, dpi, settings.pdf)
    if settings.scale:
        d.scale = settings.scale
    if not settings.ocr.enabled:
        d.entities = [e for e in d.entities if not isinstance(e, Text)]
    apply_auto_scale(d, settings)
    bw = to_binary(gray, settings.preprocess) if gray is not None else \
        np.zeros((d.height, d.width), np.uint8)
    if progress:
        progress(100, "Fertig")
    return ConvertResult(d, bw, [])


def convert_source(path: str, page: int, settings: ConvertSettings, gray: np.ndarray,
                   dpi_scale: float, pdf_dpi: int = 300, source: str = "",
                   progress: Optional[Callable[[int, str], None]] = None,
                   allow_vectors: bool = True) -> ConvertResult:
    """Wählt automatisch: Vektor-PDF direkt übernehmen oder Raster vektorisieren."""
    if allow_vectors and path and has_vectors(path, page, settings.pdf):
        return convert_pdf_vectors(path, page, pdf_dpi, settings, gray, progress)
    return convert(gray, settings, dpi_scale, source, progress)
