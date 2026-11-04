"""Tests zu 0.12.0: schräge Texte, KI für Handschrift, Ecken statt Bögen, Schraffur, Wände,
Dehnen von Polylinien/Bögen, neue Prüfstand-Kennzahlen."""
import json
import math

import cv2
import numpy as np
import pytest

import traceify as tf
from traceify.core import benchmark, cad
from traceify.core.model import (LAYER_HATCH, LAYER_THICK, LAYER_WALLS, Arc, Drawing, Line,
                                 Polyline, Text)
from traceify.core.ocr import OcrSettings, recognize, tesseract_available, text_layer
from traceify.core.style import detect_hatch, walls_to_outline
from traceify.core.textlines import find_candidates, read_candidates
from traceify.core.vectorize import VectorizeSettings, vectorize


def _rotated_text(text, angle, size=(700, 900), scale=1.6, thick=3, font=cv2.FONT_HERSHEY_SIMPLEX):
    """Schwarz-auf-Weiß-Bild mit einem um angle (Grad, gegen den Uhrzeigersinn) gedrehten Text."""
    img = np.full(size, 255, np.uint8)
    (tw, th), _ = cv2.getTextSize(text, font, scale, thick)
    cx, cy = size[1] // 2, size[0] // 2
    cv2.putText(img, text, (cx - tw // 2, cy + th // 2), font, scale, 0, thick)
    M = cv2.getRotationMatrix2D((cx, cy), angle, 1.0)
    return cv2.warpAffine(img, M, (size[1], size[0]), borderValue=255)


# ----------------------------------------------------------------- schräge Texte
def test_kandidaten_finden_schraege_zeile_und_winkel():
    img = _rotated_text("PERSONAL 12", 35)
    ink = 255 - img
    c = find_candidates(text_layer(ink, 6.0, 15.0), 6.0)
    assert c
    best = max(c, key=lambda k: k.length)
    # Leserichtung im Bild: 35° gegen den Uhrzeigersinn = -35° (y nach unten) = 145° mod 180
    assert min(abs(best.angle - 145), abs(best.angle + 35)) < 6
    assert best.n >= 6


def test_kandidaten_ignorieren_strichlinien():
    ink = np.zeros((400, 900), np.uint8)
    for x in range(50, 850, 40):                 # Strichlinie aus gleichartigen Strichen
        cv2.line(ink, (x, 200), (x + 25, 200), 255, 3)
    assert not find_candidates(text_layer(ink, 6.0, 15.0), 6.0)


def test_read_candidates_waehlt_bessere_leserichtung():
    img = _rotated_text("MMMMM---", 30)
    ink = 255 - img
    cands = find_candidates(text_layer(ink, 6.0, 15.0), 6.0)

    def fake_ocr(crops, s):
        # „liest“ nur die richtig herum liegende Variante: die dicken M stehen links
        out = []
        for c in crops:
            left = (c[:, : c.shape[1] // 2] < 128).sum()
            right = (c[:, c.shape[1] // 2:] < 128).sum()
            out.append(("MMMMM---", 90.0) if left > right else ("", -1.0))
        return out
    texts, boxes = read_candidates(cands, ink, OcrSettings(), run_ocr=fake_ocr)
    assert len(texts) == 1 and texts[0].text == "MMMMM---"
    assert abs(((texts[0].angle - 30) + 180) % 360 - 180) < 6
    assert boxes


@pytest.mark.skipif(not tesseract_available(), reason="Tesseract nicht installiert")
def test_ocr_liest_schraegen_text():
    img = _rotated_text("BR 900 Dusche", 50)
    texts, _ = recognize(img, OcrSettings(), px_per_mm=6.0)
    hits = [t for t in texts if "Dusche" in t.text or "900" in t.text]
    assert hits
    assert abs(((hits[0].angle - 50) + 180) % 360 - 180) < 8


# ----------------------------------------------------------------- KI für Handschrift
class FakeClient:
    def __init__(self):
        self.calls = 0

    def chat(self, model, msgs, fmt=None, temperature=0.0, **kw):
        self.calls += 1
        assert msgs[0]["images"]
        return json.dumps({"text": "Keller", "sicher": True, "kopf": False})


def test_read_unrecognized_mit_attrappe():
    from traceify.ai.assistant import entities_in_region, read_unrecognized
    img = _rotated_text("Keller", 20, font=cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, scale=2.4)
    bw = 255 - img
    ents = vectorize(bw, VectorizeSettings())
    d = Drawing(width=900, height=700, scale=25.4 / 150, entities=ents)
    client = FakeClient()
    fixes = read_unrecognized(client, "x", img, bw, d, 6.0)
    assert fixes and fixes[0].is_new and fixes[0].new == "Keller"
    t = fixes[0].entity
    # Leserichtung (0° oder 180° dazu) entscheidet die KI über „kopf“ – hier nur die Lage
    assert isinstance(t, Text) and abs(((t.angle - 20) + 90) % 180 - 90) < 8
    gone = entities_in_region(d.entities, fixes[0].region)
    assert len(gone) >= 0.8 * len(ents)     # fast alle Buchstaben-Linien liegen im Bereich


def test_bereits_erkannte_texte_werden_nicht_nochmal_gelesen():
    from traceify.ai.assistant import unread_candidates
    img = _rotated_text("KELLER 12", 0)
    bw = 255 - img
    d = Drawing(width=900, height=700, scale=0.2, entities=[])
    assert unread_candidates(bw, d, 6.0)
    ys, xs = np.nonzero(bw)
    d.entities.append(Text("KELLER 12", (float(xs.min()), float(ys.max())),
                           float(ys.max() - ys.min()) * 0.8))
    assert not unread_candidates(bw, d, 6.0)


# ----------------------------------------------------------------- Ecken statt Bögen
def test_rechteckecke_wird_ecke_nicht_bogen():
    img = np.zeros((300, 300), np.uint8)
    cv2.rectangle(img, (50, 50), (250, 250), 255, 7)       # dicker Strich -> gerundete Ecken
    ents = vectorize(img, VectorizeSettings())
    assert not [e for e in ents if isinstance(e, Arc)]
    assert len([e for e in ents if isinstance(e, Line)]) <= 6


def test_kleiner_echter_kreisbogen_bleibt():
    img = np.zeros((300, 300), np.uint8)
    cv2.ellipse(img, (150, 150), (40, 40), 0, 0, 120, 255, 2)
    ents = vectorize(img, VectorizeSettings())
    assert any(isinstance(e, Arc) and abs(e.radius - 40) < 3 for e in ents)


# ----------------------------------------------------------------- Schraffur und Wände
def _hatched_wall(img, x0, y0, x1, y1, step=8):
    cv2.rectangle(img, (x0, y0), (x1, y1), 255, 2)
    w = y1 - y0
    for x in range(x0 - w, x1, step):
        a, b = (x, y1), (x + w, y0)
        # nur innerhalb der Wand zeichnen
        cv2.line(img, a, b, 255, 1)
    img[:y0, :] = 0
    img[y1 + 1:, :] = 0
    img[:, :x0] = 0
    img[:, x1 + 1:] = 0
    cv2.rectangle(img, (x0, y0), (x1, y1), 255, 2)


def test_schraffur_auf_eigenen_layer():
    ents = []
    for k in range(10):                                  # schräge Schar in regelmäßigem Abstand
        ents.append(Line((100 + 8 * k, 120.0), (115 + 8 * k, 100.0)))
    edge = Line((90.0, 120.0), (300.0, 120.0))
    stairs = [Line((400.0, 100 + 10 * k), (500.0, 100 + 10 * k)) for k in range(8)]
    single = Line((600.0, 600.0), (640.0, 560.0))
    all_ = ents + [edge, single] + stairs
    n = detect_hatch(all_, 25.4 / 96)
    assert n == 10
    assert all(e.layer == LAYER_HATCH for e in ents)
    assert edge.layer != LAYER_HATCH and single.layer != LAYER_HATCH
    assert all(s.layer != LAYER_HATCH for s in stairs)    # waagrechte Scharen bleiben


def test_schraffur_in_pipeline():
    img = np.zeros((300, 700), np.uint8)
    _hatched_wall(img, 50, 120, 650, 150)
    s = tf.ConvertSettings()
    s.ocr.enabled = False
    d = tf.convert(255 - img, s, 25.4 / 96).drawing
    assert sum(e.layer == LAYER_HATCH for e in d.entities) >= 40


def test_waende_als_umriss():
    img = np.zeros((400, 600), np.uint8)
    cv2.rectangle(img, (50, 50), (550, 350), 255, 14)        # dicke Wand
    for y in range(110, 300, 30):                           # dünne Linien (Einrichtung o. Ä.)
        cv2.line(img, (100, y), (500, y), 255, 2)
    ents = vectorize(img, VectorizeSettings())
    from traceify.core.style import StyleSettings, classify_thick, measure_widths
    measure_widths(ents, img, 0.25)
    classify_thick(ents, StyleSettings())
    assert any(e.layer == LAYER_THICK for e in ents)
    out = walls_to_outline(ents, img, 0.25)
    walls = [e for e in out if e.layer == LAYER_WALLS]
    assert walls and all(isinstance(e, Polyline) and e.closed for e in walls)
    assert not any(e.layer == LAYER_THICK for e in out)
    assert any(isinstance(e, Line) and abs(e.p1[1] - 200) < 3 for e in out)  # dünne bleiben
    # Außen- und Innenkante der Wand: zwei geschlossene Umrisse
    assert len(walls) == 2


def test_waende_umriss_ueber_einstellung():
    img = np.zeros((400, 600), np.uint8)
    cv2.rectangle(img, (50, 50), (550, 350), 255, 14)
    for y in range(110, 300, 30):
        cv2.line(img, (100, y), (500, y), 255, 2)
    s = tf.ConvertSettings()
    s.ocr.enabled = False
    s.style.walls_outline = True
    d = tf.convert(255 - img, s, 0.25).drawing
    assert any(e.layer == LAYER_WALLS for e in d.entities)
    s2 = tf.ConvertSettings.from_dict(s.to_dict())
    assert s2.style.walls_outline and s2.style.hatch_layer and s2.ocr.free_angles


# ----------------------------------------------------------------- Dehnen
def test_dehnen_offene_polylinie_beide_enden():
    wall_r = Line((500.0, 0.0), (500.0, 400.0))
    wall_l = Line((0.0, 0.0), (0.0, 400.0))
    p = Polyline([(100.0, 100.0), (200.0, 200.0), (300.0, 200.0)])
    assert cad.extend([p, wall_r, wall_l], p, (295, 200))
    assert p.points[-1] == pytest.approx((500.0, 200.0))
    assert cad.extend([p, wall_r, wall_l], p, (101, 101))
    assert p.points[0] == pytest.approx((0.0, 0.0))
    assert len(p.points) == 3


def test_geschlossene_polylinie_wird_nicht_gedehnt():
    p = Polyline([(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)], closed=True)
    assert not cad.extend([p, Line((50.0, -50.0), (50.0, 50.0))], p, (10, 0))


def test_dehnen_bogen_bis_linie():
    arc = Arc((0.0, 0.0), 100.0, 0.0, 45.0)              # Bild: von rechts nach rechts unten
    stop = Line((-200.0, 100.0 * math.sin(math.radians(80))),
                (200.0, 100.0 * math.sin(math.radians(80))))
    end_pt = (100 * math.cos(math.radians(45)), 100 * math.sin(math.radians(45)))
    assert cad.extend([arc, stop], arc, end_pt)
    assert arc.end_angle == pytest.approx(80.0, abs=0.01) and arc.start_angle == 0.0


def test_dehnen_bogen_ohne_ziel():
    arc = Arc((0.0, 0.0), 100.0, 0.0, 45.0)
    assert not cad.extend([arc, Line((500.0, 500.0), (600.0, 600.0))], arc, (100, 0))


# ----------------------------------------------------------------- Prüfstand-Kennzahlen
def test_ortho_anteil_und_offene_enden():
    ents = [Line((0.0, 0.0), (100.0, 0.0)), Line((100.0, 0.0), (100.0, 100.0)),
            Line((0.0, 0.0), (100.0, 102.0))]            # schräg, zählt nicht als ortho
    share = benchmark.ortho_share(ents)
    assert 0.4 < share < 0.6
    # Enden: (0,0) dreifach verbunden, (100,0) verbunden, (100,100) frei, (100,102) frei?
    # (100,102) liegt 2 px neben (100,100) -> innerhalb Toleranz 2 verbunden
    assert benchmark.free_ends(ents, tol=2.0) == 0
    ents.append(Line((300.0, 300.0), (400.0, 300.0)))
    assert benchmark.free_ends(ents, tol=2.0) == 2


def test_t_stoss_ist_kein_offenes_ende():
    ents = [Line((0.0, 0.0), (200.0, 0.0)), Line((100.0, 0.0), (100.0, 100.0))]
    assert benchmark.free_ends(ents) == 3        # nur die drei echten Enden


def test_metrics_enthalten_neue_kennzahlen():
    img = np.zeros((300, 300), np.uint8)
    cv2.rectangle(img, (50, 50), (250, 250), 255, 3)
    ents = vectorize(img, VectorizeSettings())
    m = benchmark.measure("x", ents, img, 0.2)
    assert m.ortho > 0.95 and m.free_ends == 0
    assert "ortho" in m.as_dict() and "free_ends" in m.as_dict()


# ----------------------------------------------------------------- Schräglage / Ausrichten
def _skewed_plan(deg, size=(800, 1000)):
    img = np.zeros(size, np.uint8)
    cv2.rectangle(img, (150, 150), (850, 650), 255, 4)
    for y in (300, 450):
        cv2.line(img, (150, y), (850, y), 255, 3)
    cv2.line(img, (500, 150), (500, 650), 255, 3)
    M = cv2.getRotationMatrix2D((size[1] / 2, size[0] / 2), deg, 1.0)
    return cv2.warpAffine(img, M, (size[1], size[0]))


def test_schraeglage_wird_erkannt_und_beim_export_herausgedreht(tmp_path):
    import ezdxf
    from traceify.core.straighten import estimate_skew
    img = _skewed_plan(1.0)                       # 1° gegen den Uhrzeigersinn (Bildschirm)
    s = tf.ConvertSettings()
    s.ocr.enabled = False
    d = tf.convert(255 - img, s, 0.2).drawing
    skew = float(d.meta["schraeglage"])
    assert abs(skew + 1.0) < 0.15                 # Bildsystem: -1°
    assert abs(estimate_skew(d.entities) - skew) < 1e-6
    # auf dem Scan bleiben die Vektoren deckungsgleich (also schief) …
    long_ = [l for l in d.by_type(Line) if math.dist(l.p1, l.p2) > 300]
    assert all(abs(benchmark.ortho_share([l]) - 0) < 1e-9 for l in long_)
    # … der Export ist exakt achsparallel
    assert benchmark.ortho_share(d.export_view().entities) > 0.99
    p = str(tmp_path / "x.dxf")
    tf.export(d, p)
    lines = ezdxf.readfile(p).modelspace().query("LINE")
    long_dxf = [l for l in lines if math.dist(l.dxf.start, l.dxf.end) > 50]
    assert long_dxf and all(abs(l.dxf.start.x - l.dxf.end.x) < 1e-4
                            or abs(l.dxf.start.y - l.dxf.end.y) < 1e-4 for l in long_dxf)


def test_ausrichten_haelt_ecken_verbunden():
    img = _skewed_plan(0.7)
    s = tf.ConvertSettings()
    s.ocr.enabled = False
    d = tf.convert(255 - img, s, 0.2).drawing
    assert benchmark.free_ends(d.export_view().entities) == 0


def test_ohne_schraeglage_keine_drehung():
    img = _skewed_plan(0.0)
    s = tf.ConvertSettings()
    s.ocr.enabled = False
    d = tf.convert(255 - img, s, 0.2).drawing
    assert "schraeglage" not in d.meta
    assert d.export_view() is d


def test_ausrichten_abschaltbar():
    img = _skewed_plan(1.0)
    s = tf.ConvertSettings()
    s.ocr.enabled = False
    s.style.straighten = False
    d = tf.convert(255 - img, s, 0.2).drawing
    assert "schraeglage" not in d.meta


def test_export_view_dreht_boegen_texte_und_symbole():
    from traceify.core.edit import rotate
    from traceify.core.model import Insert
    d = Drawing(width=200, height=200, scale=1.0, meta={"schraeglage": "10"}, entities=[
        Arc((100.0, 100.0), 50.0, 10.0, 100.0), Text("A", (100.0, 100.0), 5.0, 0.0),
        Insert("S", (150.0, 100.0), 0.0)])
    v = d.export_view()
    a, t, i = v.entities
    assert a.start_angle == pytest.approx(0.0) and a.end_angle == pytest.approx(90.0)
    assert t.angle == pytest.approx(10.0)          # CAD-Winkel: gegen den Uhrzeigersinn
    assert i.rotation == pytest.approx(10.0)
    back = rotate(rotate(Line((0.0, 0.0), (10.0, 0.0)), (5.0, 5.0), 33), (5.0, 5.0), -33)
    assert back.p2 == pytest.approx((10.0, 0.0))
    assert "schraeglage" in d.meta and "schraeglage" not in v.meta


def test_ortho_zeichnen_folgt_schraeglage():
    p = cad.ortho((0.0, 0.0), (100.0, 3.0), angle_deg=2.0)
    assert math.degrees(math.atan2(p[1], p[0])) == pytest.approx(2.0)
    assert cad.ortho((0.0, 0.0), (100.0, 3.0)) == (100.0, 0.0)


# ----------------------------------------------------------------- 0.14.0
def test_kurze_linie_mit_unsicherem_winkel_wird_ausgerichtet():
    from traceify.core.edit import orthogonalize
    short = Line((0.0, 0.0), (8.0, 1.0))          # 7° schief, Ende nur 1 px daneben
    long_ = Line((0.0, 50.0), (100.0, 60.0))      # 5,7° schief, 10 px daneben – bleibt
    assert orthogonalize([short, long_], tol_deg=3.0, min_px=1.5) == 1
    assert short.p1[1] == short.p2[1]
    assert long_.p1[1] != long_.p2[1]
    diag = Line((0.0, 0.0), (3.0, 3.0))           # kurz, aber schräg (45°) – bleibt
    assert orthogonalize([diag], tol_deg=3.0, min_px=1.5) == 0


def test_kleine_luecken_schliessen():
    wall = Line((0.0, 0.0), (0.0, 100.0))
    t = Line((3.0, 50.0), (80.0, 50.0))            # endet 3 px vor der Wand
    far = Line((20.0, 80.0), (80.0, 80.0))          # 20 px Abstand – bleibt (z. B. Tür)
    n = cad.close_gaps([wall, t, far], 5.0)
    assert n == 1
    assert t.p1 == pytest.approx((0.0, 50.0))
    assert far.p1 == (20.0, 80.0)
    assert cad.close_gaps([wall, t, far], 5.0) == 0    # schon geschlossen


def test_luecken_schliessen_in_pipeline_und_abschaltbar():
    img = np.zeros((300, 400), np.uint8)
    cv2.line(img, (50, 50), (50, 250), 255, 3)
    cv2.line(img, (56, 150), (350, 150), 255, 3)     # Lücke 4 px zur Senkrechten (0,4 mm)
    s = tf.ConvertSettings()
    s.ocr.enabled = False
    d = tf.convert(255 - img, s, 0.1).drawing
    assert benchmark.free_ends(d.entities) == 3
    s.style.close_gaps_mm = 0
    d2 = tf.convert(255 - img, s, 0.1).drawing
    assert benchmark.free_ends(d2.entities) == 4


@pytest.mark.skipif(not tesseract_available(), reason="Tesseract nicht installiert")
def test_ocr_behaelt_dezimalpunkt():
    img = np.full((200, 700), 255, np.uint8)
    cv2.putText(img, "143.50 qm", (60, 120), cv2.FONT_HERSHEY_SIMPLEX, 1.2, 0, 2)
    s = tf.ConvertSettings()
    s.preprocess.despeckle = 40                      # starkes Entflecken für die Linien
    d = tf.convert(img, s, 25.4 / 200).drawing
    assert any("143.50" in t.text or "143,50" in t.text for t in d.by_type(Text)), \
        [t.text for t in d.by_type(Text)]
