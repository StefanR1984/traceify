# Übergabe Traceify – Stand 14.11.2026

**Zuerst lesen:** `.claude/CLAUDE.md` (Regeln, Aufbau, Stolpersteine, Befunde des Wahrheits-Prüfstands mit Messwerten). Danach `git pull`, `git log --oneline -8`.

## Stand
- Aktuelle Version: **0.23.0** (Maßzahlen in der Lücke der Maßlinie, `core/dimensions.py`), davor 0.22.0 (Ampel-Hinweis „300 dpi empfohlen“ bei viel Schrift < 2 mm unter 200 dpi, `quality.small_text_hint`), davor 0.21.0, Branch `main` (Dateien aufs Programmsymbol, Hochziffern, Wörterbuch-Fix, DXF-Import für Allplan-MTEXT, echte Plots im Wahrheits-Prüfstand).
- Tests: 209 grün, 7 übersprungen, pyflakes sauber.
- `v0.20.0` ist getaggt (vom Nutzer). `v0.22.0` getaggt (vom Nutzer), 0.23.0 noch nicht – Tag/Release nur der Nutzer.
- CAD-Programm des Nutzers: **Allplan**.

## Umgebung auf diesem Rechner
- Python 3.12 fehlt: `.venv` mit Python 3.13 im Projektordner (gitignored), Aufruf `.venv/Scripts/python`.
- **Tesseract** liegt unter `D:\Programme\Tesseract` und steht **nicht im PATH**. Für Tests und Messungen vorher anhängen, z. B. in Bash: `export PATH="/d/Programme/Tesseract:$PATH"`. Die installierte Traceify-EXE bringt ihr eigenes Tesseract mit (gleiche Version 5.5.3, gleiche Sprachdateien).
- Qt-Tests ohne Fenster: `QT_QPA_PLATFORM=offscreen`.
- Neu (14.11.): `Testdaten Traceify/PDF/PLAN1_EG|OG1|UG.pdf` = Allplan-Rasterplots (300 dpi, 1:200) zu den gleichnamigen DXF → `tools/wahrheit.py "Testdaten Traceify/dxf/dxf" --scans "Testdaten Traceify/PDF" --massstab 200`. `Autocad/TB_*.dxf` enthalten nur ein IMAGE (kein Vergleich), `Konvertiert mit Traceify/` = Ergebnisse des Nutzers.
- Testdaten (nie ins Repo): `Testdaten Traceify/` – 9 Scans (`image-*.pdf`), Vergleichs-DXFs nur zu image-4 und image-11, Allplan-Originale unter `Testdaten Traceify/dxf/dxf/PLAN1–3_*.dxf` (17 Pläne, Einheit m, enthalten einen Personennamen in `$LASTSAVEDBY`).

## Was seit 0.17.0 gebaut wurde
- **Wahrheits-Prüfstand** (`core/truth.py`, `tools/wahrheit.py`): Allplan-DXF → simulierter Scan (1:100, 150 dpi, 0,25 mm Strich) → Traceify → Messung gegen das Original (Trefferquote, Genauigkeit, Lagefehler, Objekte, Bögen, Ortho, Wörter). Aufruf: `python tools/wahrheit.py "Testdaten Traceify/dxf/dxf" --bericht wahr.md --json wahr.json`. Mit OCR ca. 25 min für alle Pläne.
- **0.18.0 – Doppellinien getrennt:** `merge_through_junctions` verbiegt Linienenden an Abzweigen nicht mehr (kurze seitliche Stege).
- **0.19.0 – weniger falsche Bögen:** `Fitter.fit` sucht in kurzen, nicht geraden Stücken mit kleinerem Fenster nach Ecken; winziger Schenkel → eine Linie. `merge_through_junctions` legt zusammengefügte Linien per Ausgleichsgerade durch alle Stützpunkte, Ecken werden mitgeführt.
- **0.20.0 – Ausrichten mit Tintenprüfung:** `align_axes(..., ink=cad.ink_share(...))` richtet eine Linie nur aus, wenn sie danach zu ≥ 90 % auf Tinte liegt oder nicht schlechter als vorher. Bewusst leicht schräge Linien (Dachgeschoss) bleiben schräg.

