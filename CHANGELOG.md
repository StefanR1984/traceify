# Changelog

## 0.16.0 – 09.11.2026
### Neu: Hilfe direkt am Schalter
- **Tooltips überall:** Bleibt die Maus kurz auf einem Schalter, Feld oder dessen Beschriftung stehen, erscheint eine kurze Erklärung, was er bewirkt. Das gilt für alle Einstellungen, den KI-Bereich, den Dialog *KI-Server* und die Menü- und Leistenbefehle. Die Texte stehen gesammelt in `gui/tips.py`.

### Schraffur-Flächen vollständiger
- Deutlich mehr Schraffurlinien werden im DXF/DWG zu Schraffur-Flächen (HATCH). Gemessen an den echten Bauplan-Scans bleiben nur noch so viele Einzellinien übrig: 14 % statt 41 %, 14 % statt 64 %, 19 % statt 34 %, 44 % statt 57 %. Beim handschraffierten Kellerplan sind es 46 % statt 72 %. Die Musterlinien liegen weiterhin zu 96–99 % auf der Tinte des Scans.
- **Zerrissene Schraffurlinien:** Stücke derselben Linie zählen als eine Rasterlinie, statt den Abstand zu verfälschen.
- **Abstand darf leicht wandern** (verzerrte Scans, Handzeichnung): Das Raster wird per Ausgleichsgerade angepasst.
- **Wände mit versetztem Raster**, die an Ecken und T-Stößen aneinanderstoßen, werden getrennt erkannt, statt die ganze Gruppe zu verwerfen.
- Übrig gebliebene Linien, die ins Raster einer benachbarten Fläche passen, werden dieser zugeordnet.
- **Keine Fehltreffer mehr in schrägen Gebäudeteilen:** Liegt ein Gebäudeflügel schräg, galten seine Wände, Regale und Treppen bisher als Schraffur. Beim A1-Testplan waren das 157 Linien, jetzt sind es 5. Wenige lange Parallelen ergeben keine Schraffur-Fläche mehr.

### Texterkennung: Wörterbuch für Planbegriffe
- Verlesene Wörter werden mit typischen Planbegriffen (Raumnamen, Bauteile, Abkürzungen wie WFL/NFL/BR) abgeglichen. Dazu kommen Wörter, die im selben Plan sicher gelesen wurden. Beispiele: „Schiafen“ → „Schlafen“, „Kuche“ → „Küche“, „Dele“ → „Diele“, „Bakon“ → „Balkon“, „Deckenhohe“ → „Deckenhöhe“, „Pee 05 Siehtweh“ → „Pos 05 Sichtwahl“.
- Der Abgleich kennt typische OCR-Verwechslungen (i/l/!, v/w, rn/m, ii/ü, Umlaute) und korrigiert nur bei einem eindeutigen Treffer. Sicher gelesene Texte werden nur bei reinen Formverwechslungen und fehlenden Umlauten angepasst (aus „HALLO“ wird nie „HALLE“). Gebeugte Formen („Garagen“, „Details“) und normale Wörter wie „Kellner“, „Stuhl“, „Trockenbau“ oder Namen bleiben unverändert, „ss“ wird nicht zu „ß“. **Zahlen werden nie verändert.**
- Unsicher gelesene schräge Beschriftungen werden übernommen, wenn ihre Wörter eindeutig Planbegriffe sind. Auf dem A1-Plan sind so „Pos 06.1 Arbeitsplatz“, „Pos 05 Sichtwahl“, „Freiwahl“ und „OFFIZIN“ dazugekommen, auf dem Kellerplan „Heizraum“ und „Keller“.
- Einstellung „Wörterbuch für Planbegriffe“ (Standard an), für KI-Regeln und Chat `woerterbuch`.

### Aufgeräumter
- **Fransen entfernen** (neu, Standard bis 1,5 mm, einstellbar oder „aus“): Kurze Stummel, die an rauen Wandkanten oder überstehender Schraffur seitlich abstehen, werden entfernt. Verlängerungen, Ecken und freistehende Striche bleiben. Beim Kellerplan sind das 177 Objekte und 131 offene Enden weniger, bei gleicher Abdeckung. Für KI-Regeln und Chat `fransen_mm`.

