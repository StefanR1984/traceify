# Changelog

## 0.7.0 – 04.11.2026
### Neu: CNC
- **G-Code-Vorschau** (Datei → G-Code-Vorschau, Strg+Umschalt+G, oder der Knopf im CNC-Bereich) zeigt:
  - alle Werkzeugwege, gestrichelt die Eilgänge und grün die Haltestege
  - eine Animation mit Werkzeugposition, oder Schritt für Schritt per Schieberegler
  - Schnittweg, Eilweg, Durchgänge und die **geschätzte Bearbeitungszeit**
  - Hinweise zu Problemen und den fertigen G-Code als Text

  Aus der Vorschau lässt sich direkt speichern.
- **Fräserradius-Korrektur** mit einstellbarem Fräser-Ø:
  - *außen*: Kontur bleibt stehen
  - *innen*: Tasche oder Loch
  - *automatisch*: Teile ausschneiden. Traceify erkennt die Verschachtelung; Löcher werden innen und zuerst gefräst, Außenkonturen außen und zuletzt, damit das Teil bis zum Schluss hält.
  - Kreise bleiben echte G2/G3-Bögen; zu kleine Konturen werden mit Hinweis ausgelassen.
- **Gleichlauf/Gegenlauf:** Die Fräsrichtung wird passend zur Korrektur festgelegt (rechtsdrehende Spindel).
- **Haltestege:** Anzahl je Außenkontur, Breite und Höhe sind einstellbar. Die Fräse hebt nur in den letzten Durchgängen über die Stege; Laser und Plasma unterbrechen den Strahl. Löcher bekommen keine Stege.
- Der G-Code-Kopf enthält Schnittweg, geschätzte Zeit, Korrektur und Stege.
- Der KI-Assistent kann Fräser-Ø, Radiuskorrektur und Haltestege setzen und die Vorschau öffnen.

### Technik
- Neue Abhängigkeit `shapely` für robuste Konturversätze.
- G-Code, Vorschau und Zeitschätzung entstehen aus demselben Bewegungsplan (`traceify.export.gcode.plan`).

## 0.6.0 – 04.11.2026
### Neu: Linien und Farben
- **Strichlinien erkennen:** Kurze Striche auf einer Linie mit regelmäßigen Lücken werden zu **einer** Linie mit echtem Linientyp zusammengefasst, auf dem Layer `STRICHLINIEN`:
  - gestrichelt wird `DASHED`
  - Strichpunkt (Mittellinien) wird `CENTER`
  - einzelne Linien mit großen Abständen bleiben unverändert
- **Strichstärken messen:** Die Breite jedes Strichs wird im Scan gemessen und als Strichstärke übernommen (in mm auf dem Papier); DXF zeigt sie mit Strichstärkenanzeige an.
- **Dicke Linien auf eigenem Layer:** Linien ab dem 1,7-Fachen der üblichen Stärke, zum Beispiel Wände, kommen auf `DICKE_LINIEN`. Der Faktor ist einstellbar, und die Funktion wirkt auch bei Vektor-PDFs. In der Anzeige erscheinen sie dicker.
- **Farben auf Layer trennen:** Farbige Pläne werden in Farbgruppen zerlegt und getrennt vektorisiert, auf Layer wie `FARBE_ROT`, `FARBE_BLAU` und `FARBE_SCHWARZ`, jeweils mit Originalfarbe:
  - die Anzahl der Farben bestimmt Traceify automatisch, man kann sie aber auch vorgeben
  - funktioniert auch bei Vektor-PDFs
  - Drehen, Zuschneiden, Begradigen, Radierer und Stift wirken auf das Farbbild mit, Strg+Z ebenso
- Neue Einstellungsgruppe „Linien und Farben“. Der KI-Assistent kennt die neuen Optionen.

## 0.5.0 – 04.11.2026
### Neu: Bearbeiten
- **Raster-Radierer und Stift** in der neuen Werkzeugleiste „Bearbeiten“:
  - Radierer (E) entfernt Flecken, Stempel oder Lochungen
  - Stift (P) zieht unterbrochene Linien nach
  - Pinselgröße einstellbar, Vorschau als Kreis am Mauszeiger
  - Strg+Z macht jeden Strich rückgängig; bereits erkannte Vektoren bleiben stehen, bis neu konvertiert wird
