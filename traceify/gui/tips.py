"""Tooltips: kurze Erklärungen, die erscheinen, wenn die Maus auf einem Schalter verweilt.

Alle Texte stehen hier an einer Stelle, nach Attributnamen der Bedienelemente geordnet.
``apply_tips`` setzt sie auf das Element und – in Formularen – auch auf dessen Beschriftung,
damit die Erklärung auch beim Zeigen auf den Text links daneben erscheint. Bereits im Code
gesetzte Tooltips bleiben erhalten.
"""
from __future__ import annotations

SETTINGS = {
    # Konvertierung
    "rb_cad": "Für Pläne und technische Zeichnungen: jede Linie wird als Mittellinie "
              "nachgezeichnet (Linien, Bögen, Kreise) – ideal zum Weiterbearbeiten im CAD.",
    "rb_cnc": "Für Logos, Schriftzüge und Frästeile: die Außenkanten jeder schwarzen Fläche "
              "werden als geschlossene Kontur nachgezeichnet – ideal für Fräse, Laser, Plotter.",
    "preset": "Fertige Einstellungen für typische Vorlagen (Bauplan, technische Zeichnung, Logo …). "
              "Setzt alle Werte unten passend; danach kannst du einzelne Werte anpassen.",
    "btn_convert": "Wandelt das geöffnete Bild mit den aktuellen Einstellungen in Vektoren um (F5).",
    # Raster
    "threshold": "Grauwert, ab dem ein Bildpunkt als Linie zählt (0–254). „automatisch“ ermittelt "
                 "ihn selbst; höher = auch blasse Linien, aber mehr Rauschen.",
    "adaptive": "Schwellwert örtlich anpassen – hilft bei ungleichmäßig belichteten Scans, "
                "Schatten oder vergilbtem Papier.",
    "invert": "Für helle Linien auf dunklem Grund (z. B. Blaupausen, Negative).",
    "deskew": "Dreht das ganze Bild vor der Umwandlung gerade, wenn der Scan schief eingelegt war.",
    "despeckle": "Entfernt Flecken und Staub bis zu dieser Fläche. Zu hoch: kleine Punkte "
                 "(Dezimalpunkte, i-Punkte) gehen verloren.",
    "fill_holes": "Füllt kleine weiße Löcher in Linien und Flächen bis zu dieser Größe.",
    "smooth": "Glättet ausgefranste Kanten vor der Umwandlung. Höher = ruhigere Linien, "
              "aber feine Details verschwimmen.",
    "thicken": "Verdickt Linien um so viele Pixel – schließt kleine Unterbrechungen in dünnen "
               "oder blassen Strichen.",
    # Vektorisierung
    "tolerance": "Wie genau Kurven nachgezeichnet werden. Kleiner = genauer, aber mehr Punkte; "
                 "größer = weniger, glattere Objekte.",
    "arcs": "Gebogene Linien als echte Bögen ausgeben statt als viele kurze Linienstücke.",
    "circles": "Geschlossene runde Linien als Kreise ausgeben (Bohrungen, Stützen, Symbole).",
    "polylines": "Alles als Polylinien ausgeben – manche Fräs- und Laserprogramme verlangen das.",
    "min_length": "Kürzere Linienstücke werden verworfen (entfernt Krümel und Rauschen).",
    "corner": "Ab welcher Richtungsänderung eine Linie als Ecke statt als Rundung gilt. "
              "Kleiner = mehr Ecken.",
    "snap": "Linienenden, die so nah beieinander liegen, werden zu einem gemeinsamen Punkt "
            "zusammengezogen (saubere Ecken und Anschlüsse).",
    "contour_smooth": "Nur im CNC-Modus: glättet die Umrisse. Höher = rundere Konturen.",
    # Linien, Farben, Symbole
    "dashed": "Erkennt gestrichelte und strichpunktierte Linien und gibt sie als eine Linie mit "
              "passendem Linientyp aus (statt vieler Einzelstriche).",
    "widths": "Misst, wie dick jede Linie im Scan ist, und übernimmt die Strichstärke ins CAD.",
    "thick": "Deutlich dickere Linien (meist Wände) kommen auf einen eigenen Layer "
             "DICKE_LINIEN – im CAD getrennt ein-/ausblendbar.",
    "thick_ratio": "Ab dem Wievielfachen der normalen Strichstärke eine Linie als „dick“ gilt.",
    "spurs": "Entfernt kurze Stummel, die an rauen Wandkanten oder überstehender Schraffur "
             "seitlich abstehen. „aus“ = alles behalten.",
    "color_count": "Wie viele Farben getrennt werden. „automatisch“ ermittelt die Zahl selbst.",
    # OCR
    "ocr": "Schrift im Plan erkennen und als bearbeitbaren Text ausgeben. Die erkannten Stellen "
           "werden nicht zusätzlich als Linien nachgezeichnet. Benötigt Tesseract.",
    "ocr_lang": "Sprache(n) der Texterkennung. „deu+eng“ passt für die meisten Pläne.",
    "ocr_conf": "Wie sicher die Erkennung sein muss, damit ein Wort übernommen wird. "
                "Höher = weniger Fehler, aber mehr übersehene Texte.",
    "ocr_vertical": "Auch Text suchen, der um 90° gedreht steht (z. B. Maße an senkrechten Wänden).",
    "ocr_upside": "Auch Text suchen, der auf dem Kopf steht (180°/270°).",
    "ocr_dict": "Verlesene Wörter mit einer Liste typischer Planbegriffe und mit sicher gelesenen "
                "Wörtern desselben Plans abgleichen („Schiafen“ → „Schlafen“, „Kuche“ → „Küche“). "
                "Zahlen werden nie verändert.",
    # Maßstab
    "scale_auto": "Maßstab aus der Auflösung des Bildes (DPI) berechnen – richtig, wenn der Scan "
                  "in Originalgröße vorliegt.",
    "mmpx": "Wie viele Millimeter ein Bildpunkt in der Wirklichkeit sind. Nur bei "
            "ausgeschalteter Automatik; bequemer über „Maßstab per Länge kalibrieren“.",
    "btn_calibrate": "Eine bekannte Strecke im Bild anklicken und ihre echte Länge eingeben – "
                     "Traceify rechnet den Maßstab daraus aus.",
    "pdf_fills": "Gefüllte Flächen aus dem Vektor-PDF (z. B. schwarze Wände) mit übernehmen.",
    "pdf_colors": "Die Linienfarben aus dem Vektor-PDF übernehmen.",
    # CNC
    "machine": "Fräse (mit Z-Achse) oder Laser (Leistung statt Tiefe) – bestimmt, wie der "
               "G-Code aufgebaut wird.",
    "feed": "Vorschub beim Fräsen/Schneiden.",
    "plunge": "Vorschub beim Eintauchen ins Material.",
    "spindle": "Spindeldrehzahl (Fräse) bzw. Laserleistung (S-Wert).",
    "safe_z": "Höhe über dem Material für Leerfahrten.",
    "depth": "Gesamte Frästiefe.",
    "step_down": "Wie tief pro Durchgang gefräst wird – die Frästiefe wird in so viele Durchgänge "
                 "aufgeteilt.",
    "optimize": "Reihenfolge der Konturen so wählen, dass möglichst wenig leer gefahren wird.",
    "tool_d": "Durchmesser des Fräsers – für die Radiuskorrektur.",
    "climb": "Fräsrichtung: Gleichlauf gibt meist sauberere Kanten; Gegenlauf ist schonender "
             "bei weichen Maschinen.",
    "tab_w": "Breite eines Haltestegs.",
    "tab_h": "Höhe eines Haltestegs (so viel Material bleibt stehen).",
    "rapid": "Geschwindigkeit der Leerfahrten – nur für die Zeitschätzung.",
    "btn_preview": "Zeigt die Fräswege an und schätzt die Laufzeit.",
}

