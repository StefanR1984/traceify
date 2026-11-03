"""Gesamte Konvertierung: Graustufenbild -> Drawing."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

import numpy as np

from . import ocr as ocr_mod
from .model import Drawing
from .preprocess import PreprocessSettings, to_binary
from .vectorize import VectorizeSettings, vectorize


@dataclass
class ConvertSettings:
    preprocess: PreprocessSettings = field(default_factory=PreprocessSettings)
    vectorize: VectorizeSettings = field(default_factory=VectorizeSettings)
    ocr: ocr_mod.OcrSettings = field(default_factory=ocr_mod.OcrSettings)
    scale: Optional[float] = None  # mm pro Pixel; None = aus DPI

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ConvertSettings":
        return cls(
            preprocess=PreprocessSettings(**d.get("preprocess", {})),
            vectorize=VectorizeSettings(**d.get("vectorize", {})),
            ocr=ocr_mod.OcrSettings(**d.get("ocr", {})),
            scale=d.get("scale"),
        )


@dataclass
class ConvertResult:
    drawing: Drawing
    binary: np.ndarray        # vorverarbeitetes Binärbild (Zeichnung weiß)
    text_boxes: list


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
    step(100, "Fertig")
    return ConvertResult(d, bw, boxes)