- **Bereiche** (R): Rechteck aufziehen und eine Behandlung wählen:
  - *ignorieren*
  - *CAD – Mittellinie*
  - *CNC – Umriss*
  - *nur Text*, ohne Linien

  Bereiche werden farbig angezeigt; Rechtsklick ändert oder entfernt sie. Sie wirken auch bei Vektor-PDFs (ignorieren, nur Text).
- **Knoten bearbeiten:** Bei genau einem markierten Objekt erscheinen ziehbare Knoten:
  - Linie, Polylinie: Endpunkte und Eckpunkte
  - Kreis: Mittelpunkt und Radius
  - Bogen: Mittelpunkt und Enden

  Verbundene Linien wandern mit; abschaltbar unter Bearbeiten → „Verbundene Knoten mitziehen“.
- **Vektor-Werkzeuge** (Menü Bearbeiten und Leiste):
  - **Ecke schließen** (C): zwei Linien bis zum Schnittpunkt verlängern oder kürzen
  - **Gerade ausrichten** (O): fast waagrechte und senkrechte Linien exakt ausrichten, Ecken bleiben verbunden
  - **Lücken schließen** (L): nahe Endpunkte zusammenführen, Abstand frei wählbar
  - **Zu Polylinie verbinden** (J) und **In Einzellinien auflösen** (X)

  Ohne Auswahl wirken Ausrichten und Lücken schließen auf alle sichtbaren Linien.
- API: Bereiche über `ConvertSettings.regions` (Liste von `Region` oder Dicts mit x, y, w, h, mode).

### Verbessert
- Werkzeugleisten stehen in zwei Zeilen. Eine ältere gespeicherte Fensteranordnung wird einmalig zurückgesetzt.

## 0.4.0 – 04.11.2026
### Neu
- **Vektor-PDFs direkt übernehmen:** PDFs aus CAD- und Grafikprogrammen werden erkannt. Statt sie zu rastern und neu zu vektorisieren, übernimmt Traceify die Daten millimetergenau:
  - Linien, Rechtecke, Kreise und Bögen; Bézierkurven, die einem Kreis entsprechen, werden echte Bögen
  - Texte mit Drehung
  - Linienfarben, Strichstärken und gestrichelte Linien
  - gedrehte Seiten werden richtig umgerechnet
  - optional auch gefüllte Flächen (Layer `FLAECHEN`)
  - funktioniert in der Oberfläche, im Stapel, in der Kommandozeile und in der API
- **Maßstab aus dem Plan:** Steht „M 1:100“, „Maßstab 1:50“ oder „SCALE 1:20“ auf der Zeichnung, exportiert Traceify in Originalgröße (Option unter „Maßstab“). Die Anzeige links zeigt den erkannten Maßstab.
- **DWG-Export** über den kostenlosen ODA File Converter, wenn er installiert ist; ohne ihn bietet Traceify den Download an. Auch im Stapel und in der Kommandozeile (`-f dwg`).
- **Update-Hinweis:** einmal täglich wird nach einer neuen Version auf GitHub gesucht. Ist eine da, erscheint ein Hinweis mit direktem Download; Versionen lassen sich überspringen, die Suche lässt sich abschalten.
- **Problem melden / Idee vorschlagen** (Menü Hilfe): öffnet ein vorbefülltes GitHub-Formular mit Version, Umgebung, Einstellungen und dem Ende des Protokolls.
- Protokolldatei `%APPDATA%\Traceify\traceify.log` (Menü Hilfe → Protokolldatei öffnen).
- Vorlagen für Fehlerberichte und Ideen auf GitHub.
- Objekte können eigene Farben, Linientypen und Strichstärken tragen. DXF, SVG und Anzeige berücksichtigen sie.

### Behoben
- **PDFs ließen sich in der Oberfläche nicht öffnen** („fz_pixmap_xres_set … int“): Die Auflösung ging als Kommazahl an PyMuPDF. Betroffen waren alle Versionen seit 0.1; Stapel, Kommandozeile und API funktionierten.
- Ältere oder neuere Einstellungsdateien (JSON) mit unbekannten Feldern werden toleriert.

