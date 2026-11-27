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
# Windows lokal: .venv/Scripts/python; für Messungen Tesseract in den PATH:
export PATH="/d/Programme/Tesseract:$PATH" PYTHONIOENCODING=utf-8   # sonst misst wahrheit.py ohne OCR
```

## Aufbau
- `core/model.py` – Line, Arc, Circle, Polyline, Text, Insert; `Drawing` (scale = mm/px).
  Koordinaten in **Bildpixeln, y nach unten**; Bogenwinkel in Grad im Bildsystem
  (DXF-Export spiegelt: start=-end, end=-start). Layer-Konstanten + `layer_color`.
- `core/pipeline.py` – `ConvertSettings`, `convert`/`convert_source`, Bereiche (Region).
- `core/stitch.py` – in Teilen gescannte Pläne (mehrere Bilder mit Fuge auf einer PDF-Seite) zusammensetzen; Aufruf in `loader.load_pdf_page`/`load_color` (`scan_tiles`, `_stitch_page`), Bild wird dadurch kleiner als die Seite.
- `core/preprocess.py` (`auto` = Sprenkel in Wandfüllung schließen + `add_pale_lines` blasse Rasterlinien ergänzen (0.42.0), nur fürs Vektorisieren, OCR liest ohne), `vectorize.py` (Kachel-Skelett, Fransen, Fit),
  `style.py` (Strichlinien, Strichstärken, Schraffur-Layer, Wände als Umriss), `colors.py`,
  `ocr.py` (Tesseract, 4 Richtungen, Maßzahlen), `textlines.py` (schräge Texte nachlesen),
  `lexicon.py` (Wörterbuch für Planbegriffe, OCR-Verwechslungen; Zahlen nie ändern),
  `straighten.py` (Schräglage, Meta `schraeglage`; Export dreht über `Drawing.export_view`),
  `pdf_vector.py` (Vektor-PDF direkt), `scale_detect.py` (M 1:N), `symbols.py` (Blöcke),
  `quality.py` (Ampel), `dots.py` (Kies/Punktfelder → Kreise auf KIES), `dimensions.py` (Maßzahlen gezielt lesen: Lücke der Maßlinie, zwischen Sternen, Paar über/unter der Linie; `merge` ersetzt verlesene Zahlen), `edit.py` (Ecke, Ausrichten inkl. Polylinien `align_axes`, Lücken, Knoten),
  `hatch.py` (Schraffur-Flächen für den DXF-Export: Rasternummern per Nachbarschaft,
  Ausgleichsgerade, Reste anhängen), `cad.py` (Fang, Schnittpunkte, Stutzen, Dehnen, SnapIndex,
  `close_gaps`, `remove_spurs`, `join_collinear` = an Kreuzungen zerfallene Linien durchziehen,
  `isolate_specks` = frei stehende Scanpunkte < 1 mm auf Layer SCANPUNKTE).
- `core/dashes.py` – feine Strichlinien (Striche < 0,8 mm, die Entflecken/Mindestlänge verlieren): `small_dashes` im
  nicht entfleckten Binärbild, `chain_dashes` (Reihe verfolgen, an großen Lücken teilen), `join_chains` (über Kreuzungen,
  2 mm), `drop_covered`; Aufruf in `pipeline.convert` nach dem Vektorisieren (nur ohne Farbtrennung/Schräglagenkorrektur).
  `quality.assess`: Strichlinie (linetype ≠ CONTINUOUS) richtig, wenn ≥ 30 % auf Tinte, geprüft gegen `dash_ink`
  (nicht entfleckt; `benchmark.run_file` übergibt es) – die Lücken zählen nicht (0.41.1).
  **0.45.0 Punktlinien:** `small_dots` (Teile ≤ 0,4 mm) + `chain_dots` (≥ 6 Punkte, Abstand 0,5–3,5 mm, Suche ±15 %, ein
  fehlender Punkt erlaubt, Abstands-CV ≤ 0,1) → Linie DOT auf STRICHLINIEN, `_merge_rows` fasst Überlappende zusammen. Raster-/
  Staubsperre: Median der Querpunkte je Reihenpunkt (±½ Abstand längs, bis 3,2 Abstände quer) < 2 – zwei parallele Punktlinien
  (PLAN1_OG1, 1,4 mm) bleiben. Verworfen: Sperre nach Punktdichte im Umkreis (warf PLAN1_OG1-Doppellinie weg), nach Querebenen
  (Tonerstaub = eine „Ebene“ → Plan6_UG Scheinlinie), nach Streupunkt-Anteil (Treffer-Länge PLAN3_OG1 197 → 44 mm); `join_chains`
  für Punkte (O(n²), Plan4 20 s).
  **0.43.0** zweiter `style.detect_dashed`-Durchgang am Pipeline-Ende (vor `isolate_specks`), nur LINIEN ≤ `DASH2_MAX_MM` 3 mm,
  `skip_missing` (ein an der Kreuzung verschluckter Strich: Lücke ≈ 2 Lücken + Strich ±25 %); `DASH_MIN_COVER` 0,2. Ohne die
  Beschränkungen (alle Layer bzw. lange Stücke) entstehen Schein-Strichlinien aus Wand-Doppellinien (DICKE_LINIEN-Stücke beider
  Kanten → Mittellinie) und fluchtenden Linienenden (7–9-mm-Stücke, `dash_max_len` 120 px = 20 mm bei 150 dpi): Sim −1…−2,6 Genauigkeit.
- `core/bands.py` (0.44.0) – Wandbänder: `find_bands` (Schließen 3×3, Öffnen mit Kreis Ø max(0,8 mm, 4 × Median-Strich
  `stroke_width`), ≥ 70 % Tinte) → Band aus dem Skelettbild, `band_outlines` = geschlossene Polylinien auf WAENDE. Geschlossene
  WAENDE-Polylinien werden gefüllt (`fill_mask`, `groups` für DXF-SOLID-HATCH, SVG evenodd, `canvas.wall_fill`), Schalter `hatch.META_KEY`.
  `truth.compare`: Original in der Füllung = getroffen, `wand_genau`; `quality.assess`: Füllung deckt ab. Ohne 4×-Strich-Regel griff es auf
  150-dpi-Scans (Striche ~1 mm) Möbel/Schrift (image-27 36000 mm²).
- `core/benchmark.py` + `tools/pruefstand.py` – Prüfstand (Objekte, Splitter, Abdeckung,
  Texte), `core/dxf_import.py` liest fremde DXF (z. B. eines kommerziellen Vektorisierungsprogramms) und richtet sie aufs Bild aus.
  Echte Scans liegen **nicht** im Repo (Datenschutz) – der Nutzer liefert sie bei Bedarf.
- `core/truth.py` + `tools/wahrheit.py` – **Wahrheits-Prüfstand**: Original-CAD-DXF (Allplan,
  `Testdaten Traceify/dxf neu/dxf neu/PLAN1–3_*.dxf`, Einheit m; Standard seit 17.11., mit Maßketten als LINE/MTEXT
  und PLAN1_Dach – die alten ohne Maßketten in `Testdaten Traceify/dxf/dxf/` bleiben als Vergleich) → simulierter Scan (1:100, 150 dpi,
  Strich 0,25 mm, Rauschen) → Traceify → Messung gegen die Originalgeometrie (Trefferquote,
  Genauigkeit, Lagefehler in Papier-mm, Objekte, Bögen, Ortho, Wörter). Abbildung ist exakt
  bekannt, keine Lage-Schätzung. Noch ohne Schräglage. Echte Plots: `truth.load_fills` (HATCH-Vollfüllung, SOLID) zählt nur für
  `wand_genau` (0.44.1); `printed` lässt Punktlinien (Linientyp PUNKT/DOT, `load_cad` setzt ihn, `dxf_import.transform` behält ihn)
  schon ab 25 % auf Tinte zu (0.45.0).
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
- OpenCV 5 (Build zieht die neueste): `HoughLinesP` liefert (N, 4) statt (N, 1, 4) – immer `reshape(-1, 4)`
  (0.38.2, Absturz „cannot unpack non-iterable numpy.int32“ in `preprocess.estimate_skew`).
- PowerShell im Workflow: keine deutschen Anführungszeichen „“ in Inline-Skripten
  (Release-Notizen kommen aus `tools/release_notes.py`).
- Tesseract wird **nach** dem PyInstaller-Build nach `dist/Traceify/tesseract` kopiert.
- Esc ist ein Fenster-Kürzel („Auswahl“); die Zeichenfläche fängt es beim Zeichnen über
  `ShortcutOverride` ab.
- Performance-Referenz: A0 mit 400 dpi (13245×9362) ≈ 21 s mit OCR auf 2 Kernen.
- PDF-DPI 0 = automatisch (`loader.resolve_dpi`): Scan-PDFs in Originalauflösung, sonst 300.
- Vektor-PDF-Erkennung (`pdf_vector.has_vectors`, ab 15 Zeichenbefehlen): weiße Flächen ohne Strich (`_mask`, Abdeckungen über
  Scans) zählen nicht – sonst wird ein Scan mit 4 weißen Rechtecken zur leeren Vektorzeichnung (0.38.11, `Testdaten Traceify/Fehler/erledigt/wolfgang.pdf`,
  Scan ~65 dpi auf einem Teil der A3-Seite → 300 dpi gerendert, nicht `native_dpi`).
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

**Messbasis echte Plots, Stand 0.43.0** (21.11., `Testdaten Traceify/dxf neu/dxf neu`, alle 17 Allplan-Plots, 300 dpi,
mit Tesseract, `--jobs 3`; „gedruckt“ = Tinte < 160 plus kleine hellgraue Teile ≤ 1 mm (`truth._printed_ink`) – nur < 210
überall ließ PLAN1 auf 50 % fallen, graue Füllflächen decken ausgeblendete Objekte; Wörter/Texte ab 0.36.1 gezählt mit
zusammengeführten Hochziffern und ohne Schrift < 0,6 mm, „Texte richtig“ = je gedrucktem Text; Summe Texte 1984 von 4360, Wörter falsch 281):
| Plan (1:N) | Treffer | Genauigk. | Lage 95 % mm | Objekte (Orig.) | Bögen (Orig.) | Ortho (Orig.) | Wörter richtig/falsch | Texte richtig |
|---|---|---|---|---|---|---|---|---|
| PLAN1_EG (200) | 97,7 % | 98,9 % | 0,162 | 2757 (20958) | 43 (198) | 79 (89) % | 63 von 88 / 15 | 145 von 244 |
| PLAN1_OG1 (200) | 93,8 % | 98,9 % | 0,162 | 664 (2941) | 11 (10) | 52 (81) % | 2 von 3 / 2 | 2 von 3 |
| PLAN1_UG (200) | 94,0 % | 98,9 % | 0,243 | 2425 (13026) | 55 (94) | 80 (87) % | 63 von 114 / 9 | 93 von 284 |
| PLAN2_Dach (100) | 94,0 % | 100,0 % | 0,162 | 2717 (10699), 35 Kies-Fl. | 3 (8035) | 82 (89) % | 27 von 32 / 7 | 82 von 107 |
| PLAN2_EG (100) | 95,6 % | 98,5 % | 0,243 | 4875 (11901) | 101 (94) | 76 (84) % | 214 von 258 / 22 | 466 von 637 |
| PLAN2_OG1 (100) | 97,6 % | 99,3 % | 0,162 | 4568 (11734) | 84 (93) | 76 (84) % | 160 von 192 / 22 | 394 von 540 |
| PLAN2_OG2 (100) | 97,2 % | 99,2 % | 0,197 | 4573 (11149) | 81 (99) | 72 (83) % | 155 von 185 / 28 | 348 von 491 |
| PLAN2_OG3 (100) | 97,2 % | 98,0 % | 0,162 | 3448 (10638), 11 Kies-Fl. | 67 (2708) | 84 (91) % | 126 von 161 / 27 | 256 von 390 |
| PLAN3_DG (350) | 48,5 % | 87,1 % | 0,359 | 57 (256) | 2 (0) | 97 (53) % | 2 von 6 / 1 | 0 von 2 |
| PLAN3_EG (350) | 88,7 % | 97,7 % | 0,162 | 3454 (84511) | 165 (4195) | 56 (73) % | 61 von 165 / 39 | 55 von 305 |
| PLAN3_OG1 (350) | 90,0 % | 97,9 % | 0,243 | 3274 (64112) | 152 (4108) | 58 (70) % | 55 von 99 / 25 | 35 von 108 |
| PLAN3_OG2 (350) | 90,0 % | 98,8 % | 0,243 | 2851 (60343) | 109 (4069) | 59 (74) % | 35 von 71 / 22 | 16 von 67 |
| PLAN3_OG3 (350) | 95,0 % | 99,3 % | 0,162 | 1851 (64363) | 21 (979) | 72 (88) % | 14 von 24 / 2 | 10 von 21 |
| PLAN3_OG4 (350) | 99,6 % | 99,9 % | 0,162 | 300 (938) | 17 (19) | 90 (98) % | 15 von 19 / 5 | 14 von 19 |
| PLAN3_UG1 (350) | 91,7 % | 98,0 % | 0,162 | 3262 (56418) | 188 (4401) | 65 (75) % | 70 von 405 / 48 | 59 von 1125 |
| PLAN3_UG2 (350) | 99,9 % | 99,6 % | 0,162 | 160 (367) | 6 (6) | 98 (100) % | 10 von 15 / 5 | 8 von 14 |
| PLAN3_UG3 (350) | 100,0 % | 100,0 % | 0,162 | 46 (72) | 0 (0) | 99 (100) % | 3 von 5 / 2 | 1 von 3 |
**Stand 0.44.0 (22.11., Wandbänder, Messung im Notizordner `messbasis_0440/`):** echt Treffer PLAN3_EG 97,5, OG1 96,5, OG2 96,7, OG3 97,9,
UG1 96,6, PLAN1_OG1 97,0 % (Rest der Tabelle gleich ±0,1), Genauigkeit gleich/besser, Objekte PLAN3 −30…−37 %, PLAN1_OG1 192, Ortho PLAN3 69–79 %,
PLAN1_OG1 88 %; Texte 1984 / falsch 281 gleich; Sim PLAN1_EG 91,7, PLAN1_UG 89,8, PLAN3 90,0–91,8 % (wand_genau Sim PLAN3_EG 63 %, UG1 51 % –
simulierte Bänder breiter als die Originalstriche); Scans fast gleich. Zeiten der 0.43.0-Tabelle sind bei geringerer Last gemessen (heute ×1,8 auch ohne Änderung).
**Stand 0.45.0 (23.11., Messung im Notizordner der Sitzung local_379be5d4 `messbasis_0450/`):** echt Treffer PLAN1_OG1 97,3,
PLAN3_OG1 96,7, OG2 96,7, OG3 97,9, UG1 97,5 % (Wahrheit enthält jetzt gedruckte Punktlinien; ohne Erkennung 96,1/95,7/95,7/97,6/96,5),
wand_genau PLAN1_UG 94,3 % (0.44.1, Füllungen), Rest gleich; Texte 1984 / falsch 281; Sim 150 unverändert; Scans ±2 Objekte; Plan4.pdf
offene Enden 1128 → 1002, Plan5 1352 → 1260. Analyse Weg A (23.11., `ERGEBNIS_2026-11-23_wegA_0440.md`): PLAN3-Trefferquote ausgereizt
(Rest 82–94 % nur 0,3–1 mm daneben, meist enge Parallelen); Ortho > 3° PLAN3_EG 16,5 → 2,5 % durch Wandbänder; PLAN2_EG 1–3° = kurze
Schraffurstriche mit Winkelrauschen (nur Optik). Größter offener Hebel: Schrift.
**Schrift nach Klassen (24.11., Stand 0.45.0, Notizordner der Sitzung local_8a09df45 `schrift/`, `ERGEBNIS_2026-11-24_schrift_klassen.md`):**
je gedrucktem Originaltext, ohne PLAN3_UG1 1310 Fehlstellen (1925 von 3235 richtig). Exklusive Ursachenkette: überlappt (Knäuel, doppelt
gedruckt, PLAN3_EG-Maßketten 8°) 325, schräg 94, grau gedruckt 98 (davon 39 „NN⁷⁵“, alle falsch), Linie durch die Schrift 365 (quer 219,
längs = eigene Maßlinie 97, Schraffur 49), klein < 1,2 mm 219, **frei/schwarz/≥ 1,2 mm 209** (cm 150, Maß m 46). cm-Maße = 61 % aller
Fehlstellen; einstellige „N“ 21 %, „N⁵“ 5 % richtig. „Ziffern falsch“ heißt meist ungelesen (nächste Lesung = Nachbarmaß). PLAN3_UG1: 1066
Fehlstellen, 834 überlappen. Bestes Ziel: die 209 freien (saubere „✳30✳“, „65“, „1⁵“ ungelesen, noch kein verworfener Versuch), dann längs
laufende Maßlinie; quer laufende Linien zuletzt (drei Versuche verworfen).
**Lesekette (24.11., gleicher Ordner, `trace.py`/`stufe.py`, 7 Plots PLAN2 + PLAN1_EG/UG, 909 Fehlstellen):** erste verlorene Stufe –
keine Lücke trotz Stern 452 (frei: meist nur einseitig erkannter Stern; Doppelstern „✳✳“ kleiner Maße als ein breites Diagonal-Bauteil
von `_ticks` verworfen, ~42 von 143; Stern an Wandecke), kein Stern 164, Ausschnitt ungelesen 202 (Tesseract leer), sicher falsch 38,
Breitenprobe 26, merge 22, Längenprobe 5. **0.45.1** behebt Breitenprobe (schmale „1“, „9⁵“ über Sternpaar) und merge (Unsinn
„Las“/„sve 9“/„962%“ weicht einer Maßzahl mit Maßlinie, `_garbage`): echt Texte 1984 → 2006, falsch 281 → 276, Sim +2, Scans gleich.
Offen: Doppelsterne/Sterne an Wänden in `_ticks` (je fehlendem Stern erst messen, welche Probe scheitert); merge ersetzt 9 × eine
richtige Seitenlesung durch falsche Lückenzahl (4.25 → 25, 1.13⁵ → 1.12⁵).
**Fehlende Sterne (24.11., Notizordner der Sitzung local_7d6130cc `sterne/`, `ERGEBNIS_2026-11-24_fehlende_sterne.md`):** von 452
„keine Lücke trotz Stern“ fehlt nur bei 225 ein Originalstern; Grund meist verschmolzene Sternreihe (113 von 235 Sternen, davon 64
PLAN1_UG-Knäuel, frei nur 12), keine Waagrechte 33, Seitenverhältnis 21. **Je Richtung** gerechnet war bei 79 weiteren der Stern nur
in der anderen Richtung erkannt (`_ticks` verlangt beide Linien beidseits; waagrecht strenge Bildzeile `.all`, gedreht ±1 px) →
**0.45.2** `line_gaps` teilt die Sterne beider Richtungen (`_join_ticks`; `keep`/template_numbers behält die eigenen – geteilt verlor
PLAN1_EG vier „88⁵“): echt Texte 2006 → 2026, falsch 276 → 272, Sim −7, Scans gleich; PLAN1_EG Treffer −0,3 = Schein-Strichlinien
(Maßkette y 787, Wand-Doppellinie) 2–3 px verschoben, weil die Falschlesung „40“ wegfiel (`style.detect_dashed` anfällig für
Maßketten). Rest der 201 Fehlstellen mit Sternen: Zahl über durchgehender Linie zwischen weit entfernten Sternen 54 (auch Höhenkoten),
neben Kettenende 26, neben engem Paar 24 + 10, Einzelstern/Türmaß 22.
**0.45.3 merge:** von 8 „merge überschreibt richtige Seitenlesung“ waren 4 Teilfolgen („4.25“ → „25“, „7.58⁵“ → „758⁵“) → Seitenlesung
bleibt, wenn sie einen Punkt hat und die Lückenzahl keinen. Ohne Punkt-Bedingung PLAN2_OG3 −4: „425“/„424“/„204“/„388“ der Seite sind
Hochziffer bzw. Sternstrich als Ziffer. Echt 2026 → 2030, falsch 272 → 271; Sim +10/−5. Rest (1.13⁵ → 1.12⁵, 1.21 → 4.21) Ein-Ziffer-Tausch.
**0.45.3 `_close_pairs` (34 Fälle „enges Paar, Wort/Höhe/_number“, `sterne/cp.py`, `cp2.py`):** Stand 0.45.3 richtig 1, Lücke aber
Ausschnitt ungelesen 11 (Box nur eine Ziffer), falsch 6 (davon 3 × „14⁷⁵“ → „14“), keine Lücke 16 (10 × Nachbarwort gewinnt). Ursache
meist senkrechte Maßhilfslinie: klebt an der Ziffer (Teil 2,3 h, fällt aus 0,75–1,3 h) → im Fenster Striche ≥ 1,6 h abziehen (Öffnen,
**Rand = 0** – mit OpenCV-Standardrand galt eine „1“ am unteren Fensterrand als lang: echt −2). Echt +4, Sim −1, Scans gleich. Die 34
selbst bleiben: Ziffern stehen *auf* den Hilfslinien (Linie durch die „1“/„0“, Klasse „Linie durch“).
**Ausschnitt ungelesen / Linie durch (25.11., Notizordner local_7d6130cc `ungelesen/`, `durch/`, `strich/`):** 200 Fehlstellen mit
Lücke, aber Ausschnitt verworfen (leer 71, unsicher 71, Form/Breite 58); bei 107 deckt die Box < 60 % der Zahl – Linie durch/an der Zahl,
„leer“ sind fast nur Bruchstücke; Rohlesung = Original nur 14 (5 × „1⁵“ = „15“, einstellig + ⁵ nur über Sternpaar erlaubt, ≤ 5 Texte).
Freie Fehlstellen nach Lage zu den Sternen (583, 7 Plots): längs (Zahl auf der Maßlinie zwischen Sternen) 72, quer (Hilfslinie am Stern
durch die Zahl) 83, sonst 414. „längs“: die Lücke ist schmaler als die Zahl, die Linie stößt an die äußeren Ziffern (Zeilentinte in der
Box 0,3–0,9, nicht durchgehend); die Lückenbox hat die Ziffern meist schon. **0.45.4** `_crop` → `_strip`: waagrechte Läufe ≥ 1,5 h im
Band der tintenreichsten Mittelzeile (ohne Spalten, in denen ein Ziffernstrich kreuzt) und senkrechte Striche ≥ 1,6 h (Rand = 0) weiß:
echt Texte 2034 → 2043, falsch gleich; Sim 1263 → 1270, falsch 639 → 629; Scans gleich. **Verworfen:** eigene Suche „Zahl auf der Linie“
zwischen Sternen (`_on_line`, Bruchstücke ersetzen) – Linie läuft nicht von Stern zu Stern durch, mit Lockerung nur Unsinn (Schraffur),
echt ±0. Schein-Strichlinien gezählt: 39 von 1227 Strichlinien (0,5 von 19,7 m) neben dem Original, ohne sie Genauigkeit +0,1…+0,4 –
kein Hebel. **0.45.5** `_horizontal_gaps`: im Suchfenster jeder Lücke senkrechte Striche ≥ 4 mm abziehen (Rand = 0) – Wand-/Hilfslinie
an der Ziffer: echt Texte 2043 → 2059, falsch 271 → 267; Sim 1270 → 1267, falsch 629 → 640 (verteilt, Gegenprobe); Scans gleich. Die „quer“-
Fälle (Hilfslinie am Stern durch die Zahl, 83) bleiben: PLAN1_UG meist doppelt gedruckte Knäuel, PLAN2 Zahlen in schraffierten Wanddetails.
**„sonst“ (26.11., Notizordner local_7d6130cc `sonst/`, `sonst.py`, `proto.py`):** 401 freie Fehlstellen ohne Lage zu Sternen (Stand 0.45.5) –
Einzelstern ≤ 3 h 143 (120 keine Lücke), enges Paar ≤ 3 h 123, kein Stern 112 (93 keine Lücke; „2“, Raumstempel), weites Paar 23. Im engen Paar
die zweistelligen Hochziffern: alle 49 „NN²⁵/NN⁷⁵“ der Plots falsch (Lesung „27“/„27⁵“) – Allplan druckt diese Maße **grau** (Ziffern ~110,
Hochziffer 130–200), `gray < 128` verliert die Hochziffer. **0.45.6** `ocr.quarter_superscripts` (nach `tidy_numbers`, nur mit `detail`): nur
graue Hauptziffern (10-%-Perzentil ≥ 80), Schwelle (Grau + 255)/2, `_superscript_box`, Spanne über Spalten (Lücke ≤ 0,2 sh); breiter als 0,95 × hoch
→ zwei Ziffern, erste 2 (Fußstrich ≥ 55 % der Spalten) sonst 7. Prototyp an den Originalen: grau 26 von 41 richtig, 3 Zahlen ohne Hochziffer
bekamen eine, ⁵ nie verwechselt; schwarze ⁵ würden ohne Grau-Tor zu 80 × „²⁵/⁷⁵“. Echt Texte 2059 → 2079, falsch gleich; Sim −1/+1; Scans gleich.
**0.45.7 Einzelstern** (`sonst/ein.py`, `weak.py`): von 143 „Einzelstern ≤ 3 h“ passt bei 19 ein schwacher Partner (`_weak_ticks`, Stern auf
Wand-/Hilfslinie, `_ticks` verwirft ihn), kein schwacher Partner ≤ 2,5 h 45, falsche Länge 21, Rest meist winzige verschmolzene Doppelsterne. `_close_pairs(weak=…)`:
schwacher Stern auf der Zeile (±2,5 px) nur als Partner eines sicheren, dem auf dieser Seite bis 2,5 h kein sicherer folgt; Längenprobe schützt vor
Schraffurkreuzungen. Echt Texte 2079 → 2090, falsch 267 → 268; Sim 1266 → 1274, falsch 641 → 638; Scans gleich.
**0.45.8 Einzelstern Länge 0:** die „klein“-Fälle (23, L < 0,3 h) sind „1⁵/2⁵“ an Wänden – 1,5 cm = 1,8 px, das Paar ist ein Stern. Die übrigen
„Einzelstern“-Fälle: 35 große Maße (L > 2,5 h, Partner weit), 45 gemischt (Partner am Linienende ohne Hilfslinie, Zahl neben Mittelstern), 8 Raumstempel
(`sonst/dbl.py`, Bilder `d_*.png`). `_close_pairs` nimmt jeden sicheren Stern zusätzlich als Paar (a, a), Wort mit echtem Paar hat Vorrang;
`check_lengths` lässt bei L = 0 nur `[1-3][5⁵]` → „N⁵“ zu (±3,5 px). Echt 2090 → 2096, falsch gleich; Sim −2/+6; Scans gleich. Ohne Wertbeschränkung
(„01“, „0“, „1“, „2“, PLAN1 „4“/„5“ – `sonst/einzel.py`) echt +4/+5.
**CAD-Brauchbarkeit (27.11., Notizordner local_7d6130cc `geom/`: `dump.py` sichert Original + Traceify je Plot, `zerfall.py`, `grund.py`,
`linientyp.py`):** je Originallinie ≥ 2 mm außerhalb Text (34254, 28149 zu ≥ 90 % getroffen): 1 Stück 81 %, 2 Stücke 13 %, ≥ 3 6 %; Brüche 9074 an
Kreuzungen, 327 frei. Ecken (zwei Linien, 30–150°): 3137 von 3377 geschlossen, 67 > 1 mm offen – kein Hebel. Warum `join_collinear` die Stücke nicht
verbindet: andere Art 4662 (nur `lineweight` 2075 – Nachbarstufen 0,085/0,152, 0,254/0,287; dick/dünn mit Layerwechsel 1083; DASHED/CONTINUOUS
1359), Line/Polyline 1966 (Wandband-Umrisse PLAN3/PLAN1_OG1), Winkel > 2° 1515, überlappen 529, quer versetzt 424, sollte verbunden sein 176.
**Nächster Hebel: Linienstärke entlang einer Flucht vereinheitlichen.** Linientyp: Traceify-Strichlinien 10,7 m auf durchgezogenem Original, 5,4 m
auf Strichlinien (Original-Strich unter durchgezogener Traceify-Linie 3,7 m). **0.45.9** `style.detect_dashed`: Kette keine Strichlinie, wenn bei
≥ 50 % der Striche an beiden Enden (2 px) eine Querlinie (> 60°) oder Polylinie ansetzt (Kanten von Quadrat-Reihen, Rasterfelder); zweiter Durchgang
mit `context=ents`. Echt Genauigkeit +0…+1,4 (PLAN2_OG3), falsche Strichlinien 10,7 → 8,9 m; Sim Genauigkeit +0…+1,8; Scans +2…+7 Objekte,
image 94 Ortho −2,3, Schraffur-Einzellinien 215 → 236. **Messhinweis:** seit 27.11. sperrt ein Virenscanner Tesseract-Temp-Dateien (pytesseract
`cleanup` WinError 32) → `ocr._setup` fängt das ab; Messläufe brachen vorher zufällig ab.
**0.45.10** `cad.join_collinear`: LINIEN/DICKE_LINIEN gleiche Art, Stärke bis Faktor 1,8 gleich (`same_weight`), verbundene Linie Layer + Stärke der
längengewichteten Mehrheit. Echt Brüche 8907 → 7892, 1 Stück 22675 → 23025, Objekte −1,5…−3 %, Treffer −0,1…+0,01; Sim gleich; Scans Objekte bis −7 %.
Rest „Art verschieden“ 3560: 0,085/0,152 429 (scheitern an Lücke/Winkel/Versatz), 0,085/0,254 325 (Faktor 3, absichtlich getrennt), DASHED/CONTINUOUS
1248. Danach Line/Polyline 1917 (Wandband-Umrisse), Winkel > 2° 1496.
**0.45.11** `join_collinear`: Winkelbrüche (`geom/winkel.py`, `haken.py`) sind fast nur kurze Endstücke 1–3 mm, ~5° zum Knoten abgeknickt, das
Nachbarstück liegt richtig; fernes Ende ≤ 1,5 px neben der Flucht bei 924 von 2165. Jetzt Querprobe am kürzeren Stück (a = längeres), `angle_tol`
15°, Richtung der verbundenen Linie nach Länge² (sonst kippt sie). Echt Brüche 7892 → 6974, Winkel > 2° 1496 → 933, Objekte −1…−4 %, Treffer ±0,1;
Sim gleich; Scans Objekte bis −5 %, Schraffur-Muster auf Tinte image-4 84 → 79 %. Rest: Art verschieden 3074, Line/Polyline 1915.
**0.45.12 Strichlinien** (`geom/strichbruch.py`, `haken2.py`, `grau.py`, `falsch_bild.py`): von 1515 Brüchen Strich/durchgezogen liegen 1093 auf
durchgezogenem Original, falsch ist die Strichlinie (≥ 10 mm); falsche Strichlinien haben 2,0 schräge Ansätze je cm (richtige 0,6) und meist keine
weiße Stelle entlang der Linie (301 von 585, 4,45 m; richtige 38 von 384). `style.paper_checker(bw)` → `detect_dashed(paper=…)`: Kette verworfen, wenn
keine Lücke Papier zeigt (3×3 frei im vollen Binärbild mit Schrift); `hooked` ab 25° statt 60°. Echt falsche Strichlinien 8,8 → 6,0 m, richtige gleich,
Brüche 6974 → 6602; Sim Treffer bis +3,2; Scans image 89 Ortho 15 → 35 %, image 27 Schraffur-Muster 95 → 88 %.
**0.45.13** (`geom/staerke.py`, `staerke_bild.py`): 1131 Brüche mit Stärkefaktor > 1,8 (meist 0,085/0,254); das dicke Stück < 3 mm bei 685, Tinte im Plot
dort wirklich breiter (0,34 gegen 0,17 mm) – `measure_widths` (5×5-Maximum der Distanz) misst Maßstern/Diagonale/Schraffur an der Kreuzung mit. Statt die
Messung zu ändern (DICKE_LINIEN, Wände hängen daran): `join_collinear(short_len=3 mm)` – kürzeres Stück darunter darf andere Stärke haben. Echt Brüche
6602 → 5961, Objekte −1…−3,5 %, Treffer ±0,2; Sim/Scans gleich. Rest: Line/Polyline 1938, Art verschieden 1992 (Strich/durchgezogen 698), Winkel 945.
**Simuliert, Stand 0.43.0** (21.11., 18 Pläne): 150 dpi Treffer 87,1–100 %, Genauigkeit 96,1–100 %, Lage 95 % ≤ 0,23 mm, Texte 1259 von 7446, Wörter falsch 638, Zeit 873 s.
**Zweite Stufe 300 dpi** (`--dpi 300 --jobs 2`, ~17 min, PLAN3 ~16000×8500 px): Treffer 87,9–100 %, Genauigkeit 98,4–100 %,
Lage 95 % ≤ 0,16 mm, Texte 1973 von 7446, Wörter falsch 877, Zeit 1726 s. Schrift bleibt trotz gleicher Auflösung weit unter den
echten Plots (26 % gegen 45 %, PLAN1_EG sogar 124 → 100 Texte): die simulierte Schrift (`_draw_text`) ähnelt der Allplan-Schrift nicht –
Texte-Entscheidungen an den echten Plots treffen, beide Simulationsstufen nur als Gegenprobe gegen Rückschritte.
**Scans** (16, `tools/pruefstand.py`): Abdeckung 95,3–100 %, offene Enden image-11 1436, image-4 1916, image-99 472.

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
Texte (nur PLAN2), Simulation +5, Scans gleich. **0.37.1** `ocr._allplan_dims`: „141⁵“ → „1.41⁵“ (Allplan:
ab 1 m immer d.dd, nur nach ⁵, nicht nach „°“ – „135°“ ist ein echter Winkel), „d.dd%“ → „d.dd⁵“: echt 1729 → 1753
Texte, falsch 394 → 372; Sim +43/−34. Einstellige „2⁵“: Tesseract liefert dort meist gar nichts (24 von 38). **0.37.2**
`dimensions.tidy_numbers`: Türmaß-Paar „101“/„2.40“ → „1.01“ (Paar muss Tür ergeben: 0,55–1,5 × 1,9–3,0 m – PLAN1_UG hat
echte „200“, „150“ neben Maßen), „2 75°“ → „2.75⁵“: echt 1753 → 1767. Länge der Maßlinie trennt „101“/„1.01“ und
⁵ nicht (gleiche Länge bzw. < 1 px). Stand PLAN2 je Maß: 705 richtig, Rest in vielen kleinen Gruppen (1↔4,
Hochziffer nicht gesehen, Teil gelesen). Offen: „N°“ ohne gefundene Komponente (14 auf PLAN2_EG, Hochziffer
an Linie verschmolzen), einstellige cm-Maße „2⁵“ (fast nie gelesen – Filter Kurztexte < 85 % Sicherheit), „275°“
(Punkt fehlt), reine Zahlen (cm-Maße „25“, „30“)
nur 14–40 % richtig (0.38.3: `_horizontal_gaps` h_min 1,2 → 0,8 mm – cm-Maße sind 1 mm hoch; PLAN2 echt +32 Texte. Analyse 18.11. je Maß
PLAN2 alle 4: „NN“ 38 %, „NN⁵“ 47 %, d.dd 84 %, d.dd⁵ 82 %; bei NN meist gar nichts gelesen, oft Ziffern an Sternen), Maße auf PLAN2 noch ~25 % verlesen; Raumstempel („0.27 Druckerpool“) oft nur teilweise.
**0.38.4 cm-Maße (Befund 18.11., je Fall belegt):** Ursache Nr. 1 war **keine Lücke**: (a) `_ticks` verwarf ~2/3 der
Sterne – ohne Maßlinie (✳30✳) ragt der Waagrecht-Arm kleiner Sterne (~9 px bei 300 dpi) nur ±4 px über die Mitte, der
Diagonal-Schwerpunkt liegt 1 px daneben → zweiter Versuch (kürzere Arme, ±1 px, Waagrechte ≤ 1 px am Schwerpunkt, senkrecht
um die Waagrechte, alle Arme im Bauteil der Mitte) **nur in Größe ±15 % des Medians der sicher erkannten Sterne** – ohne diese
Grenze traf er auf PLAN1 (1:200, Sterne ~23 px, fette Ziffern) „1“, „4“, „2“-Füße und Wandecken (echt PLAN1_UG 98 → 79
Texte). (b) Allplan stellt kleine Maße **neben** das Sternpaar über die verlängerte Linie oder über Paare bis 2,5 h Abstand →
`_close_pairs` sucht dort mit (Längenprobe bleibt Schutz). (c) Stern als Lückenende nur Mitte ± 0,15 mm statt 0,4 mm.
(d) einstellige Maße („5“) nur über Sternpaar (Längenprobe). (e) Hochziffer an Lückenzahlen immer ⁵ (las „⁹/²/⁶“).
Gemessen PLAN2 (klass.py): NN 226 → 304, NN⁵ 235 → 258, d.dd⁵ 315 → 331, d.dd 413 → 411, falsche Zahlen 241 → 221;
echt Texte 1801 → 1916, falsche Wörter 359 → 337 (PLAN1 ±1); Sim gleich (PLAN1_UG −3 Texte), Scans unverändert.
**Verworfen:** Hochziffer ohne eigene Box („445“ → „44⁵“ per Breite, netto 0); zweistellige Hochziffer („14⁷⁵“, „21²⁵“ –
echte Allplan-Maße, `truth.merge_superscripts` macht daraus „14⁷“ + „5“) verwerfen → echte Maße verloren; Armbreite ≤ 3 px
als Ziffernschutz (PLAN2 −90 NN); „Linie liegt auf dem Arm“ als Ziffernschutz (wirkungslos). Rest NN: Sterne mit zu kurzem
Schrägstrich (< 0,7 mm Öffnung), Zahlen über langer Linie ohne Sternpaar, „5“ als abgetrennte Hochziffer im Original.
**0.38.5 Hochziffern (Befund 18.11.):** (1) Prüfstand: Allplan legt zweistellige Hochziffern Ziffer für Ziffer ab
(„14“ + „7“ + „5“ = 14⁷⁵, Viertelzentimeter) – `merge_superscripts` hängt jetzt alle kleinen Ziffern an; Basis PLAN2
damit NN 55 %, NN⁵ 57 %, d.dd⁵ 86 %, 56 zweistellige (vorher als falsch/„5“ gezählt). (2) „2.83⁵“-Verluste kamen fast nur
aus `fix_superscripts`, nicht aus den Lückenzahlen: Tesseract-Wortbox bis zur Hochziffer-Oberkante (h 22 statt 15 →
keine „vollen“ Ziffern → Höhe aus den Bauteilen unten in der Box nachmessen), „83“ ein Bauteil (`n_full` nach Breite,
sonst wurde die „3“ zur Hochziffer: „2.8⁵“), Einzel-Nachlesen der 5×9-px-Ziffer scheitert → hinter d.dd immer ⁵, ganze
Zahlen ohne Loch ⁵; Strichreste (2 px breit) keine Hochziffer; `dimensions.merge` behält die Hochziffer der OCR. PLAN2:
d.dd⁵ 331 → 359, NN⁵ 258 → 267, falsche Zahlen 221 → 177; echt Texte 1916 → 1958, falsch 337 → 318.
**Offen/verworfen:** zweistellige Hochziffern im Plot meist nicht lesbar – die dünne „⁷“ zerfällt schon im Bild in
Splitter (Schwelle 160 statt 128 wirkungslos, Bild dort bereits binär; Band links der „5“ als Ziffer mitnehmen griff
auch volle Ziffern). Rest d.dd⁵: „283°“ ohne Komponente (Winkel „135°“ nicht unterscheidbar).
**0.38.6:** `_close_pairs` Zahl neben dem Paar bis 1,5 h (vorher 0,8; 2,0 bringt nichts mehr): PLAN2 NN⁵ 267 → 283, echt
Texte +13. Rest NN (55 %, Befund 18.11.): ~200 ohne Lücke – Zahlen in Wanddetails mit Schraffur (Bauteilstärken, keine
Maßkette), fette Sterne am Ende eines Stummels mit einseitigem Waagrecht-Arm. **Verworfen:** einseitigen Arm im zweiten
Stern-Versuch zulassen (Fehlsterne in Zahlen: PLAN2 NN −17, falsch +9); Sternpaar-Zahl nicht über gefundene Lückenzahl
legen (wirkungslos). Lückenzahlen-Schnellmessung schwankt um einige Maße, weil Tesseract die Ausschnitte im Stapel liest.
**0.38.7 Raumstempel (Befund 18.11.):** PLAN2 Texte mit Buchstaben 80 von 121 richtig; fast alle Fehlstellen werden von einer
grau gedruckten Linie gekreuzt (Türschwenk, Grau 100–200; Schrift < 100) – `text_layer` warf Wort + Linie als ein Bauteil
weg. `recognize`: Tinte nur mit dunklem Kern (`detail` < 128, 5×5 erweitert), **nur wenn ≥ 25 % der Tinte ≤ 10 ist**
(Plots; Scans 25 %-Perzentil 32–64, Simulation ~30+) – ohne dieses Tor Simulation je Text 1257 → 1145, Scan image 136
Texte 46 → 24. Schwelle 100 statt 128: weniger falsche Zahlen (149), aber cm-Maße −17 (1-mm-Ziffern ohne tiefschwarzen
Kern). Ergebnis: Buchstaben 86, echt falsche Wörter 316 → 295. Rest: Wörter an schwarzen Linien, „Büro“ teils ohne
Umlaut („Biro“), fehlende Leerzeichen („121WCD“).
**0.38.8 Raumstempel (Befund 18.11.):** Alle Fehlstellen waren *sicher* gelesen (≥ 80), die Formregeln griffen nicht.
(a) Raumnamen fehlten im Wörterbuch (Teeküche, Druckerpool, Putzkammer …), (b) „Büro“ → „Bure“/„Biro“/„Buro-“ (zu kurz für
die Ähnlichkeitsregel → Tabelle `lexicon._MISREAD`), (c) „Beralung“ (l/t jetzt in `_FORM`), (d) **schwarze** Türschwenk-Bögen
durch das Wort („Druck pool“, „Putz mmer“) → `lexicon._join_cut` (Begriff ≥ 8, Anfang + Ende, 1–3 fehlende Buchstaben,
eindeutig, nicht zwei bekannte Wörter). PLAN2 Buchstaben-Texte 86 → 95 von 121, echt Texte 1968 → 1977, falsch 295 → 284.
Offen: Raumnummer ohne Punkt („0 21a“, „121WCD“ – Zahlen nie ändern), abgeschnittenes Wortende („Putzka“, „Drucke“ +
„kerpool“ als zwei Texte), „Pod t2“, Stempel ganz ungelesen („2.18 Flur“, „3.10 Flur/ Garderobe“).
**0.38.9 Türmaße (Befund 18.11., `tuer.py` im Notizordner):** Türpaare (Breite 0,55–1,5 über Höhe 1,9–3,0 m) auf den Plots:
PLAN2 141, PLAN1 14 (UG 13). Stand 0.38.8: beide richtig PLAN2 81 %, PLAN1_UG 15 %. Belegte Ursachen PLAN2_EG: (a) OCR-Zeile
„25 1.01“, Lückenzahl „25“ ersetzte sie ganz → `dimensions._split_off` behält den Rest; (b) „101“ über „2.75⁵“: OCR-Höhe 9,6 statt
14 px → `_stacked` in beide Richtungen. PLAN2_EG beide 71 → 80 %, echt Texte +6. Rest fast nur **Türbogen durch die Ziffern**
(„2.40“ → „24“, „1.01“ → „1.91“/„LOL“) und OCR ohne Fund („88⁵“ über „2.26“, Ausschnitt sauber – auch der Schablonen-Leser
findet sie nicht). PLAN1_UG: Paare senkrecht und an Wänden („NO“), nicht untersucht.
**Verworfen (18.11.): Türschwenk-Bögen vor der OCR aus dem Schriftbild löschen.** Skelett an Knoten zerlegen, RANSAC-Kreis
(R 4–30 mm, längster lückenloser Inlier-Lauf ≥ 2,5 mm, sichtbar gekrümmt), Bogen nur dort über ein Wort verlängern, wo er
dahinter ≥ 1 mm weiterläuft; zurück ins Schriftbild nur Teile ≤ 3 mm am gelöschten Band. Bild an den Fällen sauber
(„Druckerpool“, „Putzkammer“, „2.40“ frei), aber Tesseract liest den ganzen Plan anders: PLAN2 Buchstaben-Texte 95 → 97,
Türmaße ±0; Simulation Texte −25 (PLAN1_UG −11, PLAN3_UG1 −8), echt −6 (PLAN1_EG −7), Scans +240 offene Enden (andere
Textboxen → andere Geometrie), Zeit +30 %. Auch nur für Plots wäre es netto ~0. Code: Notizordner `ocr_boegen_verworfen.py` (nicht im Repo).
Dabei gefunden und behalten (0.38.10, Messung unverändert – greift erst, wenn ein Bruchstück sicher gelesen wird): `Lexicon.add_own` lernt keine Bruchstücke bekannter Begriffe mehr
(„ammer“ blockierte „Putz ammer“ → „Putzkammer“), `_join_cut` nimmt „Putz’ ammer“ (Linienrest als Apostroph).
**0.40.2:** `lexicon._cut_end` ergänzt abgeschnittene Wortenden am Textende („Putzka“, „Drucke“; nur ohne Punkt – sonst „Waschr.“ → „Waschraum.“, gefunden über alle Original-DXF-Texte: `correct` darf keinen ändern). **0.40.3:** mindestens 4 fehlende Buchstaben (OCR verliert den Punkt von „Waschr.“ → wurde „Waschraum“). Echt Texte 1983 → 1984, falsch 285 → 281. Rest Raumstempel PLAN2: „0 21a“/„121WCD“ (Zahlen nie ändern), Stempel ganz ungelesen, „Pod t2“.

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
- **0.38.1 Wellen-Bögen:** Analyse echte Plots: Fehlbögen lagen zu ~45 % „auf Linien“ (Radius 0,6–1,4 mm, ~80°,
  Spitze der gedachten Ecke weiß → keine Ecke), Rest in Text. Ketten kleiner Bögen entlang gerader Linien (Schraffur,
  Ziffern, Nachbarlinie stößt an). `cad.flatten_arcs`: Sehne ≥ 95 % Tinte und Tinte läuft über die Sehne hinaus →
  Linie. Echte Bögen bleiben (PLAN2_EG 58/58); Bögen echt PLAN2_EG 222 → 102. Ohne Verlängerungsprüfung noch weniger
  Bögen (84), aber sanfte Kurven würden Sehnen. Sim-Trefferquote −0,1…−1,1 = **Messartefakt (geprüft 18.11.)**:
  die verlorenen Trefferpixel liegen fast nur an engen Doppellinien (2 Linien ~3 px, im Scan ein Band) – die
  Wellen-Bögen pendelten zufällig über beide, die Sehne trifft eine. Genauigkeit gleich. Verworfen: Sehnenketten
  zur Ausgleichsgeraden mittig im Band zusammenfassen (PLAN3_OG4 verloren 475 → 468, Band breiter als 2 × Toleranz).
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

0. **Fette Schrift (0.38.0):** `ocr.thin_bold` – Median Strich/Höhe der buchstabengroßen Teile ≥ 0,22 → zusätzlich
   ausgedünnt lesen (Randabstand > r, Strich → ~10 % der Höhe), je Stelle gewinnt die sicherere Lesung (beide
   Fassungen in `recognize`). Nur eine Fassung oder Ausdünnen je Bauteil war schlechter (image-11/-136 verloren
   Texte). Testplan „Testdaten Traceify/Punkte weg/03-Bestand“ (Scan als Pixel-Striche im PDF, 0.37.3): 138 → 209
   Texte; Plots/Simulation lösen es nicht aus. Offen: Buchstaben, die eine lange Linie berühren, verschwinden in
   `text_layer` mit der Linie („BETRIEBSTE|CHNISCHE“). **Verworfen (17.11.):** in der zweiten Lesung aus den
   verworfenen Bauteilen H/V-Linien ≥ 5 mm per Öffnung abziehen und Reste in Schriftgröße zurückgeben (auch nur
   ≤ 1,5 mm neben Schrift): Ausschnitt sehr gut („BETRIEBSTECHNISC“, „ANGABEN“), ganzer Plan 03 aber ~+10 echte
   Wörter / ~+15 Unsinn („CNVMONVY“, „WA=“), Verluste (ÖLLAGER, DIREKT), Scans image-4/-27/-99 mehr Unsinn.
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
   Prompt nachschärfen.
   **0.40.4 (21.11.) image-4 mit Gemma 4:** echte Handschrift (Höhe 24–66 px) liest das Modell gut („Faßkeller“, „Heizraum-“,
   „250“ auch kopfüber); Kandidaten 7–11 px sind Kleckse → erfundene Raumnamen (Küche/Wohnen – nicht im Vergleichs-DXF) →
   `assistant.KAND_MIN_PX` 12. Zwei Lesungen bei Handschrift locker vergleichen (`_loose`). `text_slots`-Stellen auf Scans =
   11× „3.50“ auf Wänden → nur bei Plots (25 %-Perzentil der Tinte ≤ 10 wie `ocr.recognize`; Scans 24–30, Plots 0, Plan 03 0).
   image-4: 3 Vorschläge, alle richtig, 592 → 8 s; 5 Plots mit KI Texte +7, falsch +1 (Rauschen). Skript: Notizordner `hs.py`.
   **0.40.5:** Plan 03 (Scan als Pixelstriche, Tor sagt „Plot“) gab 67 Vorschläge, davon ~20× „3.50“ und Einzelbuchstaben auf
   Linien → Stellen-Lesung ≥ 3× ohne sichere OCR-Lesung im Plan fällt weg, Einzelbuchstaben unplausibel, zweite Lesung mit
   Folgezeile zählt (`Heizraum`). Plan 03 → 29 (Rest meist abgeschnittene Wortanfänge „AUFENTH“, „HENBA“ – Kandidat endet am
   Wortrand), 5 Plots mit KI Texte +2, falsch −1, aber PLAN3_UG1 −6 (echte wiederholte Maße im Knäuel). Offen: Kandidaten-
   Ausschnitt länger machen, damit ganze Wörter gelesen werden.
   **0.40.6:** Ursache war die Stellensuche, nicht der Ausschnitt: `find_slots` zerlegt Punktschrift (Teile < 0,5 mm fallen weg) in
   Stücke → `text_slots.merge_row` (Union-Find, kleineres Teil in der Zeile des größeren, Mitten ≤ 0,2 h, Höhe ≤ 2,5×, Lücke ≤ 1,2 h;
   Gruppe höher als 1,6 × breitester Teil → einzeln lassen, sonst Ketten über Treppensymbole), Stelle bis 60 mm. Plan 03 26 → 34
   Vorschläge (ganze Wörter, „VORPACH“ statt VORDACH; neu Unsinn „II“, „VERB“, „UG“), 5 Plots mit KI Texte 1255 → 1260, falsch
   117 → 115. Rest: „HENBA“, „SCH(MUTZWASSER)“ – Sicherung greift, weil das Wort über Zeichnungsteile kettet.
4. **Ortho-Anteil** (48 % / 43 % gegen 51 % / 49 %): Der Rest ist bei image-11 überwiegend ein
   echt schräger Flügel (≈39°); `straighten.second_axes` richtet ihn seit 0.17.0 aus – nur wo sich
   eine Linie ≤ ~0,3 mm verschiebt (`second_shift`), denn der Flügel ist im Scan um ±1,2° verzogen
   (ohne Grenze: Abdeckung 98,0 → 97,1 %). 59 % statt 54 % der Länge auf einer Bauachse.
   Bei image-4 bleiben Schraffur und kurze Striche – die H/V-Messung ändert sich nicht.
   **Analyse echte Plots (22.11., Stand 0.43.0, Skript `ortho/ortho.py` im Notizordner):** schräge Länge außerhalb Text
   je Traceify-Segment gegen die Originalrichtung daneben (≤ 0,3 mm). PLAN1_OG1 / PLAN2_EG / PLAN3_EG / PLAN3_OG1:
   ortho 52 / 76 / 56 / 58 %; Original daneben auch schräg 39 / 20 / 31 / 30 % (meist Schraffur 1–10 mm – zählt bei
   Traceify als Linie, ist im Original-DXF offenbar Fläche, ungeprüft); Original ortho, Traceify > 3° 4 / 3 / 9 / 8 %;
   0,5–3° 5 / 2 / 2 / 2 % (vor allem lange STRICHLINIEN 0,5–2,6° schief – offen). **Linienstern gefunden:** PLAN3 hat bis
   17 Knoten mit 30–97 Linienenden (je ~500 mm Schein-Linien über weißem Papier). Ursache `vectorize.trace_skeleton`:
   Pfade enden am Schwerpunkt ihrer Knotenkomponente; ein dicht schraffiertes Wandband wird im Skelett ein einziges
   Knotengeflecht (L-förmig), dessen Schwerpunkt im weißen Raum liegt. Nicht `snap_endpoints` (Leader-Fang statt Union-Find
   geprüft: Sterne unverändert). **Verworfen:** Schwerpunkt > 6 px vom Pfad und auf Papier → berührtes Knotenpixel nehmen
   (Patch + Test `ortho/linienstern_verworfen.patch` im Notizordner). Echt Ortho +0,3…+6, Genauigkeit bis +0,8, Objekte bis
   −258, aber Trefferquote −0,5…−1,9 (Sim −0,4…−1,8), kleine Scans offene Enden ×2 (image 89 50 → 93, image 94 38 → 75).
   **22.11. nachgeprüft:** Annahme „Schraffur im Original-DXF ist Fläche“ falsch – HATCH im Allplan-DXF sind nur SOLID-Füllungen, die
   Schraffurstriche sind LINE (kurz, schräg); Ortho-Vergleich ist fair. Echte Lücke: Segmente ≥ 3 mm > 3° neben jeder Bauachse (PLAN3_EG
   16,5 % gegen 0,5 % im Original), fast alle auf Tinte. PLAN3-Fehlstellen: 85–97 % in fast schwarzen Wandbändern → 0.44.0 `bands.py`.
   PLAN3_OG1: die Hälfte des Verlusts traf nur über Sternlinien (Artefakt), der Rest echt – ein Wandband war voller
   Scheinlinien, die die Kanten ungefähr deckten, danach leer samt beider Kanten. Ohne Schwerpunkt-auf-Papier-Bedingung
   −3…−5 Treffer (Schraffurbänder ganz leer). Eigentliche Aufgabe: schraffierte Wandbänder als Band erkennen und die
   beiden Kanten ziehen statt das Knotengeflecht zu skelettieren.
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
2a. **Neue Testdaten (0.40.0, 20.11.):** `Testdaten Traceify/Testdaten neu/Testdaten neu/Plan4–7*.pdf` (9 Scans, auf A3-Teilfläche,
   135–300 dpi; Plan4_EG.jpg = Duplikat). Befund: Papier überall sauber weiß (keine Vergilbung/Verläufe, Hintergrund-Ausgleich
   nutzlos). Ursachen schlechter DXF: (a) Plan4 Fliesenraster aus Punktreihen → 2352 Kies-Kreise → `dots.regular_share`
   (MAX_REGULAR 0,35); (b) Plan7_EG/OG1 grau angelegte Wände = schwarz mit weißen Sprenkeln → `preprocess.fill_speckle_holes`
   (Löcher ≤ 1,5 mm², Ring ≥ 60 % schwarz, ≥ 5 Sprenkel ≥ 0,04 mm² mit Länge/Breite < 3 in 1,5 mm, deren Flächen-CV ≥ 0,7);
   Wand am Rand bleibt teils offen (Sprenkel mit Verbindung nach außen sind keine Löcher) – Gewinn nur −2…−3,5 % Objekte;
   (c) PLAN6_UG zwei Scanteile → `stitch`; (d) Plan6_OG1 Tonerspritzer (nicht gelöst), Plan5/Plan4 blasse Graulinien zerfallen.
   Gemessen: Plan4 Objekte 5972 → 3625, Plan7_EG 5741 → 5541, OG1 4953 → 4855, Texte gleich; Wahrheit echt/Sim ±0,1, Texte gleich.
   **Verworfen:** Hysterese bei blasser Tinte (Median ≥ 100: Plan4/6_OG2 Texte +8/+11, aber Simulation hat Median 104–111 →
   Texte 1258 → 870); despeckle in mm² (0,15/0,3 mm² löscht Handschrift, Linienreste); Füllen ohne CV/Länge-Prüfung (Allplan-
   Schraffurwände werden an Otsu schwarz mit 1–2-px-Löchern bzw. Streifen → Vollfläche, PLAN1_OG1 93,6 → 69,6 %); CV 0,5/0,4
   (mehr Plan7, aber Gitter in PLAN3/Sim). KI `suggest_settings`: alle 9 „sauber“ = Standard, 2× „umriss“ (falsch) → nicht eingebaut.
   Messskripte im Notizordner (`exp.py`, `wcmp.py`).
3a. **KI-Nachlesen echt getestet (0.39.0, 19.11.)** mit Gemma-4-26B-A4B über vLLM (`http://192.168.0.160:11435/v1`):
   `core/text_slots.py` (Stellen ohne sichere Lesung, Linien ≥ 3 mm weg; `normalize`, `plausible`, `accept`),
   `ai.read_unrecognized` liest jede Stelle zweimal (Rand 0,6/1,5 mm, 8 Threads, ~4 Stellen/s), `apply_text_fixes`.
   Befunde PLAN2: KI liest Fehlstellen an richtiger Lage zu ~80–90 % (Orakel), Problem ist die Stellensuche (alte
   `unread_candidates` trafen 4 von 595 Fehlstellen, neue ~60 %). `sicher` der KI ist wertlos (fast immer true).
   Prompt-Beispiele werden halluziniert. Regel „beide Lesungen gleich“ ist der Hauptfilter (alle: 126 richtig/149 falsch;
   gleich: 53/4 auf PLAN2_EG). Linienlöschen in der Stelle kostete Trefferquote (−0,4…−1,2) → aus.
   Echt 17 Plots: Texte 1983 → 2157, falsch 285 → 288 (PLAN3_UG1 +3, Maß-Knäuel), Zeit 670 → 4367 s.
   Offen: Rest-Fehlstellen ohne Stelle (~40 %), Mehrheit 2 von 3 mit zweitem Prompt; Ergebnisse schwanken leicht
   (vLLM bei Temperatur 0 nicht ganz deterministisch). Messskripte im Notizordner `ki_nachlesen_0390/`.
   **0.39.1 Gegenprobe** (`SLOT_CHECK_PADS_MM` 1,0/2,5 mm, eine muss gleich lesen): 5 Pläne mit festen Antworten falsche
   KI-Texte 10 → 6, Texte gleich; echt 17 Plots Texte 2157, falsch 287. Rest-Fehlwörter PLAN3_UG1: einzeln mit festen Antworten
   0, frisch unter Last (3 Läufe parallel) +1 bis +6 – Maß-Knäuel („242“ = „24“ über „2“, „4.05“). Tintenanteil (richtige bis
   0,53, falsche 0,35–0,44) und Nachbardichte trennen nicht. Idee offen: mehrere Lesungen einer Stelle seriell statt parallel.
