"""Tests für Strichlinien, Strichstärken und Farbtrennung."""
import cv2
import numpy as np

import traceify as tf
from traceify.core import colors, style


def _settings(**style_kw):
    s = tf.ConvertSettings()
    s.ocr.enabled = False
    for k, v in style_kw.items():
        setattr(s.style, k, v)
    return s


def test_dashed_and_center_lines():
    img = np.full((300, 800), 255, np.uint8)
    x = 50
    while x < 700:
        cv2.line(img, (x, 40), (x + 30, 40), 0, 3)
        x += 45
    x = 50
    while x < 700:
        cv2.line(img, (x, 120), (x + 40, 120), 0, 3)
        cv2.line(img, (x + 50, 120), (x + 58, 120), 0, 3)
        x += 68
    for k in range(4):  # einzelne Linien mit großen Lücken: KEINE Strichlinie
        cv2.line(img, (50 + k * 170, 200), (180 + k * 170, 200), 0, 3)
    d = tf.convert(img, _settings()).drawing
    lines = d.by_type(tf.Line)
    dashed = [l for l in lines if l.linetype == "DASHED"]
    center = [l for l in lines if l.linetype == "CENTER"]
    assert len(dashed) == 1 and abs(dashed[0].p1[1] - 40) < 2
    assert abs(dashed[0].p1[0] - 50) < 3 and abs(dashed[0].p2[0] - 680) < 35
    assert len(center) == 1 and abs(center[0].p1[1] - 120) < 2
    assert sum(1 for l in lines if abs(l.p1[1] - 200) < 2) == 4
    assert all(l.layer == "STRICHLINIEN" for l in dashed + center)
    # abschaltbar
    d2 = tf.convert(img, _settings(detect_dashed=False)).drawing
    assert not [l for l in d2.by_type(tf.Line) if l.linetype != "CONTINUOUS"]


def test_widths_and_thick_layer():
    img = np.full((500, 800), 255, np.uint8)
    cv2.line(img, (50, 100), (700, 100), 0, 12)          # Wand
    for y in (200, 260, 320, 380, 440):
        cv2.line(img, (50, y), (700, y), 0, 3)
    d = tf.convert(img, _settings(), dpi_scale=0.1).drawing
    thick = [e for e in d.entities if e.layer == "DICKE_LINIEN"]
    assert len(thick) == 1 and abs(thick[0].p1[1] - 100) < 2
    thin = [e for e in d.by_type(tf.Line) if e.layer == "LINIEN"]
    assert len(thin) == 5
    # OpenCV zeichnet Stärke 12 als 13 px, Stärke 3 als 5 px
    assert abs(thick[0].lineweight - 1.3) < 0.15
    assert abs(np.median([e.lineweight for e in thin]) - 0.5) < 0.15
    assert all(0.1 < e.lineweight < 1.0 for e in thin)   # ~3–5 px × 0,1 mm
    d2 = tf.convert(img, _settings(thick_layer=False, measure_widths=False)).drawing
    assert not [e for e in d2.entities if e.layer == "DICKE_LINIEN"]
    assert all(e.lineweight == 0 for e in d2.entities)


def _color_plan():
    img = np.full((400, 600, 3), 250, np.uint8)
    cv2.rectangle(img, (20, 20), (580, 380), (0, 0, 0), 3)
    cv2.line(img, (50, 100), (550, 100), (0, 0, 220), 3)     # rot (BGR)
    cv2.line(img, (50, 200), (550, 200), (200, 60, 0), 3)    # blau
    cv2.circle(img, (300, 300), 50, (0, 170, 0), 3)          # grün
    noise = np.random.default_rng(1).normal(0, 5, img.shape)
    return np.clip(img + noise, 0, 255).astype(np.uint8)


def test_color_separation_groups():
    groups = colors.separate(_color_plan())
    names = sorted(g.name for g in groups)
    assert names == ["FARBE_BLAU", "FARBE_GRUEN", "FARBE_ROT", "FARBE_SCHWARZ"]
    assert not colors.is_colorful(cv2.cvtColor(cv2.cvtColor(_color_plan(), cv2.COLOR_BGR2GRAY),
                                               cv2.COLOR_GRAY2BGR))


def test_convert_with_color_layers(tmp_path):
    col = _color_plan()
    gray = cv2.cvtColor(col, cv2.COLOR_BGR2GRAY)
    d = tf.convert(gray, _settings(color_layers=True), color=col).drawing
    layers = set(d.layers())
    assert {"FARBE_ROT", "FARBE_BLAU", "FARBE_GRUEN", "FARBE_SCHWARZ"} <= layers
    red = [e for e in d.entities if e.layer == "FARBE_ROT"]
    assert red and all(e.color and e.color[0] > 150 for e in red)
    assert any(isinstance(e, tf.Circle) and e.layer == "FARBE_GRUEN" for e in d.entities)
    # über die API (lädt das Farbbild selbst)
    p = tmp_path / "farbe.png"
    cv2.imwrite(str(p), col)
    d2 = tf.open_file(str(p), settings=_settings(color_layers=True)).drawing
    assert "FARBE_ROT" in d2.layers()
    import ezdxf
    tf.export(d2, str(tmp_path / "f.dxf"))
    doc = ezdxf.readfile(str(tmp_path / "f.dxf"))
    assert "FARBE_ROT" in doc.layers


def test_color_name():
    assert colors.color_name((220, 10, 10)) == "ROT"
    assert colors.color_name((10, 60, 200)) == "BLAU"
    assert colors.color_name((5, 5, 5)) == "SCHWARZ"
    assert colors.layer_for_rgb(None) == "FARBE_SCHWARZ"


def test_style_settings_roundtrip(tmp_path):
    s = tf.ConvertSettings()
    s.style.color_layers = True
    s.style.thick_ratio = 2.2
    p = tmp_path / "s.json"
    tf.save_settings(s, str(p))
    s2 = tf.load_settings(str(p))
    assert s2.style.color_layers and s2.style.thick_ratio == 2.2
    assert isinstance(s2.style, style.StyleSettings)


def test_thick_wall_ends_without_spurs():
    """Dicke Wände: keine Fransen-Bögen an den Enden, Mittellinie reicht bis zur Stirnseite."""
    img = np.full((400, 900), 255, np.uint8)
    cv2.line(img, (100, 200), (800, 200), 0, 22)
    d = tf.convert(img, _settings()).drawing
    assert not d.by_type(tf.Arc)
    lines = d.by_type(tf.Line)
    assert len(lines) == 1
    xs = sorted([lines[0].p1[0], lines[0].p2[0]])
    # cv2 zeichnet mit runden Enden: ±11 px über die Endpunkte hinaus
    assert abs(xs[0] - 89) < 6 and abs(xs[1] - 811) < 6


def test_dashed_line_with_slightly_tilted_dash():
    img = np.full((200, 1600), 255, np.uint8)
    x = 100
    k = 0
    while x < 1450:
        dy = 1 if k == 10 else 0          # ein Strich minimal schief (Scanfehler)
        cv2.line(img, (x, 100), (x + 58, 100 + dy), 0, 4)
        x += 95
        k += 1
    d = tf.convert(img, _settings()).drawing
    dashed = [l for l in d.by_type(tf.Line) if l.linetype == "DASHED"]
    assert len(dashed) == 1
    l = dashed[0]
    assert abs(l.p1[1] - l.p2[1]) < 0.6           # waagrecht trotz schiefem Strich
    assert l.p1[0] < 105 and l.p2[0] > 1380        # über die ganze Länge