## 0.3.2 – 04.11.2026
### Behoben
- Windows-Build: Der EXE-Selbsttest las je nach Zufall das Protokoll eines früheren Testlaufs aus dem Quellcode, dort ohne Tesseract. Deshalb scheiterten die Release-Builds zu v0.3.0 und v0.3.1, obwohl die EXE selbst in Ordnung war. Alte Protokolle werden jetzt vorher gelöscht, gelesen wird das neueste, und der Python-Test schreibt in einen eigenen Ordner.
- Release-Build: Die deutschen Anführungszeichen im Hinweistext brachen den PowerShell-Schritt ab. Den Release-Text erzeugt jetzt ein Python-Skript (`tools/release_notes.py`).
- Release-Build: Der Build akzeptiert auch die Tag-Schreibweise `v.0.3.2`. Mit „Run workflow“ und Angabe `release_tag` lassen sich die Dateien an ein bestehendes Release nachreichen.
- Inhaltlich gleich wie 0.3.1 (T-Icon, Tesseract neben der EXE).

## 0.3.1 – 04.11.2026
### Neu
- Neue Bildmarke: ein **T**. Oben die glatte CAD-Vektorlinie mit Ankerpunkten, der Stamm wird nach unten immer pixeliger, wie ein Scan. Das gilt für App-Icon, Taskleiste, Setup und EXE.

