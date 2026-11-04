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
QT_QPA_PLATFORM=offscreen python3 -W ignore -m pytest -q   # ~165 Tests, ca. 12 s
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
  `straighten.py` (Schräglage, Meta `schraeglage`; Export dreht über `Drawing.export_view`),
  `pdf_vector.py` (Vektor-PDF direkt), `scale_detect.py` (M 1:N), `symbols.py` (Blöcke),
  `quality.py` (Ampel), `edit.py` (Ecke, Ausrichten inkl. Polylinien `align_axes`, Lücken, Knoten),
  `hatch.py` (Schraffur-Flächen für den DXF-Export),
  `cad.py` (Fang, Schnittpunkte, Stutzen, Dehnen, SnapIndex).
- `core/benchmark.py` + `tools/pruefstand.py` – Prüfstand (Objekte, Splitter, Abdeckung,
  Texte), `core/dxf_import.py` liest fremde DXF (z. B. eines kommerziellen Vektorisierungsprogramms) und richtet sie aufs Bild aus.
  Echte Scans liegen **nicht** im Repo (Datenschutz) – der Nutzer liefert sie bei Bedarf.
- `export/` – dxf, dwg (ODA File Converter), svg, gcode (`plan()` = gemeinsame Basis für
  G-Code, Vorschau, Zeit; Radiuskorrektur, Haltestege).
- `ai/` – Ollama-Client und `openai_client.py` (vLLM/OpenAI-kompatibel, gleiche Schnittstelle;
  Auswahl über config `ki_server`, `make_client`), beide stdlib urllib; Assistent, KI-Stapelregeln.
- `gui/main_window.py` – Aktionen, Menüs, Leisten, Undo-Stack
  (`("entities", liste)`, `("drawing", d)`, `("raster", …)`, `("raster_only", …)`).
  Ändern sich Leisten/Docks: `UI_STATE_VERSION` erhöhen.
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

## Offene Ideen
Gemessen mit `tools/pruefstand.py` an 9 echten Bauplan-Scans (96–150 dpi) und DXF-Dateien eines kommerziellen Vergleichsprogramms für
image-11 (A1 Apotheke) und image-4 (verrauschter Kellerplan, Handschrift). Die Scans liegen
nicht im Repo; der Nutzer liefert sie bei Bedarf.

Stand 0.15.0 (Traceify / Vergleichsprogramm):
| | image-11 | image-4 |
|---|---|---|
| Abdeckung | 98,0 % / 86,1 % | 96,9 % / 88,4 % |
| Objekte | 3106 / 2697 | 6007 / 10408 |
| Bögen | 412 / 51 | 672 / 253 |
| exakt waagrecht/senkrecht | 48 % / 51 % | 43 % / 49 % |
| offene Enden | 1698 / 1330 | 2475 / 4173 |
| Wörter wie Vergleichsprogramm | 47 von 129 | 3 von 22 |

1. **Schraffur-Flächen vervollständigen** – beim DXF-Export werden aus 900 Schraffurlinien
   (image-94) nur 43 HATCH-Flächen, 368 Linien (41 %) bleiben übrig; image-4: 26 Flächen,
   538 von 744 Linien (72 %) übrig. Ziel: kleinere Gruppen zulassen, an Wandkanten begrenzen,
   Reste benachbarten Flächen zuordnen. Später HATCH auch in GUI und SVG.
2. **OCR** – Zahlen noch teils zerrissen („NFL 14 94“, „NFL 34 43“), Wörter verstümmelt
   („Schiafen“, „Dele“, „Kuche“). Ideen: Wörterbuch für Planbegriffe (Raumnamen, NFL/WFL, qm),
   Zahlenformat „NN,NN“ prüfen, zweiter Lesedurchgang für unsichere Treffer.
3. **Handschrift mit echter KI testen** – „Unerkannte Schrift mit KI lesen“ und vLLM sind nur mit
   Attrappen getestet. Mit echtem Ollama-Modell bzw. vLLM-Server des Nutzers an image-4 prüfen,
   Prompt nachschärfen. Den Workflow „Integration (echt)“ **nicht ungefragt starten**.
4. **Ortho-Anteil** an das Vergleichsprogramm heranführen (48 % / 43 % gegen 51 % / 49 %): Wandkanten vor dem
   Ausrichten zu durchgehenden Linien zusammenfassen; Schraffur und Text aus der Messung nehmen.
5. **Weniger Bögen** – der Rest stammt aus nicht erkannten Buchstaben: schriftähnliche Bereiche
   (`textlines.py`) ohne OCR-Treffer auf eigenen Layer legen; Mini-Bögen unter ca. 1 mm Radius
   als Polylinie.
6. **Offene Enden** (image-11: 1698 gegen 1330) – Enden von Schraffurlinien auf die Wandkante
   ziehen, kurze freistehende Fransen entfernen.
7. **Bemaßungen** (Maßketten) als DIMENSION-Objekte erkennen; dabei Maßstab plausibilisieren.
8. Workflow „Integration (echt)“: ODA-Download-Link wird nicht mehr gefunden (Seite geändert) –
   reparieren (feste Version) oder Workflow entfernen, wenn er nicht mehr gebraucht wird.
