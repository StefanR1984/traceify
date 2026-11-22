"""Wahrheits-Prüfstand: Original-CAD-Pläne als Scan simulieren und Traceify daran messen.

Aufruf:
    python tools/wahrheit.py DXF_ORDNER_ODER_DATEI [--massstab 100] [--dpi 150] [--stift 0.25]
                             [--bilder ORDNER] [--bericht bericht.md] [--json roh.json]
                             [--einstellungen gui.json] [--jobs 4]
                             [--scans ORDNER [--massstab 200]]

Für jede DXF wird ein Scanbild (PNG) erzeugt, mit Traceify vektorisiert und gegen die
Originalgeometrie gemessen. Mit --scans werden statt der Simulation echte Scans/Plots
derselben Pläne gemessen (gleicher Dateiname, .pdf/.png/.tif). Ohne --massstab wird der
Plotmaßstab je Plan erkannt (`truth.scan_scale`, Spalte Datei zeigt ihn mit Passung);
gezählt wird nur, was auf dem Scan auch zu sehen ist. Die Originale und Bilder gehören
nicht ins Repo (Datenschutz).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import tempfile
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from traceify.api import load_settings  # noqa: E402
from traceify.core.truth import run, run_real  # noqa: E402

KOPF = ("| Datei | Bild px | Zeit s | Trefferquote | Genauigkeit | Lage Median mm | Lage 95 % mm "
        "| Objekte (Original) | Bögen (Original) | Ortho (Original) | Wörter richtig | Wörter falsch "
        "| Texte richtig |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|")
SCAN_EXT = (".pdf", ".png", ".tif", ".tiff", ".jpg", ".jpeg", ".bmp")


def _kies(r: dict) -> str:
    n = r.get("kies_flaechen") or 0
    out = f", davon {n} Kies-Fl. ({r['kies_genau'] * 100:.0f} % an Kies)" if n else ""
    if r.get("wand_genau") is not None:
        out += f", Wandfläche {r['wand_mm2']:.0f} mm² ({r['wand_genau'] * 100:.0f} % am Original)"
    return out


def zeile(name: str, r: dict) -> str:
    return (f"| {name} | {r['bild'][0]}×{r['bild'][1]} | {r['sekunden']} | "
            f"{r['trefferquote'] * 100:.1f} % | {r['genauigkeit'] * 100:.1f} % | "
            f"{r['lage_median_mm']} | {r['lage_p95_mm']} | {r['objekte']} ({r['objekte_original']}){_kies(r)} | "
            f"{r['boegen']} ({r['boegen_original']}) | {r['ortho'] * 100:.0f} % "
            f"({r['ortho_original'] * 100:.0f} %) | {r['woerter']} von {r['woerter_original']} | "
            f"{r['woerter_falsch']} | {r['texte_richtig']} von {r['texte_original']} |")


def _name(r: dict) -> str:
    name = os.path.splitext(os.path.basename(r["datei"]))[0]
    if r.get("passung") is not None:
        name += f" (1:{r['massstab']:g}, Passung {r['passung']:.2f})"
    return name


def _scan_for(dxf: str, folder: str):
    base = os.path.splitext(os.path.basename(dxf))[0].lower()
    for f in sorted(os.listdir(folder)):
        b, e = os.path.splitext(f)
        if b.lower() == base and e.lower() in SCAN_EXT:
            return os.path.join(folder, f)
    return None


def _one(job):
    f, scan, out_dir, a = job
    s = load_settings(a.einstellungen) if a.einstellungen else None
    print(f"{os.path.basename(f)} …", file=sys.stderr, flush=True)
    if scan:
        ki = None
        if a.ki:
            from traceify.ai import make_client
            kind = "openai" if a.ki.rstrip("/").endswith("/v1") else "ollama"
            ki = (make_client({"ki_server": kind, "openai_url": a.ki, "ollama_url": a.ki}), a.ki_modell)
        return run_real(f, scan, a.massstab or 0, s, ki=ki)
    base = os.path.splitext(os.path.basename(f))[0]
    return run(f, os.path.join(out_dir, base + ".png"), s, a.massstab or 100.0, a.dpi, a.stift)


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("quelle", help="DXF-Datei oder Ordner mit DXF-Dateien")
    p.add_argument("--massstab", type=float,
                   help="Planmaßstab 1:N (Simulation: 100; echte Scans: sonst je Plan erkannt)")
    p.add_argument("--dpi", type=float, default=150.0)
    p.add_argument("--stift", type=float, default=0.25, help="Strichbreite auf dem Papier in mm")
    p.add_argument("--bilder", help="Ordner für die erzeugten Scanbilder (sonst temporär)")
    p.add_argument("--scans", help="Ordner mit echten Scans/Plots der Pläne (statt Simulation)")
    p.add_argument("--jobs", type=int, default=1, help="Pläne parallel messen")
    p.add_argument("--bericht")
    p.add_argument("--json")
    p.add_argument("--einstellungen", help="JSON-Einstellungsdatei aus der GUI")
    p.add_argument("--ki", help="nur mit --scans: KI-Server (…/v1 = vLLM/OpenAI, sonst Ollama), "
                                "liest danach unerkannte Schrift nach und übernimmt sie")
    p.add_argument("--ki-modell", default="Gemma-4-26B-A4B", help="Bildmodell für --ki")
    a = p.parse_args(argv)
    files = sorted(glob.glob(os.path.join(a.quelle, "*.dxf"))) if os.path.isdir(a.quelle) \
        else [a.quelle]
    out_dir = a.bilder or tempfile.mkdtemp(prefix="traceify_wahrheit_")
    os.makedirs(out_dir, exist_ok=True)
    jobs = []
    for f in files:
        scan = _scan_for(f, a.scans) if a.scans else None
        if a.scans and not scan:
            continue
        jobs.append((f, scan, out_dir, a))
    if a.jobs > 1:
        with ProcessPoolExecutor(a.jobs) as ex:
            raw = list(ex.map(_one, jobs))
    else:
        raw = [_one(j) for j in jobs]
    rows = [KOPF] + [zeile(_name(r), r) for r in raw]
    mst = f"Maßstab 1:{a.massstab:g}" if a.massstab else "Maßstab je Plan erkannt"
    kopf = (f"Echte Scans aus {a.scans}, {mst}" if a.scans else
            f"Maßstab 1:{a.massstab or 100:g}, {a.dpi:g} dpi, Strich {a.stift:g} mm")
    text = kopf + "\n\n" + "\n".join(rows)
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
