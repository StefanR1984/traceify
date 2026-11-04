"""Gesamte Konvertierung: Graustufenbild (oder Vektor-PDF) -> Drawing."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from typing import Callable, List, Optional

import numpy as np

from . import ocr as ocr_mod
from .model import Drawing, Text
from .pdf_vector import PdfVectorSettings, has_vectors, import_page
from .preprocess import PreprocessSettings, to_binary
from .scale_detect import find_scale, format_scale
from .vectorize import MODE_CENTERLINE, MODE_OUTLINE, VectorizeSettings, vectorize

REGION_IGNORE = "ignorieren"
REGION_TEXT_ONLY = "nur_text"
REGION_MODES = {REGION_IGNORE: "Ignorieren", MODE_CENTERLINE: "CAD – Mittellinie",
                MODE_OUTLINE: "CNC – Umriss", REGION_TEXT_ONLY: "Nur Text (keine Linien)"}


@dataclass
class Region:
    """Rechteckiger Bildbereich mit eigener Behandlung (Koordinaten in Bildpixeln)."""
    x: int
    y: int
    w: int
    h: int
    mode: str = REGION_IGNORE

    def slices(self, shape):
        H, W = shape[:2]
        x0, y0 = max(0, int(self.x)), max(0, int(self.y))
        x1, y1 = min(W, int(self.x + self.w)), min(H, int(self.y + self.h))
        return slice(y0, max(y0, y1)), slice(x0, max(x0, x1))

    def contains(self, p) -> bool:
        return self.x <= p[0] <= self.x + self.w and self.y <= p[1] <= self.y + self.h


def _regions(settings) -> List[Region]:
    out = []
    for r in settings.regions or []:
        out.append(r if isinstance(r, Region) else _make(Region, r))
    return [r for r in out if r.mode in REGION_MODES and r.w > 0 and r.h > 0]


def _anchor(e):
    """Repräsentativer Punkt eines Objekts (für Bereichszuordnung)."""
    from .model import Arc, Circle, Line, Polyline
    if isinstance(e, Line):
        return ((e.p1[0] + e.p2[0]) / 2, (e.p1[1] + e.p2[1]) / 2)
    if isinstance(e, (Circle, Arc)):
        return e.center
    if isinstance(e, Polyline) and e.points:
        xs = [p[0] for p in e.points]
        ys = [p[1] for p in e.points]
        return ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
    if isinstance(e, Text):
        return e.position
    return (0, 0)


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
    regions: list = field(default_factory=list)  # Bereiche mit eigener Behandlung (Region/dict)

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
            regions=list(d.get("regions") or []),
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
    regions = _regions(settings)
    for r in regions:
        if r.mode == REGION_IGNORE:
            bw[r.slices(bw.shape)] = 0

    texts, boxes = [], []
    if settings.ocr.enabled:
        step(25, "Texterkennung (OCR) …")
        ocr_src = 255 - bw  # sauberes Schwarz-auf-Weiß-Bild für Tesseract
        texts, boxes = ocr_mod.recognize(ocr_src, settings.ocr)
        bw_vec = ocr_mod.erase_boxes(bw, boxes, settings.ocr.erase_padding)
    else:
        bw_vec = bw

    step(55, "Vektorisierung …")
    main = bw_vec
    special = [r for r in regions if r.mode != REGION_IGNORE and r.mode != settings.vectorize.mode]
    if special:
        main = bw_vec.copy()
        for r in special:
            main[r.slices(main.shape)] = 0
    ents = vectorize(main, settings.vectorize)
    for r in special:
        if r.mode not in (MODE_CENTERLINE, MODE_OUTLINE):
            continue  # nur Text: keine Linien
        sy, sx = r.slices(bw_vec.shape)
        sub = bw_vec[sy, sx]
        if sub.size == 0:
            continue
        from .edit import translate
        part = vectorize(np.ascontiguousarray(sub), replace(settings.vectorize, mode=r.mode))
        ents += [translate(e, sx.start, sy.start) for e in part]

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
    for r in _regions(settings):
        if r.mode == REGION_IGNORE:
            d.entities = [e for e in d.entities if not r.contains(_anchor(e))]
        elif r.mode == REGION_TEXT_ONLY:
            d.entities = [e for e in d.entities if isinstance(e, Text) or not r.contains(_anchor(e))]
    if settings.scale:
        d.scale = settings.scale
    # PDF-Texte stammen direkt aus der Datei (keine Texterkennung nötig) – sie werden über
    # settings.pdf.include_text gesteuert, unabhängig davon, ob Tesseract vorhanden ist.
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
