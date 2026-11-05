import os
import sys


def selftest() -> int:
    """Prüft ohne Oberfläche, ob alle Bausteine laufen (für CI und gebündelte Builds)."""
    import tempfile

    import cv2
    import numpy as np

    from . import __version__
    from .core.pipeline import ConvertSettings, convert
    from .core.ocr import _tesseract_cmd, available_languages, tesseract_available
    from .export import export

    img = np.full((400, 600), 255, np.uint8)
    cv2.rectangle(img, (50, 50), (550, 350), 0, 3)
    cv2.circle(img, (300, 200), 80, 0, 3)
    s = ConvertSettings()
    s.ocr.enabled = False
    res = convert(img, s)
    st = res.drawing.stats()
    out = tempfile.mkdtemp(prefix="traceify_selftest_")
    for ext in (".dxf", ".svg", ".nc"):
        export(res.drawing, os.path.join(out, "selftest" + ext))
    import pymupdf  # PDF-Unterstützung vorhanden?
    import shapely  # Radiuskorrektur vorhanden?
    from .core import quality, symbols   # Module im Paket?
    assert pymupdf.__name__ and shapely.__name__ and quality.assess and symbols.find_matches
    from .core.hatch import find_regions          # Schraffur-Flächen (shapely.ops)
    from .core.model import LAYER_HATCH, Line
    hl = [Line((10.0 + 8 * k, 10.0), (50.0 + 8 * k, 50.0), LAYER_HATCH) for k in range(8)]
    assert len(find_regions(hl)) == 1
    msg = (f"Traceify {__version__} Selbsttest: {st} | Tesseract: "
           f"{'ja ' + '+'.join(l for l in available_languages() if l in ('deu', 'eng')) if tesseract_available() else 'nein'}"
           f" | Pfad: {_tesseract_cmd()} | Ausgabe: {out}")
    print(msg)
    try:
        with open(os.path.join(out, "selftest.txt"), "w", encoding="utf-8") as f:
            f.write(msg + "\n")
    except OSError:
        pass
    ok = st["Kreise"] >= 1 and st["Linien"] >= 4
    if tesseract_available():
        # echte Texterkennung: fängt fehlende/unlesbare Sprachdaten schon im Build ab
        from .core.ocr import OcrSettings, recognize
        t = np.full((200, 700), 255, np.uint8)
        cv2.putText(t, "HALLO 123", (20, 130), cv2.FONT_HERSHEY_SIMPLEX, 3, 0, 6)
        texts, _ = recognize(t, OcrSettings())
        print("OCR-Probe:", [x.text for x in texts])
        if not any("HALLO" in x.text.upper() or "123" in x.text for x in texts):
            print("FEHLER: Texterkennung liefert nichts (Sprachdaten lesbar?)")
            ok = False
    return 0 if ok else 1


def run():
    args = sys.argv[1:]
    if args == ["--selbsttest"]:
        sys.exit(selftest())
    # Keine Argumente oder genau eine Datei (Doppelklick / "Öffnen mit") -> Oberfläche
    if not args or (len(args) == 1 and os.path.isfile(args[0])):
        from .gui.app import main as gui_main
        sys.exit(gui_main())
    from .cli import main
    sys.exit(main())


if __name__ == "__main__":
    run()
