"""Gescannte Planteile zusammensetzen (core/stitch.py, loader)."""
import cv2
import numpy as np

from traceify.core import loader
from traceify.core.stitch import align, chain_offsets, compose, tile_order


def _plan(h=600, w=900, seed=1):
    """Synthetischer Grundriss: Wände, Schraffur, Text-Kleckse, Kreise."""
    rng = np.random.default_rng(seed)
    img = np.full((h, w), 255, np.uint8)
    for y in sorted(rng.integers(30, h - 30, 6)):
        cv2.line(img, (20, int(y)), (w - 20, int(y)), 0, 3)
    for x in sorted(rng.integers(30, w - 30, 7)):
        y0 = int(rng.integers(20, h // 2))
        cv2.line(img, (int(x), y0), (int(x), int(rng.integers(y0 + 50, h - 20))), 0, 2)
    for _ in range(25):
        x, y = int(rng.integers(40, w - 80)), int(rng.integers(40, h - 40))
        cv2.putText(img, str(int(rng.integers(10, 999))), (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 2)
    for _ in range(8):
        cv2.circle(img, (int(rng.integers(50, w - 50)), int(rng.integers(50, h - 50))),
                   int(rng.integers(10, 40)), 0, 2)
    return img


def test_tile_order_reihe_und_spalte():
    assert tile_order([(625, 190, 1120, 632), (67, 190, 619, 632)]) == ("x", [1, 0])
    assert tile_order([(0, 0, 400, 300), (0, 305, 400, 600)]) == ("y", [0, 1])
    # überdeckende Bilder (Maske über dem Scan) und einzelne Bilder sind keine Teile
    assert tile_order([(90, 120, 930, 690), (92, 120, 933, 695)]) is None
    assert tile_order([(0, 0, 100, 100)]) is None
    # weit auseinander (zwei Pläne auf einer Seite) oder verschieden hoch
    assert tile_order([(0, 0, 400, 300), (600, 0, 1000, 300)]) is None
    assert tile_order([(0, 0, 400, 300), (402, 0, 800, 120)]) is None


def test_stoss_mit_hoehenversatz():
    img = _plan()
    a, b = img[:, :450], img[:, 450:]
    b = np.vstack([np.full((12, b.shape[1]), 255, np.uint8), b])[:600]  # rechter Scan 12 px tiefer
    dx, dy, how = align(a, b, "x")
    assert how == "stoß" and dx == 450 and dy == -12
    out = compose([a, b], [(0, 0), (dx, dy)])
    assert np.array_equal(out[12:592, :], img[:580, :])  # b ragt 12 px über a hinaus


def test_ueberlappung_gefunden():
    img = _plan(seed=3)
    a, b = img[:, :520], img[7:, 430:]  # 90 px Überlappung, b 7 px nach oben beschnitten
    dx, dy, how = align(a, b, "x")
    assert how == "überlappt" and (dx, dy) == (430, 7)
    offs, kinds = chain_offsets([a, b], "x")
    out = compose([a, b], offs)
    assert np.array_equal(out[7:, :], img[7:, :])


def test_spalte_untereinander():
    img = _plan(seed=5).T.copy()
    a, b = img[:450], img[450:]
    b = np.hstack([np.full((b.shape[0], 9), 255, np.uint8), b])[:, :600]
    dx, dy, how = align(a, b, "y")
    assert how == "stoß" and (dx, dy) == (-9, 450)


def test_pdf_mit_zwei_scanteilen_wird_zusammengesetzt(tmp_path):
    import pymupdf
    img = _plan(h=600, w=900, seed=7)
    a, b = img[:, :450], img[:, 450:]
    b = np.vstack([np.full((10, 450), 255, np.uint8), b])[:600]
    # Scankante: gepunktete Linie ganz am Rand des linken Teils
    a = a.copy()
    a[::9, -3] = 0
    pa, pb = tmp_path / "a.png", tmp_path / "b.png"
    cv2.imwrite(str(pa), a)
    cv2.imwrite(str(pb), b)
    doc = pymupdf.open()
    pg = doc.new_page(width=842, height=595)
    # 300 dpi: 450 px = 108 pt; 6 pt weiße Fuge
    pg.insert_image(pymupdf.Rect(100, 100, 208, 244), filename=str(pa))
    pg.insert_image(pymupdf.Rect(214, 100, 322, 244), filename=str(pb))
    f = tmp_path / "zwei.pdf"
    doc.save(str(f))
    doc.close()
    gray, mm = loader.load(str(f), 0, 300)
    assert abs(mm - 25.4 / 300) < 1e-9
    m = int(round(loader.STITCH_MARGIN_MM / 25.4 * 300))
    assert gray.shape[1] == 900 + 2 * m          # Fuge geschlossen
    inner = gray[m + 10 + 12:m + 10 + 590, m:m + 900]  # b ragt 10 px über a hinaus
    ref = img[12:590]
    diff = (inner < 128) != (ref < 128)
    assert diff.mean() < 0.01                    # deckungsgleich bis auf Kanten der Interpolation
    assert (inner[:, 445:449] < 128).sum() < (ref[:, 445:449] < 128).sum() + 20  # Scankante weg
    color = loader.load_color(str(f), 0, 300)
    assert color is None or color.shape[:2] == gray.shape


def test_einzelner_scan_unveraendert(tmp_path):
    import pymupdf
    img = _plan()
    p = tmp_path / "a.png"
    cv2.imwrite(str(p), img)
    doc = pymupdf.open()
    pg = doc.new_page(width=842, height=595)
    pg.insert_image(pymupdf.Rect(100, 100, 316, 244), filename=str(p))
    f = tmp_path / "eins.pdf"
    doc.save(str(f))
    doc.close()
    gray, _ = loader.load(str(f), 0, 300)
    assert abs(gray.shape[0] - 595 / 72 * 300) <= 1 and abs(gray.shape[1] - 842 / 72 * 300) <= 1
