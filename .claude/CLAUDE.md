# Traceify – Hinweise für Claude

Desktop-App (nur Windows) nach dem Vorbild kommerzieller Vektorisierungsprogramme: Raster/PDF → DXF/DWG/SVG/G-Code, mit GUI,
OCR, KI über Ollama oder vLLM. Python 3.12, PySide6. Lizenz AGPL-3.0. Repo: StefanR1984/traceify.

## Zusammenarbeit
- Auf Deutsch antworten, den Nutzer duzen. Auch Code-Kommentare, UI-Texte, Doku,
  Changelog und Commit-Nachrichten auf Deutsch. Englisch ist nicht nötig.
- **Keine ZIPs liefern** – der Stand liegt auf GitHub. Nach einer Änderung kurz
  zusammenfassen (was, Commit, Build-Ergebnis).
- **Keine Tags, Releases oder sonstigen öffentlichen Veröffentlichungen ohne
  ausdrückliches Okay.** Der Nutzer legt Releases normalerweise selbst an (Tag `vX.Y.Z`).
- Nutzer-E-Mail nirgends verwenden. Git-Autor:
  `StefanR1984 <StefanR1984@users.noreply.github.com>`
- Commit-Nachrichten enden mit den Attribution-Zeilen, die die Sitzung vorgibt.
- Nicht gewünscht: signierte EXE, winget, englische Übersetzung.

## Ablauf pro Feature
1. Kernlogik als reine, testbare Funktionen in `traceify/core/` (oder `export/`).
2. Tests in `tests/` (Core-Tests + bei GUI-Änderungen ein Offscreen-Test mit echten
   Mausereignissen über `QTest`, siehe `tests/test_gui.py`).
3. GUI anbinden, README (Tabelle „Funktionen“, „Bedienung“), Kurzanleitung
   (`MainWindow.show_help`) und `CHANGELOG.md` ergänzen.
4. Version in `traceify/__init__.py` erhöhen (bei neuen Funktionen Minor).
5. `pyflakes` + alle Tests grün, committen, pushen.
6. Windows-Probe-Build: `gh workflow run release.yml --ref main`, mit
   `gh run watch <id> --exit-status` abwarten (ca. 6 min; enthält EXE-Selbsttest).
7. Danach alte Actions-Läufe löschen (nur die zum aktuellen Commit behalten).

## Befehle
```bash
pip install -r requirements.txt -r requirements-dev.txt --break-system-packages
QT_QPA_PLATFORM=offscreen python3 -W ignore -m pytest -q   # ~180 Tests, ca. 12 s
python3 -m pyflakes traceify tests
python3 -m traceify                 # GUI;  python3 -m traceify --selbsttest
```

## Aufbau
- `core/model.py` – Line, Arc, Circle, Polyline, Text, Insert; `Drawing` (scale = mm/px).
  Koordinaten in **Bildpixeln, y nach unten**; Bogenwinkel in Grad im Bildsystem
  (DXF-Export spiegelt: start=-end, end=-start). Layer-Konstanten + `layer_color`.
- `core/pipeline.py` – `ConvertSettings`, `convert`/`convert_source`, Bereiche (Region).
- `core/preprocess.py`, `vectorize.py` (Kachel-Skelett, Fransen, Fit),
  `style.py` (Strichlinien, Strichstärken, Schraffur-Layer, Wände als Umriss), `colors.py`,
  `ocr.py` (Tesseract, 4 Richtungen, Maßzahlen), `textlines.py` (schräge Texte nachlesen),
  `lexicon.py` (Wörterbuch für Planbegriffe, OCR-Verwechslungen; Zahlen nie ändern),
  `straighten.py` (Schräglage, Meta `schraeglage`; Export dreht über `Drawing.export_view`),
  `pdf_vector.py` (Vektor-PDF direkt), `scale_detect.py` (M 1:N), `symbols.py` (Blöcke),
  `quality.py` (Ampel), `dots.py` (Kies/Punktfelder → Kreise auf KIES), `dimensions.py` (Maßzahlen gezielt lesen: Lücke der Maßlinie, zwischen Sternen, Paar über/unter der Linie; `merge` ersetzt verlesene Zahlen), `edit.py` (Ecke, Ausrichten inkl. Polylinien `align_axes`, Lücken, Knoten),
  `hatch.py` (Schraffur-Flächen für den DXF-Export: Rasternummern per Nachbarschaft,
  Ausgleichsgerade, Reste anhängen), `cad.py` (Fang, Schnittpunkte, Stutzen, Dehnen, SnapIndex,
  `close_gaps`, `remove_spurs`).
- `core/benchmark.py` + `tools/pruefstand.py` – Prüfstand (Objekte, Splitter, Abdeckung,
  Texte), `core/dxf_import.py` liest fremde DXF (z. B. eines kommerziellen Vektorisierungsprogramms) und richtet sie aufs Bild aus.
  Echte Scans liegen **nicht** im Repo (Datenschutz) – der Nutzer liefert sie bei Bedarf.
