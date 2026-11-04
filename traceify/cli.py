"""Kommandozeile: python -m traceify konvertieren …"""
from __future__ import annotations

import argparse
import os
import sys

from . import __version__
from .api import batch_convert, load_settings
from .core.pipeline import ConvertSettings
from .core.vectorize import MODE_CENTERLINE, MODE_OUTLINE
from .export import GcodeSettings


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="traceify", description="Bilder/PDFs nach DXF, SVG, G-Code")
    p.add_argument("--version", action="version", version=__version__)
    p.add_argument("eingabe", help="Datei oder Ordner")
    p.add_argument("-o", "--ausgabe", default="ausgabe", help="Zielordner")
    p.add_argument("-f", "--format", action="append", default=None,
                   help="dxf, svg, nc (mehrfach möglich)")
    p.add_argument("-m", "--modus", choices=[MODE_CENTERLINE, MODE_OUTLINE], default=None)
    p.add_argument("--kein-ocr", action="store_true")
    p.add_argument("--einstellungen", help="JSON-Einstellungsdatei aus der GUI")
    p.add_argument("--tiefe", type=float, default=1.0, help="G-Code Frästiefe mm")
    p.add_argument("-r", "--rekursiv", action="store_true")
    p.add_argument("--ki", action="store_true",
                   help="Einstellungen je Datei von der KI (Ollama) wählen lassen")
    p.add_argument("--ki-regeln", default="", metavar="TEXT",
                   help="Regeln in Klartext für die KI, z. B. \"Logos als G-Code mit 2 mm Tiefe, "
                        "Notizen überspringen\"")
    p.add_argument("--ki-modell", default=None, help="Ollama-Modell für --ki")
    a = p.parse_args(argv)

    s = load_settings(a.einstellungen) if a.einstellungen else ConvertSettings()
    if a.modus:
        s.vectorize.mode = a.modus
    if a.kein_ocr:
        s.ocr.enabled = False
    fmts = ["." + f.lstrip(".").lower() for f in (a.format or ["dxf"])]

    def prog(i, n, msg):
        print(f"[{i}/{n}] {msg}", flush=True)

    def item_done(it):
        if it.note:
            print("   " + it.note, flush=True)

    res = batch_convert(a.eingabe, a.ausgabe, fmts, s, GcodeSettings(cut_depth=a.tiefe),
                        recursive=a.rekursiv, progress=prog, ai=a.ki or bool(a.ki_regeln),
                        rules=a.ki_regeln, ai_model=a.ki_modell, on_item=item_done)
    errors = [r for r in res if r.error]
    for r in errors:
        print(f"FEHLER {os.path.basename(r.source)}: {r.error}", file=sys.stderr)
    skipped = sum(1 for r in res if r.skipped)
    print(f"{len(res) - len(errors) - skipped} von {len(res)} erfolgreich"
          + (f", {skipped} übersprungen" if skipped else "") + ".")
    return 1 if errors else 0