AI = {
    "btn_start": "Startet den Ollama-Dienst auf diesem Rechner, falls er noch nicht läuft.",
    "model": "KI-Modell für den Assistenten. Für die Bildfunktionen ein Modell mit Bildverständnis "
             "wählen (z. B. ein „vision“- oder „vl“-Modell).",
    "btn_pull": "Lädt das angegebene Modell herunter (einmalig, kann dauern).",
    "btn_suggest": "Die KI schaut sich das Bild an und wählt passende Einstellungen "
                   "(Vorlage, Schwellwert, Texterkennung …).",
    "btn_texts": "Die KI prüft die erkannten Texte und schlägt Korrekturen vor – du entscheidest, "
                 "was übernommen wird.",
    "btn_unread": "Die KI liest Schrift, die die normale Erkennung nicht geschafft hat "
                  "(z. B. Handschrift), und legt sie als Text an.",
    "btn_review": "Die KI vergleicht Ergebnis und Vorlage und schlägt Verbesserungen vor.",
    "btn_apply": "Führt die Aktionen aus, die die KI im Verlauf vorgeschlagen hat.",
    "send_image": "Das aktuelle Bild wird mit der Frage an die KI geschickt (Modell mit "
                  "Bildverständnis nötig).",
    "auto_exec": "Vorgeschlagene Aktionen ohne Rückfrage sofort ausführen.",
    "btn_send": "Frage oder Auftrag an die KI schicken (Strg+Enter).",
    "kind": "Ollama (lokal auf diesem Rechner) oder ein OpenAI-kompatibler Server wie vLLM "
            "(z. B. im eigenen Netz).",
    "ollama_url": "Adresse des Ollama-Dienstes, normalerweise http://localhost:11434.",
    "openai_url": "Adresse des Servers bis einschließlich /v1, z. B. http://server:8000/v1.",
    "openai_key": "API-Schlüssel, falls der Server einen verlangt (sonst leer lassen).",
    "btn_test": "Prüft, ob der Server erreichbar ist und welche Modelle er anbietet.",
}