- `core/truth.py` + `tools/wahrheit.py` – **Wahrheits-Prüfstand**: Original-CAD-DXF (Allplan,
  `Testdaten Traceify/dxf neu/dxf neu/PLAN1–3_*.dxf`, Einheit m; Standard seit 17.11., mit Maßketten als LINE/MTEXT
  und PLAN1_Dach – die alten ohne Maßketten in `Testdaten Traceify/dxf/dxf/` bleiben als Vergleich) → simulierter Scan (1:100, 150 dpi,
  Strich 0,25 mm, Rauschen) → Traceify → Messung gegen die Originalgeometrie (Trefferquote,
  Genauigkeit, Lagefehler in Papier-mm, Objekte, Bögen, Ortho, Wörter). Abbildung ist exakt
  bekannt, keine Lage-Schätzung. Noch ohne Füllflächen (SOLID) und ohne Schräglage.
  Geometrie in Textbereichen des Originals zählt nicht (Schrift → Wörter-Spalte).
  Aufruf: `python tools/wahrheit.py "Testdaten Traceify/dxf neu/dxf neu" --jobs 4 --bilder <tmp>` (~6 min, 18 Pläne).
  **Echte Plots (alle 17):** `Testdaten Traceify/PDF/PLAN*.pdf` = Allplan-Rasterplots, A3 quer, 300 dpi; PLAN1 1:200,
  PLAN2 1:100, PLAN3 1:350. `--scans "Testdaten Traceify/PDF" --jobs 4` (~6 min) erkennt den Maßstab je Plan
  (`truth.scan_scale`: Schätzung aus der Ausdehnung ±30 %, dann übliche Maßstäbe + Vielfache von 25, bestes
  harmonisches Mittel aus „Original auf Tinte“ und „Tinte am Original“ = Spalte „Passung“, scharfes Maximum);
  `--massstab N` erzwingt einen. `truth.run_real`: Lage per Kreuzkorrelation,
  nur gedruckte Objekte zählen – das DXF enthält ausgeblendete Layer. DXF-Import liest Allplan-MTEXT mit
  Drehung (Richtungsvektor), Ausrichtung und Hochziffern (`2.38\S5^ ;` → „2.38⁵“, `words` zählt 2.385).
- `export/` – dxf, dwg (ODA File Converter), svg, gcode (`plan()` = gemeinsame Basis für
  G-Code, Vorschau, Zeit; Radiuskorrektur, Haltestege).
- `ai/` – Ollama-Client und `openai_client.py` (vLLM/OpenAI-kompatibel, gleiche Schnittstelle;
  Auswahl über config `ki_server`, `make_client`), beide stdlib urllib; Assistent, KI-Stapelregeln.
- `gui/main_window.py` – Aktionen, Menüs, Leisten, Undo-Stack
  (`("entities", liste)`, `("drawing", d)`, `("raster", …)`, `("raster_only", …)`).
  Ändern sich Leisten/Docks: `UI_STATE_VERSION` erhöhen.
- `gui/tips.py` – alle Tooltips an einer Stelle (Attributname → Text, `apply_tips`); neue
  Schalter dort eintragen, `test_gui_tooltips_bei_mauszeiger` prüft, dass keiner fehlt.
- `gui/canvas.py` – QGraphicsView; Werkzeuge select/erase/pen/region/symbol und
  line/polyline/rect/circle/arc/trim/extend; Signale an das Hauptfenster.
- `api.py`, `cli.py` – Python-API und Kommandozeile; `installer.py`, `config.py`
  (`%APPDATA%\Traceify\config.json`), `update.py`, `support.py`.
- Packaging: `packaging/traceify.spec` (PyInstaller onedir; neue Module mit
  dynamischem Import in `hiddenimports`), `packaging/windows/traceify.iss` (Inno Setup),
  `.github/workflows/ci.yml` (Tests) und `release.yml` (Windows-Build, Tag `v*` oder
  manuell, optional `release_tag` zum Anhängen an ein bestehendes Release).

## Stolpersteine
- PyMuPDF-DPI muss `int` sein.
- PowerShell im Workflow: keine deutschen Anführungszeichen „“ in Inline-Skripten
  (Release-Notizen kommen aus `tools/release_notes.py`).
- Tesseract wird **nach** dem PyInstaller-Build nach `dist/Traceify/tesseract` kopiert.
- Esc ist ein Fenster-Kürzel („Auswahl“); die Zeichenfläche fängt es beim Zeichnen über
  `ShortcutOverride` ab.
- Performance-Referenz: A0 mit 400 dpi (13245×9362) ≈ 21 s mit OCR auf 2 Kernen.
- PDF-DPI 0 = automatisch (`loader.resolve_dpi`): Scan-PDFs in Originalauflösung, sonst 300.
- QThread: `finished` kommt, bevor der Thread wirklich endet – vor dem Loslassen `w.wait()`,
  sonst Absturz beim Beenden („Destroyed while thread is still running“, v. a. unter Windows).
- Neue Exporte/Ansichten: `Drawing.export_view()` verwenden (dreht die Schräglage heraus).
- Tesseract-Rohlesungen in `core/dimensions.py` nie ungeprüft in `int()`/`float()` geben: die Whitelist
  `0123456789.,` liefert auch Randpunkte („2.45.“, „.245“) von Maßlinie/Pfeilspitze. 0.34.1 behebt den
  Abbruch „invalid literal for int() with base 10: '.'“ (`_variants`, Befund 16.11.2026, Konvertierung
  fehlgeschlagen); 0.34.2 entfernt Randpunkte schon beim Rohtext in `read_gap_numbers` (sonst „4.17.“ mit Punkt
  als Hochziffer); übrige `int()`/`float()` in `ocr.py`/`textlines.py`/`scale_detect.py` geprüft. Neue Lesart-/Prüf-Funktionen dort mit solchen Randfällen testen (`test_massketten.py`).

