"""Öffentliche Python-API von Traceify.

Beispiel::

    import traceify as rc

    # Einzeldatei
    rc.convert_file("plan.png", "plan.dxf")

    # Mit eigenen Einstellungen
    s = rc.ConvertSettings()
    s.vectorize.mode = rc.MODE_OUTLINE      # Umriss für CNC
    s.ocr.enabled = False
    rc.convert_file("logo.png", "logo.nc", settings=s,
                    gcode=rc.GcodeSettings(cut_depth=2, step_down=0.5))

    # Feinsteuerung
    drawing = rc.open_file("scan.pdf", page=0).drawing
    print(drawing.stats())
    rc.export(drawing, "scan.svg")

    # Stapel
    rc.batch_convert("eingang/", "ausgang/", formats=[".dxf"])
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Callable, Iterable, List, Optional

from .core import loader
from .core.pipeline import ConvertResult, ConvertSettings, convert
from .export import GcodeSettings, export


def open_file(path: str, page: int = 0, settings: Optional[ConvertSettings] = None,
              pdf_dpi: int = 300, progress=None) -> ConvertResult:
    """Lädt eine Datei (Bild oder PDF-Seite) und vektorisiert sie."""
    settings = settings or ConvertSettings()
    gray, scale = loader.load(path, page, pdf_dpi)
    return convert(gray, settings, scale, source=os.path.basename(path), progress=progress)


def ai_settings(path: str, page: int = 0, model: str | None = None,
                base: Optional[ConvertSettings] = None, pdf_dpi: int = 300):
    """Lässt die KI (Ollama) die Datei ansehen und passende Einstellungen wählen.

    Gibt (ConvertSettings, Vorschlag-dict) zurück.
    """
    from .ai import apply_suggestion, default_client, suggest_settings
    from .gui_presets import PRESETS
    client, default_model = default_client()
    gray, _ = loader.load(path, page, pdf_dpi)
    sug = suggest_settings(client, model or default_model, gray)
    s = apply_suggestion(base or ConvertSettings(), sug, PRESETS.get(sug.get("vorlage")))
    return s, sug


def convert_file(src: str, dst: str, settings: Optional[ConvertSettings] = None,
                 page: int = 0, gcode: Optional[GcodeSettings] = None,
                 dxf_version: str = "R2010", pdf_dpi: int = 300) -> ConvertResult:
    res = open_file(src, page, settings, pdf_dpi)
    export(res.drawing, dst, gcode, dxf_version)
    return res


@dataclass
class BatchItem:
    source: str
    page: int
    outputs: List[str]
    error: Optional[str] = None
    stats: Optional[dict] = None


def batch_jobs(sources: Iterable[str]):
    """Zerlegt Dateien in Einzeljobs (jede PDF-Seite ist ein Job)."""
    jobs = []
    for src in sources:
        try:
            n = loader.page_count(src)
        except Exception:
            n = 1
        for p in range(n):
            jobs.append((src, p, n))
    return jobs


def batch_convert(src: str, out_dir: str, formats=(".dxf",),
                  settings: Optional[ConvertSettings] = None,
                  gcode: Optional[GcodeSettings] = None, recursive: bool = False,
                  dxf_version: str = "R2010", pdf_dpi: int = 300,
                  progress: Optional[Callable[[int, int, str], None]] = None,
                  should_stop: Optional[Callable[[], bool]] = None) -> List[BatchItem]:
    """Konvertiert einen Ordner (oder eine Dateiliste) – mehrseitige PDFs seitenweise."""
    sources = loader.list_inputs(src, recursive) if isinstance(src, str) and os.path.isdir(src) \
        else ([src] if isinstance(src, str) else list(src))
    os.makedirs(out_dir, exist_ok=True)
    jobs = batch_jobs(sources)
    results = []
    for k, (path, page, n) in enumerate(jobs):
        if should_stop and should_stop():
            break
        base = os.path.splitext(os.path.basename(path))[0]
        if n > 1:
            base += f"_S{page + 1:03d}"
        if progress:
            progress(k, len(jobs), f"{os.path.basename(path)}" + (f" Seite {page + 1}" if n > 1 else ""))
        item = BatchItem(path, page, [])
        try:
            res = open_file(path, page, settings, pdf_dpi)
            for ext in formats:
                dst = os.path.join(out_dir, base + ext)
                export(res.drawing, dst, gcode, dxf_version)
                item.outputs.append(dst)
            item.stats = res.drawing.stats()
        except Exception as exc:  # weitermachen, Fehler protokollieren
            item.error = f"{type(exc).__name__}: {exc}"
        results.append(item)
    if progress:
        progress(len(jobs), len(jobs), "Fertig")
    return results


def save_settings(settings: ConvertSettings, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings.to_dict(), f, indent=2, ensure_ascii=False)


def load_settings(path: str) -> ConvertSettings:
    with open(path, encoding="utf-8") as f:
        return ConvertSettings.from_dict(json.load(f))
