"""KI-Stapel: Regeln in Klartext auf jede Datei anwenden.

Beispiel-Regeln:
    „Grundrisse mit Maßstab aus dem Plan, Logos als CNC-Umriss mit 2 mm Frästiefe als G-Code,
     handschriftliche Notizen überspringen.“

Für jede Datei bekommt die KI ein verkleinertes Bild, den Dateinamen und die Regeln und
antwortet mit JSON: Art der Zeichnung, Einstellungen, Formate oder „überspringen“.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import List, Optional

import numpy as np

from ..core.pipeline import ConvertSettings
from ..core.vectorize import MODE_CENTERLINE, MODE_OUTLINE
from ..export.gcode import COMP_LABELS, MACHINE_LASER, MACHINE_MILL, GcodeSettings
from ..gui_presets import PRESETS
from .assistant import encode_image
from .ollama_client import OllamaClient, OllamaError, parse_json

SETTING_NAMES = """modus ("mittellinie" = CAD-Strichzeichnung | "umriss" = CNC-Kontur/Logo),
vorlage (%s), toleranz (px), flecken (px²), luecken_schliessen (px), invertieren, adaptiv,
begradigen, ocr, ocr_sprache, boegen, kreise, nur_polylinien, strichlinien, strichstaerken,
dicke_linien_layer, waende_umriss, schraffur_layer, schraege_texte, gerade_ausrichten,
farben_trennen,
anzahl_farben, massstab_aus_plan, symbole_automatisch,
maschine ("fraese"|"laser"), vorschub (mm/min), fraestiefe (mm), zustellung (mm),
fraeser_durchmesser (mm), radiuskorrektur ("keine"|"aussen"|"innen"|"auto"), haltestege (Anzahl),
steg_breite (mm), steg_hoehe (mm)""" % ", ".join(PRESETS)

PROMPT = """Du steuerst die Stapelkonvertierung von Traceify (Scans/PDFs -> DXF, DWG, SVG, G-Code).
Regeln des Nutzers (Klartext):
---
{rules}
---
Datei: {name}
Sieh dir das Bild an, bestimme die Art der Zeichnung und wende die Regeln an.
Mögliche Einstellungen: {names}
Formate: "dxf", "dwg", "svg", "nc" (G-Code).
Antworte NUR als JSON:
{{"art": "kurz", "ueberspringen": false, "formate": [], "einstellungen": [{{"name": "...", "wert": ...}}],
  "begruendung": "1 Satz"}}