## Offene Ideen
Gemessen mit `tools/pruefstand.py` an 9 echten Bauplan-Scans (96–150 dpi) und DXF-Dateien eines kommerziellen Vergleichsprogramms für
image-11 (A1 Apotheke) und image-4 (verrauschter Kellerplan, Handschrift). Die Scans liegen
nicht im Repo; der Nutzer liefert sie bei Bedarf.

Stand 0.17.0 (Traceify / Vergleichsprogramm):
| | image-11 | image-4 |
|---|---|---|
| Abdeckung | 98,1 % / 86,1 % | 97,1 % / 88,4 % |
| Objekte | 2924 / 2697 | 5768 / 10408 |
| Bögen | 375 / 51 | 661 / 253 |
| exakt waagrecht/senkrecht | 48 % / 51 % | 43 % / 49 % |
| offene Enden | 1554 / 1330 | 2218 / 4173 |
| Wörter wie Vergleichsprogramm | 51 von 129 | 5 von 22 |

Achtung: Auch das Vergleichsprogramm liest viel Unsinn („sightwal“, „poe“) – die
Wort-Übereinstimmung ist kein Wahrheitsmaßstab. Schraffur als HATCH: Einzellinien übrig
image-94 14 %, -89 14 %, -99 19 %, -27 44 %, -37 46 %, -4 46 % (handschraffiert).

**Messbasis echte Plots, Stand 0.36.1** (17.11., `Testdaten Traceify/dxf neu/dxf neu`, alle 17 Allplan-Plots, 300 dpi,
mit Tesseract, `--jobs 4`; „gedruckt“ = Tinte < 160 plus kleine hellgraue Teile ≤ 1 mm (`truth._printed_ink`) – nur < 210
überall ließ PLAN1 auf 50 % fallen, graue Füllflächen decken ausgeblendete Objekte; Wörter/Texte ab 0.36.1 gezählt mit
zusammengeführten Hochziffern und ohne Schrift < 0,6 mm, „Texte richtig“ = je gedrucktem Text, Pfeil = 0.36.0 → 0.36.1 → 0.36.2):
| Plan (1:N) | Treffer | Genauigk. | Lage 95 % mm | Objekte (Orig.) | Bögen (Orig.) | Ortho (Orig.) | Wörter richtig/falsch | Texte richtig |
|---|---|---|---|---|---|---|---|---|
| PLAN1_EG (200) | 97,3 % | 99,0 % | 0,162 | 2925 (20958) | 86 (198) | 79 (89) % | 64 von 87 / 15 | 146 von 245 |
| PLAN1_OG1 (200) | 93,8 % | 98,8 % | 0,162 | 677 (2941) | 16 (10) | 52 (81) % | 2 von 3 / 2 | 2 von 3 |
| PLAN1_UG (200) | 93,8 % | 99,1 % | 0,243 | 2630 (13026) | 120 (94) | 79 (87) % | 63 von 114 / 20 | 98 von 284 |
| PLAN2_Dach (100) | 94,0 % | 100,0 % | 0,162 | 2814 (10699), 35 Kies-Fl. | 21 (8035) | 82 (89) % | 27 von 32 / 9 | 79 von 107 |
| PLAN2_EG (100) | 95,3 % | 98,6 % | 0,243 | 5292 (11901) | 222 (94) | 76 (84) % | 197 von 258 / 47 | 356 → 371 → **391** von 637 |
| PLAN2_OG1 (100) | 97,2 % | 99,3 % | 0,162 | 4821 (11734) | 125 (93) | 76 (84) % | 148 von 192 / 48 | 304 → 313 → **321** von 558 |
| PLAN2_OG2 (100) | 96,8 % | 99,3 % | 0,162 | 4783 (11149) | 135 (99) | 73 (83) % | 136 von 185 / 59 | 281 → 285 → **289** von 509 |
| PLAN2_OG3 (100) | 97,1 % | 98,1 % | 0,162 | 3648 (10638), 11 Kies-Fl. | 111 (2708) | 84 (91) % | 112 von 161 / 44 | 196 → **205** von 402 |
| PLAN3_DG (350) | 48,5 % | 87,1 % | 0,359 | 57 (256) | 2 (0) | 97 (53) % | 2 von 6 / 1 | 0 von 2 |
| PLAN3_EG (350) | 88,8 % | 98,3 % | 0,162 | 3613 (84511) | 234 (4195) | 56 (73) % | 61 von 165 / 39 | 55 von 305 |
| PLAN3_OG1 (350) | 90,1 % | 97,8 % | 0,243 | 3437 (64112) | 195 (4108) | 58 (70) % | 55 von 99 / 25 | 35 von 108 |
| PLAN3_OG2 (350) | 90,3 % | 98,8 % | 0,232 | 3049 (60343) | 173 (4069) | 59 (74) % | 35 von 71 / 24 | 16 von 67 |
| PLAN3_OG3 (350) | 94,8 % | 99,6 % | 0,162 | 1963 (64363) | 27 (979) | 72 (88) % | 14 von 24 / 2 | 10 von 21 |
| PLAN3_OG4 (350) | 99,6 % | 100,0 % | 0,116 | 315 (938) | 22 (19) | 90 (98) % | 15 von 19 / 5 | 14 von 19 |
| PLAN3_UG1 (350) | 91,8 % | 98,1 % | 0,162 | 3442 (56418) | 271 (4401) | 66 (75) % | 70 von 402 / 47 | 59 von 1133 |
| PLAN3_UG2 (350) | 99,9 % | 99,7 % | 0,162 | 172 (367) | 8 (6) | 98 (100) % | 10 von 15 / 5 | 8 von 14 |
| PLAN3_UG3 (350) | 100,0 % | 100,0 % | 0,162 | 47 (72) | 0 (0) | 99 (100) % | 3 von 5 / 2 | 1 von 3 |

