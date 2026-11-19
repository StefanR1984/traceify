"""Scan-PDF mit weißen Abdeckflächen gilt nicht als Vektor-PDF (0.38.11, wolfgang.pdf)."""
import numpy as np

from traceify.core.pdf_vector import has_vectors


def _pdf(tmp_path, masks: bool, lines: int = 0):
    import pymupdf
    doc = pymupdf.open()
    pg = doc.new_page(width=842, height=595)
    img = np.full((200, 300), 255, np.uint8)
    img[50:150, 100] = 0
    pix = pymupdf.Pixmap(pymupdf.csGRAY, 300, 200, img.tobytes(), False)
    pg.insert_image(pymupdf.Rect(100, 100, 400, 300), pixmap=pix)
    if masks:                       # 4 weiße Rechtecke ohne Strich = 16 Zeichenbefehle
        for i in range(4):
            pg.draw_rect(pymupdf.Rect(120 + 40 * i, 120, 150 + 40 * i, 200), color=None, fill=(1, 1, 1))
    for i in range(lines):
        pg.draw_line((500, 100 + 10 * i), (800, 100 + 10 * i), color=(0, 0, 0))
    f = tmp_path / "scan.pdf"
    doc.save(f)
    return str(f)


def test_weisse_abdeckungen_sind_keine_vektoren(tmp_path):
    assert not has_vectors(_pdf(tmp_path, masks=True))


def test_echte_linien_bleiben_vektoren(tmp_path):
    assert has_vectors(_pdf(tmp_path, masks=True, lines=20))