„formate“ leer lassen, wenn die Regeln nichts dazu sagen. Nur Einstellungen nennen, die die Regeln
oder die Art der Zeichnung erfordern."""

SCHEMA = {
    "type": "object",
    "properties": {
        "art": {"type": "string"},
        "ueberspringen": {"type": "boolean"},
        "formate": {"type": "array", "items": {"type": "string"}},
        "einstellungen": {"type": "array", "items": {
            "type": "object", "properties": {"name": {"type": "string"}, "wert": {}},
            "required": ["name", "wert"]}},
        "begruendung": {"type": "string"},
    },
    "required": ["art", "ueberspringen", "formate", "einstellungen", "begruendung"],
}


@dataclass
class FilePlan:
    art: str = ""
    skip: bool = False
    formats: List[str] = field(default_factory=list)
    settings: ConvertSettings = None
    gcode: GcodeSettings = None
    applied: List[str] = field(default_factory=list)
    reason: str = ""

    def note(self) -> str:
        if self.skip:
            return f"KI: {self.art} – übersprungen ({self.reason})"
        s = f"KI: {self.art}"
        if self.applied:
            s += " – " + ", ".join(self.applied)
        if self.formats:
            s += " – Formate: " + ", ".join(self.formats)
        return s


def _b(v) -> bool:
    return v if isinstance(v, bool) else str(v).strip().lower() in ("1", "true", "ja", "an", "yes")


def apply_named(s: ConvertSettings, g: GcodeSettings, name: str, value) -> str:
    """Setzt eine Einstellung per Namen (ohne Oberfläche). Gibt Klartext zurück."""
    n = str(name).strip().lower()
    if n == "vorlage":
        key = next((k for k in PRESETS if k.lower() == str(value).lower()), None) or \
            next((k for k in PRESETS if str(value).lower() in k.lower()), None)
        if not key:
            raise ValueError(f"unbekannte Vorlage {value}")
        p = PRESETS[key]
        v = s.vectorize
        v.mode, v.tolerance, v.detect_arcs = p["mode"], p["tolerance"], p["arcs"]
        v.detect_circles, v.output_polylines = p["circles"], p["polylines"]
        s.preprocess.despeckle, s.preprocess.smooth = p["despeckle"], p["smooth"]
        s.ocr.enabled = p["ocr"]
        return f"Vorlage {key}"
    if n == "modus":
        s.vectorize.mode = MODE_OUTLINE if str(value).lower().startswith("u") else MODE_CENTERLINE
        return f"Modus {s.vectorize.mode}"
    bools = {"invertieren": (s.preprocess, "invert"), "adaptiv": (s.preprocess, "adaptive"),
             "begradigen": (s.preprocess, "deskew"), "ocr": (s.ocr, "enabled"),
             "boegen": (s.vectorize, "detect_arcs"), "kreise": (s.vectorize, "detect_circles"),
             "nur_polylinien": (s.vectorize, "output_polylines"),
             "strichlinien": (s.style, "detect_dashed"),
             "strichstaerken": (s.style, "measure_widths"),
             "dicke_linien_layer": (s.style, "thick_layer"),
             "waende_umriss": (s.style, "walls_outline"),
             "schraffur_layer": (s.style, "hatch_layer"),
             "schraege_texte": (s.ocr, "free_angles"),
             "gerade_ausrichten": (s.style, "straighten"),
             "farben_trennen": (s.style, "color_layers"),
             "massstab_aus_plan": (s, "auto_scale"), "symbole_automatisch": (s, "symbols_auto"),
             "pdf_vektoren": (s.pdf, "enabled")}
    if n in bools:
        obj, attr = bools[n]
        setattr(obj, attr, _b(value))
        return f"{n}={'an' if _b(value) else 'aus'}"
    nums = {"toleranz": (s.vectorize, "tolerance", float), "flecken": (s.preprocess, "despeckle", int),
            "luecken_schliessen": (s.preprocess, "thicken", int),
            "glaetten": (s.preprocess, "smooth", int), "schwellwert": (s.preprocess, "threshold", int),
            "min_laenge": (s.vectorize, "min_length", float),
            "anzahl_farben": (s.style, "color_count", int),
            "vorschub": (g, "feed_rate", float), "fraestiefe": (g, "cut_depth", float),
            "zustellung": (g, "step_down", float), "fraeser_durchmesser": (g, "tool_diameter", float),
            "haltestege": (g, "tabs", int), "steg_breite": (g, "tab_width", float),
            "steg_hoehe": (g, "tab_height", float)}
    if n in nums:
        obj, attr, typ = nums[n]
        setattr(obj, attr, typ(float(value)))
        return f"{n}={getattr(obj, attr)}"
    if n == "ocr_sprache":
        s.ocr.language = str(value)
        return f"OCR {value}"
    if n == "radiuskorrektur":
        v = str(value).lower().replace("ß", "ss").replace("ä", "ae").replace("ö", "oe") \
            .replace("ü", "ue")
        key = next((k for k in COMP_LABELS if v.startswith(k[:3])), None)
        if not key:
            raise ValueError(f"unbekannte Radiuskorrektur {value}")
        g.compensation = key
        return f"Radiuskorrektur {key}"
    if n == "maschine":
        g.machine = MACHINE_LASER if str(value).lower().startswith(("l", "p")) else MACHINE_MILL
        return f"Maschine {g.machine}"
    raise ValueError(f"unbekannte Einstellung {name}")


def plan_for_file(client: OllamaClient, model: str, gray: Optional[np.ndarray], name: str,
                  rules: str, base: ConvertSettings, gbase: GcodeSettings,
                  with_image: bool = True) -> FilePlan:
    msg = {"role": "user", "content": PROMPT.format(rules=(rules or "(keine – wähle passend)").strip(),
                                                    name=name, names=SETTING_NAMES)}
    if with_image and gray is not None:
        msg["images"] = [encode_image(gray, 1024)]
    try:
        raw = client.chat(model, [msg], fmt=SCHEMA, temperature=0.1)
    except OllamaError as e:
        if "format" in str(e).lower() or "schema" in str(e).lower():
            raw = client.chat(model, [msg], fmt="json", temperature=0.1)
        else:
            raise
    data = parse_json(raw)
    if not isinstance(data, dict):
        raise OllamaError("Unerwartete Antwort der KI")
    plan = FilePlan(art=str(data.get("art", "")), skip=_b(data.get("ueberspringen", False)),
                    reason=str(data.get("begruendung", "")),
                    settings=copy.deepcopy(base), gcode=copy.deepcopy(gbase))
    fmts = []
    for f in data.get("formate") or []:
        f = "." + str(f).lower().strip().lstrip(".")
        if f in (".gcode", ".g-code"):
            f = ".nc"
        if f in (".dxf", ".dwg", ".svg", ".nc") and f not in fmts:
            fmts.append(f)
    plan.formats = fmts
    for item in data.get("einstellungen") or []:
        if not isinstance(item, dict):
            continue
        try:
            plan.applied.append(apply_named(plan.settings, plan.gcode, item.get("name"),
                                            item.get("wert")))
        except (ValueError, TypeError):
            continue
    return plan