**Neue DXF (17.11.):** gleiche Geometrie, Layer ohne Präfix `XR$1$`; PLAN2/PLAN3 enthalten jetzt die Maßketten –
nicht als DIMENSION, sondern aufgelöst als LINE/MTEXT (ARC, LWPOLYLINE) auf `MA_LINIE_1_50` (PLAN2) bzw.
`MA_LINIE_ALLGEMEIN` (PLAN3), z. B. PLAN2_EG +5213 Linien/+1297 Texte. Neu `PLAN1_Dach.dxf` (ohne Plot, nur
simuliert). Damit sind Genauigkeit (vorher 64–84 %), Lage 95 % (vorher 9–42 mm) und falsche Wörter auf PLAN2/PLAN3
aussagekräftig: Genauigkeit jetzt überall ≥ 97,8 % (außer PLAN3_DG 87,1 %), Lage 95 % ≤ 0,36 mm. Objekte zählen
weniger, weil die Maßtexte jetzt Textbereiche sind. 1:350 heißt winzige Schrift (PLAN3_DG Treffer 48,5 %: nur 57
Objekte, Schraffur/Kleinteile). Kies auf PLAN2_Dach/OG3: im Plot hellgraue Ringe (Ø ~4 px, Grau ~170).
**Simuliert (neue DXF, 0.35.0):** Treffer 87,6–100 %, Genauigkeit 96,0–100 %, Lage 95 % ≤ 0,23 mm; Wörter z. B.
PLAN2_EG 46 von 299 / 53 falsch, PLAN3_UG1 125 von 374 / 70 (Maßzahlen jetzt im Original). 0.36.0 Kies-Fläche:
Dach 6427 → 2130 Objekte (22 Flächen), OG3 4131 → 2975, Treffer gleich (89,4 / 87,6 %).
**Schrift auf den echten Plots (Analyse 17.11., 8 Pläne, je gedrucktem Text):** (1) Prüfstand-Artefakt: Allplan löst
Maße in Hauptzahl + kleine Hochziffer als **zwei** MTEXT auf („2“ + „5“), Traceify liest richtig „2⁵“ → galt als falsch.
`truth.merge_superscripts` fügt sie zusammen (rechts oben, 0,4–0,8 der Höhe): je Text 13,7 → 31,9 % richtig, Wörter
PLAN2_EG 141 → 193, falsch 104 → 52. (2) PLAN3_OG1–3: Schrift 0,17–0,5 mm Papier (2–6 px) – zählt nicht mehr
(`MIN_TEXT_MM` 0,6). (3) PLAN3_UG1: die 1,5–2-mm-Texte sind übereinander gedruckte Maß-Knäuel (1133 Texte, 59 richtig),
nicht lesbar. (4) Lesefehler „2.75°“ statt „2.75⁵“ (62 Stellen auf PLAN2): Hochziffer gefunden, Einzel-Nachlesen
scheitert (an der Maßlinie angeschnitten) → **0.36.1** `ocr._DIM2`: Maß d.dd + Zeichen dahinter = ⁵. Echt Texte
1660 → 1688, Simulation und 16 Scans unverändert. **0.36.2** auch ganze Zahlen „28°“ → „28⁵“, wenn die
kleine Komponente gefunden wurde und kein Loch hat (`ocr._has_hole`; „°“ ist ein Ring, „30°“ bleibt): echt 1688 → 1729
Texte (nur PLAN2), Simulation +5, Scans gleich. Offen: „N°“ ohne gefundene Komponente (14 auf PLAN2_EG, Hochziffer
an Linie verschmolzen), einstellige cm-Maße „2⁵“ (fast nie gelesen – Filter Kurztexte < 85 % Sicherheit), „275°“
(Punkt fehlt), reine Zahlen (cm-Maße „25“, „30“)
nur 14–40 % richtig, Maße auf PLAN2 noch ~25 % verlesen; Raumstempel („0.27 Druckerpool“) oft nur teilweise.

