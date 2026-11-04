<p align="center"><img src="traceify/assets/traceify.png" width="128" alt="Traceify-Logo"></p>

<h1 align="center">Traceify</h1>

<p align="center"><b>Scans, Bilder und PDFs → DXF, SVG und G-Code. Mit lokaler KI.</b><br>
Freie Windows-Software · GNU AGPL v3</p>

<p align="center">
<a href="https://github.com/StefanR1984/traceify/actions/workflows/ci.yml"><img src="https://github.com/StefanR1984/traceify/actions/workflows/ci.yml/badge.svg" alt="Tests"></a>
<a href="https://github.com/StefanR1984/traceify/actions/workflows/release.yml"><img src="https://github.com/StefanR1984/traceify/actions/workflows/release.yml/badge.svg" alt="Windows-Build"></a>
<a href="https://github.com/StefanR1984/traceify/releases/latest"><img src="https://img.shields.io/github/v/release/StefanR1984/traceify?label=Download" alt="Download"></a>
</p>

Traceify wandelt gescannte Zeichnungen, Pläne, Skizzen und Logos in saubere CAD-Geometrie (Linien, Bögen, Kreise, Texte) oder in fräsfertige Konturen für CNC, Laser und Plasma um.

## Funktionen

| Bereich | Was es kann |
|---|---|
| **Eingabe** | PNG, JPG, BMP, TIFF, GIF, WebP und PDF (auch mehrseitig). Öffnen per Menü oder Drag & Drop. **Gescannte PDFs** werden automatisch in ihrer Originalauflösung gelesen – ohne künstliches Hochrechnen, dadurch schneller und mit weniger Kleinteilen (einstellbar unter „PDF-Render-DPI“). |
| **Vektor-PDF** | PDFs aus CAD-Programmen werden erkannt und **direkt übernommen**: Linien, Kreise, Bögen, Texte, Farben, Strichstärken und gestrichelte Linien – millimetergenau, ohne Umweg über ein Rasterbild. Abschaltbar unter „Vektor-PDF“. |
| **Raster-Werkzeuge** | Schwellwert (automatisch, fest oder adaptiv), Flecken entfernen, Löcher füllen, Glätten, Lücken schließen, Invertieren, Drehen, Zuschneiden, Schräglage begradigen. Mit der Binärbild-Vorschau prüfst du das Ergebnis. |
| **CAD-Modus (Mittellinie)** | Skelettierung mit Eckenerkennung. Daraus entstehen Linien, Bögen und Kreise, nahe Endpunkte werden zusammengeführt. Gerade Kanten bleiben **eine Linie**, auch wenn Schraffur oder andere Linien abzweigen; flache Rausch-„Beulen“ und vom Skelett abgerundete Ecken werden nicht zu Bögen. **Schräglage ausgleichen:** Traceify erkennt, wie schief der Scan liegt, richtet fast waagrechte/senkrechte Linien exakt aus – auch kurze Stücke mit unsicherem Winkel (Ecken bleiben verbunden) und dreht die Schräglage beim Export heraus – auf dem Scan bleiben die Vektoren deckungsgleich. **Kleine Lücken schließen:** Linienenden, die knapp (Standard 0,8 mm) vor einem anderen Objekt enden, werden bis dorthin verlängert. Alternativ gibt es eine reine Polylinien-Ausgabe, zum Beispiel für Höhenlinien. |
| **CNC-Modus (Umriss)** | Geschlossene, geglättete Außen- und Innenkonturen. Runde Bohrungen werden als echte Kreise erkannt. |
| **Linien und Farben** | **Strichlinien** (gestrichelt, Strichpunkt) werden zu echten Linientypen (DASHED, CENTER) auf dem Layer STRICHLINIEN zusammengefasst. **Strichstärken** werden gemessen und als DXF-Strichstärke übernommen; deutlich dickere Linien (z. B. Wände) landen auf DICKE_LINIEN – auf Wunsch als **Umriss (Doppellinie)** auf dem Layer WAENDE. **Schraffuren** (schräge, parallele Linien in regelmäßigem Abstand, z. B. in Wänden) kommen auf den Layer SCHRAFFUR und lassen sich im CAD mit einem Klick ausblenden. **Farbige Pläne** lassen sich nach Farbe auf eigene Layer trennen (FARBE_ROT, FARBE_BLAU, …) – auch bei Vektor-PDFs. |
| **OCR** | Texterkennung mit Tesseract (Deutsch und Englisch, weitere Sprachen möglich) in **allen vier Richtungen** – auch senkrecht und auf dem Kopf stehend. **Schräge Beschriftungen** in beliebigem Winkel werden gefunden, geradegerückt und nachgelesen. **Handschrift**, die Tesseract nicht lesen kann, liest auf Wunsch die KI („Unerkannte Schrift mit KI lesen“). Linien, Wände und Schraffuren werden vor der Erkennung ausgeblendet, Zeichensalat wird herausgefiltert, grobe Scans (unter ca. 130 dpi) werden für die Erkennung intern vergrößert, Dezimalpunkte und Kommas in Zahlen bleiben beim Entflecken erhalten. Erkannte Texte landen als echte CAD-Texte auf dem Layer `TEXT` und erzeugen keinen Linienwirrwarr. |
| **Raster bereinigen** | **Radierer** (E) für Flecken, Stempel und Lochungen, **Stift** (P) zum Nachziehen unterbrochener Linien – Pinselgröße in der Werkzeugleiste. |
| **Bereiche** | Rechteck aufziehen (R) und festlegen: *ignorieren*, *CAD – Mittellinie*, *CNC – Umriss* oder *nur Text*. So wird z. B. der Plan als Linien, das Logo im Schriftfeld als Umriss und die Legende gar nicht übernommen. Rechtsklick auf einen Bereich ändert oder entfernt ihn. |
| **Bearbeiten** | Objekte anklicken oder per Rahmen markieren und mit Entf löschen. Bei einem markierten Objekt erscheinen **Knoten zum Ziehen** (verbundene Linien wandern mit). **Ecke schließen** (C), **gerade ausrichten** (O, rechte Winkel bleiben verbunden), **Lücken schließen** (L), **zu Polylinie verbinden** (J), **auflösen** (X). Strg+Z macht alles rückgängig. Layer lassen sich ein- und ausblenden. |
| **Zeichnen** | Senkrechte Leiste links: **Linie** (N), **Polylinie** (Umschalt+N), **Rechteck** (Umschalt+K), **Kreis** (K), **Bogen aus 3 Punkten** (A). **Fangpunkte** (F3) für Endpunkt, Mittelpunkt, Zentrum, Schnittpunkt, Lotfußpunkt und den nächsten Punkt, mit CAD-üblichen Symbolen; einzeln abschaltbar unter Zeichnen → Fangarten. **Ortho** (F7, oder Umschalt halten) zeichnet nur waagrecht oder senkrecht. **Maße per Tastatur**: Länge oder Radius in mm eintippen und Enter drücken, beim Rechteck „Breite;Höhe“. Länge und Winkel stehen live in der Statuszeile. Neue Objekte landen auf einem wählbaren Layer (Standard GEZEICHNET) und bleiben beim Neu-Konvertieren erhalten. Zeichnen geht auch ohne vorheriges Konvertieren. |
| **Stutzen und Dehnen** | **Stutzen** (T): Teilstück anklicken, es wird bis zu den nächsten Schnittpunkten entfernt; das wegfallende Stück ist vorher rot markiert. Das geht bei Linien, Polylinien, Kreisen (werden zum Bogen) und Bögen. **Dehnen** (D): Linie, offene Polylinie oder Bogen nahe dem Ende anklicken – das Objekt wird bis zum nächsten Objekt verlängert (Bögen entlang ihres Kreises). |
| **Maßstab** | Wird automatisch aus der Bild- oder PDF-DPI übernommen. Steht im Plan „M 1:100“ (oder „Maßstab 1:50“, „SCALE 1:20“), exportiert Traceify in **Originalgröße**. Alternativ klickst du zwei Punkte einer bekannten Strecke an und gibst die wahre Länge ein. |
| **Export** | DXF (R12 bis R2018) mit den Layern LINIEN, BOEGEN, KREISE, POLYLINIEN, KONTUREN und TEXT, außerdem **DWG** (über den kostenlosen [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter), falls installiert), SVG und G-Code. Es werden nur sichtbare Layer exportiert. |
| **G-Code** | Für Fräsen (Z-Zustellung in mehreren Durchgängen) oder Laser/Plasma (M3/M5). Echte G2/G3-Bögen, verkettete Wege und optimierte Fahrreihenfolge. **Fräserradius-Korrektur** außen, innen oder automatisch (Teile ausschneiden: Löcher zuerst und innen, Außenkontur zuletzt und außen), Gleich- oder Gegenlauf. **Haltestege** mit einstellbarer Breite und Höhe (beim Laser als Unterbrechung). **Vorschau** (Strg+Umschalt+G) mit Animation, Eilgängen, Stegen und Zeitschätzung. |
| **Stapel** | Ganze Ordner und mehrseitige PDFs in einem Durchgang, mit Fortschritt, Protokoll und Abbruchmöglichkeit. |
| **Qualitätsampel** | Nach jedem Konvertieren vergleicht Traceify die Vektoren mit dem Scan: **Abdeckung**, **Genauigkeit** und eine Ampel in der Statusleiste. Klick darauf (oder Q) markiert die Problemstellen auf der Zeichenfläche – rot: Tinte ohne Vektor, violett: Vektor ohne Tinte; **F8** springt von Stelle zu Stelle. |
| **Symbole** | Werkzeug **Symbol** (Y): Rechteck um ein Beispiel ziehen (z. B. Steckdose) – Traceify findet alle gleichen, auch um 90/180/270° gedreht, und ersetzt sie durch **einen CAD-Block** (DXF: BLOCK/INSERT). Zählung links („Steckdose: 12“). Die KI schlägt auf Wunsch einen Namen vor. Symbole lassen sich in einer **Bibliothek** speichern und in neuen Plänen automatisch einsetzen. |
| **Updates & Hilfe** | Traceify sucht einmal täglich nach neuen Versionen (abschaltbar im Menü Hilfe). **Jetzt installieren** lädt das Setup mit Fortschrittsanzeige, prüft Größe und SHA-256-Prüfsumme, beendet Traceify, installiert still drüber und startet neu. Die portable ZIP und der Start aus dem Quellcode bekommen weiterhin den Download-Link. **Hilfe → Problem melden** öffnet einen vorbefüllten Fehlerbericht auf GitHub (Version, Umgebung, Einstellungen, Protokoll). |
| **Automatisierung** | Python-API und Kommandozeile. Einstellungen lassen sich als JSON speichern und laden und in Stapel oder Kommandozeile weiterverwenden. |