### Behoben
- Windows-Build: Der Release-Build zu v0.3.0 brach im EXE-Selbsttest ab, weil das eingebaute Tesseract nicht gefunden wurde. Tesseract liegt jetzt als eigener Ordner `tesseract\` direkt neben `Traceify.exe`, statt von PyInstaller eingepackt zu werden. Der Build prüft vorab, ob Programm und deutsche Sprachdaten im Paket sind.
- Der Selbsttest gibt jetzt den gefundenen Tesseract-Pfad aus. Das erleichtert die Fehlersuche.

## 0.3.0 – 03.11.2026
### Neuer Name, Logo, Open Source
- Das Projekt heißt jetzt **Traceify** (vorher RasterCAD). Paket `traceify`, Startdatei `Traceify_Start_Windows.bat`.
- Neues Logo und App-Icon: Eine Pixeltreppe geht in eine Vektorkurve über. Es steht in Fenster, Taskleiste, Setup und EXE.
- Lizenz: GNU AGPL v3 oder später. Die Lizenzen der Komponenten stehen in der README.
- Öffentliches Repo: github.com/StefanR1984/traceify

### Windows-EXE und Installer
- Traceify.exe (PyInstaller) mit **eingebautem Tesseract OCR** und deutschen und englischen Sprachdaten: Die Texterkennung funktioniert ohne Installation.
- Setup (Inno Setup):
  - Installation ohne Administratorrechte, wahlweise für alle Benutzer
  - Startmenü- und Desktop-Verknüpfung
  - „Öffnen mit → Traceify“ für Bilder und PDFs
  - Deinstallation
- Zusätzlich eine portable ZIP-Version.
- Beim ersten Start der installierten Version fragt Traceify einmal, ob die KI (Ollama mit Modell) automatisch eingerichtet werden soll.
- Einstellungen liegen jetzt im Benutzerordner (`%APPDATA%\Traceify\config.json`), damit sie auch bei Installation unter „Programme“ beschreibbar sind.

### Build-Pipeline (GitHub Actions, nur Windows)
- „Tests“: pyflakes, pytest (Kern, Exporte, PDF-Stapel, OCR, Oberfläche, KI-Panel gegen einen nachgebauten Ollama-Server) und Selbsttest bei jedem Push.
- „Windows-Build“ läuft manuell oder per Tag `v*`:
  - baut EXE, Setup und portable ZIP
  - prüft die fertige EXE per Selbsttest
  - erzeugt Prüfsummen
  - veröffentlicht beim Tag ein GitHub-Release mit den Notizen aus diesem Changelog

### Verbessert / behoben
- Neuer Startparameter `--selbsttest`: prüft ohne Oberfläche, ob alle Bausteine laufen.
- Eine einzelne Datei als Argument (Doppelklick oder „Öffnen mit“) öffnet die Oberfläche statt der Kommandozeile.
- OCR: Große Beschriftungen in kleinen Bildern wurden fälschlich verworfen.
- Über-Dialog mit Lizenz und Projektlink.

### Entfernt
- Startdateien für macOS und Linux. Traceify konzentriert sich auf Windows.

## 0.2.0 – 03.11.2026
### Neu: Vollautomatische Einrichtung
- Neue Startdateien `Traceify_Start_Windows.bat`, `Traceify_Start_Mac.command` und `Traceify_Start_Mac_Linux.sh`. Sie holen und installieren alles selbst:
  - Python 3.12 (falls fehlend)
  - Bibliotheken in `.venv`
  - Tesseract OCR
  - deutsche und englische Sprachdaten
  - Ollama mit KI-Modell (auf Nachfrage)
- Bibliotheken werden nach einem Update automatisch nachinstalliert; die Prüfung läuft über eine Prüfsumme der `requirements.txt`.
- Linux: Die fehlenden Qt-Systembibliotheken (u. a. `libxcb-cursor0`) werden automatisch installiert.
- Neuer Dialog „Werkzeuge → Komponenten prüfen / installieren“ zeigt den Status und installiert Fehlendes nach.
- `config.json` speichert den Tesseract-Pfad, den Sprachdaten-Ordner sowie Ollama-Adresse und -Modell.

### Neu: KI-Assistent über Ollama (lokal)
- KI-Analyse: erkennt die Art der Zeichnung, wählt passende Einstellungen und konvertiert direkt.
- KI-Textprüfung: liest OCR-Texte einzeln aus Bildausschnitten nach. Korrekturen werden als Liste angezeigt und einzeln übernommen.
- Ergebnisbewertung: Die KI vergleicht das Original mit der Vektorüberlagerung und gibt Verbesserungsvorschläge.
- Chat mit ausführbaren Aktionen:
  - Einstellungen ändern, konvertieren
  - Layer löschen oder ausblenden
  - kurze Objekte löschen, Text ersetzen
  - drehen, begradigen, exportieren
- Modellverwaltung im Panel: Liste der installierten und empfohlenen Modelle, Download mit Fortschritt, Ollama starten.
- Ollama wird beim Programmstart automatisch gestartet, wenn die KI aktiviert ist.
- Neues Menü „KI“ und Werkzeugleisten-Schaltflächen „✨ KI-Analyse“ und „KI-Chat“.
- API: `traceify.ai_settings()`; Kommandozeile: `--ki` und `--ki-modell`.

### Verbessert
- Die OCR nutzt den Tesseract-Pfad und die Sprachdaten aus der Einrichtung. Nicht installierte Sprachen werden automatisch ausgelassen statt einen Fehler zu erzeugen.
- Die Vorlagen liegen jetzt in `gui_presets.py`, damit GUI, API und KI dieselben verwenden.

### Entfernt
- Die alten Startdateien `start_windows.bat` und `start_mac_linux.sh` sind durch die neuen ersetzt.

## 0.1.0 – 03.11.2026
Erste lauffähige Version.

- Desktop-Oberfläche (PySide6):
  - Zeichenfläche mit Zoom, Verschieben, Rahmenauswahl und Layer-Panel
  - Einstellungsbereich mit Vorlagen
  - Fortschrittsanzeige; die Konvertierung läuft im Hintergrund
  - Drag & Drop, Seitenwahl für PDFs
- Raster-Vorverarbeitung:
  - Schwellwert automatisch (Otsu), fest oder adaptiv
  - Flecken entfernen, Löcher füllen, Glätten, Lücken schließen
  - Invertieren, Drehen, Zuschneiden, Schräglage begradigen
- Vektorisierung im CAD-Modus (Mittellinie): Linien, Bögen und Kreise mit Ecken- und Endpunkt-Fang; optional reine Polylinien
- Vektorisierung im CNC-Modus (Umriss): geschlossene, geglättete Konturen mit Kreiserkennung
- OCR mit Tesseract, waagrecht und senkrecht; Textbereiche werden vor der Vektorisierung entfernt
- Bearbeiten: Löschen, Alles auswählen, Layer auswählen, Rückgängig (auch für Raster-Änderungen)
- Maßstab automatisch aus DPI oder per Kalibrierung an einer bekannten Strecke
- Export:
  - DXF R12–R2018 mit Layern
  - SVG
  - G-Code für Fräse oder Laser/Plasma: G2/G3, Mehrfachzustellung, Wegoptimierung
- Stapelkonvertierung (Ordner, mehrseitige PDFs) als Dialog, Kommandozeile und Python-API
- Einstellungen als JSON speichern und laden