## 0.15.1 – 05.11.2026
### Behoben
- **Texterkennung brach unter Windows mit „Error opening data file …\\tessdata"/deu.traineddata“ ab** („Konvertierung fehlgeschlagen“, Tesseract konnte keine Sprache laden). Ursache: Der Sprachdaten-Ordner wurde als `--tessdata-dir "…"` übergeben; pytesseract wertet die Anführungszeichen unter Windows nicht aus, Tesseract bekam sie als Teil des Pfads. Der Ordner wird jetzt über `TESSDATA_PREFIX` gesetzt – das funktioniert auch bei Leerzeichen im Pfad.
- **Viele kurz aufblitzende cmd-Fenster beim Konvertieren:** Alle Tesseract-Aufrufe (auch die Sprachliste) starten jetzt ohne Konsolenfenster.
- Der EXE-Selbsttest macht jetzt eine echte Texterkennung („HALLO 123“) und schlägt fehl, wenn die Sprachdaten nicht lesbar sind. So fällt ein solcher Fehler schon im Build auf.

## 0.15.0 – 04.11.2026
### Neu: Schraffur als Fläche (DXF-HATCH)
- Regelmäßige Schraffuren (Layer SCHRAFFUR) kommen im DXF und DWG jetzt als **eine Schraffur-Fläche** mit Umriss, Winkel und Linienabstand statt als viele Einzellinien. Im CAD lässt sich die Schraffur so als Ganzes auswählen, umfärben, im Abstand ändern oder löschen.
- Das Muster liegt deckungsgleich auf den erkannten Linien (Abweichung unter 0,01 mm im Test). Der Umriss folgt den Linienenden, auch bei L-förmigen Wänden; Löcher werden mitgenommen.
- Unregelmäßige Gruppen (Abstände passen nicht zu einem festen Raster) bleiben Einzellinien. In der Oberfläche, im SVG und im G-Code bleiben die Linien wie bisher.
- Einstellung „Schraffur als Fläche exportieren (DXF-HATCH)“, Standard an; bei DXF R12 immer Einzellinien. KI-Regeln und Chat kennen `schraffur_flaeche`.

### Genauer
- **Gerade ausrichten (O) und die automatische Ausrichtung nehmen jetzt auch Polylinien mit.** Segmente mit echten Ecken werden exakt waagrecht/senkrecht (an der Schräglage des Scans), verbundene Ecken bleiben verbunden. Segmente in Rundungen (viele kleine Knicke) bleiben unberührt, damit Kurven nicht zu Treppen werden.
- **Maßzahlen nachlesen:** Zahlen, bei denen ein Komma fehlen kann („24 85“, „251“) oder Komma und Punkt verwechselt sein können, werden gezielt noch einmal gelesen – aus dem Graustufenbild, in dem feine Kommas noch erhalten sind, und nur mit Ziffern, Komma und Punkt. Übernommen wird das nur, wenn die Ziffern exakt gleich bleiben; es kommt also höchstens ein Trennzeichen dazu. Abschaltbar unter „Maßzahlen nachlesen“ (`zahlen_nachlesen`).
- **Einheiten bleiben stehen:** „qm“, „m²“, „cm“ usw. direkt hinter einer Zahl fielen bisher durch den Zeichensalat-Filter.
- **Zerrissene Zeilen:** Teile derselben Zeile, die Tesseract getrennt geliefert hat („NFL“ und „13,12“), werden wieder zu einem Text zusammengefügt.
- Auf einem nachgebauten Testplan (12 Beschriftungen) liest Traceify jetzt bei 100 dpi 7 statt 3, bei 150 dpi 10 statt 8 und bei 300 dpi 11 statt 9 Beschriftungen vollständig richtig. Auf den echten Prüfstand-Scans steht die Messung noch aus.

## 0.14.0 – 04.11.2026
### vLLM
- **Verbindung testen** im Dialog *KI-Server*: zeigt sofort Serverversion (z. B. „vLLM 0.11.0“) und die angebotenen Modelle oder den Fehler.
- **Kommandozeile:** `--ki-server vllm|ollama`, `--ki-url`, `--ki-schluessel` (zusammen mit `--ki` / `--ki-regeln` / `--ki-modell`) gelten nur für diesen Lauf und ändern die gespeicherten Einstellungen nicht. In der Python-API heißt das `batch_convert(..., ai_server={...})`.

