"""Erzeugt aus traceify/assets/traceify.svg die App-Icons (PNG, ICO, ICNS).

Aufruf:  python tools/make_icons.py
Benötigt PySide6 (SVG-Rendering) und Pillow.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage, QPainter  # noqa: E402
from PySide6.QtSvg import QSvgRenderer  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "traceify", "assets")
SVG = os.path.join(ASSETS, "traceify.svg")
SIZES = [16, 24, 32, 48, 64, 128, 256, 512, 1024]


def render(size: int) -> Image.Image:
    r = QSvgRenderer(SVG)
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    r.render(p)
    p.end()
    path = os.path.join(ASSETS, f"_tmp_{size}.png")
    img.save(path)
    im = Image.open(path).convert("RGBA")
    im.load()
    os.remove(path)
    return im


def main() -> int:
    QGuiApplication(sys.argv)
    imgs = {s: render(s) for s in SIZES}
    imgs[256].save(os.path.join(ASSETS, "traceify.png"))
    imgs[1024].save(os.path.join(ASSETS, "traceify_1024.png"))
    imgs[256].save(os.path.join(ASSETS, "traceify.ico"),
                   sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print("Icons geschrieben nach", ASSETS)
    return 0


if __name__ == "__main__":
    sys.exit(main())
