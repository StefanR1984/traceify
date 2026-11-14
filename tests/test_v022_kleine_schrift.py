"""0.22.0: Hinweis auf 300 dpi bei viel sehr kleiner Schrift in groben Scans."""
import cv2
import numpy as np

from traceify.core.quality import assess, small_text_hint


def _blatt(zeichen_px: int, n: int = 150) -> np.ndarray:
    """Weißes Blatt (255 = Tinte) mit n kleinen „Buchstaben“ (Ringe) der Höhe zeichen_px."""
    ink = np.zeros((800, 1200), np.uint8)
    for i in range(n):
        x, y = 20 + (i % 30) * 38, 30 + (i // 30) * 60
        cv2.ellipse(ink, (x, y), (zeichen_px // 3, zeichen_px // 2), 0, 0, 360, 255, 1)
    return ink


def test_hinweis_nur_bei_kleiner_schrift_und_grobem_scan():
    mm150, mm300 = 25.4 / 150, 25.4 / 300
    assert small_text_hint(_blatt(8), mm150) is not None           # ~1,35 mm bei 150 dpi
    assert small_text_hint(_blatt(8), mm300) is None                # 300 dpi: kein Hinweis
    assert small_text_hint(_blatt(22), mm150) is None               # 3,7 mm: normale Schrift
    assert small_text_hint(_blatt(8, n=40), mm150) is None          # nur wenig kleine Schrift
    assert small_text_hint(_blatt(8), 0.0) is None                  # Auflösung unbekannt


def test_hinweis_steht_in_der_ampel():
    q = assess(_blatt(8), [], mm_per_px=25.4 / 150)
    assert q.hints and "300 dpi" in q.summary()
    assert not assess(_blatt(8), [], mm_per_px=0.0).hints