### Genauer
- **Zahlen mit Dezimalpunkt:** Die Texterkennung entfleckt schwächer als die Linienerkennung (neue Einstellung `ocr.despeckle`, Standard 3 px²). So bleiben Punkte und Kommas in „143.50 qm“ erhalten. Auf dem A1-Testplan stimmen jetzt 47 statt 41 Wörter mit dem Vergleichsprogramm überein.
- **Auch kurze Linien werden ausgerichtet:** Stücke, deren Enden höchstens 1,5 px neben der Achse liegen, werden beim Ausrichten mitgenommen, auch wenn ihr Winkel im Scan größer wirkt. Der Anteil exakt waagrechter/senkrechter Linien steigt bei den Testplänen z. B. von 39 auf 43 %, von 41 auf 44 % und von 46 auf 48 % (Vergleichsprogramm: 49 bzw. 51 %).
- **Kleine Lücken schließen** (neu, Standard 0,8 mm, einstellbar oder „aus“): Linienenden, die knapp vor einem anderen Objekt enden, werden bis dorthin verlängert. Ecken und T-Stöße sind damit geschlossen, Türöffnungen bleiben offen. Offene Enden bei den Testplänen: 8–28 % weniger.
- KI-Stapelregeln und Chat kennen `luecken_mm`.

### Behoben
- **Seltener Absturz beim Beenden** („QThread: Destroyed while thread is still running“): Hintergrund-Threads (KI-Verbindung, Modellliste, Stapel, Komponenten, Updates) wurden manchmal schon freigegeben, während sie noch liefen. Jetzt wird ihr Ende abgewartet, auch beim Schließen des Fensters.


## 0.13.0 – 04.11.2026
### Neu: vLLM und andere OpenAI-kompatible KI-Server
- Statt Ollama kann die KI jetzt auch über **vLLM** laufen, etwa auf einem eigenen GPU-Server im Netz. Das geht ebenso mit jedem anderen Server, der die OpenAI-Schnittstelle anbietet (LM Studio, llama.cpp-Server, LocalAI).
- Umschalten im KI-Panel über **⚙ → KI-Server**: Art, Adresse (z. B. `http://gpu-server:8000/v1`), optionaler API-Schlüssel und Zeitlimit.
- Alle KI-Funktionen laufen mit beiden Servern gleich: Bild analysieren, Texte prüfen, unerkannte Schrift lesen, Chat mit Aufträgen und KI-Stapel (auch über Kommandozeile und Python-API).
- Bilder werden als `image_url` mitgeschickt, Antwortvorgaben als `response_format` (JSON-Schema). Lehnt der Server das Schema ab, fragt Traceify automatisch mit einfacherer Vorgabe nach.
- Die Modellliste zeigt die Modelle, die der Server anbietet. Das gewählte Modell wird je Server getrennt gemerkt. Fehlt einem Modell die Bildfähigkeit, gibt es einen Hinweis. „Laden“ entfällt, weil vLLM sein Modell beim Start festlegt.
- Ollama wird beim Programmstart nur noch automatisch gestartet, wenn Ollama als KI-Server gewählt ist.

### Behoben
- Workflow *Integration (echt)*: Der Ollama-Installer kehrte auf dem Runner nie zurück (er startet am Ende die Ollama-App). Jetzt wird das portable Ollama-ZIP genutzt, und jeder Schritt hat ein eigenes Zeitlimit.