**Wahrheits-Prüfstand, Stand 0.17.0** (18 Allplan-Pläne, 1:100, 150 dpi, ohne Tesseract gemessen):
Trefferquote 81–93 % (UG3 99,6 %, Dach 60,7 %), Genauigkeit 90–97 % (DG 82 %), Lagefehler
95 % ≤ 0,4 mm Papier (DG 0,6). Mit 300 dpi (PLAN2_EG / Dach / OG4): Trefferquote 92,7 / 71,5 /
99,3 %, Genauigkeit ≥ 99,3 %. Befunde:
- Fehlende Geometrie sind fast nur **eng liegende Doppellinien** (Wandschichten, Trockenbau,
  Treppenkanten, 2–4 px Abstand bei 150 dpi): Traceify zieht eine Mittellinie statt zwei.
  **0.18.0:** Hauptursache behoben – `merge_through_junctions` hat kurze, seitlich wegführende
  Stege geschluckt und dabei das Linienende bis 4 px verbogen (ganze Wand schräg → verschmolzen).
  Jetzt bleibt das Ende auf der Achse; führt der Steg zu weiterer Geometrie, bleibt er stehen.
  Trefferquote/Genauigkeit +2–5 Punkte (PLAN2_EG 86,4/92,7 → 90,8/95,7; PLAN1_OG1 91,1/94,4 →
  95,5/98,5; Dach 60,7/93,8 → 64,9/99,4; nur PLAN3_DG −0,4/−0,9). Echte Scans: offene Enden
  überall weniger (bis −28 %), Objekte +5–7 % auf 4 Plänen (kurze Verbindungsstege). Offen:
  Stege < 0,5 mm in die Nachbarlinie einrechnen, um die Objekte wieder zu senken.
- **Dach – 0.35.0 gelöst:** `dots.find_dots` auf dem Graubild vor dem Vektorisieren: Schwelle Mitte Otsu/Papier
  (mind. 70 % Richtung Papier – Allplan-Ringe Grau ~170), kompakte Kleckse ≤ 0,9 mm, frei stehend (0,25 mm nur
  andere Kleckse), nicht in Textboxen, ≥ 6 Nachbarn in 3 mm mit flächiger Streuung (kleinere Hauptachse ≥ 0,5 mm,
  sonst Punktreihe/Strichpunktlinie wie in PLAN3_OG1), Gruppe ≥ 30. Kreis-Radius = halber Klecks − 0,5 px.
  Simuliert Dach 65,5 → 87,6 %, OG3 85,5 → 89,4 % (Genauigkeit gleich/besser), echt Dach 73,6 → 93,0 %, OG3
  90,5 → 94,9 %; alle anderen Pläne und alle 16 Scans unverändert (0 Kreise). **0.36.0 Kies-Fläche:**
  `dots.find_areas` (Kreise vereinigt, um 0,75 × 90 %-Nachbarabstand gewachsen, auf halben Abstand geschrumpft) →
  DXF-HATCH mit Punktmuster auf KIES, SVG-Muster; Schalter = `hatch.META_KEY`; Zeichenfläche zeigt weiter Kreise.
  `truth.compare(areas=…)`: Original-Kies (Kreise r ≤ 0,5 mm) in der Fläche = getroffen, `kies_genau` = Flächenanteil
  ≤ 1 mm neben Original-Kies (Dach/OG3 100 %). Offen: Dach zerfällt in 35 Flächen (echt); Punkte, die Linien berühren, fehlen (echt Dach 5092 von ~6400). Befund vorher:
  Kies-/Punktmuster aus Kreisen r < 0,5 mm fehlen zu 95 %. **Analyse 15.11. (PLAN2_Dach):**
  6406 Kreise, alle r = 0,15 mm Papier (Ø 0,3 mm ≈ Strichbreite 0,25 mm) – im Scan gefüllte Punkte, nie
  Ringe. 150 dpi: Punkt = 5 px² (Ø ~1,8 px); `despeckle` (12 px²) löscht 87 %, ohne Entflecken sind alle
  6406 im Binärbild, aber das Skelett eines Kleckses ist ein Punkt → `min_length` 6 px verwirft ihn
  (roh: 6388 ohne Objekt). 300 dpi: Punkte 41 px², überleben das Entflecken, ebenfalls ohne Loch →
  ebenso verworfen. Lösungsidee: eigener Schritt „Punkt → kleiner Kreis“ auf dem Binärbild (vor dem
  Entflecken): kompakte, runde Kleckse (Fläche ~4–60 px², Seitenverhältnis ≈ 1, nicht in Textboxen) als
  Circle (Radius aus Fläche minus halbe Strichbreite, Untergrenze Strich/2); Rauschen ausschließen über
  Dichte/Regelmäßigkeit (Kies = viele Punkte in einer Fläche, Rauschen verstreut; Mindestzahl Nachbarn
  in z. B. 3 mm). Alternativ/ergänzend als Schraffur-Fläche (Kiesmuster) statt tausender Kreise – fürs
  CAD meist sinnvoller; dann müsste `truth.compare` solche Flächen werten. Echte Scans (image-*) prüfen,
  ob Punktfelder vorkommen und ob Rauschpunkte fälschlich Kreise würden.
- **Stand 0.20.0, was fehlt noch** (PLAN2_EG/3_EG/1_EG, je ~13 % der Länge): praktisch nichts
  > 1 mm entfernt – fehlend heißt „Traceify-Linie 0,3–1 mm daneben“. ~8 Punkte sind Doppellinien
  < 0,6 mm Abstand (bei 150 dpi/0,25 mm Strich im Scan verschmolzen, kaum lösbar), ~2–3 Punkte
  Schraffurlinien in Wänden (Abstand 0,6–1 mm; im DXF ohnehin HATCH), ~2 Punkte Einzellinien
  (nur 9 % der Linienenden > 0,3 mm zu kurz, kein Systemfehler).
