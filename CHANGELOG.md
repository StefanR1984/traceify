# Changelog

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