## 0.12.0 – 04.11.2026
### Neu
- **Schräge Texte:** Beschriftungen in beliebigem Winkel (z. B. 45° an schrägen Wänden) werden gefunden, geradegerückt und gelesen. Traceify sucht dazu schriftähnliche Zeichengruppen, die die normale Erkennung übrig gelassen hat, bestimmt ihre Lage und liest alle in einem Tesseract-Durchgang, jeweils in beiden Leserichtungen. Strichlinien und Fliesenraster werden dabei ausgeschlossen. Abschaltbar unter „Schräge Texte nachlesen“. Auf dem A1-Testplan sind jetzt 41 statt 33 Wörter gleich wie beim Vergleichsprogramm, z. B. „Dusche“, „BR 900“ und „Pos 01“.
- **Unerkannte Schrift mit KI lesen** (KI-Panel und Menü KI): Traceify sucht Stellen, die wie Schrift aussehen, aber von der OCR nicht gelesen wurden (typisch Handschrift wie „Privat Keller“), und lässt sie vom Bildmodell lesen, auch auf dem Kopf. Die Vorschläge erscheinen in einer Liste. Übernommene Texte ersetzen die Linien der Buchstaben, alles mit Strg+Z rückgängig.
- **Erkannte Texte mit KI prüfen** schneidet jetzt auch gedrehte und schräge Texte richtig aus.
- **Schräglage ausgleichen:** Traceify erkennt, wie schief der Scan liegt (bei den Testplänen 0,5–1,3°), richtet fast waagrechte und senkrechte Linien exakt an diesen Achsen aus und dreht die Schräglage beim Export (DXF, DWG, SVG, G-Code) heraus. Auf dem Scan bleiben die Vektoren deckungsgleich, Ecken bleiben verbunden. Ortho beim Zeichnen und „Gerade ausrichten“ (O) folgen der Schräglage. Anteil exakt waagrechter/senkrechter Linien bei den Testplänen: z. B. 66 % statt 16 % und 39 % statt 17 %. Abschaltbar unter „Linien gerade ausrichten“.
- **Schraffur-Layer:** Schräge Schraffuren (parallele Linien in regelmäßigem Abstand, z. B. in Wänden) kommen auf den Layer SCHRAFFUR und lassen sich im CAD mit einem Klick ausblenden oder löschen. Treppenstufen, Wandkanten und Handschrift bleiben unberührt.
- **Wände als Umriss** (Option): Dicke Linien werden als geschlossene Umrisse (Doppellinie) auf den Layer WAENDE gelegt statt als Mittellinie mit Strichstärke.
- **Dehnen** funktioniert jetzt auch bei offenen Polylinien (in Richtung des End-Segments) und bei Bögen (entlang ihres Kreises).
- **Prüfstand:** neue Kennzahlen „Ortho“ (Anteil exakt waagrechter/senkrechter Linien im Export) und „Offene Enden“.
- **Test mit echtem Ollama und ODA File Converter:** neuer Workflow *Integration (echt)*. Er wird nur manuell gestartet, installiert beides auf einem Windows-Runner und prüft Einstellungsvorschlag, Chat, KI-Lesen von Handschrift und den DWG-Export hin und zurück.

### Verbessert
- **Weniger unnötige Bögen:** Passen zwei Linien mit Ecke mindestens so gut wie ein Bogen, wird die Ecke genommen. Vom Skelett abgerundete Rechteckecken werden so wieder echte Ecken. Bei den Testplänen gibt es 55–60 % weniger Bögen (z. B. 413 statt 904) bei gleicher Abdeckung.
- Die KI-Regeln für den Stapel und der Chat kennen die neuen Einstellungen (`waende_umriss`, `schraffur_layer`, `schraege_texte`, `gerade_ausrichten`).


## 0.11.0 – 04.11.2026
### Getestet mit echten Scans
Grundlage dieser Version ist ein Prüfstand mit 9 echten Bauplan-Scans (96–150 dpi, sauber bis stark verrauscht, teils handschriftlich, teils gedreht) und ein Vergleich mit einem kommerziellen Vektorisierungsprogramm.

- **Saubere, durchgehende Kanten:** Eine gerade Linie zerfiel bisher an jeder Abzweigung, etwa an jeder Schraffurlinie einer Wand, in viele kurze Stücke. Jetzt werden kollineare Stücke über Abzweigungen hinweg zu **einer Linie** verbunden, solange alle Stützpunkte innerhalb der Toleranz liegen. Ergebnis bei den Testplänen: **47–80 % weniger Objekte** bei gleicher Abdeckung und deutlich weniger Splitter unter 1 mm.
- **Keine Lücken an dichten Abzweigungen:** Kurze Verbindungsstücke zwischen zwei nahen Abzweigungen wurden als „zu kurz“ verworfen, sodass Kanten dort unterbrochen waren. Sie bleiben jetzt erhalten.
- **Keine Mini-Bögen aus Rauschen:** Flache, kurze Ausbeulungen (unter 60° und höchstens doppelte Toleranz Abweichung) werden als gerade Linie ausgegeben statt als Bogen.
- **Gescannte PDFs in Originalauflösung:** Die PDF-Render-DPI steht jetzt standardmäßig auf **automatisch**. Besteht eine Seite aus einem Scan-Bild, liest Traceify sie in dessen Auflösung, statt sie auf 300 dpi hochzurechnen. Das ist etwa doppelt so schnell und liefert weniger Kleinteile. Vektor-PDFs und gemischte Seiten werden weiter mit 300 dpi gelesen; eine feste DPI kann wie bisher eingestellt werden. In der Python-API bedeutet `pdf_dpi=0` dasselbe (neuer Standard).
- **Bessere Texterkennung:**
  - Texte werden in **allen vier Richtungen** gesucht, auch auf dem Kopf stehend (180°) und von oben nach unten (270°). Liefern zwei Richtungen an derselben Stelle etwas, gewinnt die sicherere Erkennung. Abschaltbar über `ocr.upside_down`.
  - **Linien, Wände und Schraffuren** werden vor der Erkennung ausgeblendet; handschriftliche Wörter bleiben dabei erhalten.
  - **Zeichensalat-Filter:** Treffer wie „Mm“, „om>Z“ oder „%y“ aus Schraffuren werden verworfen, kurze Kürzel (WC, KG, BR) nur bei hoher Sicherheit übernommen.
  - **Grobe Scans** (unter ca. 130 dpi) werden für die Texterkennung intern auf etwa 300 dpi vergrößert. Die Linien bleiben in Originalauflösung.
  - Ergebnis auf einem A1-Plan: 33 statt 19 Wörter wie beim Vergleichsprogramm, 8 statt 51 Mülltexte.