## Installation (Windows 10/11, 64 Bit)

1. Unter **[Releases](https://github.com/StefanR1984/traceify/releases/latest)** die Datei `Traceify-Setup-<Version>.exe` herunterladen.
2. Ausführen. Administratorrechte sind nicht nötig; im Setup ist auch „für alle Benutzer“ wählbar.
3. Beim ersten Start fragt Traceify einmal, ob die **KI-Funktionen** eingerichtet werden sollen. Dann werden Ollama und ein KI-Modell (ca. 3–4 GB) automatisch geladen.

**Tesseract OCR mit deutschen und englischen Sprachdaten ist bereits eingebaut.** Die Texterkennung funktioniert sofort, ohne weitere Installation.

> Windows-Hinweis: Die EXE ist (noch) nicht digital signiert. Erscheint „Der Computer wurde durch Windows geschützt“, klicke auf **Weitere Informationen → Trotzdem ausführen**.

Alternativ gibt es eine **portable ZIP** ohne Installation (entpacken, `Traceify.exe` starten).

Einstellungen liegen unter `%APPDATA%\Traceify\config.json`.

### Aus dem Quellcode starten

Repo klonen oder als ZIP herunterladen und `Traceify_Start_Windows.bat` doppelklicken. Beim ersten Start holt die Datei alles selbst: Python 3.12, alle Bibliotheken (in `.venv`), Tesseract mit Sprachdaten und auf Wunsch Ollama samt KI-Modell.
Optionen: `--ja` (alles bestätigen), `--ohne-ki`, `--modell qwen2.5vl:7b`, `--nur-pruefen`.

## KI-Assistent (Ollama oder vLLM)

Die KI läuft **lokal** auf deinem Rechner über [Ollama](https://ollama.com) – oder auf einem eigenen KI-Server mit **[vLLM](https://docs.vllm.ai)** bzw. einem anderen OpenAI-kompatiblen Server (LM Studio, llama.cpp-Server, LocalAI). Es gehen keine Daten ins Internet. Der Assistent sitzt rechts als Reiter neben den Einstellungen (Strg+Umschalt+K).

**KI-Server wählen:** Im KI-Panel auf **⚙** klicken → *Ollama* oder *vLLM / OpenAI-kompatibel*, Adresse (z. B. `http://gpu-server:8000/v1`) und – falls der Server einen verlangt – API-Schlüssel eintragen. **Verbindung testen** zeigt sofort Serverversion und angebotene Modelle. vLLM legt das Modell beim Start fest, z. B.:
```
vllm serve Qwen/Qwen2.5-VL-7B-Instruct --port 8000
```
Für die Bild-Funktionen braucht es ein Bildmodell (VL/Vision). Alle KI-Funktionen – Analyse, Textprüfung, Handschrift, Chat, KI-Stapel – laufen mit beiden Servern gleich. Das gewählte Modell wird je Server getrennt gemerkt.

- **✨ KI-Analyse** (Strg+Umschalt+A): Die KI sieht sich das Bild an und erkennt die Art der Zeichnung (Grundriss, technische Zeichnung, Logo …). Dann wählt sie Vorlage, Modus, Entrauschen, Begradigen und OCR und konvertiert sofort.
- **Texte mit KI prüfen**: Jeder OCR-Text wird als Ausschnitt einzeln von einem Bildmodell nachgelesen (auch gedrehte und schräge Texte). Korrekturen siehst du in einer Liste und kannst sie einzeln übernehmen.
- **Unerkannte Schrift mit KI lesen**: Traceify sucht Stellen, die wie Schrift aussehen, aber von der OCR nicht gelesen wurden – typisch Handschrift wie „Privat Keller“ – und lässt sie vom Bildmodell lesen. Übernommene Texte ersetzen die Linien der Buchstaben.
- **Ergebnis bewerten**: Die KI vergleicht Original und Vektoren und schlägt Verbesserungen vor. Auf Wunsch setzt sie diese gleich um.
- **Chat mit Aufträgen**: Zum Beispiel „Lösche alle Texte und exportiere als DXF“, „Toleranz auf 3 und neu konvertieren“, „Entferne alles unter 0,5 mm“ oder „Ersetze ‚Kuche‘ durch ‚Küche‘“. Die KI antwortet und führt die passenden Aktionen aus. Ist „Aktionen sofort ausführen“ abgehakt, musst du erst bestätigen. Alles lässt sich mit Strg+Z zurücknehmen.
- **Modelle**: Im Panel wählen und (bei Ollama) mit „Laden“ herunterladen. Empfohlen: `gemma3:4b` (schnell), `qwen2.5vl:7b` (beste Texterkennung), `gemma3:12b` (genauer, braucht ca. 16 GB RAM bzw. eine gute Grafikkarte).
- **Ergebnis bewerten**: nutzt zusätzlich die Qualitätsampel (Problemstellen mit Koordinaten).
- **Stapel mit Regeln in Klartext** (Stapel-Dialog oder `--ki-regeln`): z. B. „Grundrisse als DXF mit Maßstab aus dem Plan, Logos als CNC-Umriss mit 2 mm Frästiefe als G-Code, handschriftliche Notizen überspringen“. Die KI sieht sich jede Datei an und setzt Einstellungen, Formate oder überspringt sie; das Protokoll zeigt jede Entscheidung.
  ```
  python -m traceify eingang\ -o ausgang\ --ki-regeln "Logos als G-Code mit 2 mm Tiefe, Fotos überspringen"
  ```

## Bedienung

1. Datei öffnen (Strg+O) oder ins Fenster ziehen. Bei PDFs wählst du die Seite oben in der Werkzeugleiste.
2. Bei Bedarf drehen, zuschneiden oder begradigen (Menü Raster).
3. Einen Modus oder eine Vorlage wählen, zum Beispiel „Technische Zeichnung“ oder „Logo / CNC-Umriss“.
4. **Konvertieren** (F5). Das Ergebnis erscheint farbig über dem Bild.
5. Überflüssige Objekte markieren und mit Entf entfernen. Fehlendes mit den Zeichenwerkzeugen links ergänzen, Überstände stutzen (T), zu kurze Linien dehnen (D).
6. Exportieren: DXF mit Strg+E, G-Code mit Strg+G.

Zeichnen: Klicken setzt Punkte, Esc bricht die laufende Form ab (zweimal Esc = zurück zur Auswahl), Rechtsklick beendet Linienzug und Polylinie. Die Zahl, die du während des Zeichnens tippst, ist eine Länge in mm (Komma oder Punkt); Enter setzt den Punkt in Mausrichtung.

Updates: Erscheint unten rechts „⬆ Update … verfügbar“, genügt ein Klick und **Jetzt installieren** – Einstellungen bleiben erhalten. Vorher die aktuelle Zeichnung exportieren.

Navigation: Mausrad zoomt. Mit mittlerer Maustaste oder Umschalt+Ziehen verschiebst du die Ansicht, Strg+0 passt sie ein.

**Tipps:**
- Sind Linien zerrissen, erhöhe „Lücken schließen“ oder senke den Schwellwert.
- Sind zu viele kleine Linien entstanden, erhöhe „Flecken entfernen“ und die Toleranz.
- Werden Bögen zu Linienketten, erhöhe die Toleranz leicht.
- Wände sollen im CAD als Doppellinie erscheinen? „Wände als Umriss“ einschalten (Linien, Farben, Symbole).
- Handschrift wurde nicht erkannt? Im KI-Panel „Unerkannte Schrift mit KI lesen“.

## Kommandozeile

```
python -m traceify EINGABE -o ZIELORDNER -f dxf -f nc [-m umriss] [--kein-ocr] [--einstellungen datei.json]
```

`EINGABE` kann eine Datei oder ein Ordner sein. Ohne Argumente startet `python -m traceify` die Oberfläche.

KI-Stapel über einen vLLM-Server (nur für diesen Lauf, die Einstellungen bleiben unverändert):
```
python -m traceify eingang\ -o ausgang\ --ki --ki-server vllm --ki-url http://gpu-server:8000/v1 --ki-modell Qwen/Qwen2.5-VL-7B-Instruct [--ki-schluessel GEHEIM]
```

## Python-API

```python
import traceify as rc

rc.convert_file("plan.png", "plan.dxf")

s = rc.ConvertSettings()
s.vectorize.mode = rc.MODE_OUTLINE
s.ocr.enabled = False
rc.convert_file("logo.png", "logo.nc", settings=s,
                gcode=rc.GcodeSettings(cut_depth=2, step_down=0.5))

# KI wählt die Einstellungen (Ollama muss laufen)
s, vorschlag = rc.ai_settings("scan.png")
rc.convert_file("scan.png", "scan.dxf", settings=s)

res = rc.open_file("scan.pdf", page=2)
print(res.drawing.stats())
rc.export(res.drawing, "scan.svg")

rc.batch_convert("eingang/", "ausgang/", formats=[".dxf", ".svg"])
```

## Entwicklung

```bat
py -3.12 -m venv .venv
.venv\Scripts\pip install -r requirements.txt -r requirements-dev.txt
.venv\Scripts\python -m pytest
.venv\Scripts\python -m traceify            &rem Oberfläche
.venv\Scripts\python -m traceify --selbsttest
```

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

## Bekannte Grenzen (v0.1)

- **DWG** wird nicht direkt geschrieben, weil das Format proprietär ist. Jedes CAD-Programm öffnet aber DXF und kann es als DWG speichern. Der kostenlose ODA File Converter wandelt DXF auch stapelweise in DWG um.
- Die Erkennungsqualität hängt stark von der Scanqualität ab. Empfohlen sind mindestens 300 dpi und klare Linien.
- Strichstärken, Schraffuren und Bemaßungsobjekte werden noch nicht als eigene CAD-Objekte erkannt.
