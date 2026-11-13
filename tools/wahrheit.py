"""Wahrheits-Prüfstand: Original-CAD-Pläne als Scan simulieren und Traceify daran messen.

Aufruf:
    python tools/wahrheit.py DXF_ORDNER_ODER_DATEI [--massstab 100] [--dpi 150] [--stift 0.25]
                             [--bilder ORDNER] [--bericht bericht.md] [--json roh.json]
                             [--einstellungen gui.json]

Für jede DXF wird ein Scanbild (PNG) erzeugt, mit Traceify vektorisiert und gegen die
Originalgeometrie gemessen. Die Originale und Bilder gehören nicht ins Repo (Datenschutz).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from traceify.api import load_settings  # noqa: E402
from traceify.core.truth import run  # noqa: E402

KOPF = ("| Datei | Bild px | Zeit s | Trefferquote | Genauigkeit | Lage Median mm | Lage 95 % mm "
        "| Objekte (Original) | Bögen (Original) | Ortho (Original) | Wörter richtig | Wörter falsch |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|")


def zeile(name: str, r: dict) -> str:
    return (f"| {name} | {r['bild'][0]}×{r['bild'][1]} | {r['sekunden']} | "
            f"{r['trefferquote'] * 100:.1f} % | {r['genauigkeit'] * 100:.1f} % | "
            f"{r['lage_median_mm']} | {r['lage_p95_mm']} | {r['objekte']} ({r['objekte_original']}) | "
            f"{r['boegen']} ({r['boegen_original']}) | {r['ortho'] * 100:.0f} % "
            f"({r['ortho_original'] * 100:.0f} %) | {r['woerter']} von {r['woerter_original']} | "
            f"{r['woerter_falsch']} |")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("quelle", help="DXF-Datei oder Ordner mit DXF-Dateien")
    p.add_argument("--massstab", type=float, default=100.0, help="Planmaßstab 1:N")
    p.add_argument("--dpi", type=float, default=150.0)
    p.add_argument("--stift", type=float, default=0.25, help="Strichbreite auf dem Papier in mm")
    p.add_argument("--bilder", help="Ordner für die erzeugten Scanbilder (sonst temporär)")
    p.add_argument("--bericht")
    p.add_argument("--json")
    p.add_argument("--einstellungen", help="JSON-Einstellungsdatei aus der GUI")
    a = p.parse_args(argv)
    s = load_settings(a.einstellungen) if a.einstellungen else None
    files = sorted(glob.glob(os.path.join(a.quelle, "*.dxf"))) if os.path.isdir(a.quelle) \
        else [a.quelle]
    out_dir = a.bilder or tempfile.mkdtemp(prefix="traceify_wahrheit_")
    os.makedirs(out_dir, exist_ok=True)
    rows, raw = [KOPF], []
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0]
        print(f"{base} …", file=sys.stderr, flush=True)
        r = run(f, os.path.join(out_dir, base + ".png"), s, a.massstab, a.dpi, a.stift)
        rows.append(zeile(base, r))
        raw.append(r)
    text = (f"Maßstab 1:{a.massstab:g}, {a.dpi:g} dpi, Strich {a.stift:g} mm\n\n" + "\n".join(rows))
    print(text)
    if a.bericht:
        with open(a.bericht, "w", encoding="utf-8") as fh:
            fh.write("# Traceify-Wahrheits-Prüfstand\n\n" + text + "\n")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(raw, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