- **Prüfstand** `tools/pruefstand.py`: misst Zeit, Objekte, Splitter, Abdeckung, Genauigkeit und Texte für einen ganzen Ordner. Er liest DXF-Dateien anderer Programme ein (neu: `traceify.core.dxf_import`), richtet sie automatisch auf den Scan aus und bewertet sie mit denselben Kennzahlen.

### Behoben
- **Absturz** beim Konvertieren mancher Scans („'<' not supported between instances of 'Line' and 'Line'“): In der Strichlinien-Erkennung wurden bei deckungsgleichen Strichen Linienobjekte verglichen.


## 0.10.0 – 04.11.2026
### Neu: Echter Updater
- **Jetzt installieren** statt nur Hinweis: Traceify lädt das neue Setup selbst herunter (mit Fortschrittsanzeige und Abbrechen), beendet sich, installiert das Update still und startet danach von selbst neu. Einstellungen bleiben erhalten.
- **Geprüfter Download:** nur über https, Dateigröße und SHA-256-Prüfsumme werden mit den Angaben von GitHub verglichen, außerdem muss es ein Windows-Programm sein. Beschädigte oder abgebrochene Downloads werden verworfen.
- Ein bereits geladenes und geprüftes Setup wird beim nächsten Versuch wiederverwendet.
- Schlägt etwas fehl, bietet Traceify den Download im Browser an.
- Das Setup wartet, bis Traceify wirklich beendet ist, damit keine Dateien gesperrt sind. Es behält die bisherige Installationsart (nur für mich / für alle Benutzer) bei; bei „für alle Benutzer“ fragt Windows nach Administratorrechten.
- Portable ZIP und Start aus dem Quellcode: weiterhin Hinweis mit Download-Link.
- Protokoll des Update-Setups: `%TEMP%\Traceify-Update\update-setup.log`.
- Hinweis: Das automatische Update funktioniert ab Version 0.10.0. Von 0.9.0 aus bitte noch einmal von Hand aktualisieren.


## 0.9.0 – 04.11.2026
### Neu: Zeichnen, Fangpunkte, Stutzen, Dehnen
- **Zeichenwerkzeuge** in einer neuen senkrechten Leiste links und im Menü „Zeichnen“:
  - **Linie** (N): Punkt für Punkt, die nächste Linie beginnt am Ende der letzten; Rechtsklick oder Esc beendet.
  - **Polylinie** (Umschalt+N): Rechtsklick oder Enter beendet, ein Klick auf den Startpunkt schließt sie.
  - **Rechteck** (Umschalt+K), **Kreis** (K) und **Bogen aus 3 Punkten** (A).
  - Gummiband-Vorschau; **Länge und Winkel** (beim Kreis Radius und Ø, beim Rechteck Breite × Höhe) stehen live in der Statuszeile.
  - **Maße per Tastatur:** Zahl in mm eintippen (Komma oder Punkt) und Enter drücken. Bei Linien wird so die Länge in Mausrichtung gesetzt, beim Kreis der Radius, beim Rechteck „Breite;Höhe“.
  - Neue Objekte kommen auf einen **wählbaren Layer** (Standard GEZEICHNET, Eintippen legt einen neuen an). Sie **bleiben beim Neu-Konvertieren erhalten**.
  - Zeichnen geht auch **ohne vorheriges Konvertieren**, also direkt auf dem Scan.
  - Esc bricht nur die laufende Form ab; das zweite Esc führt zurück zur Auswahl.
