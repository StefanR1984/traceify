<p align="center"><img src="traceify/assets/traceify.png" width="128" alt="Traceify-Logo"></p>

<h1 align="center">Traceify</h1>

<p align="center"><b>Scans, Bilder und PDFs → DXF, DWG, SVG und G-Code. Mit lokaler KI.</b><br>
Freie Windows-Software · GNU AGPL v3</p>

<p align="center">
<a href="https://github.com/StefanR1984/traceify/actions/workflows/ci.yml"><img src="https://github.com/StefanR1984/traceify/actions/workflows/ci.yml/badge.svg" alt="Tests"></a>
<a href="https://github.com/StefanR1984/traceify/actions/workflows/release.yml"><img src="https://github.com/StefanR1984/traceify/actions/workflows/release.yml/badge.svg" alt="Windows-Build"></a>
<a href="https://github.com/StefanR1984/traceify/releases/latest"><img src="https://img.shields.io/github/v/release/StefanR1984/traceify?label=Download" alt="Download"></a>
</p>

Traceify wandelt gescannte Baupläne, technische Zeichnungen, Skizzen und Logos in saubere CAD-Geometrie – Linien, Bögen, Kreise, Texte, Bemaßungen, Schraffuren – oder in fräsfertige Konturen für CNC, Laser und Plasma.

## Auf einen Blick

- **Eingabe:** PNG, JPG, BMP, TIFF, GIF, WebP und PDF (mehrseitig, Scan- oder CAD-PDF).
- **Zwei Modi:** *CAD – Mittellinie* für Pläne und Zeichnungen, *CNC – Umriss* für Logos und Frästeile.
- **Für Baupläne gemacht:** Schräglage, Strichlinien, Strichstärken, Wände, Schraffur als HATCH-Fläche, Kies, Treppen, Maßketten als DIMENSION, Maßstab aus dem Plan.
- **Texterkennung** (Tesseract eingebaut) in allen Richtungen, mit Maßzahlen samt Hochziffern („2.38⁵“) und Wörterbuch für Planbegriffe.
- **Nacharbeiten im Programm:** Radierer, Stift, Bereiche, CAD-Werkzeuge mit Fang, Stutzen und Dehnen, Symbole als Blöcke.
- **Export:** DXF (R12–R2018), DWG (über ODA File Converter), SVG, G-Code mit Radiuskorrektur und Haltestegen.
- **Lokale KI** über Ollama oder vLLM: Einstellungen wählen, Texte prüfen, Handschrift lesen, Chat mit Aufträgen, Stapel mit Regeln in Klartext. Keine Daten ins Internet.
- **Qualitätsampel**, Stapelverarbeitung, Kommandozeile, Python-API, automatische Updates.

## Installation (Windows 10/11, 64 Bit)

