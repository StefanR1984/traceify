"""KI-Funktionen von Traceify auf Basis von Ollama.

* suggest_settings – Bild ansehen, Zeichnungsart erkennen, Einstellungen vorschlagen
* correct_texts    – OCR-Ergebnisse Ausschnitt für Ausschnitt mit einem Bildmodell prüfen
* read_unrecognized – Schrift, die die OCR nicht lesen konnte (Handschrift), vom Bildmodell
                     lesen lassen
* Assistant.ask    – Chat in natürlicher Sprache; die KI antwortet mit Text UND
                     ausführbaren Aktionen (Einstellungen ändern, Layer löschen, …)
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Callable, List, Optional

import cv2
import numpy as np

from ..core.model import Drawing, Text
from ..core.pipeline import ConvertSettings
from ..core.vectorize import MODE_CENTERLINE, MODE_OUTLINE
from .ollama_client import OllamaClient, OllamaError, parse_json

PRESET_NAMES = ["Technische Zeichnung", "Grundriss / Architektur", "Handskizze",
                "Kontur-Polylinien (Karte)", "Logo / CNC-Umriss"]


# ------------------------------------------------------------------ Bilder
def encode_image(img: np.ndarray, max_side: int = 1280) -> str:
    """Graustufen- oder BGR-Bild -> base64-PNG (verkleinert)."""
    h, w = img.shape[:2]
    f = min(1.0, max_side / max(h, w))
    if f < 1.0:
        img = cv2.resize(img, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise OllamaError("Bild konnte nicht kodiert werden")
    return base64.b64encode(buf.tobytes()).decode()


def render_overlay(gray: np.ndarray, d: Drawing, max_side: int = 1280) -> np.ndarray:
    """Original (blass) + erkannte Vektoren (farbig) als BGR-Bild – für die KI-Bewertung."""
    from ..core.model import Arc, Circle, Line, Polyline, layer_color
    f = min(1.0, max_side / max(gray.shape))
    base = cv2.resize(gray, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else gray.copy()
    img = cv2.cvtColor((255 - (255 - base) // 3).astype(np.uint8), cv2.COLOR_GRAY2BGR)
    P = lambda p: (int(round(p[0] * f)), int(round(p[1] * f)))
    for e in d.expanded():
        rgb = getattr(e, "color", None) or layer_color(e.layer)[1]
        col = (rgb[2], rgb[1], rgb[0])
        if isinstance(e, Line):
            cv2.line(img, P(e.p1), P(e.p2), col, 2, cv2.LINE_AA)
        elif isinstance(e, Circle):
            cv2.circle(img, P(e.center), int(e.radius * f), col, 2, cv2.LINE_AA)
        elif isinstance(e, Arc):
            span = (e.end_angle - e.start_angle) % 360
            cv2.ellipse(img, P(e.center), (int(e.radius * f),) * 2, 0, e.start_angle,
                        e.start_angle + span, col, 2, cv2.LINE_AA)
        elif isinstance(e, Polyline) and len(e.points) > 1:
            pts = np.array([P(p) for p in e.points], np.int32).reshape(-1, 1, 2)
            cv2.polylines(img, [pts], e.closed, col, 2, cv2.LINE_AA)
        elif isinstance(e, Text):
            cv2.putText(img, e.text, P(e.position), cv2.FONT_HERSHEY_SIMPLEX,
                        max(0.3, e.height * f / 22), col, 1, cv2.LINE_AA)
    return img


# --------------------------------------------------- Einstellungs-Vorschlag
SUGGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "art": {"type": "string"},
        "vorlage": {"type": "string", "enum": PRESET_NAMES},
        "modus": {"type": "string", "enum": [MODE_CENTERLINE, MODE_OUTLINE]},
        "invertieren": {"type": "boolean"},
        "ungleichmaessig_beleuchtet": {"type": "boolean"},
        "schraeg": {"type": "boolean"},
        "verrauscht": {"type": "boolean"},
        "enthaelt_text": {"type": "boolean"},
        "begruendung": {"type": "string"},
    },
    "required": ["art", "vorlage", "modus", "invertieren", "ungleichmaessig_beleuchtet",
                 "schraeg", "verrauscht", "enthaelt_text", "begruendung"],
}

SUGGEST_PROMPT = """Du bist Experte für die Umwandlung gescannter Zeichnungen in CAD- und CNC-Dateien.
Sieh dir das Bild an und bestimme:
- art: Was ist es? (z. B. technische Zeichnung, Grundriss, Schaltplan, Höhenlinienkarte, Logo, Handskizze, Foto)
- vorlage: die passendste Vorlage aus der Liste
- modus: "mittellinie" für Strichzeichnungen (CAD), "umriss" für gefüllte Flächen/Logos/Schneidteile (CNC)
- invertieren: true nur bei hellen Linien auf dunklem Grund
- ungleichmaessig_beleuchtet: Schatten, Vergilbung, Helligkeitsverlauf?
- schraeg: ist der Scan sichtbar schief?
- verrauscht: viele Punkte, Flecken, Körnung?
- enthaelt_text: Beschriftungen vorhanden, die als Text erkannt werden sollen?
- begruendung: 1–2 Sätze auf Deutsch.
Antworte ausschließlich als JSON."""


def suggest_settings(client: OllamaClient, model: str, gray: np.ndarray) -> dict:
    msg = {"role": "user", "content": SUGGEST_PROMPT, "images": [encode_image(gray)]}
    try:
        txt = client.chat(model, [msg], fmt=SUGGEST_SCHEMA, temperature=0.1)
    except OllamaError as e:
        if "format" in str(e).lower() or "schema" in str(e).lower():
            txt = client.chat(model, [msg], fmt="json", temperature=0.1)
        else:
            raise
    data = parse_json(txt)
    if not isinstance(data, dict):
        raise OllamaError("Unerwartete Antwort der KI")
    return data


def apply_suggestion(s: ConvertSettings, sug: dict, preset_values: Optional[dict] = None) -> ConvertSettings:
    """Überträgt einen KI-Vorschlag in ConvertSettings (mit Plausibilitätsprüfung)."""
    if preset_values:
        p = preset_values
        s.vectorize.mode = p["mode"]
        s.vectorize.tolerance = p["tolerance"]
        s.vectorize.detect_arcs = p["arcs"]
        s.vectorize.detect_circles = p["circles"]
        s.vectorize.output_polylines = p["polylines"]
        s.preprocess.despeckle = p["despeckle"]
        s.preprocess.smooth = p["smooth"]
        s.ocr.enabled = p["ocr"]
    if sug.get("modus") in (MODE_CENTERLINE, MODE_OUTLINE):
        s.vectorize.mode = sug["modus"]
    s.preprocess.invert = bool(sug.get("invertieren", False))
    s.preprocess.adaptive = bool(sug.get("ungleichmaessig_beleuchtet", False))
    s.preprocess.deskew = bool(sug.get("schraeg", False))
    if sug.get("verrauscht"):
        s.preprocess.despeckle = max(s.preprocess.despeckle, 40)
    if "enthaelt_text" in sug:
        s.ocr.enabled = bool(sug["enthaelt_text"]) and s.vectorize.mode == MODE_CENTERLINE
    return s


# ------------------------------------------------------- OCR-Korrektur
READ_SCHEMA = {"type": "object",
               "properties": {"text": {"type": "string"}, "sicher": {"type": "boolean"}},
               "required": ["text", "sicher"]}

READ_PROMPT = ("Lies den Text in diesem Ausschnitt einer technischen Zeichnung exakt ab – "
               "Zeichen für Zeichen, inklusive Zahlen, Einheiten, Ø, ±, °, Komma/Punkt. "
               "Nichts erfinden, nichts übersetzen. Bisherige Erkennung: \"{old}\". "
               "Antworte als JSON: text = gelesener Text, sicher = ob du sicher bist. "
               "Ist kein Text zu sehen, gib text = \"\".")


@dataclass
class TextFix:
    entity: Text
    old: str
    new: str
    sure: bool
    is_new: bool = False            # neuer Text (bisher nicht erkannt)
    region: Optional[tuple] = None  # (cx, cy, länge, höhe, winkel) – Bereich der Schrift


def _rotated_crop(gray: np.ndarray, cx: float, cy: float, length: float, height: float,
                  angle_img: float, pad: float = 0.4) -> np.ndarray:
    """Ausschnitt um (cx, cy), so gedreht, dass die Zeile waagrecht liegt.

    angle_img: Leserichtung im Bild in Grad (y nach unten, 0 = nach rechts)."""
    p = pad * height
    w, h = int(length + 2 * p) + 2, int(height + 2 * p) + 2
    M = cv2.getRotationMatrix2D((cx, cy), angle_img, 1.0)
    M[0, 2] += w / 2 - cx
    M[1, 2] += h / 2 - cy
    return cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_LINEAR, borderValue=255)


def _text_crop(gray: np.ndarray, t: Text) -> np.ndarray:
    """Waagrecht gedrehter Ausschnitt um einen erkannten Text (beliebiger Winkel)."""
    import math
    n = max(1, len(t.text))
    h = t.height / 0.8
    L = h * 0.62 * n
    a = math.radians(t.angle)                 # CAD-Winkel, gegen den Uhrzeigersinn
    ux, uy = math.cos(a), -math.sin(a)        # Leserichtung im Bild
    nx, ny = -uy, ux                          # zur Grundlinie hin („unten“)
    x, y = t.position
    cx = x + ux * L / 2 - nx * h / 2
    cy = y + uy * L / 2 - ny * h / 2
    return _rotated_crop(gray, cx, cy, L, h, -t.angle)


def _prepare(crop: np.ndarray) -> np.ndarray:
    # Kleine Ausschnitte vergrößern – Bildmodelle lesen dann besser
    scale = max(1.0, 64 / max(1, crop.shape[0]))
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return cv2.copyMakeBorder(crop, 16, 16, 16, 16, cv2.BORDER_CONSTANT, value=255)


def correct_texts(client: OllamaClient, model: str, gray: np.ndarray, d: Drawing,
                  progress: Optional[Callable[[int, int, str], None]] = None,
                  should_stop: Optional[Callable[[], bool]] = None,
                  limit: int = 60) -> List[TextFix]:
    fixes = []
    texts = d.by_type(Text)[:limit]
    for i, t in enumerate(texts):
        if should_stop and should_stop():
            break
        if progress:
            progress(i, len(texts), t.text)
        crop = _text_crop(gray, t)
        if crop.size == 0:
            continue
        crop = _prepare(crop)
        msg = {"role": "user", "content": READ_PROMPT.format(old=t.text),
               "images": [encode_image(crop, 768)]}
        try:
            res = parse_json(client.chat(model, [msg], fmt=READ_SCHEMA, temperature=0.0))
        except OllamaError:
            continue
        new = str(res.get("text", "")).strip()
        if new and new != t.text:
            fixes.append(TextFix(t, t.text, new, bool(res.get("sicher", False))))
    if progress:
        progress(len(texts), len(texts), "Fertig")
    return fixes


UNREAD_PROMPT = ("Dieser Ausschnitt stammt aus einer technischen Zeichnung oder einem Bauplan und "
                 "enthält vermutlich Schrift, oft von Hand geschrieben (Raumnamen, Maße). Lies sie "
                 "exakt ab, Zeichen für Zeichen; nichts erfinden, nichts übersetzen. Die Schrift kann "
                 "auch auf dem Kopf stehen – dann kopf = true. Antworte als JSON: text = gelesener "
                 "Text, sicher = ob du sicher bist, kopf = steht die Schrift auf dem Kopf. "
                 "Ist keine Schrift zu sehen (nur Linien, Schraffur, Symbole), gib text = \"\".")
UNREAD_SCHEMA = {"type": "object",
                 "properties": {"text": {"type": "string"}, "sicher": {"type": "boolean"},
                                "kopf": {"type": "boolean"}},
                 "required": ["text", "sicher", "kopf"]}


def unread_candidates(bw: np.ndarray, d: Drawing, px_per_mm: float, limit: int = 60):
    """Schriftähnliche Bereiche, an denen noch kein Text steht (Kandidaten für die KI)."""
    from ..core.benchmark import text_box
    from ..core.ocr import text_layer
    from ..core.textlines import find_candidates
    layer = text_layer(bw, px_per_mm, 15.0)
    boxes = [text_box(t, pad=1.0) for t in d.by_type(Text)]
    return find_candidates(layer, px_per_mm, boxes, max_candidates=limit)


def read_unrecognized(client: OllamaClient, model: str, gray: np.ndarray, bw: np.ndarray,
                      d: Drawing, px_per_mm: float,
                      progress: Optional[Callable[[int, int, str], None]] = None,
                      should_stop: Optional[Callable[[], bool]] = None,
                      limit: int = 60) -> List[TextFix]:
    """Lässt das Bildmodell schriftähnliche Stellen lesen, an denen die OCR nichts fand.

    Gibt Vorschläge für neue Texte zurück (TextFix mit is_new=True); übernommen werden sie
    erst nach Bestätigung."""
    import math
    cands = unread_candidates(bw, d, px_per_mm, limit)
    out = []
    for i, c in enumerate(cands):
        if should_stop and should_stop():
            break
        if progress:
            progress(i, len(cands), f"Stelle {i + 1}")
        crop = _prepare(_rotated_crop(gray, c.center[0], c.center[1], c.length, c.height,
                                      c.angle))
        msg = {"role": "user", "content": UNREAD_PROMPT, "images": [encode_image(crop, 768)]}
        try:
            res = parse_json(client.chat(model, [msg], fmt=UNREAD_SCHEMA, temperature=0.0))
        except OllamaError:
            continue
        txt = str(res.get("text", "")).strip()
        if not txt:
            continue
        a = c.angle + (180.0 if res.get("kopf") else 0.0)       # Leserichtung im Bild
        r = math.radians(a)
        ux, uy = math.cos(r), math.sin(r)
        nx, ny = -uy, ux
        bx = c.center[0] - ux * c.length / 2 + nx * c.height / 2
        by = c.center[1] - uy * c.length / 2 + ny * c.height / 2
        t = Text(txt, (float(bx), float(by)), float(c.height) * 0.8, (-a) % 360.0)
        out.append(TextFix(t, "", txt, bool(res.get("sicher", False)), True,
                           (c.center[0], c.center[1], c.length, c.height, c.angle)))
    if progress:
        progress(len(cands), len(cands), "Fertig")
    return out


def entities_in_region(ents: list, region: tuple, margin: float = 0.15) -> list:
    """Objekte (keine Texte), die vollständig im gedrehten Rechteck einer Schriftstelle liegen."""
    import math
    from ..core.edit import entity_points
    cx, cy, L, h, ang = region
    r = math.radians(ang)
    ux, uy = math.cos(r), math.sin(r)
    hl, hh = L / 2 + margin * h, h / 2 + margin * h

    def inside(p):
        dx, dy = p[0] - cx, p[1] - cy
        return abs(dx * ux + dy * uy) <= hl and abs(-dx * uy + dy * ux) <= hh
    out = []
    for e in ents:
        if isinstance(e, Text):
            continue
        try:
            pts = entity_points(e)
        except Exception:
            continue
        if pts and all(inside(p) for p in pts):
            out.append(e)
    return out


# ------------------------------------------------------------- Chat
ACTIONS_DOC = """Verfügbare Aktionen (nur verwenden, wenn der Nutzer etwas verändert haben möchte):
{"aktion":"einstellung","name":NAME,"wert":WERT}
   NAME: modus ("mittellinie"|"umriss"), vorlage (eine von: %s),
         toleranz (0.2–20 px), schwellwert (0=automatisch, 1–254), adaptiv (bool), invertieren (bool),
         begradigen (bool), flecken (px², 0–5000), luecken_schliessen (px, 0–10), glaetten (0–15),
         boegen (bool), kreise (bool), nur_polylinien (bool), min_laenge (px), eckenwinkel (Grad),
         ocr (bool), ocr_sprache ("deu+eng" …), massstab_mm_pro_px (Zahl),
         strichlinien (bool), strichstaerken (bool), dicke_linien_layer (bool),
         waende_umriss (bool), schraffur_layer (bool), schraege_texte (bool),
         gerade_ausrichten (bool), luecken_mm (0–5 mm, 0=aus),
         farben_trennen (bool), anzahl_farben (0=auto), massstab_aus_plan (bool), pdf_vektoren (bool),
         vorschub (mm/min), fraestiefe (mm), zustellung (mm), maschine ("fraese"|"laser"),
         fraeser_durchmesser (mm), radiuskorrektur ("keine"|"aussen"|"innen"|"auto"),
         haltestege (Anzahl, 0=aus), steg_breite (mm), steg_hoehe (mm)
{"aktion":"konvertieren"}                       – mit aktuellen Einstellungen neu vektorisieren
{"aktion":"layer_loeschen","layer":LAYER}        – alle Objekte eines Layers entfernen
{"aktion":"layer_sichtbar","layer":LAYER,"sichtbar":bool}
{"aktion":"kurze_objekte_loeschen","max_mm":ZAHL} – Linien/Polylinien kürzer als max_mm entfernen
{"aktion":"text_ersetzen","alt":TEXT,"neu":TEXT}  – CAD-Text ändern
{"aktion":"drehen","richtung":"links"|"rechts"}
{"aktion":"begradigen"}
{"aktion":"exportieren","format":"dxf"|"dwg"|"svg"|"nc"} – Speichern-Dialog öffnen
{"aktion":"gcode_vorschau"}                     – G-Code-Vorschau mit Zeitschätzung öffnen
Layer heißen: LINIEN, BOEGEN, KREISE, POLYLINIEN, KONTUREN, TEXT, DICKE_LINIEN, WAENDE,
SCHRAFFUR, STRICHLINIEN.""" % ", ".join(PRESET_NAMES)

SYSTEM_PROMPT = """Du bist der KI-Assistent in Traceify, einer Desktop-Software, die gescannte Zeichnungen,
Bilder und PDFs in DXF (CAD), SVG und G-Code (CNC) umwandelt. Du hilfst auf Deutsch, duzt den Nutzer
und antwortest knapp und praxisnah. Du kennst dich mit CAD, CNC-Fräsen, Lasern und Scan-Qualität aus.

