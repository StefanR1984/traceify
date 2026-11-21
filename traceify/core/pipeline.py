"""Gesamte Konvertierung: Graustufenbild (oder Vektor-PDF) -> Drawing."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, replace
from typing import Callable, List, Optional

import numpy as np

from . import ocr as ocr_mod
from .model import LAYER_DASHED, LAYER_HATCH, LAYER_LINES, Drawing, Line, Text
from .pdf_vector import PdfVectorSettings, has_vectors, import_page, is_stroke_scan
from .preprocess import PreprocessSettings, to_binary
from .scale_detect import find_scale, format_scale
from .style import (StyleSettings, classify_thick, classify_thick_mm, cleanup, detect_dashed,
                    detect_hatch, measure_widths, walls_to_outline)
from .vectorize import MODE_CENTERLINE, MODE_OUTLINE, VectorizeSettings, vectorize

DASH2_MAX_MM = 3.0      # zweiter Strichlinien-Durchgang: nur Striche bis zu dieser Länge (Papier-mm)
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
    """Erkannten Zeichnungsmaßstab anwenden (nur ohne manuell gesetzten Maßstab). Vorrang haben
    die Maßketten (viele Maße, die zur gezeichneten Länge passen) vor einer „M 1:100“-Angabe, die
    auch zu einem Detail gehören kann."""
    if settings.scale is not None or not settings.auto_scale:
        return
    from .dimensions import scale_from_dims
    texts = d.by_type(Text)
    named = find_scale(t.text for t in texts)
    measured = scale_from_dims(texts, d.scale)  # aus den Maßketten: Länge gegen Maßzahl
    n = measured or named
    if n and n != 1:
        d.scale *= n
        d.meta["massstab"] = format_scale(n)
        d.meta["massstab_quelle"] = "aus Maßketten" if measured else "aus Plan erkannt"
        if measured and named and named != measured:
            d.meta["massstab_quelle"] += f", Plan nennt {format_scale(named)}"


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
    bw = to_binary(gray, settings.preprocess, 1.0 / dpi_scale)
    bw_ocr = to_binary(gray, settings.preprocess) if settings.preprocess.auto else bw
    regions = _regions(settings)
    for r in regions:
        if r.mode == REGION_IGNORE:
            bw[r.slices(bw.shape)] = 0

    texts, boxes = [], []
    if settings.ocr.enabled:
        step(25, "Texterkennung (OCR) …")
        # sauberes Schwarz-auf-Weiß-Bild für Tesseract – ohne die automatische Aufbereitung
        # (gefüllte Löcher fetter Schrift kosten Lesungen)
        ocr_src = 255 - _ignore(bw_ocr, regions) if bw_ocr is not bw else 255 - bw
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
        detail = None                  # Graustufen für das Nachlesen von Maßzahlen
        if not settings.preprocess.deskew:
            detail = up if zoom > 1 else gray
            if settings.preprocess.invert:
                detail = 255 - detail
        texts, boxes = ocr_mod.recognize(ocr_src, settings.ocr, px_per_mm=ppm * zoom, zoom=zoom,
                                         detail=detail)
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
    gravel = []
    if settings.style.dots and not settings.preprocess.deskew:
        # Punktmuster (Kies) vor dem Vektorisieren: Entflecken und Skelett verlieren die Punkte
        from .dots import find_dots
        gravel, dot_mask = find_dots(gray, 1.0 / dpi_scale, boxes, settings.preprocess.invert)
        gravel = [c for c in gravel if not any(r.mode == REGION_IGNORE and r.contains(c.center)
                                               for r in regions)]
        if gravel:
            main = np.where(dot_mask > 0, 0, main).astype(main.dtype)
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
        if settings.style.detect_dashed and settings.vectorize.mode == MODE_CENTERLINE \
                and not settings.preprocess.deskew:
            # feine Strichlinien: Striche < 0,8 mm fallen dem Entflecken zum Opfer
            from .dashes import JOIN_MM, chain_dashes, drop_covered, join_chains, small_dashes
            raw = to_binary(gray, replace(settings.preprocess, despeckle=0, auto=False,
                                          fill_holes=0, thicken=0))
            raw = _ignore(ocr_mod.erase_boxes(raw, boxes, settings.ocr.erase_padding)
                          if boxes else raw, regions)
            for r in special:
                raw[r.slices(raw.shape)] = 0
            if gravel:
                raw[dot_mask > 0] = 0
            fine = join_chains(chain_dashes(small_dashes(raw, 1.0 / dpi_scale)), JOIN_MM / dpi_scale)
            ents = drop_covered(ents, fine, max(1.5, 0.15 / dpi_scale)) + fine
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
    ink_gray = None
    if not settings.preprocess.deskew:           # nur, wenn Graubild und Vektoren deckungsgleich
        ink_gray = 255 - gray if settings.preprocess.invert else gray
    if ink_gray is not None and settings.vectorize.mode == MODE_CENTERLINE:
        from .cad import arcs_to_corners, flatten_arcs, ink_share
        share = ink_share(ink_gray)
        arcs_to_corners(ents, share, 4.0 / dpi_scale)   # abgerundete Ecken wieder spitz
        flatten_arcs(ents, share, 4.0 / dpi_scale)      # Wellen entlang gerader Linien
    if settings.style.straighten and settings.vectorize.mode == MODE_CENTERLINE:
        from .cad import ink_share
        from .straighten import straighten
        step(90, "Linien ausrichten …")
        skew = straighten(ents, gray.shape[1], gray.shape[0], settings.style.straighten_tol,
                          join_tol=max(2.0, settings.vectorize.snap_distance),
                          second_shift=max(1.5, 0.3 / dpi_scale),
                          ink=None if ink_gray is None else ink_share(ink_gray))
    if settings.style.spurs_mm > 0 and settings.vectorize.mode == MODE_CENTERLINE:
        from .cad import remove_spurs
        remove_spurs(ents, settings.style.spurs_mm / dpi_scale,
                     tol=max(1.0, 0.15 / dpi_scale), skip_layers=(LAYER_DASHED,))
    if settings.style.close_gaps_mm > 0 and settings.vectorize.mode == MODE_CENTERLINE:
        from .cad import close_gaps, ink_checker
        ink_ok = None if ink_gray is None else ink_checker(ink_gray)
        # bis 0,8 mm immer; bis zum 2,5-Fachen nur, wo der Scan durchgehend Tinte zeigt
        close_gaps(ents, settings.style.close_gaps_mm / dpi_scale,
                   far=2.5 * settings.style.close_gaps_mm / dpi_scale, ink_ok=ink_ok)
    if settings.style.join_lines and settings.vectorize.mode == MODE_CENTERLINE:
        from .cad import ink_checker, join_collinear
        # an Kreuzungen zerfallene Linien wieder durchziehen (Lücke gekreuzt oder voller Tinte)
        join_collinear(ents, 1.0 / dpi_scale, lateral=max(1.5, 0.15 / dpi_scale),
                       ink_ok=None if ink_gray is None else ink_checker(ink_gray),
                       skip_layers=(LAYER_DASHED,))
    if settings.style.hatch_layer and not groups and settings.vectorize.mode == MODE_CENTERLINE:
        from .cad import extend_hatch_ends, ink_checker
        # zweiter Durchgang: nach Ausrichten, Fransen und Lückenschließen sind die Striche
        # sauberer – vorher zerrissene Schraffurlinien werden jetzt erkannt
        detect_hatch(ents, dpi_scale)
        # Schraffur endet im Scan oft kurz vor der Wandkante: bis dorthin ziehen, wenn
        # Nachbarlinien an derselben Kante enden
        extend_hatch_ends(ents, 2.5 / dpi_scale, 8.0 / dpi_scale, LAYER_HATCH,
                          None if ink_gray is None else ink_checker(ink_gray))
        from .hatch import find_regions
        from .style import drop_loose_hatch
        # lose Striche ohne Fläche und ohne Kanten (Handschrift, Möbel) sind keine Schraffur
        drop_loose_hatch(ents, find_regions(ents), 3.0 / dpi_scale, 10.0 / dpi_scale)
    if settings.style.detect_dashed and not groups and settings.vectorize.mode == MODE_CENTERLINE:
        # zweiter Durchgang auf der fertigen Geometrie: blasse Striche waren beim ersten noch
        # zerrissen oder hingen an Nachbarn. Nur dünne Linien – Stücke dicker Wandkanten und
        # Schraffur würden in Doppellinien zu falschen Mittellinien verkettet, längere Stücke
        # verschiedener Linien auf einer Geraden zu einer Scheinstrichlinie
        import math

        def short(e):
            return (isinstance(e, Line) and e.layer == LAYER_LINES
                    and math.dist(e.p1, e.p2) <= DASH2_MAX_MM / dpi_scale)
        fine = detect_dashed([e for e in ents if short(e)], settings.style, skip_missing=True)
        ents = [e for e in ents if not short(e)] + fine
    if settings.style.specks_layer:
        from .cad import isolate_specks
        from .model import LAYER_SPECKS
        isolate_specks(ents, 1.0 / dpi_scale, 1.0 / dpi_scale, LAYER_SPECKS)
    scale = settings.scale or dpi_scale
    d = Drawing(width=gray.shape[1], height=gray.shape[0], scale=scale,
                entities=ents + gravel + texts, source=source)
    if (settings.style.hatch_layer or gravel) and settings.style.hatch_areas:
        from .hatch import META_KEY as HATCH_KEY
        d.meta[HATCH_KEY] = "1"     # beim DXF-Export Schraffur und Kies als Fläche ausgeben
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
    if settings.style.dots and path and is_stroke_scan(path, page):
        # Scan als Pixel-Striche: dichte Punktwolken sind Scanstaub, kein Kies
        import copy
        settings = copy.deepcopy(settings)
        settings.style.dots = False
    return convert(gray, settings, dpi_scale, source, progress, color=color)
