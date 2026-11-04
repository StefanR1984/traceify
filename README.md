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
| **Eingabe** | PNG, JPG, BMP, TIFF, GIF, WebP und PDF (auch mehrseitig). Öffnen per Menü oder Drag & Drop. |
| **Vektor-PDF** | PDFs aus CAD-Programmen werden erkannt und **direkt übernommen**: Linien, Kreise, Bögen, Texte, Farben, Strichstärken und gestrichelte Linien – millimetergenau, ohne Umweg über ein Rasterbild. Abschaltbar unter „Vektor-PDF“. |
| **Raster-Werkzeuge** | Schwellwert (automatisch, fest oder adaptiv), Flecken entfernen, Löcher füllen, Glätten, Lücken schließen, Invertieren, Drehen, Zuschneiden, Schräglage begradigen. Mit der Binärbild-Vorschau prüfst du das Ergebnis. |
| **CAD-Modus (Mittellinie)** | Skelettierung mit Eckenerkennung. Daraus entstehen Linien, Bögen und Kreise, nahe Endpunkte werden zusammengeführt. Alternativ gibt es eine reine Polylinien-Ausgabe, zum Beispiel für Höhenlinien. |
| **CNC-Modus (Umriss)** | Geschlossene, geglättete Außen- und Innenkonturen. Runde Bohrungen werden als echte Kreise erkannt. |
| **Linien und Farben** | **Strichlinien** (gestrichelt, Strichpunkt) werden zu echten Linientypen (DASHED, CENTER) auf dem Layer STRICHLINIEN zusammengefasst. **Strichstärken** werden gemessen und als DXF-Strichstärke übernommen; deutlich dickere Linien (z. B. Wände) landen auf DICKE_LINIEN. **Farbige Pläne** lassen sich nach Farbe auf eigene Layer trennen (FARBE_ROT, FARBE_BLAU, …) – auch bei Vektor-PDFs. |
| **OCR** | Texterkennung mit Tesseract (Deutsch und Englisch, weitere Sprachen möglich), auch für senkrechten Text. Erkannte Texte landen als echte CAD-Texte auf dem Layer `TEXT` und erzeugen keinen Linienwirrwarr. |
| **Raster bereinigen** | **Radierer** (E) für Flecken, Stempel und Lochungen, **Stift** (P) zum Nachziehen unterbrochener Linien – Pinselgröße in der Werkzeugleiste. |
| **Bereiche** | Rechteck aufziehen (R) und festlegen: *ignorieren*, *CAD – Mittellinie*, *CNC – Umriss* oder *nur Text*. So wird z. B. der Plan als Linien, das Logo im Schriftfeld als Umriss und die Legende gar nicht übernommen. Rechtsklick auf einen Bereich ändert oder entfernt ihn. |
| **Bearbeiten** | Objekte anklicken oder per Rahmen markieren und mit Entf löschen. Bei einem markierten Objekt erscheinen **Knoten zum Ziehen** (verbundene Linien wandern mit). **Ecke schließen** (C), **gerade ausrichten** (O, rechte Winkel bleiben verbunden), **Lücken schließen** (L), **zu Polylinie verbinden** (J), **auflösen** (X). Strg+Z macht alles rückgängig. Layer lassen sich ein- und ausblenden. |
| **Maßstab** | Wird automatisch aus der Bild- oder PDF-DPI übernommen. Steht im Plan „M 1:100“ (oder „Maßstab 1:50“, „SCALE 1:20“), exportiert Traceify in **Originalgröße**. Alternativ klickst du zwei Punkte einer bekannten Strecke an und gibst die wahre Länge ein. |
| **Export** | DXF (R12 bis R2018) mit den Layern LINIEN, BOEGEN, KREISE, POLYLINIEN, KONTUREN und TEXT, außerdem **DWG** (über den kostenlosen [ODA File Converter](https://www.opendesign.com/guestfiles/oda_file_converter), falls installiert), SVG und G-Code. Es werden nur sichtbare Layer exportiert. |
| **G-Code** | Für Fräsen (Z-Zustellung in mehreren Durchgängen) oder Laser/Plasma (M3/M5). Echte G2/G3-Bögen, verkettete Wege und optimierte Fahrreihenfolge. |
| **Stapel** | Ganze Ordner und mehrseitige PDFs in einem Durchgang, mit Fortschritt, Protokoll und Abbruchmöglichkeit. |
| **Updates & Hilfe** | Traceify meldet neue Versionen (einmal täglich, abschaltbar im Menü Hilfe). **Hilfe → Problem melden** öffnet einen vorbefüllten Fehlerbericht auf GitHub (Version, Umgebung, Einstellungen, Protokoll). |
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

## KI-Assistent (Ollama)

Die KI läuft **lokal** auf deinem Rechner über [Ollama](https://ollama.com). Es gehen keine Daten ins Internet. Der Assistent sitzt rechts als Reiter neben den Einstellungen (Strg+Umschalt+K).

- **✨ KI-Analyse** (Strg+Umschalt+A): Die KI sieht sich das Bild an und erkennt die Art der Zeichnung (Grundriss, technische Zeichnung, Logo …). Dann wählt sie Vorlage, Modus, Entrauschen, Begradigen und OCR und konvertiert sofort.
- **Texte mit KI prüfen**: Jeder OCR-Text wird als Ausschnitt einzeln von einem Bildmodell nachgelesen. Korrekturen siehst du in einer Liste und kannst sie einzeln übernehmen.
- **Ergebnis bewerten**: Die KI vergleicht Original und Vektoren und schlägt Verbesserungen vor. Auf Wunsch setzt sie diese gleich um.
- **Chat mit Aufträgen**: Zum Beispiel „Lösche alle Texte und exportiere als DXF“, „Toleranz auf 3 und neu konvertieren“, „Entferne alles unter 0,5 mm“ oder „Ersetze ‚Kuche‘ durch ‚Küche‘“. Die KI antwortet und führt die passenden Aktionen aus. Ist „Aktionen sofort ausführen“ abgehakt, musst du erst bestätigen. Alles lässt sich mit Strg+Z zurücknehmen.
- **Modelle**: Im Panel wählen und mit „Laden“ herunterladen. Empfohlen: `gemma3:4b` (schnell), `qwen2.5vl:7b` (beste Texterkennung), `gemma3:12b` (genauer, braucht ca. 16 GB RAM bzw. eine gute Grafikkarte).
- **Stapel mit KI**: `python -m traceify ordner/ -o aus/ --ki` wählt die Einstellungen für jede Datei einzeln.

## Bedienung

1. Datei öffnen (Strg+O) oder ins Fenster ziehen. Bei PDFs wählst du die Seite oben in der Werkzeugleiste.
2. Bei Bedarf drehen, zuschneiden oder begradigen (Menü Raster).
3. Einen Modus oder eine Vorlage wählen, zum Beispiel „Technische Zeichnung“ oder „Logo / CNC-Umriss“.
4. **Konvertieren** (F5). Das Ergebnis erscheint farbig über dem Bild.
5. Überflüssige Objekte markieren und mit Entf entfernen.
6. Exportieren: DXF mit Strg+E, G-Code mit Strg+G.

Navigation: Mausrad zoomt. Mit mittlerer Maustaste oder Umschalt+Ziehen verschiebst du die Ansicht, Strg+0 passt sie ein.

**Tipps:**
- Sind Linien zerrissen, erhöhe „Lücken schließen“ oder senke den Schwellwert.
- Sind zu viele kleine Linien entstanden, erhöhe „Flecken entfernen“ und die Toleranz.
- Werden Bögen zu Linienketten, erhöhe die Toleranz leicht.

## Kommandozeile

```
python -m traceify EINGABE -o ZIELORDNER -f dxf -f nc [-m umriss] [--kein-ocr] [--einstellungen datei.json]
```

`EINGABE` kann eine Datei oder ein Ordner sein. Ohne Argumente startet `python -m traceify` die Oberfläche.

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

**EXE lokal bauen:** `python tools/make_icons.py`, `python tools/make_version_info.py`, dann `pyinstaller --noconfirm packaging/traceify.spec`. Soll Tesseract mit hinein, vorher einen Tesseract-Ordner (mit `tessdata\`) nach `packaging\tesseract\` kopieren. Den Installer baut anschließend `iscc /DAppVersion=x.y.z packaging\windows\traceify.iss`.

**Automatisch über GitHub Actions:**
- *Tests* läuft bei jedem Push und Pull Request (Windows).
- *Windows-Build* lässt sich unter Actions manuell starten. Setup.exe und portable ZIP liegen danach als Download unter „Artifacts“.
- **Release:** Version in `traceify/__init__.py` erhöhen, Abschnitt in `CHANGELOG.md` ergänzen, dann taggen:
  ```
  git tag v0.3.1 && git push origin v0.3.1
  ```
  Der Workflow baut alles, prüft die EXE per Selbsttest und veröffentlicht ein GitHub-Release mit Setup, ZIP und Prüfsummen.

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
