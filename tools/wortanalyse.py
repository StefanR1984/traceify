"""Wortanalyse: pro Originaltext prüfen, ob Traceify ihn liest, und Merkmale sammeln.

Aufruf: python tools/wortanalyse.py . DXF_ORDNER OUT.json [--dpi 150] [--jobs 4]

Je Originaltext: Text, Lage, Höhe (Papier-mm), Winkel, Wörter, davon gefundene, Traceify-Texte
in der Nähe. Die Scanbilder landen neben OUT.json in „bilder/“ (nicht ins Repo).
"""
import glob
import json
import math
import os
import sys
from concurrent.futures import ProcessPoolExecutor


def one(args):
    repo, path, dpi, tmp = args
    sys.path.insert(0, repo)
    from PIL import Image
    from traceify.api import open_file
    from traceify.core.benchmark import words
    from traceify.core.model import Text
    from traceify.core.truth import load_cad, render_scan
    cad, unit = load_cad(path)
    sc = render_scan(cad, 100.0, dpi, 0.25, unit_mm=unit)
    png = os.path.join(tmp, os.path.basename(path) + f".{int(dpi)}.png")
    Image.fromarray(sc.gray).save(png, dpi=(dpi, dpi))
    res = open_file(png, 0, None)
    got = [e for e in res.drawing.expanded() if isinstance(e, Text)]
    allw = words(got)
    out = {"datei": os.path.basename(path), "mm_per_px": sc.mm_per_px, "texte": [],
           "traceify": [{"text": t.text, "pos": list(t.position), "h": t.height,
                         "winkel": t.angle} for t in got]}
    for t in sc.truth:
        if not isinstance(t, Text) or not t.text.strip():
            continue
        w = sorted(words([t]))
        near = [g.text for g in got
                if math.dist(g.position, t.position) < max(4 * t.height, 30)]
        out["texte"].append({"text": t.text, "pos": list(t.position), "h_mm": t.height * sc.mm_per_px,
                             "winkel": t.angle, "woerter": w,
                             "gefunden": [x for x in w if x in allw], "nah": near})
    return out


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("repo"); p.add_argument("src"); p.add_argument("out")
    p.add_argument("--dpi", type=float, default=150.0); p.add_argument("--jobs", type=int, default=4)
    a = p.parse_args()
    files = sorted(glob.glob(os.path.join(a.src, "*.dxf")))
    tmp = os.path.join(os.path.dirname(os.path.abspath(a.out)), "bilder")
    os.makedirs(tmp, exist_ok=True)
    with ProcessPoolExecutor(a.jobs) as ex:
        res = list(ex.map(one, [(a.repo, f, a.dpi, tmp) for f in files]))
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=0)
    print("fertig", len(res))
