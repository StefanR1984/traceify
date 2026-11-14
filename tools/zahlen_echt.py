"""Je gedrucktem Originaltext im echten Plot prüfen, ob Traceify ihn an derselben Stelle liest.

Aufruf: python tools/zahlen_echt.py PLAN.dxf PLOT.pdf AUSGABE_ORDNER [--massstab 200]

Genauer als die Spalte „Wörter“ des Wahrheits-Prüfstands: dort zählt jedes Wort nur einmal,
wiederholte Maße („6.70“ viermal) fallen nicht ins Gewicht. Schreibt texte.json (Text, Lage,
Höhe, Winkel, gelesen ja/nein, Traceify-Texte in der Nähe) und je fehlendem Text einen
Bildausschnitt in den Ausgabeordner (echte Pläne – nicht ins Repo).
"""
import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main(argv=None) -> int:
    import numpy as np
    from PIL import Image

    from traceify.api import open_file
    from traceify.core import loader
    from traceify.core.model import Text
    from traceify.core.truth import align_scan, load_cad, printed
    p = argparse.ArgumentParser()
    p.add_argument("dxf"); p.add_argument("scan"); p.add_argument("out")
    p.add_argument("--massstab", type=float, default=200.0)
    a = p.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    cad, unit = load_cad(a.dxf)
    gray, mm_per_px = loader.load(a.scan)
    ink = ((gray < 160) * 255).astype(np.uint8)
    truth = printed(align_scan(cad, ink, unit / mm_per_px / a.massstab), ink)
    got = [e for e in open_file(a.scan, 0, None).drawing.expanded() if isinstance(e, Text)]
    rows = []
    for i, t in enumerate(t for t in truth if isinstance(t, Text) and t.text.strip()):
        s = t.text.strip()
        near = [g.text for g in got if math.dist(g.position, t.position) < 4 * t.height + 20]
        ok = any(s in g.split() for g in near)
        rows.append({"text": s, "pos": [round(v) for v in t.position], "h": round(t.height, 1),
                     "winkel": t.angle, "gelesen": ok, "nah": near})
        if not ok:
            x, y = map(int, t.position)
            r = int(t.height * 4)
            Image.fromarray(gray[max(0, y - r):y + r, max(0, x - r):x + 2 * r]).save(
                os.path.join(a.out, f"fehlt_{i:03d}.png"))
    with open(os.path.join(a.out, "texte.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, indent=0)
    print("Texte", len(rows), "gelesen", sum(r["gelesen"] for r in rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