- **PLAN3_DG (0.20.0 behoben):** 39 % der Linienlänge echt 0,05–3° schräg; `straighten` zwang sie
  auf die Achse (Genauigkeit 81 %). Jetzt Tintenprüfung `cad.ink_share` in `align_axes`: nur
  ausrichten, wenn danach ≥ 90 % auf Tinte oder nicht schlechter als vorher → 93,4/96,8 %.
  Feste Querverschiebungsgrenze (`max_shift`) für die Hauptachsen kostete in Grundrissen bis
  12 Punkte Ortho – verworfen.
- **Bögen zu viele** auch außerhalb von Text (PLAN2_EG 261 gegen 90 im Original, bei 300 dpi
  407). **0.19.0:** Hauptursache behoben – `find_corners` braucht ≥ 15 Punkte, kurze Stücke
  (Schraffur an Kante, kleine Wandecken) gingen ohne Eckprüfung in die Kreisanpassung. Jetzt in
  `Fitter.fit` kleineres Fenster für kurze, nicht gerade Stücke; Schenkel < `min_length` → eine
  Linie bis zum Anschluss. Dazu `merge_through_junctions`: zusammengefügte Linie per
  Ausgleichsgerade durch alle Stützpunkte, Enden über Schnittpunkt/Projektion mitgeführt
  (vorher bestimmten vom Fangen verschobene Enden die Lage, z. B. Kante 1,5 px neben der Tinte).
  Bögen −20–64 % (Scans), PLAN2_EG 261 → 189; Trefferquote/Genauigkeit fast überall besser,
  Splitter und offene Enden weniger. Rest: flache Ausbeulungen an Abzweigen, Kehren an
  Doppellinienenden, Fehlbögen in fleckigen Füllflächen.
- **0.31.0 Fehlbögen = abgerundete Ecken** (Analyse: 421 von 598 Bögen in 4 Plänen liegen auf Originallinien, Radius
  1–3 mm, ~90°): `cad.arcs_to_corners` – Tangenten-Ecke P auf Tinte und beide Tangentenstücke ≥ 70 % Tinte → zwei
  Linien (echte Bögen ≤ 68 %), Radius ≤ 4 mm Papier. PLAN2_EG 189→141, echt EG 147→86. Rest: Ecken mit Tinte
  < 70 % an den Tangenten (Bogenenden schräg). Verworfen: Geraden hinter den Bogenenden verlangen (Gewinn weg).
- **Ortho** 52–73 % gegen 71–91 % im Original (Schraffur des Originals ist dort als Einzellinien).
- **Wörter (0.21.0, korrigierte Simulation, mit Tesseract):** 523 von 887 richtig, 199 falsch. Je Gruppe
  (Stand vor 0.21): Maße mit Hochziffer 8 % (0.21: Nachlesen `ocr.fix_superscripts`), reine Zahlen 50 %,
  Wörter 73 %, Raumnr.+Name 78 %; Schrift 2,5–3,5 mm nur 16 %. Nächste große Gruppe: reine Zahlen
  (oft Hauptziffern unlesbar, senkrechte Maße 55 %). Echte PLAN1-Plots: 100 von 208.
  **Ursache Zahlen (untersucht 14.11.):** frei stehend 84 % gelesen, mit Linie im Textfeld (Maß-/Hilfslinie)
  nur 30 % – `text_layer` verwirft die Zahl samt Linie. Verworfen: (a) lange H/V-Linien (10-mm-Öffnung) vor
  der OCR abziehen → falsch 20→46 (PLAN1_UG); (b) zweiter Durchgang nur Ziffern auf dem befreiten Bild →
  +4 richtig, +18 falsch, Trefferquote leicht schlechter; (c) wie (b), Linie aber an Ziffernkreuzungen
  stehen lassen (Tinte beidseits) → 0 richtig mehr, falsch +2/+3. Die betroffenen Zahlen liegen zwischen
  vielen Linienresten; ohne Lage-Wissen (Maßkette) nicht trennbar. Offen: KI/Maßketten-Erkennung.
  Simulationsartefakt: PLAN1_EG/UG zeichnen ungedruckte, übereinanderliegende Maßtexte (69 Zahlen).
  **Linienstücke im OCR-Bild (untersucht 14.11., 0.22.0):** In echten Plots fehlen auch *freistehende* Maße
  („6.70“ mitten in der Maßlinie). `text_layer` behält jedes Teil < `max_char_mm` (15 mm) – also auch die
  Maßlinienstücke zwischen Tick und Zahl; an „——6.70——“ scheitert Tesseract. Gemessen (je gedrucktem Text
  nach Lage, echte PLAN1-Plots EG/UG; simuliert Wörter richtig/falsch): vorher 87/54, 523/199.
  (d) lange dünne Teile (> 3 mm, Strich < 5 % der Länge) entfernen → 83/60, 527/194 – instabil: ohne
  Maßlinie kippt Tesseracts Seitenaufteilung, „3.26“/„3.76“ werden gar nicht mehr gefunden.
  (e) zwei Durchgänge (mit/ohne Linienstücke, bessere Lesung gewinnt) → 91/64, 532/195, aber echte
  Plots +8 falsche Wörter und +25–39 % Zeit. (f) zweiter Durchgang nur Schrift ≤ 2 mm neben Linienstücken
  → 89/56, nicht schneller (Tesseract braucht den Kontext). Alle verworfen zugunsten der Maßketten-
  Erkennung (Idee 7): Lage aus Linie + Ticks, Segment gezielt lesen, Summe gegen Gesamtmaß prüfen.
  Je-Text-Messung ist aussagekräftiger als `woerter` (Menge – wiederholte Maße zählen nur einmal).
  **Kleine Schrift (untersucht 14.11.):** Hauptgruppe 1,25 mm (PLAN2-Raumstempel), bei 150 dpi ~7 px, 21 von
  231 gelesen; Binarisieren verliert Punkte/Formen. Verworfen: OCR-Zoom 2 (Nummern zerfallen, „05 Bure“),
  Graustufen für Tesseract (gesamt +18 richtig/+31 falsch, echte Scans verlieren Texte), Graustufen nur für
  Schrift < 2 mm (+5/+7). **Mit 300 dpi ohne Änderung: PLAN2_EG 13 → 45 von 55, PLAN2_OG1 18 → 33 von 46**
  – kleine Schrift ist eine Frage der Scanauflösung.