WINDOW = {
    "opacity": "Wie stark das Originalbild unter den Vektoren durchscheint.",
    "page_spin": "Seite des PDFs, die angezeigt und umgewandelt wird.",
    "brush_spin": "Pinselgröße für Radierer und Stift (Bildpunkte).",
}

ACTIONS = {
    "a_ai_review": "Die KI vergleicht Ergebnis und Vorlage und schlägt Verbesserungen vor.",
    "a_ai_show": "Blendet den Bereich des KI-Assistenten ein.",
    "a_ai_suggest": "Die KI schaut sich das Bild an und wählt passende Einstellungen.",
    "a_ai_texts": "Die KI prüft die erkannten Texte und schlägt Korrekturen vor.",
    "a_connected": "Beim Verschieben eines Punktes die daran hängenden Linien mitziehen, "
                   "damit Anschlüsse erhalten bleiben.",
    "a_deskew": "Das Rasterbild jetzt gerade drehen, wenn der Scan schief liegt.",
    "a_explode": "Markierte Polylinien wieder in einzelne Linien zerlegen.",
    "a_fit": "Ganze Zeichnung ins Fenster einpassen.",
    "a_help": "Kurze Bedienungsanleitung anzeigen (F1).",
    "a_invert": "Hell und dunkel im Rasterbild tauschen (für helle Linien auf dunklem Grund).",
    "a_join": "Markierte Linien, die aneinanderstoßen, zu einer Polylinie verbinden.",
    "a_log": "Protokolldatei öffnen – hilfreich, wenn etwas schiefgeht.",
    "a_markers": "Stellen markieren, an denen die Umwandlung unsicher ist (Lücken, offene Enden, "
                 "nicht abgedeckte Tinte).",
    "a_next_problem": "Zur nächsten markierten Problemstelle springen.",
    "a_regions_clear": "Alle festgelegten Bereiche (eigener Modus/ignorieren) wieder entfernen.",
    "a_rot_l": "Bild und Zeichnung um 90° gegen den Uhrzeigersinn drehen.",
    "a_rot_r": "Bild und Zeichnung um 90° im Uhrzeigersinn drehen.",
    "a_select_all": "Alle Objekte markieren.",
    "a_select_layer": "Alle Objekte auf den Layern der aktuellen Auswahl markieren.",
    "a_show_bin": "Statt des Originals das Schwarz-Weiß-Bild zeigen, mit dem umgewandelt wird.",
    "a_show_vec": "Die erzeugten Vektoren über dem Bild ein- oder ausblenden.",
    "a_symbol_folder": "Ordner mit den gespeicherten Symbolen öffnen.",
    "a_undo": "Letzten Schritt zurücknehmen (Strg+Z).",
    "a_update_auto": "Beim Programmstart prüfen, ob es eine neuere Version gibt.",
    "a_zoom_100": "Bild in Originalgröße anzeigen (1 Bildpunkt = 1 Bildschirmpunkt).",
    "a_zoom_in": "Ansicht vergrößern.",
    "a_zoom_out": "Ansicht verkleinern.",
}


def _unset(w) -> bool:
    """Noch keine eigene Erklärung? (Aktionen zeigen sonst einfach ihren Namen.)"""
    tip = w.toolTip()
    if not tip:
        return True
    text = w.text() if hasattr(w, "text") and callable(w.text) else ""
    return bool(text) and tip.replace("&", "") == text.replace("&", "")


def apply_tips(owner, tips: dict) -> int:
    """Setzt Tooltips auf die Attribute von ``owner`` (vorhandene bleiben). Gibt die Anzahl."""
    from PySide6.QtWidgets import QFormLayout
    n = 0
    for name, text in tips.items():
        w = getattr(owner, name, None)
        if w is None or not hasattr(w, "setToolTip"):
            continue
        if _unset(w):
            w.setToolTip(text)
            if hasattr(w, "setStatusTip") and not w.statusTip():
                w.setStatusTip(text)
            n += 1
        tip = w.toolTip()
        # Beschriftung links im Formular („Toleranz:“) bekommt dieselbe Erklärung
        par = w.parentWidget() if hasattr(w, "parentWidget") else None
        lay = par.layout() if par is not None else None
        if isinstance(lay, QFormLayout):
            lab = lay.labelForField(w)
            if lab is not None and not lab.toolTip():
                lab.setToolTip(tip)
    return n
