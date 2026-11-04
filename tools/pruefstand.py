"""Prüfstand: Traceify an echten Scans messen und mit anderen Programmen vergleichen.

Aufruf:
    python tools/pruefstand.py SCAN_ORDNER [--vergleich DXF_ORDNER] [--name Scan2CAD]
                               [--bericht bericht.md] [--einstellungen gui.json]

Im Vergleichsordner werden DXF-Dateien mit gleichem Namen wie der Scan gesucht
(plan.pdf -> plan.dxf). Die Scans selbst gehören nicht ins Repo (Datenschutz).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from traceify.api import load_settings  # noqa: E402
from traceify.core import loader  # noqa: E402
from traceify.core.benchmark import run_file  # noqa: E402

KOPF = ("| Datei | Programm | Zeit s | Objekte | Linien | Bögen | Kreise | Texte | Splitter "
        "| Ortho | Offene Enden | Abdeckung | Genauigkeit | Wörter gemeinsam |\n"
        "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")


def zeile(datei, m, woerter=""):
    return (f"| {datei} | {m.name} | {m.seconds or ''} | {m.objects} | {m.lines} | {m.arcs} | "
            f"{m.circles} | {m.texts} | {m.splinters} | {m.ortho * 100:.0f} % | {m.free_ends} | "
            f"{m.coverage * 100:.1f} % | "
            f"{m.precision * 100:.1f} % | {woerter} |")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("ordner")
    p.add_argument("--vergleich", help="Ordner mit DXF-Dateien eines anderen Programms")
    p.add_argument("--name", default="Vergleich", help="Name des anderen Programms")
    p.add_argument("--bericht", help="Bericht als Markdown speichern")
    p.add_argument("--json", help="Rohdaten als JSON speichern")
    p.add_argument("--einstellungen", help="JSON-Einstellungsdatei aus der GUI")
    a = p.parse_args(argv)
    s = load_settings(a.einstellungen) if a.einstellungen else None
    rows, raw = [KOPF], []
    for f in loader.list_inputs(a.ordner):
        base = os.path.splitext(os.path.basename(f))[0]
        ref = os.path.join(a.vergleich, base + ".dxf") if a.vergleich else None
        ref = ref if ref and os.path.isfile(ref) else None
        print(f"{base} …", file=sys.stderr, flush=True)
        r = run_file(f, s, reference=ref, ref_name=a.name)
        w = r.get("woerter")
        rows.append(zeile(base, r["traceify"],
                          f"{w['gemeinsam']} von {w['gemeinsam'] + w['nur_vergleich']}" if w else ""))
        if ref:
            rows.append(zeile(base, r["vergleich"]))
        raw.append({k: (v.as_dict() if hasattr(v, "as_dict") else v) for k, v in r.items()})
    text = "\n".join(rows)
    print(text)
    if a.bericht:
        with open(a.bericht, "w", encoding="utf-8") as fh:
            fh.write("# Traceify-Prüfstand\n\n" + text + "\n")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(raw, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
