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
  `quality.py` (Ampel), `edit.py` (Ecke, Ausrichten inkl. Polylinien `align_axes`, Lücken, Knoten),
  `hatch.py` (Schraffur-Flächen für den DXF-Export: Rasternummern per Nachbarschaft,
  Ausgleichsgerade, Reste anhängen), `cad.py` (Fang, Schnittpunkte, Stutzen, Dehnen, SnapIndex,
  `close_gaps`, `remove_spurs`).
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
5. **Schraffur**: Handschraffur (image-4) und viele Kleinstgruppen (image-27/-37) bleiben
   Einzellinien; viele Handschraffur-Striche erkennt schon `detect_hatch` nicht. HATCH auch in
   GUI und SVG zeigen.
6. **Offene Enden** (image-11: 1554 gegen 1330): Seit 0.17 schließt `close_gaps` bis 2,5 × Reichweite,
   wenn `cad.ink_checker` Tinte auf der ganzen Lücke sieht. Übrig sind vor allem kurze, echte Striche
   (Möbeldetails, Fliesenmarken, Schriftreste) – pauschal 2 mm verbinden wäre falsch (Strichlinien,
   Maßhilfslinien, Buchstaben). Enden von Schraffurlinien auf die Wandkante ziehen ist noch offen.
7. **Bemaßungen** (Maßketten) als DIMENSION-Objekte erkennen; dabei Maßstab plausibilisieren.
8. Workflow „Integration (echt)“: ODA-Suchmuster angepasst (Dateiname hat keine Versionsnummer
   mehr: `ODAFileConverter_QT6_vc16_amd64dll.msi`), aber noch **nicht live getestet**.