1. **Kleine, fette Schrift** (image-11: „Pos 13 Labor“, „Pos 11 Vorräte“, ca. 11 px hoch, schräg):
   Untersucht in 0.17 – sie klebt meist **nicht** an Linien, sondern steht frei; die Buchstaben
   verschmelzen zu Klecksen. Von 147 Mini-Bögen (r < 1 mm) bei image-11 stammen 51 aus solcher
   ungelesener Schrift, nur 11 aus Schrift an Linien (ein Versuch, Linien abzuziehen und den Rest
   zu lesen, brachte nur Unsinn wie „AN“/„ME“ und wurde verworfen). Graustufen-Lesung hilft schon
   (0.17); offen: Kandidaten besser gruppieren (Wort „Vorräte“ fehlt oft), ggf. KI für solche Stellen.
2. **OCR** – Wörterbuch ist da (`lexicon.py`; sicher gelesen → nur Formverwechslungen; die
   Negativliste in `test_v016_ocr_fransen.py` muss grün bleiben). Offen: Zahlen weiter teils zerrissen
   („NFL 14 94“), getrennte Wörter wieder zusammensetzen („Fo renbergen Sc ube“), Ziffern hinter
   „Pos“ („OB“ → „08“?) – nur mit sehr vorsichtiger Regel.
3. **Handschrift mit echter KI testen** – „Unerkannte Schrift mit KI lesen“ und vLLM sind nur mit
   Attrappen getestet. Mit echtem Ollama-Modell bzw. vLLM-Server des Nutzers an image-4 prüfen,
   Prompt nachschärfen. Den Workflow „Integration (echt)“ **nicht ungefragt starten**.
4. **Ortho-Anteil** (48 % / 43 % gegen 51 % / 49 %): Der Rest ist bei image-11 überwiegend ein
   echt schräger Flügel (≈39°); `straighten.second_axes` richtet ihn seit 0.17.0 aus – nur wo sich
   eine Linie ≤ ~0,3 mm verschiebt (`second_shift`), denn der Flügel ist im Scan um ±1,2° verzogen
   (ohne Grenze: Abdeckung 98,0 → 97,1 %). 59 % statt 54 % der Länge auf einer Bauachse.
   Bei image-4 bleiben Schraffur und kurze Striche – die H/V-Messung ändert sich nicht.
5. **Schraffur**: **0.32.0** Flächen auch in Zeichenfläche (`canvas.HatchItem`, steht für `members`,
   Einzellinien verborgen; Schalter Ansicht → Schraffur als Fläche = `hatch.META_KEY` in `d.meta`) und
   SVG (`<pattern>`). `find_regions` 0,2–0,4 s je `set_entities`. Prüfstand-Spalten Schraffur/Einzellinien
   (`benchmark.hatch_stats`). **0.33.0** zweiter `detect_hatch`-Durchgang nach `close_gaps` (fertige
   Geometrie; nicht bei Farb-Layern) + Mauerwerk (langer/kurzer Strich, kurzer ganz daneben,
   ≥ 0,2 × lang, lang ≤ 10 mm). Linien in Flächen image-4 405→589, -27 781→868, -37 213→269.
   **0.34.0** `hatch._fit_to_edges` (Standard in `find_regions`, `fit_edges=True`): Wandband zwischen zwei
   parallelen Kanten (Fläche ≥ 80 % im Band, Breite 0,6–3 × Strichlänge·sin), Kanten zu Ketten (Lücke ≤ 2 sp),
   Band so weit Schraffur/Bruchstücke liegen (Lücke ≤ 3 sp), Bruchstücke anderer Layer werden `members`
   (Achtung: `members` enthält jetzt auch Nicht-Schraffur-Linien). `style.drop_loose_hatch` im Pipeline-Ende.
   Einzellinien 39/42/25/12/6/12 % (image-4/-27/-37/-89/-94/-99), image-17 35→9. Verworfen: Umriss
   pauschal 1,5 sp wachsen lassen und an Vektorkanten schneiden (Muster auf Tinte 99 → 70 %, Kanten
   fehlen oft); `_adopt_rest` lockern (wenig Gewinn). Offen: Wandstücke ohne Fläche verlieren Striche an
   LINIEN; Zickzack-Mitte in image-27 teils noch nicht im Band; dichte Wandknäuel ohne Fläche.
   Offen (0.33): Einzellinien-Anteil steigt (mehr erkannte Reste in verrauschten Wänden, image-27 51 %);
   Handschrift-Großbuchstaben (N, M, A) werden teils Schraffur (image-17 35 Striche, keine Fläche);
   Mauerwerk wird als HATCH mit halbem Abstand durchgezogen (kurze Striche = volle Linien);
   an der Wandkante abknickende Strichenden (anderer Winkel) bleiben eigene Linien.