1. Unter **[Releases](https://github.com/StefanR1984/traceify/releases/latest)** die Datei `Traceify-Setup-<Version>.exe` herunterladen.
2. Ausführen. Administratorrechte sind nicht nötig; im Setup ist auch „für alle Benutzer“ wählbar.
3. Beim ersten Start fragt Traceify einmal, ob die **KI-Funktionen** eingerichtet werden sollen. Dann werden Ollama und ein KI-Modell (ca. 3–4 GB) automatisch geladen.

**Tesseract OCR mit deutschen und englischen Sprachdaten ist eingebaut** – die Texterkennung funktioniert sofort.

> Die EXE ist nicht digital signiert. Erscheint „Der Computer wurde durch Windows geschützt“, klicke auf **Weitere Informationen → Trotzdem ausführen**.

Alternativ gibt es eine **portable ZIP** (entpacken, `Traceify.exe` starten). Einstellungen liegen unter `%APPDATA%\Traceify\config.json`.

**Aus dem Quellcode:** Repo klonen oder als ZIP laden und `Traceify_Start_Windows.bat` doppelklicken. Beim ersten Start holt die Datei alles selbst: Python 3.12, alle Bibliotheken (in `.venv`), Tesseract mit Sprachdaten und auf Wunsch Ollama samt KI-Modell. Optionen: `--ja` (alles bestätigen), `--ohne-ki`, `--modell qwen2.5vl:7b`, `--nur-pruefen`.

## Schnellstart

1. Datei öffnen (Strg+O), ins Fenster oder **aufs Traceify-Symbol** ziehen – läuft Traceify schon, öffnet sie im offenen Fenster. Bei PDFs die Seite oben in der Werkzeugleiste wählen.
2. Bei Bedarf drehen, zuschneiden oder begradigen (Menü Raster).
3. Modus oder Vorlage wählen, z. B. „Technische Zeichnung“ oder „Logo / CNC-Umriss“ – oder **✨ KI-Analyse** wählen lassen.
4. **Konvertieren** (F5). Das Ergebnis erscheint farbig über dem Bild, die Ampel unten rechts zeigt die Qualität.
5. Überflüssiges markieren und mit Entf löschen, Fehlendes nachzeichnen, Überstände stutzen (T), zu kurze Linien dehnen (D).
6. Exportieren: DXF mit Strg+E, G-Code mit Strg+G, DWG und SVG über das Menü Datei.

**Hilfe zu jedem Schalter:** Mit der Maus kurz auf einem Schalter, Feld oder seiner Beschriftung stehen bleiben – es erscheint eine Erklärung. **Navigation:** Mausrad zoomt, mittlere Maustaste oder Umschalt+Ziehen verschiebt, Strg+0 passt ein.

## Funktionen im Detail

### Eingabe und PDF

- Öffnen per Menü, Drag & Drop oder über das Programmsymbol (Desktop, Startmenü, EXE).
- **Gescannte PDFs** werden in ihrer Originalauflösung gelesen – ohne künstliches Hochrechnen, dadurch schneller und mit weniger Kleinteilen (einstellbar unter „PDF-Render-DPI“).
- **Vektor-PDFs** aus CAD-Programmen werden direkt übernommen: Linien, Kreise, Bögen, Texte, Farben, Strichstärken und Strichlinien – millimetergenau, ohne Umweg über ein Rasterbild (abschaltbar unter „Vektor-PDF“).
- Scans, die nur als Tausende Pixel-Striche im PDF stecken, werden erkannt und wie ein Scan vektorisiert.
- **In Teilen gescannte Pläne:** Liegen zwei (oder mehr) Scanteile mit weißer Fuge neben- oder untereinander auf der Seite, setzt Traceify sie vor dem Umwandeln zu einem Bild zusammen. Den Versatz bestimmt es selbst – bei echter Überlappung per Kreuzkorrelation, sonst Stoß an Stoß mit der Höhenlage aus den Linien, die über die Fuge laufen. Die Scankante an der Fuge wird entfernt.

### Raster vorbereiten

- **Automatisch aufbereiten** (Standard an): Bei blassen Scans (Kopie, grau gedruckt) zählen auch hellere Bildpunkte, wenn sie an einer Linie hängen – an der Schwelle zerfallene Linien und kleine Schrift wachsen wieder zusammen. Grau angelegte Wände, die im Scan schwarz mit weißen Sprenkeln erscheinen, werden geschlossen statt in Hunderte Linien zerlegt; Buchstaben und Aussparungen in Symbolen bleiben offen. Blasse, grau gerasterte Linien (Möbel, Strichraster) werden ergänzt, graue Flächen nicht.
- Schwellwert (automatisch, fest oder adaptiv), Flecken entfernen, Löcher füllen, Glätten, Lücken schließen, Invertieren, Drehen, Zuschneiden, Schräglage begradigen; die **Binärbild-Vorschau** zeigt das Ergebnis.
- **Radierer** (E) für Flecken, Stempel und Lochungen, **Stift** (P) zum Nachziehen unterbrochener Linien – Pinselgröße in der Werkzeugleiste.
- **Bereiche** (R): Rechteck aufziehen und festlegen – *ignorieren*, *CAD – Mittellinie*, *CNC – Umriss* oder *nur Text*. So wird z. B. der Plan als Linien, das Logo im Schriftfeld als Umriss und die Legende gar nicht übernommen. Rechtsklick ändert oder entfernt einen Bereich.

### Vektorisieren

**CAD-Modus (Mittellinie)** – Skelettierung mit Eckenerkennung, daraus Linien, Bögen und Kreise:
- Gerade Kanten bleiben **eine Linie**, auch wenn Schraffur oder andere Linien abzweigen.
- Rausch-„Beulen“, vom Skelett abgerundete Ecken und Wellen entlang gerader Linien werden nicht zu Bögen; abgerundete Ecken werden wieder spitz.
- **Schräglage:** Traceify erkennt, wie schief der Scan liegt, richtet fast waagrechte/senkrechte Linien exakt aus (Ecken bleiben verbunden) und dreht die Schräglage beim Export heraus – auf dem Scan bleiben die Vektoren deckungsgleich. Ein **schräger Gebäudeflügel** wird in sich ebenfalls parallel und rechtwinklig ausgerichtet; bewusst schräge Linien bleiben schräg.
- **Lücken schließen:** Linienenden knapp (Standard 0,8 mm) vor einem anderen Objekt werden verlängert – bis 2 mm, wenn der Scan auf der ganzen Lücke Tinte zeigt. Absichtliche Lücken (Strichlinien, vor Maßzahlen) bleiben offen.
- **Zerstückelte Linien**, die im Scan an jeder kreuzenden Linie zerfallen (Deckenraster, Stufen, Maßlinien), werden wieder durchgezogen.
- **Fransen entfernen:** kurze Stummel (Standard bis 1,5 mm) an rauen Wandkanten verschwinden.
- **Scanpunkte** (frei stehend, unter 1 mm) kommen auf den Layer SCANPUNKTE zum Ausblenden.
- Alternativ reine Polylinien-Ausgabe, z. B. für Höhenlinien.

**CNC-Modus (Umriss)** – geschlossene, geglättete Außen- und Innenkonturen; runde Bohrungen werden echte Kreise.

### Baupläne: Linien, Wände, Schraffur, Kies

- **Strichlinien** (gestrichelt, Strichpunkt) werden echte Linientypen (DASHED, CENTER) auf STRICHLINIEN – auch feine, grau gedruckte Strichlinien aus Strichen unter 0,8 mm (Möbel, Verdecktes), die sonst beim Entflecken verloren gingen, und Strichlinien, denen an Kreuzungen ein Strich fehlt.
- **Strichstärken** werden gemessen und als DXF-Strichstärke übernommen; dicke Linien (Wände) kommen auf DICKE_LINIEN – auf Wunsch als **Umriss (Doppellinie)** auf WAENDE.
- **Schraffur** (schräge, parallele Linien in regelmäßigem Abstand) kommt auf SCHRAFFUR und wird im DXF/DWG als **echte Schraffur-Fläche (HATCH)** mit Winkel und Abstand ausgegeben – auch bei zerrissenen Linien, schwankendem Abstand und versetztem Raster. Die Fläche reicht von Wandkante zu Wandkante; lose Striche darin gehen in ihr auf. Auch handgezeichnetes Mauerwerk zählt als Schraffur. Zeichenfläche und SVG zeigen dieselben Flächen (ein Klick wählt die ganze Schraffur).
- **Keine Verwechslung:** Wände und Möbel in schrägen Gebäudeteilen, **schräge Treppen** (Stufen stoßen rechtwinklig auf die Wangen) und einzelne schräge Striche (Handschrift) bleiben normale Linien.
- **Kies und Punktmuster** (auch hellgrau geplottete Ringe) werden kleine Kreise auf KIES, im DXF/DWG/SVG eine **Kies-Fläche** (HATCH mit Punktmuster). Einzelne Punkte, Rauschen, Strichpunktlinien und gepunktete Raster (Fliesenraster, Achsen) bleiben außen vor.
- **Farbige Pläne** lassen sich nach Farbe auf eigene Layer trennen (FARBE_ROT, FARBE_BLAU, …) – auch bei Vektor-PDFs.

Umschalten: Ansicht → **Schraffur als Fläche** (Flächen oder Einzellinien, gilt auch für Kies und für DXF/SVG). Die übrigen Schalter stehen in den Einstellungen unter „Linien, Farben, Symbole“.

### Texte und Maße (OCR)

- Tesseract (Deutsch und Englisch, weitere Sprachen möglich) liest in **allen vier Richtungen**; **schräge Beschriftungen** werden gefunden, geradegerückt und nachgelesen.
- Linien, Wände und Schraffuren werden vor der Erkennung ausgeblendet, Zeichensalat wird gefiltert, grobe Scans (unter ca. 130 dpi) intern vergrößert.
- **Fette Schablonen- oder Plotterschrift**, die zu Klecksen verläuft, wird zusätzlich ausgedünnt gelesen.
- **Maßzahlen** werden gezielt nachgelesen (nur Ziffern, Punkt, Komma):
  - in der Lücke einer Maßlinie („—— 6.70 ——“, waagrecht und senkrecht),
  - zwischen zwei Maßbegrenzungen ohne Linie („✳74✳“) und über eng liegenden Sternen („24“ über „✳✳“),
  - als Paar über und unter der Linie („3.01“ / „3.00“), auch **Türmaße** („88⁵“ / „2.12⁵“) per Ziffern-Schablonen aus dem eigenen Plan,
  - mit **Hochziffern** (Allplan-Schreibweise „2.38⁵“ = 2,385 m), auch wenn Tesseract sie als „°“ liest.
- Aus sicher gelesenen Maßen ermittelt Traceify den Maßstab und prüft jede Maßzahl gegen den Abstand ihrer Maßbegrenzungen: passende unsichere Lesungen werden übernommen, unmögliche verworfen.
- Ein **Wörterbuch für Planbegriffe** (Raumnamen, Bauteile, WFL/NFL/BR) korrigiert verlesene Wörter („Kuche“ → „Küche“); Zahlen werden nie verändert.
- **Handschrift** liest auf Wunsch die KI.
- Texte landen als echte CAD-Texte auf TEXT, erkannte Maßketten zusätzlich als **Bemaßung (DIMENSION)** von Stern zu Stern.
- Grobe Scans mit viel kleiner Schrift: Die Ampel empfiehlt dann **300 dpi** – kleine Schrift wird damit ein Vielfaches besser gelesen.

### Maßstab

- Automatisch aus der Bild- oder PDF-DPI.
- Steht im Plan „M 1:100“ (oder „Maßstab 1:50“, „SCALE 1:20“), exportiert Traceify in **Originalgröße**.
- Noch sicherer: aus erkannten Maßketten (gezeichnete Länge gegen Maßzahl) – auch ohne Maßstabsangabe.
- Von Hand: zwei Punkte einer bekannten Strecke anklicken und die wahre Länge eingeben.

### Bearbeiten und Zeichnen

| Werkzeug | Taste | |
|---|---|---|
| Auswahl | Esc | Klick oder Rahmen, Entf löscht; bei einem Objekt **Knoten zum Ziehen** (verbundene Linien wandern mit) |
| Ecke schließen | C | |
| Gerade ausrichten | O | Linien und Polylinien; rechte Winkel bleiben verbunden, Rundungen rund |
| Lücken schließen | L | |
| Zu Polylinie verbinden / auflösen | J / X | |
| Linie, Polylinie | N, Umschalt+N | Rechtsklick beendet den Linienzug |
| Rechteck, Kreis, Bogen (3 Punkte) | Umschalt+K, K, A | |
| Stutzen | T | Teilstück bis zu den nächsten Schnittpunkten entfernen (Linie, Polylinie, Kreis, Bogen); wird vorher rot markiert |
| Dehnen | D | Linie, offene Polylinie oder Bogen bis zum nächsten Objekt verlängern |
| Symbol | Y | siehe unten |
| Fang / Ortho | F3 / F7 | Endpunkt, Mitte, Zentrum, Schnittpunkt, Lot, Nächster (einzeln unter Zeichnen → Fangarten); Ortho auch mit Umschalt halten |
| Rückgängig | Strg+Z | gilt für alles |

- **Maße per Tastatur:** beim Zeichnen Länge oder Radius in mm tippen (Komma oder Punkt), Enter setzt den Punkt in Mausrichtung; beim Rechteck „Breite;Höhe“. Länge und Winkel stehen live in der Statuszeile.
- Esc bricht die laufende Form ab, zweimal Esc = zurück zur Auswahl.
- Neue Objekte landen auf einem wählbaren Layer (Standard GEZEICHNET) und bleiben beim Neu-Konvertieren erhalten. Zeichnen geht auch ohne vorheriges Konvertieren.
- Layer lassen sich ein- und ausblenden; exportiert werden nur sichtbare.

### Symbole

Werkzeug **Symbol** (Y): Rechteck um ein Beispiel ziehen (z. B. Steckdose) – Traceify findet alle gleichen, auch um 90/180/270° gedreht, und ersetzt sie durch **einen CAD-Block** (DXF: BLOCK/INSERT). Die Zählung steht links („Steckdose: 12“), die KI schlägt auf Wunsch einen Namen vor. Symbole lassen sich in einer **Bibliothek** speichern und in neuen Plänen automatisch einsetzen.

### Qualitätsampel

Nach jedem Konvertieren vergleicht Traceify die Vektoren mit dem Scan: **Abdeckung**, **Genauigkeit** und eine Ampel in der Statusleiste. Klick darauf (oder Q) markiert die Problemstellen – rot: Tinte ohne Vektor, violett: Vektor ohne Tinte; **F8** springt von Stelle zu Stelle.

### Export und Layer

- **DXF** R12 bis R2018, **DWG** über den kostenlosen [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter) (falls installiert), **SVG** und **G-Code**.
- Schraffur und Kies als HATCH-Flächen, Maßketten als DIMENSION, Symbole als BLOCK/INSERT, Strichstärken und Linientypen wie im Scan.

| Layer | Inhalt |
|---|---|
| LINIEN, BOEGEN, KREISE, POLYLINIEN | Geometrie aus dem CAD-Modus |
| KONTUREN | Umrisse aus dem CNC-Modus |
| TEXT | erkannte Texte und Maßzahlen |
| STRICHLINIEN, DICKE_LINIEN, WAENDE | Linientypen, dicke Linien, Wände als Doppellinie |
| SCHRAFFUR, KIES | Schraffur- und Kies-Flächen |
| SYMBOLE | erkannte Symbole (Blöcke) |
| SCANPUNKTE | Scanstaub zum Ausblenden |
| FLAECHEN | gefüllte Flächen aus Vektor-PDFs |
| FARBE_… | nach Farbe getrennte Linien |
| GEZEICHNET | selbst gezeichnete Objekte (Layer wählbar) |

### G-Code

- Für Fräsen (Z-Zustellung in mehreren Durchgängen) oder Laser/Plasma (M3/M5).
- Echte G2/G3-Bögen, verkettete Wege, optimierte Fahrreihenfolge.
- **Fräserradius-Korrektur** außen, innen oder automatisch (Löcher zuerst und innen, Außenkontur zuletzt und außen), Gleich- oder Gegenlauf.
- **Haltestege** mit einstellbarer Breite und Höhe (beim Laser als Unterbrechung).
- **Vorschau** (Strg+Umschalt+G) mit Animation, Eilgängen, Stegen und Zeitschätzung.

### Stapel, Updates, Hilfe

- **Stapel:** ganze Ordner und mehrseitige PDFs in einem Durchgang, mit Fortschritt, Protokoll und Abbruch. Einstellungen lassen sich als JSON speichern und in Stapel oder Kommandozeile weiterverwenden.
- **Updates:** Traceify sucht einmal täglich nach neuen Versionen (abschaltbar im Menü Hilfe). Erscheint unten rechts „⬆ Update … verfügbar“, genügt ein Klick auf **Jetzt installieren**: Das Setup wird geladen, Größe und SHA-256 geprüft, Traceify beendet, still installiert und neu gestartet; Einstellungen bleiben erhalten. Vorher die aktuelle Zeichnung exportieren. Portable ZIP und Quellcode bekommen den Download-Link.
- **Hilfe → Problem melden** öffnet einen vorbefüllten Fehlerbericht auf GitHub (Version, Umgebung, Einstellungen, Protokoll).

## KI-Assistent (Ollama oder vLLM)

Die KI läuft **lokal** über [Ollama](https://ollama.com) – oder auf einem eigenen Server mit **[vLLM](https://docs.vllm.ai)** bzw. einem anderen OpenAI-kompatiblen Server (LM Studio, llama.cpp-Server, LocalAI). Es gehen keine Daten ins Internet. Der Assistent sitzt rechts als Reiter neben den Einstellungen (Strg+Umschalt+K).

**Server wählen:** Im KI-Panel auf **⚙** → *Ollama* oder *vLLM / OpenAI-kompatibel*, Adresse (z. B. `http://gpu-server:8000/v1`) und – falls verlangt – API-Schlüssel eintragen. **Verbindung testen** zeigt Serverversion und Modelle. vLLM legt das Modell beim Start fest:
```
vllm serve Qwen/Qwen2.5-VL-7B-Instruct --port 8000
```
Für die Bild-Funktionen braucht es ein Bildmodell (VL/Vision). Alle Funktionen laufen mit beiden Servern gleich; das Modell wird je Server getrennt gemerkt.

- **✨ KI-Analyse** (Strg+Umschalt+A): erkennt die Art der Zeichnung (Grundriss, technische Zeichnung, Logo …), wählt Vorlage, Modus, Entrauschen, Begradigen und OCR und konvertiert sofort.
- **Texte mit KI prüfen:** Jeder OCR-Text wird als Ausschnitt einzeln nachgelesen (auch gedreht und schräg); Korrekturen erscheinen in einer Liste zum einzelnen Übernehmen.
- **Unerkannte Schrift mit KI lesen:** Stellen, die wie Schrift aussehen, aber nicht oder nicht sicher gelesen wurden – Handschrift wie „Privat Keller“, auf Plänen vor allem Maße an Maßlinien und Raumstempel unter Türbögen. Jede Stelle wird zweimal mit verschiedenem Ausschnitt gelesen; vorgeschlagen wird nur, was beide Male gleich ist und von der Länge her passt (keine einstelligen Zahlen). Sicher gelesene Texte bleiben unberührt, unsichere Lesungen an der Stelle werden ersetzt. Übernommene Texte ersetzen die Linien der Buchstaben. Mit Gemma 4 (26B) über vLLM etwa 3–5 min je A3-Plan.
- **Ergebnis bewerten:** Die KI vergleicht Original und Vektoren (mit den Problemstellen der Qualitätsampel) und schlägt Verbesserungen vor; auf Wunsch setzt sie sie gleich um.
- **Chat mit Aufträgen:** z. B. „Lösche alle Texte und exportiere als DXF“, „Toleranz auf 3 und neu konvertieren“, „Entferne alles unter 0,5 mm“, „Ersetze ‚Kuche‘ durch ‚Küche‘“. Ist „Aktionen sofort ausführen“ abgehakt, bestätigst du erst. Alles lässt sich mit Strg+Z zurücknehmen.
- **Stapel mit Regeln in Klartext** (Stapel-Dialog oder `--ki-regeln`): z. B. „Grundrisse als DXF mit Maßstab aus dem Plan, Logos als CNC-Umriss mit 2 mm Frästiefe als G-Code, handschriftliche Notizen überspringen“. Das Protokoll zeigt jede Entscheidung.
- **Modelle:** im Panel wählen und (bei Ollama) mit „Laden“ herunterladen. Empfohlen: `gemma3:4b` (schnell), `qwen2.5vl:7b` (beste Texterkennung), `gemma3:12b` (genauer, braucht ca. 16 GB RAM bzw. eine gute Grafikkarte).

## Tipps

- Linien zerrissen? „Lücken schließen“ erhöhen oder den Schwellwert senken.
- Zu viele kleine Linien? „Flecken entfernen“ und die Toleranz erhöhen.
- Bögen werden zu Linienketten? Toleranz leicht erhöhen.
- Viele kleine Stummel an Wandkanten? „Fransen entfernen bis“ erhöhen.
- Wände als Doppellinie gewünscht? „Wände als Umriss“ einschalten.
- Kleine Schrift und Maße schlecht gelesen? Mit 300 dpi scannen.
- Handschrift oder Maße nicht erkannt? Im KI-Panel „Unerkannte Schrift mit KI lesen“.

## Kommandozeile

```
python -m traceify EINGABE -o ZIELORDNER -f dxf -f svg -f nc [-m umriss] [--kein-ocr] [--einstellungen datei.json] [-r]
```

`EINGABE` ist eine Datei oder ein Ordner (`-r` mit Unterordnern). Ohne Argumente startet die Oberfläche.

KI-Stapel mit Regeln, hier über einen vLLM-Server (gilt nur für diesen Lauf):
```
python -m traceify eingang\ -o ausgang\ --ki-regeln "Logos als G-Code mit 2 mm Tiefe, Fotos überspringen" --ki-server vllm --ki-url http://gpu-server:8000/v1 --ki-modell Qwen/Qwen2.5-VL-7B-Instruct [--ki-schluessel GEHEIM]
```

## Python-API

```python
import traceify as tf

tf.convert_file("plan.png", "plan.dxf")

s = tf.ConvertSettings()
s.vectorize.mode = tf.MODE_OUTLINE
s.ocr.enabled = False
tf.convert_file("logo.png", "logo.nc", settings=s,
                gcode=tf.GcodeSettings(cut_depth=2, step_down=0.5))

# KI wählt die Einstellungen (Ollama muss laufen)
s, vorschlag = tf.ai_settings("scan.png")
tf.convert_file("scan.png", "scan.dxf", settings=s)

res = tf.open_file("scan.pdf", page=2)
print(res.drawing.stats())
tf.export(res.drawing, "scan.svg")

tf.batch_convert("eingang/", "ausgang/", formats=[".dxf", ".svg"])
```

## Entwicklung

```bat
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pytest
.venv\Scripts\python -m traceify            &rem Oberfläche
.venv\Scripts\python -m traceify --selbsttest
```

## Grenzen

- Die Qualität hängt stark vom Scan ab. Empfohlen sind **300 dpi** und klare Linien; bei 150 dpi ist Schrift unter 2 mm kaum lesbar.
- **DWG** braucht den kostenlosen ODA File Converter; ohne ihn exportiert Traceify DXF, das jedes CAD-Programm öffnet.
- Bemaßungen (DIMENSION) entstehen nur für Maßzahlen mittig zwischen zwei erkannten Maßbegrenzungen; Maße über/unter der Linie (Türen) bleiben Texte. Die Maßlinie aus dem Scan bleibt zusätzlich als Linie stehen.
- Sehr eng liegende Doppellinien (unter ca. 0,6 mm) verschmelzen im Scan und werden eine Linie.
- Handschrift liest nur die KI, und auch sie nicht immer.

## Lizenz

Traceify ist freie Software unter der **GNU Affero General Public License v3.0 oder später** (siehe [LICENSE](LICENSE)). Mitgelieferte Komponenten behalten ihre eigenen Lizenzen:

| Komponente | Lizenz |
|---|---|
| PyMuPDF | AGPL-3.0 |
| Qt / PySide6 | LGPL-3.0 |
| OpenCV, Tesseract OCR | Apache-2.0 |
| scikit-image, NumPy, SciPy | BSD |
| ezdxf, Pillow, pytesseract | MIT / HPND / Apache-2.0 |
| Ollama (separat installiert) | MIT |