Bedienung von Traceify: Datei öffnen → ggf. drehen/zuschneiden/begradigen → Modus wählen
(CAD-Mittellinie für Strichzeichnungen, CNC-Umriss für Logos/Flächen) → Konvertieren (F5) →
falsche Objekte markieren und mit Entf löschen → Export DXF (Strg+E) / G-Code (Strg+G).
Tipps: Linien zerrissen → „Lücken schließen“ erhöhen oder Schwellwert ändern; viele Krümel →
„Flecken entfernen“ erhöhen; Bögen werden zu Linienketten → Toleranz leicht erhöhen.

%s

Antworte IMMER als JSON: {"antwort": "dein Text an den Nutzer", "aktionen": [ … ]}.
Lass "aktionen" leer, wenn nur eine Frage beantwortet wird. Erfinde keine anderen Aktionen.""" % ACTIONS_DOC

CHAT_SCHEMA = {
    "type": "object",
    "properties": {
        "antwort": {"type": "string"},
        "aktionen": {"type": "array", "items": {"type": "object"}},
    },
    "required": ["antwort", "aktionen"],
}


@dataclass
class Assistant:
    client: OllamaClient
    model: str
    history: List[dict] = field(default_factory=list)
    max_history: int = 12

    def reset(self):
        self.history.clear()

    def ask(self, text: str, context: str = "", image_b64: Optional[str] = None) -> dict:
        user = text if not context else f"{text}\n\n[Aktueller Zustand von Traceify]\n{context}"
        msg = {"role": "user", "content": user}
        if image_b64:
            msg["images"] = [image_b64]
        msgs = [{"role": "system", "content": SYSTEM_PROMPT}] + self.history[-self.max_history:] + [msg]
        try:
            raw = self.client.chat(self.model, msgs, fmt=CHAT_SCHEMA, temperature=0.3)
        except OllamaError as e:
            if "format" in str(e).lower() or "schema" in str(e).lower():
                raw = self.client.chat(self.model, msgs, fmt="json", temperature=0.3)
            else:
                raise
        try:
            data = parse_json(raw)
            if not isinstance(data, dict):
                raise OllamaError("kein Objekt")
        except OllamaError:
            data = {"antwort": raw.strip(), "aktionen": []}
        data.setdefault("antwort", "")
        acts = data.get("aktionen") or []
        data["aktionen"] = [a for a in acts if isinstance(a, dict) and a.get("aktion")]
        # Verlauf ohne Bild und ohne langen Kontext speichern
        self.history.append({"role": "user", "content": text})
        self.history.append({"role": "assistant", "content": data["antwort"]})
        return data


def describe_state(path: str, gray, d: Optional[Drawing], settings: ConvertSettings,
                   visible_layers=None) -> str:
    lines = []
    if gray is None:
        return "Es ist noch keine Datei geöffnet."
    H, W = gray.shape
    lines.append(f"Datei: {path or '-'}; Bild {W}×{H} px")
    s = settings
    lines.append(
        f"Einstellungen: modus={s.vectorize.mode}, toleranz={s.vectorize.tolerance}, "
        f"schwellwert={s.preprocess.threshold or 'auto'}, adaptiv={s.preprocess.adaptive}, "
        f"invertieren={s.preprocess.invert}, flecken={s.preprocess.despeckle}, "
        f"luecken_schliessen={s.preprocess.thicken}, boegen={s.vectorize.detect_arcs}, "
        f"kreise={s.vectorize.detect_circles}, ocr={s.ocr.enabled}")
    if d is None:
        lines.append("Noch nicht konvertiert.")
    else:
        st = ", ".join(f"{k}: {v}" for k, v in d.stats().items())
        lines.append(f"Ergebnis: {st}; Größe {W * d.scale:.1f}×{H * d.scale:.1f} mm, "
                     f"Maßstab {d.scale:.5f} mm/px")
        if visible_layers is not None:
            lines.append("Sichtbare Layer: " + (", ".join(sorted(visible_layers)) or "keine"))
        texts = [t.text for t in d.by_type(Text)][:30]
        if texts:
            lines.append("Erkannte Texte: " + " | ".join(texts))
    return "\n".join(lines)


# ------------------------------------------------------------- Symbole
def name_symbol(client: OllamaClient, model: str, crop: np.ndarray) -> str:
    """Kurzer deutscher Name für ein Symbol aus einer technischen Zeichnung."""
    img = cv2.copyMakeBorder(crop, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=255)
    if max(img.shape) < 160:
        f = 160 / max(img.shape)
        img = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_NEAREST)
    msg = {"role": "user", "images": [encode_image(img, 512)],
           "content": ("Das Bild zeigt ein einzelnes Symbol aus einer technischen Zeichnung oder "
                       "einem Bauplan (z. B. Steckdose, Schalter, Leuchte, Tür, Fenster, Ventil, "
                       "Schraube, Bohrung). Wie heißt es auf Deutsch? Antworte als JSON "
                       '{"name": "1–3 Wörter"}.')}
    data = parse_json(client.chat(model, [msg], fmt="json", temperature=0.1))
    name = str(data.get("name", "")).strip() if isinstance(data, dict) else ""
    return name[:40]
