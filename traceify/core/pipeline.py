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
from .style import (StyleSettings, classify_thick, classify_thick_mm, cleanup, detect_dashed,
                    detect_hatch, measure_widths, walls_to_outline)
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


def _ignore(bw: np.ndarray, regions) -> np.ndarray:
    """Bereiche „ignorieren“ im Binärbild leeren."""
    for r in regions:
        if r.mode == REGION_IGNORE:
            bw[r.slices(bw.shape)] = 0
    return bw


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
    style: StyleSettings = field(default_factory=StyleSettings)
    scale: Optional[float] = None  # mm pro Pixel; None = aus DPI
    auto_scale: bool = True        # „M 1:N“ im Plan erkennen und in Originalgröße ausgeben
    symbols_auto: bool = False     # Symbole aus der Bibliothek automatisch als Blöcke einsetzen
    symbol_threshold: float = 0.75
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
            style=_make(StyleSettings, d.get("style")),
            scale=d.get("scale"),
            auto_scale=d.get("auto_scale", True),
            symbols_auto=d.get("symbols_auto", False),
            symbol_threshold=d.get("symbol_threshold", 0.75),
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


def _style_post(ents: list, mask: np.ndarray, paper_mm_per_px: float, settings) -> list:
    """Strichstärken messen, dicke Linien einordnen, Strichlinien zusammenfassen."""
    st = settings.style
    if settings.vectorize.mode != MODE_CENTERLINE:
        return ents
    if st.measure_widths or st.thick_layer or st.walls_outline:
        measure_widths(ents, mask, paper_mm_per_px)
        if st.thick_layer or st.walls_outline:
            classify_thick(ents, st)
        if st.walls_outline:
            ents = walls_to_outline(ents, mask, paper_mm_per_px, settings.vectorize.tolerance)
        if not st.measure_widths:
            for e in ents:
                e.lineweight = 0.0
    if st.detect_dashed:
        ents = detect_dashed(ents, st)
    if st.hatch_layer:
        detect_hatch(ents, paper_mm_per_px)
    cleanup(ents)
    return ents


def convert(gray: np.ndarray, settings: ConvertSettings, dpi_scale: float = 25.4 / 300,
            source: str = "", progress: Optional[Callable[[int, str], None]] = None,
            color: Optional[np.ndarray] = None) -> ConvertResult:
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
        ppm = 1.0 / dpi_scale
        pp_ocr = settings.preprocess
        if settings.ocr.despeckle < pp_ocr.despeckle and not pp_ocr.deskew:
            # schwächer entflecken: Punkte und Kommas in Zahlen (11,50) bleiben erhalten
            pp_ocr = replace(pp_ocr, despeckle=max(0, settings.ocr.despeckle))
            ocr_src = 255 - _ignore(to_binary(gray, pp_ocr), regions)
        # grober Scan: Original vergrößern und neu aufbereiten – kleine Schrift wird so
        # deutlich besser gelesen; die Linien bleiben in Originalauflösung. (Mit
        # Schräglagenkorrektur passen die Koordinaten nicht zum Original – dann nicht.)
        zoom = 1 if settings.preprocess.deskew else ocr_mod.ocr_zoom(ppm)
        if zoom > 1:
            import cv2
            up = cv2.resize(gray, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_LINEAR)
            ocr_src = 255 - to_binary(up, replace(pp_ocr, despeckle=pp_ocr.despeckle * zoom * zoom))
            for r in regions:
                if r.mode == REGION_IGNORE:
                    sy, sx = r.slices(bw.shape)
                    ocr_src[sy.start * zoom:sy.stop * zoom, sx.start * zoom:sx.stop * zoom] = 255
        texts, boxes = ocr_mod.recognize(ocr_src, settings.ocr, px_per_mm=ppm * zoom, zoom=zoom)
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
    groups = []
    if settings.style.color_layers and color is not None and color.shape[:2] == gray.shape[:2]:
        from .colors import is_colorful, separate
        if is_colorful(color):
            step(50, "Farben trennen …")
            groups = separate(color, settings.style.color_count)
    if groups:
        ents = []
        for gi, g in enumerate(groups):
            step(55 + int(35 * gi / len(groups)), f"Vektorisierung {g.name} …")
            m = g.mask
            for r in regions:
                if r.mode == REGION_IGNORE or r in special:
                    m[r.slices(m.shape)] = 0
            if boxes:
                m = ocr_mod.erase_boxes(m, boxes, settings.ocr.erase_padding)
            part = _style_post(vectorize(m, settings.vectorize), m, dpi_scale, settings)
            col = None if g.name.endswith(("SCHWARZ", "GRAU")) else g.rgb
            for e in part:
                e.layer = g.name
                e.color = col
            ents += part
    else:
        ents = _style_post(vectorize(main, settings.vectorize), main, dpi_scale, settings)
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

    skew = None
    if settings.style.straighten and settings.vectorize.mode == MODE_CENTERLINE:
        from .straighten import straighten
        step(90, "Linien ausrichten …")
        skew = straighten(ents, gray.shape[1], gray.shape[0], settings.style.straighten_tol,
                          join_tol=max(2.0, settings.vectorize.snap_distance))
    if settings.style.close_gaps_mm > 0 and settings.vectorize.mode == MODE_CENTERLINE:
        from .cad import close_gaps
        close_gaps(ents, settings.style.close_gaps_mm / dpi_scale)
    scale = settings.scale or dpi_scale
    d = Drawing(width=gray.shape[1], height=gray.shape[0], scale=scale,
                entities=ents + texts, source=source)
    if skew is not None and abs(skew) >= 0.05:
        d.meta["schraeglage"] = repr(float(skew))   # volle Genauigkeit für den Export
    if settings.symbols_auto:
        from .symbols import apply_library, load_library
        lib = load_library()
        if lib:
            step(92, "Symbole aus der Bibliothek suchen …")
            n, per = apply_library(d, bw, lib, settings.symbol_threshold)
            if n:
                d.meta["symbole"] = ", ".join(f"{k} ×{v}" for k, v in per.items())
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
    if settings.style.thick_layer:
        classify_thick_mm(d.entities, settings.style)
    if settings.style.color_layers:
        from .colors import layer_for_rgb
        for e in d.entities:
            if not isinstance(e, Text):
                e.layer = layer_for_rgb(e.color)
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
                   dpi_scale: float, pdf_dpi: int = 0, source: str = "",
                   progress: Optional[Callable[[int, str], None]] = None,
                   allow_vectors: bool = True, color: Optional[np.ndarray] = None) -> ConvertResult:
    """Wählt automatisch: Vektor-PDF direkt übernehmen oder Raster vektorisieren."""
    if path and (not pdf_dpi or pdf_dpi <= 0):
        from .loader import resolve_dpi
        pdf_dpi = resolve_dpi(path, page, 0)
    if allow_vectors and path and has_vectors(path, page, settings.pdf):
        return convert_pdf_vectors(path, page, pdf_dpi, settings, gray, progress)
    return convert(gray, settings, dpi_scale, source, progress, color=color)
