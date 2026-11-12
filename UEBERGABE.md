# Übergabe Traceify – Stand 12.11.2026

**Zuerst lesen:** `.claude/CLAUDE.md` (Regeln, Aufbau, Stolpersteine, offene Ideen mit Messwerten). Danach `git pull`, `git log --oneline -5`.

## Stand
- Aktuelle Version: **0.17.0**, Branch `main`, gleichauf mit GitHub.
- Tests: 188 grün (5 übersprungen), pyflakes sauber. Windows-Probe-Build samt EXE-Selbsttest grün.
- Tag `v0.16.0` hat der Nutzer selbst angelegt. **0.17.0 ist noch nicht getaggt.** Tag und Release legt nur der Nutzer an.
- CAD-Programm des Nutzers: **Allplan**.

## Was zuletzt gebaut wurde
- **0.16.0:** Schraffur-Flächen vollständiger, Wörterbuch für Planbegriffe (`lexicon.py`), Fransen entfernen (`cad.remove_spurs`), Tooltips an allen Schaltern (`gui/tips.py`).
- **0.17.0:**
  - **Zweite Bauachse:** `straighten.second_axes` richtet einen schrägen Gebäudeflügel aus. Ausgerichtet wird nur, wo sich eine Linie höchstens um etwa 0,3 mm verschiebt (`second_shift`). Ohne diese Grenze sank die Abdeckung bei image-11 von 98,0 % auf 97,1 %, weil der Flügel im Scan um ±1,2° verzogen ist.
  - **Graustufen-Lesung:** `textlines.read_candidates(..., gray=)` liest schräge Texte zusätzlich aus dem Graustufenbild.
  - **Lücken schließen:** `cad.close_gaps(..., far=, ink_ok=)` schließt Lücken bis zum 2,5-Fachen der Reichweite (2 mm), wenn `cad.ink_checker` im Scan durchgehend Tinte sieht.
  - **Integrations-Workflow:** In `integration.yml` ist das ODA-Suchmuster angepasst. Er ist noch **nicht live getestet** und darf nicht ungefragt gestartet werden.

## Messstand (Traceify / Vergleichsprogramm)
| | image-11 | image-4 |
|---|---|---|
| Abdeckung | 98,1 % / 86,1 % | 97,1 % / 88,4 % |
| Objekte | 2924 / 2697 | 5768 / 10408 |
| Bögen | 375 / 51 | 661 / 253 |
| offene Enden | 1554 / 1330 | 2218 / 4173 |
| Wörter wie Vergleichsprogramm | 51 von 129 | 5 von 22 |

Auf allen 9 Scans gab es keine Verschlechterung gegenüber 0.16. Die Wort-Übereinstimmung ist kein Wahrheitsmaßstab.

## Erkenntnisse aus der Untersuchung
- **Kleine fette Schrift** (image-11, z. B. „Pos 13 Labor“, ca. 11 px hoch) klebt meist **nicht** an Linien, sondern steht frei, und die Buchstaben verschmelzen. Von 147 Mini-Bögen stammen 51 aus solcher ungelesener Schrift, nur 11 aus Schrift an Linien.
- **Verworfen:** Linien abziehen und den Rest lesen. Das brachte nur Unsinn („AN“, „ME“).
- **Ortho-Anteil:** Der Rest bei image-11 ist ein echt schräger Flügel (≈39°). Bei image-4 bleiben Schraffur und kurze Striche übrig.
- **Offene Enden:** Übrig sind vor allem kurze, echte Striche. Pauschal 2 mm zu verbinden würde Strichlinien und Maßhilfslinien zerstören.

## Als Nächstes
Der Nutzer liefert **weitere DXF-Dateien** (Vergleichs-DXFs, evtl. Original-CAD-Dateien) und dazu die Scans. Vorher zu klären:
1. Gibt es zu einem Scan die **Original-CAD-Datei**? Das wäre die einzige echte Wahrheit.
2. Welche Pläne kommen, und gibt es welche mit **Maßketten** und bekanntem Maßstab (für Bemaßungen als DIMENSION)?
3. Was stört in der Praxis am meisten, und was hakt beim **Allplan-Import** (Schraffur als Einzellinien, falsche Stifte, Textlage)?

Vorschlag für die Reihenfolge danach:
- **Allplan-Export prüfen:** Strichstärken auf Stifte, HATCH-Muster als Fläche, Layernamen, Textstil.
- **Schraffur fertigmachen:** Enden auf die Wandkante ziehen, HATCH auch in der GUI-Ansicht und im SVG zeigen.
- **Kleine Schrift** besser gruppieren (Wörter wie „Vorräte“ fehlen oft), ggf. unlesbare Stellen gezielt an die KI geben.
- **OCR-Feinschliff:** zerrissene Wörter und Zahlen, nur mit sehr vorsichtigen Regeln.
- **Bemaßungen als DIMENSION:** erst, wenn passende Pläne da sind.

## Arbeitsweise
- **Immer vor und nach einer Änderung an allen 9 Scans messen** (Abdeckung, Genauigkeit, Objekte, Bögen, offene Enden, Wörter). Eine Änderung, die irgendwo spürbar verschlechtert, wird nachgebessert oder verworfen. Die erste Fassung der zweiten Bauachse kostete Abdeckung und fiel erst im Vergleich auf.
- **Echte Scans nie ins Repo** (Datenschutz). Das Vergleichsprogramm wird in Repo-Dateien und UI-Texten nicht beim Namen genannt.
- Modellwahl: Opus für Auswertung und heikle Eingriffe, Sonnet für Routine und Doku, Fable nur gezielt bei einem Problem, an dem Opus hängen bleibt.

## Regeln, die immer gelten
- Auf Deutsch antworten und den Nutzer duzen. Kommentare, UI-Texte, Doku, Changelog und Commit-Nachrichten ebenfalls auf Deutsch.
- **Keine ZIPs.** Nach einer Änderung kurz zusammenfassen: was, Commit, Build-Ergebnis.
- **Keine Tags, Releases oder Veröffentlichungen ohne ausdrückliches Okay.**
- Die E-Mail-Adresse des Nutzers nirgends verwenden. Git-Autor: `StefanR1984 <StefanR1984@users.noreply.github.com>`. Commit-Nachrichten enden mit den Attribution-Zeilen der Sitzung.
- Nicht gewünscht: signierte EXE, winget, englische Übersetzung.
- Ablauf pro Feature: Kernlogik und Tests, GUI anbinden (README, `show_help`, Changelog, Tooltip in `gui/tips.py`), Version erhöhen, pyflakes und Tests grün, committen, pushen, Windows-Probe-Build (`gh workflow run release.yml --ref main`, `gh run watch <id> --exit-status`), danach alte Actions-Läufe löschen (nur die zum aktuellen Commit behalten).
