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

    if a.ki:
        return _ki_batch(a, s, fmts)
    res = batch_convert(a.eingabe, a.ausgabe, fmts, s, GcodeSettings(cut_depth=a.tiefe),
                        recursive=a.rekursiv, progress=prog)
    errors = [r for r in res if r.error]
    for r in errors:
        print(f"FEHLER {os.path.basename(r.source)}: {r.error}", file=sys.stderr)
    print(f"{len(res) - len(errors)} von {len(res)} erfolgreich.")
    return 1 if errors else 0


def _ki_batch(a, base, fmts) -> int:
    import copy
    from .api import ai_settings, batch_jobs
    from .core import loader
    srcs = loader.list_inputs(a.eingabe, a.rekursiv) if os.path.isdir(a.eingabe) else [a.eingabe]
    os.makedirs(a.ausgabe, exist_ok=True)
    errors = 0
    jobs = batch_jobs(srcs)
    for k, (path, page, n) in enumerate(jobs):
        name = os.path.basename(path) + (f" Seite {page + 1}" if n > 1 else "")
        try:
            s, sug = ai_settings(path, page, a.ki_modell, copy.deepcopy(base))
            print(f"[{k + 1}/{len(jobs)}] {name}: KI erkennt {sug.get('art')} -> "
                  f"{sug.get('vorlage')}", flush=True)
            res = batch_convert([path], a.ausgabe, fmts, s, GcodeSettings(cut_depth=a.tiefe)) \
                if n == 1 else None
            if n > 1:
                from .api import convert_file
                base_name = os.path.splitext(os.path.basename(path))[0] + f"_S{page + 1:03d}"
                for ext in fmts:
                    convert_file(path, os.path.join(a.ausgabe, base_name + ext), s, page,
                                 GcodeSettings(cut_depth=a.tiefe))
            elif res and res[0].error:
                raise RuntimeError(res[0].error)
        except Exception as exc:
            errors += 1
            print(f"FEHLER {name}: {exc}", file=sys.stderr)
    print(f"{len(jobs) - errors} von {len(jobs)} erfolgreich.")
    return 1 if errors else 0