6. **Offene Enden** (image-11: 1554 gegen 1330): Seit 0.17 schließt `close_gaps` bis 2,5 × Reichweite,
   wenn `cad.ink_checker` Tinte auf der ganzen Lücke sieht. Übrig sind vor allem kurze, echte Striche
   (Möbeldetails, Fliesenmarken, Schriftreste) – pauschal 2 mm verbinden wäre falsch (Strichlinien,
   Maßhilfslinien, Buchstaben). **0.32.0** `cad.extend_hatch_ends`: Schraffurende bis 2,5 mm zur Kante,
   wenn ≥ 2 Nachbarenden (8 mm) auf derselben Kante bzw. deren Verlängerung enden (Lücke ist meist
   weißes Papier – Tintenprüfung allein greift nicht). image-89 140→98, -94 114→96 offene Enden.
   4 mm Reichweite brachte kaum mehr (+4–7 Enden).
7. **Bemaßungen** (Maßketten): **0.25.0** Längenprüfung `dimensions.check_lengths` (Maßstab px/m aus
   sicheren Lesungen, richtige Maße ±1 %; Rettung unsicherer Lesungen ab 1 m Segment, ±1 %), **0.26.0**
   DIMENSION im DXF (`Text.dim`, relativ in Texthöhen). Gemessen: EG 111→112, Wörter echt 116→117, sonst
   gleich. Verworfen: „zu langes Segment = Teilzahl“ (trifft richtige Maße bei verpassten Sternen, „43⁵“),
   2 % Toleranz („2.29“ statt „2.25“), Rettung unter 1 m („85“ statt „88⁵“, 1 px ≈ 1,7 cm).
   **Türmaße („88⁵“/„2.12⁵“, „1.01“/„2.12⁵“) offen, zwei Versuche (15.11.) gescheitert:** Der rechte Stern
   wird von den Ziffern überdeckt und von `_ticks` nicht gefunden. (1) Zeilenabtastung `_weak_ticks` auf
   bekannten Maßzeilen findet ihn (EG x=980 = 928+52), aber auch Kreuzungen in Schraffuren; Bänder über/unter
   der Linie zwischen den Sternen lesen Müll („888“, „8831“, „4.8“) – Sternstriche und überlappende Zahlen
   zerstören die Ziffern; mit Längenprobe netto EG 112→111, UG 71→72. Schwache Sterne in der normalen
   Lückensuche zerschneiden echte Ketten (UG verliert 4.17⁵, 7.50). (2) Median gleich langer, am Stern
   ausgerichteter Ausschnitte: EG „88⁵“ sauber, aber senkrecht überlappen „88⁵“/„2.12⁵“ schon im Plot,
   UG-Gruppen mischen verschiedene Stellen → nicht weiter verfolgt. Material außerhalb des Repos:
   `Testdaten Traceify/fable_tueren/`.
   **0.27.0** kleine Maße über engen Sternpaaren (`_close_pairs`, „24“ über „✳✳“, Länge gegen Sternabstand,
   Hochziffer ≠ ⁵ verworfen): EG 112→116, UG 71→80, Simulation 530/197. UG-Knäuel aus übereinander
   gedruckten Maßen („15“/„25“/„10“) unlösbar.
   **0.28.0 Türmaße (Fable):** Ziffern-Schablonen aus sicheren Lückenzahlen (`digit_templates`), Abgleich neben
   bekannten Sternen (`template_numbers`, `_door_numbers`), Breite gegen Lage geprüft, Hochziffer nur ⁵.
   EG 116→137 („88⁵“ 18/19), UG 80→89, simuliert 533/198. Offen: Höhe „2.12⁵“ im EG (überlappt), UG-Türen ohne
   erkannten Stern; Ziffernhöhe ±1 px entscheidend (UG-Gruppe nur 2 Zahlen). Ideen: Höhe ±1 px absuchen,
   untere Zahl über Plan-Wortschatz, schwacher Stern nur als Ausgangspunkt für den Schablonen-Leser.
   **0.29.0:** schwacher Stern (`_weak_ticks`) als Ausgangspunkt (`template_numbers(extra=…)`), Breite/Höhe
   desselben Paars dürfen überlappen (**0.30.0:** Maßstab aus `Text.dim` → `dimensions.scale_from_dims`, Vorrang in
   `pipeline.apply_auto_scale`; echte Plots 1:200): EG 140, UG 96, Wörter echt 129/37, simuliert 536/199. Verworfen: Höhe
   ±1 px (EG +2/−1, „86⁵“, Zeit ×3); Wortschatz für die Höhe (EG hat kein sicheres „2.12⁵“).
8. Workflow „Integration (echt)“: ODA-Suchmuster angepasst (Dateiname hat keine Versionsnummer
   mehr: `ODAFileConverter_QT6_vc16_amd64dll.msi`), aber noch **nicht live getestet**.
