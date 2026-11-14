# Übergabe Traceify – Stand 14.11.2026

**Zuerst lesen:** `.claude/CLAUDE.md` (Regeln, Aufbau, Stolpersteine, Befunde des Wahrheits-Prüfstands mit Messwerten). Danach `git pull`, `git log --oneline -8`.

## Stand
- Aktuelle Version: **0.21.0**, Branch `main` (Dateien aufs Programmsymbol, Hochziffern, Wörterbuch-Fix, DXF-Import für Allplan-MTEXT, echte Plots im Wahrheits-Prüfstand).
- Tests: 201 grün, 7 übersprungen, pyflakes sauber.
- `v0.20.0` ist getaggt (vom Nutzer). 0.21.0 noch nicht – Tag/Release nur der Nutzer.
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
1. **Reine Zahlen** (nur ~50 % gelesen; Ursache: Zahl klebt an Maß-/Hilfslinie, siehe CLAUDE.md – zwei Ansätze gemessen und verworfen): Ursache je Fall ansehen – Hauptziffern unlesbar, Zahl an Maßlinie geklebt, zerrissen? Werkzeug: Analyse-Skript nach Muster `wortanalyse.py` (pro Originaltext Lage, Höhe, Winkel, gefundene Wörter; `render_scan(...).truth`, `benchmark.words`).
2. **Schrift 2,5–3,5 mm** nur 16 % (bei 150 dpi ≈ 15–20 px hoch) – prüfen, ob Zoom für die OCR hilft.
3. Wahrheit mit 300 dpi (`--dpi 300`), restliche Fehlbögen (PLAN2_EG 189 gegen 90), Kiesmuster Dach.

Messstand 0.21.0: simuliert 523 von 887 Wörtern richtig (199 falsch); echte PLAN1-Plots 100 von 208 (48 falsch), Trefferquote 93,8–97,6 %, Genauigkeit 98,5–98,9 %.

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