## Messstand (Wahrheit, 17 Allplan-Pläne, mit Tesseract)
| | 0.17.0 | 0.20.0 |
|---|---|---|
| Trefferquote | 60,7–99,6 %, meist 81–89 % | 65,5–99,6 %, meist 87–96 % |
| Genauigkeit | 81–97 % | 94–99,9 % |
| Wörter richtig | 451 von 887 (51 %) | 451 von 887 (51 %) – unverändert |
| Wörter falsch | 226 | 226 |

Schwächste Pläne bei Wörtern: PLAN1_UG 25 von 120, PLAN1_EG 24 von 94, PLAN2_EG 13 von 55, PLAN2_OG3 8 von 31. Gut: PLAN3_UG1 92 von 127, PLAN3_EG 72 von 112.

Echte Scans 0.17.0 → 0.20.0: gleich viele Texte, Bögen −30 bis −60 %, offene Enden weniger, Abdeckung gleich oder besser.

## Als Nächstes
1. **Maßketten erkennen** (Offene Idee 7 in CLAUDE.md): Maßlinie + Maßhilfslinien + Zahl als Einheit finden. Damit ist bekannt, wo die Zahl steht und wie sie liegt – sie lässt sich dann gezielt aus dem Ausschnitt lesen (die Linie ist bekannt und kann sauber herausgerechnet werden). Das ist der Weg für die **reinen Zahlen** (nur ~50 % gelesen; Zahl klebt an Maß-/Hilfslinie). Drei pauschale Ansätze sind gemessen und verworfen (siehe CLAUDE.md). Nebenbei: Maßstab plausibilisieren, DIMENSION im DXF.
   **Befund 14.11.:** In echten Plots fehlen auch freistehende Maße („6.70“ in der Lücke der Maßlinie), weil `text_layer` Maßlinienstücke < 15 mm im OCR-Bild lässt. Pauschales Entfernen und zwei Durchgänge sind gemessen und verworfen (Zahlen in CLAUDE.md). Geplant: neues Modul `core/dimensions.py` – (1) Maßlinien finden: lange dünne H/V-Stücke mit 45°-Ticks an den Kreuzungen, Stücke einer Kette auf derselben Achse zusammenfassen; (2) je Segment zwischen zwei Ticks den Ausschnitt über/in der Linie nur mit Ziffern lesen (Linie und Ticks herausgerechnet); (3) Summe der Teilmaße gegen das Gesamtmaß der Nachbarkette prüfen. Erster Prototyp (14.11., nicht im Repo) am echten PLAN1_UG (300 dpi): H-Linien per Öffnen mit 1×3-mm-Kern, Ticks per Öffnen mit 45°-Diagonalkernen (0,8 mm), Tick zählt, wenn H-Linie ±5 px an seiner Mitte, Ticks gleicher Zeile (±5 px) = Kette → 62 Ketten/184 Segmente; obere 6.70-Kette und die 7.50-Ketten vollständig. Schwach: Kettenenden, wo Ticks, Maßhilfslinien und kleine Maße („25“, „30“) zu Knäueln verschmelzen (Tick nicht quadratisch → verworfen), Diagonalen in Ziffern („7“, „0“) liefern Fehlkandidaten (fallen durch die Linienbedingung meist raus). Idee: Kettenenden über die Maßhilfslinien (senkrecht durch die Maßlinie) statt über die Tickform finden; Zahlen in Lücken der Maßlinie („—— 6.70 ——“) sind der einfachste erste Fall. **0.23.0 erledigt – Fall 1, Zahl in der Lücke der Maßlinie:** `dimensions.line_gaps` (H-Linien per Öffnen 1×3 mm, Paare kollinearer Stücke, Schrift kreuzt die Linienmitte, mittig, Abstand zu beiden Enden; senkrecht über rot90) → `read_gap_numbers` (Ausschnitt ohne Linie, nur Ziffern, Muster `\d{1,3}` oder `\d{1,2}.\d{2,3}`, Konfidenz ≥ 60, Hochziffer über `ocr._superscript_box`) → `merge` (ersetzt überlappende reine Zahlenlesungen, Wörter bleiben). Echte Plots EG 87→93, UG 54→62, falsch 18→16/28→24; 41 Lückenlesungen in UG, 38 richtig. **Nächste Fälle:** kleine Maße über der Linie neben den Ticks („25“, „30“ – Ticks/Hilfslinien kreuzen die Ziffern), dafür Ketten über Ticks bzw. Maßhilfslinien (Prototyp-Befund oben); Kettenenden; Summenprüfung Teilmaße = Gesamtmaß; untere „6.70“-Reihe in UG fehlt, weil ein Türbogen die Zahl kreuzt. Messen mit `tools/zahlen_echt.py` (je gedrucktem Text nach Lage; Vorher-Stand 0.22.0: PLAN1_EG 87 von 260, PLAN1_UG 54 von 284).