- **Fangpunkte** (F3): Endpunkt □, Mittelpunkt △, Zentrum ○, Schnittpunkt ✕, Lotfußpunkt ⊾ und nächster Punkt, jeweils mit Symbol und Beschriftung. Die Fangarten sind einzeln abschaltbar (Zeichnen → Fangarten). Ein räumlicher Index hält den Fang auch bei sehr großen Plänen flüssig.
- **Ortho** (F7): nur waagrecht oder senkrecht zeichnen. **Umschalt** halten kehrt die Einstellung vorübergehend um.
- **Stutzen** (T): Teilstück anklicken, es wird bis zu den nächsten Schnittpunkten entfernt. Das wegfallende Stück ist beim Überfahren rot markiert. Funktioniert bei Linien, Polylinien, Bögen und Kreisen (ein Kreis wird zum Bogen); ohne Schnittpunkt verschwindet das ganze Objekt.
- **Dehnen** (D): Linie nahe dem Ende anklicken, das verlängert werden soll. Die Linie wächst bis zur nächsten Linie, Polylinie, zum nächsten Kreis oder Bogen.
- Alles lässt sich mit Strg+Z rückgängig machen.

### Schneller und genauer erkennen
- **Großformate deutlich schneller:** Ein A0-Plan mit 400 dpi braucht auf 2 Kernen jetzt etwa 21 s statt 31 s (mit OCR).
  - Die Skelettierung läuft in überlappenden Kacheln parallel und liefert dabei pixelgleiche Ergebnisse.
  - Die OCR liest waagrechten und senkrechten Text gleichzeitig.
  - Die Strichlinien-Suche arbeitet mit einem Raster statt mit „jede gegen jede“.
- **Saubere Wandenden:** Dicke Linien bekommen an den Enden keine kurzen Fransen-Bögen mehr, und die Mittellinie reicht bis zur Stirnseite.
- **Robustere Strichlinien:** Einzelne leicht schiefe Striche, etwa durch einen Scanfehler, verbiegen die zusammengefasste Linie nicht mehr. Lückenlänge und Strichlänge passen sich der jeweiligen Linie an.


## 0.8.0 – 04.11.2026
### Neu: Qualität, Symbole, KI-Stapel
- **Qualitätsampel:** Nach jedem Konvertieren werden die Vektoren mit dem Scan verglichen:
  - **Abdeckung**: Wie viel Tinte ist von Vektoren erfasst?
  - **Genauigkeit**: Wie viele Vektoren liegen auf Tinte?
  - Ampel gut / prüfen / Probleme in der Statusleiste; gemessene Strichstärken, Umrissmodus und ignorierte Bereiche werden dabei berücksichtigt.
  - **Problemstellen** werden markiert (Q oder Klick auf die Ampel): rot heißt „fehlt“, violett „überflüssig“. Mit **F8** geht es von Stelle zu Stelle.
  - Nach Änderungen zeigt die Ampel „veraltet“; Werkzeuge → Qualität prüfen aktualisiert sie.
- **Symbole als CAD-Blöcke** (Werkzeug „Symbol“, Taste Y): Rechteck um ein Beispielsymbol ziehen, Name vergeben (auf Wunsch mit KI-Vorschlag) und die Ähnlichkeitsschwelle wählen.
  - Traceify findet alle gleichen Symbole, auch um 90°, 180° oder 270° gedreht, und ersetzt die Einzellinien durch **einen Block-Verweis**.
  - DXF enthält echte BLOCK- und INSERT-Einträge mit Drehung; SVG und G-Code lösen die Symbole auf.
  - Die Stückzahlen erscheinen links („Steckdose: 12“). Symbole lassen sich als Ganzes markieren, verschieben und löschen.
  - **Symbol-Bibliothek**: Symbole werden gespeichert (`%APPDATA%\Traceify\Symbole`) und können mit „Symbol-Bibliothek anwenden“ oder automatisch beim Konvertieren in neuen Plänen eingesetzt werden. Die Option dafür steht unter „Linien, Farben, Symbole“.
- **KI-Stapel mit Regeln in Klartext:** Im Stapel-Dialog (oder mit `--ki-regeln` in der Kommandozeile) beschreibst du, was mit welcher Art von Zeichnung passieren soll. Die KI sieht sich jede Datei an und setzt Einstellungen und Formate oder überspringt die Datei. Das Protokoll zeigt jede Entscheidung.
- „Ergebnis bewerten“ (KI) bekommt jetzt auch die Problemstellen der Qualitätsampel mitgeschickt.

### Behoben
- Radiuskorrektur per KI oder Text: „außen“ mit ß und andere Umlaut-Schreibweisen werden erkannt.

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