2. **Wahrheit standardmäßig auch mit 300 dpi messen** (`tools/wahrheit.py … --dpi 300`): echte Pläne werden meist so gescannt; bei 150 dpi ist kleine Schrift nicht lesbar und verzerrt die Wortzahlen.
3. Restliche Fehlbögen (PLAN2_EG 189 gegen 90 im Original), Kiesmuster auf Dachplänen.

Werkzeug für Wortfehler: `python tools/wortanalyse.py . "Testdaten Traceify/dxf/dxf" out.json --jobs 6` (je Originaltext: gelesen ja/nein, Höhe, Winkel, Lesungen in der Nähe).
Kleine Schrift ist erledigt: Sie scheitert an der Scanauflösung (300 dpi: PLAN2_EG 13 → 45 von 55); Zoom und Graustufen sind verworfen, die Ampel weist seit 0.22.0 darauf hin.

Messstand 0.23.0: simuliert 527 von 887 Wörtern richtig (202 falsch); echte PLAN1-Plots (Wörter-Menge) 106 von 208 (42 falsch), je Text nach Lage EG 93 von 260, UG 62 von 284, Trefferquote 93,8–97,6 %, Genauigkeit 98,5–98,9 %.

## Arbeitsweise
- **Immer vor und nach einer Änderung messen:** 9 Scans (`tools/pruefstand.py`) und 17 Allplan-Pläne (`tools/wahrheit.py`). Eine Änderung, die irgendwo spürbar verschlechtert, wird nachgebessert oder verworfen.
- Für den Vorher-Stand einen Worktree des letzten Commits anlegen (`git worktree add --detach <ordner> HEAD`) und danach wieder entfernen.
- **Echte Scans nie ins Repo** (Datenschutz). Das Vergleichsprogramm wird in Repo-Dateien und UI-Texten nicht beim Namen genannt.
- Modellwahl: Opus für Auswertung und heikle Eingriffe, Sonnet für Routine und Doku, Fable nur gezielt bei einem Problem, an dem Opus hängen bleibt.

## Regeln, die immer gelten
- Auf Deutsch antworten und den Nutzer duzen. Kommentare, UI-Texte, Doku, Changelog und Commit-Nachrichten ebenfalls auf Deutsch.
- **Keine ZIPs.** Nach einer Änderung kurz zusammenfassen: was, Commit, Build-Ergebnis.
- **Keine Tags, Releases oder Veröffentlichungen ohne ausdrückliches Okay.**
- Die E-Mail-Adresse des Nutzers nirgends verwenden. Git-Autor: `StefanR1984 <StefanR1984@users.noreply.github.com>`. Commit-Nachrichten enden mit den Attribution-Zeilen der Sitzung.
- Workflow „Integration (echt)“ nicht ungefragt starten.
- Nicht gewünscht: signierte EXE, winget, englische Übersetzung.
- Ablauf pro Feature: Kernlogik und Tests, GUI anbinden (README, `show_help`, Changelog, Tooltip in `gui/tips.py`), Version erhöhen, pyflakes und Tests grün, committen, pushen, Windows-Probe-Build (`gh workflow run release.yml --ref main`, `gh run watch <id> --exit-status`), danach alte Actions-Läufe löschen (nur die zum aktuellen Commit behalten).
