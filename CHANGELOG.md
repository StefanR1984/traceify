# Changelog

## 0.38.10 – 18.11.2026
### OCR
- **Wörterbuch:** Sicher gelesene Bruchstücke bekannter Begriffe („ammer“, „kerpool“) werden nicht mehr als Wort des Plans gelernt – sie verhinderten, dass zerschnittene Wörter („Putz ammer“) wieder zu „Putzkammer“ zusammengesetzt werden. Ein Linienrest als Apostroph am Wortstück („Putz’ ammer“) stört nicht mehr.
- **Untersucht und verworfen:** Türschwenk-Bögen vor der Texterkennung aus dem Bild löschen – an den Raumstempeln besser, im ganzen Plan aber weniger richtige Texte.

## 0.38.9 – 18.11.2026
### Maßzahlen
- **Türmaße:** Hat die Texterkennung zwei Maße als eine Zeile gelesen („25 1.01“), ersetzte die gezielt gelesene Lückenzahl „25“ die ganze Zeile – die Türbreite „1.01“ ging verloren. Jetzt bleibt der Rest stehen.
- Türmaß-Paar „101“ über „2.75⁵“ wird auch dann „1.01“, wenn die Texterkennung die Höhe der oberen Zahl zu klein schätzt.
- **Gemessen:** echte Allplan-Plots Türmaße (Breite und Höhe richtig) PLAN2_EG 71 → 80 %, alle 7 Pläne mit Türen 75 → 77 %; alle 17 Plots Texte 1977 → 1983. Simulation und Scans praktisch unverändert (±1).

## 0.38.8 – 18.11.2026
### OCR
- **Raumstempel:** Das Wörterbuch kennt jetzt weitere Raumnamen (Teeküche, Druckerpool, Putzkammer, Putzraum, Garderobe, Besprechung, Vorstand, Kopierer, Drucker) und typische Verleser von „Büro“ („Bure“, „Biro“, „Buro-“). „l“ und „t“ gelten als Formverwechslung („Beralung“ → „Beratung“).
- **Vom Türbogen zerschnittene Wörter** („2.13 Druck pool“, „0.28 Putz mmer“) werden wieder zusammengesetzt, wenn genau ein bekannter Begriff mit dem einen Stück beginnt, mit dem anderen endet und dazwischen 1–3 Buchstaben fehlen. Zahlen bleiben unverändert.
- **Gemessen:** echte Allplan-Plots PLAN2 Texte mit Buchstaben 86 → 95 von 121; alle 17 Plots Texte 1968 → 1977, falsche Wörter 295 → 284. Simulation +3 Texte, falsche Wörter −2; Scans unverändert.
### KI
- **Gemma 4 über vLLM** gilt jetzt als bildfähig (vorher nur Gemma 3).

## 0.38.7 – 18.11.2026
### OCR
- **Raumstempel mit grauer Linie:** In Plots kreuzen grau gedruckte Linien (Türschwenk, Hilfslinien) oft Raumstempel wie „0.27 Druckerpool“ oder „2.16 Büro“. Die Linie hing an den Buchstaben, beide wurden vor der Texterkennung als Linie ausgeblendet. Jetzt zählt für die Schrift nur Tinte mit dunklem Kern in der Nähe – nur in Plots mit tiefschwarzer Schrift, in Scans ist Schrift oft grau.
- **Gemessen:** echte Allplan-Plots PLAN2 Texte mit Buchstaben 80 → 86 von 121, falsche Zahlen 176 → 170; alle 17 Plots falsche Wörter 316 → 295, Wörter +5, je Text −3. Simulation und Scans unverändert.

## 0.38.6 – 18.11.2026
### Maßzahlen
- **Kleine Maße neben dem Sternpaar** („✳✳ 12⁵“) werden auch gelesen, wenn sie bis 1,5 Ziffernhöhen neben dem Paar stehen (vorher 0,8); die Längenprobe gegen den Sternabstand bleibt.
- **Gemessen:** echte Allplan-Plots PLAN2 je Maß „12⁵“ 59 → 63 %, falsche Zahlen 177 → 176; je Text PLAN2 +15 (OG1 +7, OG2 +4, EG +2, OG3 +2), PLAN1 −2; Simulation und Scans unverändert.

## 0.38.5 – 18.11.2026
### Maßzahlen
- **Hochziffer ⁵ hinter Metermaßen** („2.83⁵“) ging oft verloren oder wurde „2.83¹“, „2.83°“, „283°“: Die Wortbox der Texterkennung reicht bis zur Oberkante der Hochziffer, und eng stehende Ziffern („83“) hängen im Scan zusammen. Beides wird jetzt berücksichtigt; hinter einem Maß „d.dd“ ist eine gefundene Hochziffer immer ⁵, ganze Zahlen nur ohne Ring („30°“ bleibt ein Winkel). Schmale Strichreste gelten nicht mehr als Hochziffer.
- Die gezielte Lesung in der Maßlinienlücke übernimmt eine von der Texterkennung gefundene Hochziffer, statt sie zu überschreiben.
- **Zweistellige Hochziffern** („14⁷⁵“) werden gelesen, wenn beide kleinen Ziffern im Scan erkennbar sind.
- **Prüfstand:** Allplan legt „14⁷⁵“ Ziffer für Ziffer ab; der Wahrheits-Prüfstand setzt solche Hochziffern jetzt vollständig zusammen (vorher „14⁷“ plus ein loses „5“).
- **Gemessen:** echte Allplan-Plots PLAN2 je Maß: „2.83⁵“ 86 → 93 %, „12⁵“ 57 → 59 %, falsche Zahlen 221 → 177; je Text +42 (EG +9, OG1 +20, OG2 +14), falsche Wörter 337 → 318. Simulation +9 Texte, Scans unverändert.

## 0.38.4 – 18.11.2026
### Maßzahlen
- **Kleine Maßsterne ohne Maßlinie** („✳30✳“) wurden oft nicht als Maßbegrenzung erkannt: Ihre Arme ragen kaum über den Schrägstrich hinaus. Ein zweiter, genauerer Blick findet sie jetzt – aber nur in der Größe der sicher erkannten Sterne desselben Plans, damit Ziffern und Ecken größerer, fetter Schrift nicht als Stern gelten.
- **Kleine Maße neben dem Sternpaar:** Passt die Zahl nicht zwischen die Sterne, stellt Allplan sie daneben über die verlängerte Maßlinie oder über das Paar – auch bei Abständen bis 2,5 Ziffernhöhen. Beides wird jetzt gelesen und gegen den Sternabstand geprüft; dort auch einstellige Maße („5“).
- Ziffern dürfen bis knapp an den Stern reichen („✳28✳“).
- Hochziffern an Maßzahlen sind immer ⁵ (halbe Zentimeter); klein gedruckt las die Erkennung sie teils als ⁹, ², ⁶ oder ¹.
- **Gemessen:** echte Allplan-Plots PLAN2 je Maß: cm-Maße „30“ 38 → 51 %, „12⁵“ 47 → 52 %, „2.83⁵“ 82 → 86 %, falsche Zahlen 241 → 221; je Text EG 415 → 448, OG1 335 → 366, OG2 305 → 325, OG3 221 → 252, falsche Wörter überall weniger. PLAN1/PLAN3, Simulation und Scans praktisch unverändert.

## 0.38.3 – 18.11.2026
### Maßzahlen
- **Kleine cm-Maße zwischen zwei Maßsternen** („✳30✳“, „✳24✳“) wurden nicht gezielt gelesen, wenn die Schrift nur 1 mm hoch ist (Allplan-Standard für cm-Maße): die Mindesthöhe lag bei 1,2 mm. Jetzt 0,8 mm.
- **Gemessen:** echte Allplan-Plots PLAN2 je Text EG 404 → 415, OG1 332 → 335, OG2 297 → 305, OG3 211 → 221, Dach 79 → 81, falsche Wörter gleich oder weniger; Simulation PLAN2 je Text +16 bis +45 (falsche Wörter +11 bis +17); Geometrie und Scans unverändert.

## 0.38.2 – 18.11.2026
### Fehlerbehebung
- **Absturz „cannot unpack non-iterable numpy.int32 object“** beim Umwandeln mit „Schräglage korrigieren“ (z. B. Strich-Scan-PDF): OpenCV 5 liefert erkannte Linien in anderer Form; die Schräglage-Schätzung liest jetzt beide Formen.
- **Schräge Treppen wurden Schraffur:** In schräg stehenden Gebäudeteilen sahen Treppenstufen (parallel, gleicher Abstand) wie Schraffur aus und landeten auf SCHRAFFUR. Stoßen die Striche rechtwinklig auf Wangenlinien, die nach beiden Seiten weiterlaufen (auch wenn sie im Scan an jeder Stufe zerfallen), bleiben sie normale Linien. Schraffur trifft Wandkanten schräg; Kreuzschraffur (Striche treffen sich an den Enden) bleibt Schraffur.

## 0.38.1 – 17.11.2026
### Vektorisierung
- **Wellen-Bögen:** Wo Schraffurstriche, Ziffern oder Nachbarlinien an eine dicke Linie stoßen, bekam das Skelett Wellen – daraus wurden Ketten kleiner Bögen (Radius ~1 mm) entlang einer geraden Linie. Ein kleiner Bogen (≤ 4 mm), dessen Sehne auf Tinte liegt und hinter dem die Tinte geradeaus weiterläuft, wird jetzt eine gerade Linie (`cad.flatten_arcs`); echte Bögen (Türschwenk, Rundung) haben eine leere Sehne und bleiben.
- **Gemessen:** echte Allplan-Plots Bögen PLAN2_EG 222 → 102 (Original 94), PLAN1_UG 120 → 53, PLAN3_UG1 271 → 189; echte Bögen bleiben erhalten (PLAN2_EG 58 von 58), Genauigkeit gleich. Scans 30–70 % weniger Bögen, Abdeckung gleich. Simulation Trefferquote −0,1 bis −1,1 Punkte (zappelnde Bögen berührten Nachbarlinien).

## 0.38.0 – 17.11.2026
### OCR
- **Fette Schrift:** Schablonen- und Plotterschrift mit sehr dickem Strich (Strich ≥ 22 % der Höhe, Median über alle buchstabengroßen Teile) verläuft im Scan zu Klecksen; Tesseract las dort nur Bruchstücke („ODUKTION“). Solche Pläne werden zusätzlich mit ausgedünnter Schrift gelesen (Strich auf ~10 % der Höhe), je Stelle gewinnt die sicherere Lesung. Schalter „Fette Schrift ausdünnen“ (Stapelregel `fette_schrift`).
- **Gemessen:** Bestandsplan „03-Bestand“ 138 → 209 Texte (LUFTRAUM, PRODUKTION, INSTALLATION, HOCHREGALLAGER, VERWALTUNG …), Scans image-27 13 → 29, image-136 +9, image-17 +6, image-4 +3, image-11 +2. Allplan-Plots (normale Schrift) unverändert.

## 0.37.3 – 17.11.2026
### PDF
- **Scan als Strich-PDF:** Manche Scanner speichern den Scan nicht als Bild, sondern als Hunderttausende winzige senkrechte Striche (je Bildspalte ein Strich pro schwarzem Lauf). Traceify hielt das für ein CAD-Vektor-PDF und übernahm jeden Strich – Ergebnis: Scanpunkte überall und Linien aus lauter kurzen Stücken. Solche Seiten (≥ 5000 Striche, ≥ 95 % gleich gerichtet, Median < 0,7 mm) werden jetzt wie ein Scan vektorisiert; Scanpunkte kommen auf SCANPUNKTE, Linien werden durchgezogen. Dichte Punktwolken gelten dort als Scanstaub, nicht als Kies.

## 0.37.2 – 17.11.2026
### Maßzahlen
- **Türmaß-Paare:** Steht eine dreistellige Zahl direkt über oder unter einem Maß „d.dd“ und ergibt das Paar eine Tür (Breite 0,55–1,5 m, Höhe 1,9–3,0 m), fehlt ihr der Punkt: „101“ über „2.40“ wird „1.01“. Andere dreistellige Zahlen bleiben.
- **„2 75°“** (Punkt als Lücke, Hochziffer als Gradzeichen) wird „2.75⁵“.
- **Gemessen:** echte Allplan-Plots 14 Texte mehr richtig, 6 falsche Wörter weniger; Simulation und Scans unverändert.

## 0.37.1 – 17.11.2026
### Maßzahlen
- **Verlorener Dezimalpunkt:** „141⁵“ wird „1.41⁵“ – Allplan schreibt Maße ab 1 m immer mit Punkt, darunter in cm („88⁵“); drei Ziffern mit Hochziffer sind also ein Maß, dessen kleiner Punkt im Scan verloren ging. Echte Winkel („135°“) bleiben.
- **Hochziffer als „%“ gelesen:** „2.41%“ wird „2.41⁵“ (ein Prozentwert mit zwei Nachkommastellen kommt im Plan nicht vor; „2%“ bleibt).
- **Gemessen:** echte Allplan-Plots 24 Texte mehr richtig, 22 falsche Wörter weniger; Simulation +43 / −34; Scans unverändert.

## 0.37.0 – 17.11.2026
### Saubere Linien
- **Zerstückelte Linien werden durchgezogen:** Im Scan zerfällt eine Linie an jeder kreuzenden Linie (Deckenraster, Treppenstufen, Maßlinien) in Stücke, die knapp vor der Kreuzung enden. Liegen zwei Stücke gleicher Art in einer Flucht und wird die Lücke von einer anderen Linie gekreuzt oder ist sie voller Tinte, werden sie wieder eine durchgehende Linie. Lücken auf weißem Papier (vor Maßzahlen, Strichlinien) bleiben. Abschaltbar: Einstellungen → Zerstückelte Linien durchziehen; Stapelregel `linien_durchziehen`.
- **Scanpunkte auf eigenem Layer:** Kleine, frei stehende Punkte vom Scannen (unter 1 mm, nichts in 1 mm Umkreis) kommen auf den neuen Layer SCANPUNKTE – im CAD mit einem Klick ausblenden oder löschen. Kies bleibt auf KIES. Abschaltbar: Einstellungen → Scanpunkte auf Layer SCANPUNKTE; Stapelregel `scanpunkte_layer`.
- **Gemessen:** Objekte −2 bis −7 % auf allen 17 Allplan-Plots und 16 Scans, kollineare Stückpaare z. B. PLAN2_EG 670 → 376, PLAN1_EG 222 → 122; Trefferquote, Genauigkeit und Abdeckung unverändert (±0,1 Punkte).

## 0.36.2 – 17.11.2026
### Maßzahlen
- **„28°“ statt „28⁵“** auch bei ganzen Zahlen (cm-Maße): Scheitert das Nachlesen der kleinen Hochziffer, prüft Traceify ihre Form – ein Gradzeichen ist ein Ring, die Hochziffer 5 nicht. So werden Maße zu „28⁵“, echte Winkel wie „30°“ bleiben. Echte Allplan-Plots: 41 Maße mehr richtig (PLAN2_EG +20), Scans unverändert.

## 0.36.1 – 17.11.2026
### Maßzahlen
- **„2.75°“ statt „2.75⁵“:** Klebt die kleine Hochziffer an der Maßlinie, las Tesseract sie als Gradzeichen und das Nachlesen der einzelnen Ziffer scheiterte. Ein Maß mit zwei Nachkommastellen bekommt jetzt die Hochziffer ⁵ (Winkel wie „2.75°“ kommen in Plänen nicht vor; „30°“ bleibt). Echte Allplan-Plots: 28 Maße mehr richtig (PLAN2_EG +15), Scans unverändert.
### Prüfstand
- Wahrheits-Prüfstand zählt Schrift ehrlicher: Allplan zerlegt Maße beim Auflösen in Hauptzahl und kleine Hochziffer (zwei Texte) – diese werden zusammengeführt, wie Traceify sie liest. Originalschrift unter 0,6 mm auf dem Papier zählt nicht mehr (unlesbar klein). Neue Spalte „Texte richtig“ je gedrucktem Text (wiederholte Maße zählen einzeln).

## 0.36.0 – 17.11.2026
### Kies als Fläche
- **Kies-Fläche statt tausender Kreise:** Im DXF/DWG wird jedes Kiesfeld eine Schraffur-Fläche (HATCH) mit Punktmuster auf dem Layer KIES – Umriss knapp hinter den äußeren Punkten, Punktabstand wie im Scan gemessen. Im CAD lässt sich der Kies als Ganzes auswählen, ändern oder löschen. Der SVG-Export zeigt dieselbe Fläche mit Punktmuster. Kleine Gruppen und abgerissene Randpunkte bleiben Kreise. Schalter: „Schraffur und Kies als Fläche“ (Einstellungen) bzw. Ansicht → Schraffur als Fläche; die Zeichenfläche zeigt weiterhin die Kreise.
- **Gemessen** (echte Allplan-Plots): Dachplan 7267 → 2814 Objekte (35 Kies-Flächen), PLAN2_OG3 5126 → 3648; Trefferquote gleich bzw. +0,1 Punkte.
### Prüfstand
- Wahrheits-Prüfstand wertet Kies-Flächen: Original-Kies in einer Fläche gilt als getroffen, neue Spalte „Kies-Fl.“ mit dem Anteil der Fläche an Original-Kies.
- Neue Allplan-DXF mit Maßketten (als Linien und Texte) als Vorlage: Genauigkeit der PLAN2/PLAN3-Pläne jetzt aussagekräftig (≥ 97,8 %, vorher wegen fehlender Maßketten 64–84 %).

## 0.35.0 – 16.11.2026
### Kies und Punktmuster
- **Kies, Splitt und andere Punktmuster** werden kleine Kreise auf dem neuen Layer KIES. Bisher gingen die Punkte (Ø ~0,3 mm) beim Entflecken und im Skelett verloren, in Allplan-Plots sind sie zudem hellgraue Ringe, die schon durch die Schwelle fielen. Traceify sucht sie jetzt im Graubild: kleine, kompakte, frei stehende Kleckse, die dicht und flächig beieinander liegen (mindestens 30). Einzelne Punkte, Rauschen, Schriftpunkte und Punktreihen (Strichpunktlinien) bleiben außen vor. Abschaltbar: Einstellungen → Punktmuster (Kies) als Kreise; Stapelregel `kies_punkte`.
- **Gemessen:** Dachplan simuliert Trefferquote 65,5 % → 87,6 %, PLAN2_OG3 85,5 % → 89,4 %; echte Plots Dach 73,6 % → 93,0 %, OG3 90,5 % → 94,9 %. Alle anderen Pläne und alle echten Scans unverändert – kein einziger Rauschkreis.
### Prüfstand
- Wahrheits-Prüfstand misst die echten Allplan-Plots aller 17 Pläne in einem Lauf und erkennt den Plotmaßstab je Plan (`tools/wahrheit.py --scans …` ohne `--massstab`). Hellgraue Kleinteile (Kies-Ringe) zählen als gedruckt.

## 0.34.2 – 16.11.2026
### Fehlerbehebung
- **Maßzahl mit Randpunkt** (`dimensions.read_gap_numbers`): Las Tesseract „4.17.“ in einer Lücke mit Hochziffer-Kandidat, wurde der Punkt als Hochziffer angehängt und der Text „4.17.“ ausgegeben; eine sichere Lesung „2.45.“ fiel ganz durch. Punkte am Rand werden jetzt schon beim Rohtext entfernt. Weitere `int()`/`float()` auf Rohlesungen in `dimensions.py`, `ocr.py`, `textlines.py` und `scale_detect.py` geprüft: abgesichert (Regex/Ziffernprüfung vorher). Prüfstände unverändert gegenüber 0.34.0/0.34.1 (Wörter simuliert 536, echte PLAN1-Plots 129).

## 0.34.1 – 16.11.2026
### Fehlerbehebung
- **„Konvertierung fehlgeschlagen: invalid literal for int() with base 10: '.'“** (`dimensions._variants`): Liest Tesseract in der Lücke einer Maßlinie eine unsichere Zahl mit Punkt am Rand (z. B. „2.45.“ – Rest von Maßlinie oder Pfeilspitze), wurde der Punkt als letzte Ziffer gelesen und die Konvertierung brach ab. Punkte am Rand der Rohlesung werden jetzt vor dem Bilden der Lesarten entfernt. Neuer Test in `test_massketten.py`.

## 0.34.0 – 15.11.2026
### Schraffierte Wände als Ganzes
- **Wandband:** Im Scan zerfällt die Schraffur einer Wand oft in kleine Flächen, dazwischen liegen lose Striche und Zickzack-Bruchstücke. Liegt eine Schraffurfläche zwischen zwei langen, parallelen Wandkanten, legt Traceify die Fläche jetzt auf das ganze Band zwischen diesen Kanten – so weit dort Schraffurstriche oder Bruchstücke liegen (Türöffnungen beenden das Band). Zerstückelte Kanten werden dafür zu einer Kette verbunden. Flächen mit gleichem Raster in derselben Wand werden eine Fläche, lose Striche und Bruchstücke im Band gehören dazu und verschwinden im DXF/SVG unter dem Muster. Linien längs der Wand (z. B. Dämmung) und Linien quer über die ganze Wandbreite bleiben. An Wandecken weicht die kleinere Fläche der größeren.
- **Lose Striche ohne Fläche** kommen zurück auf LINIEN, wenn keine Schraffurfläche in der Nähe ist (10 mm), keine Schar paralleler Striche und keine Kanten beidseits – meist Buchstabenstriche nicht gelesener Handschrift.
- **Gemessen:** Einzellinien image-4 39 % statt 50 %, image-27 42 % statt 51 %, image-37 25 % statt 41 %, image-89 12 % statt 15 %, image-94 6 % statt 10 %, image-99 12 % statt 17 %. Handschrift-Fehltreffer image-17 9 statt 35 Striche. Objekte, Abdeckung, offene Enden und Wahrheits-Prüfstand unverändert.
- Neue Prüfstand-Spalte „Muster auf Tinte“ (Anteil der Musterlinien auf Tinte): 87–100 %, beim handschraffierten Kellerplan 80 % – das gleichmäßige Muster läuft dort auch über die Lücken der gestrichelten Handschraffur.
- Bekannt: Einige Striche einzeln stehender, schraffierter Wandstücke ohne Fläche fallen mit zurück auf LINIEN (image-4 etwa 50).

## 0.33.0 – 15.11.2026
### Mehr Schraffur erkannt
- **Zweiter Erkennungsdurchgang:** Die Schraffur-Erkennung lief bisher nur auf den rohen Strichen, bevor Linien ausgerichtet, Fransen entfernt und Lücken geschlossen werden. Gerade bei verrauschten Scans waren Schraffurlinien da noch zerrissen und fielen durch. Jetzt prüft Traceify die fertige Geometrie ein zweites Mal.
- **Mauerwerks-Schraffur:** Lange Striche mit kurzen Strichen dazwischen (handgezeichnetes Mauerwerk) wurden nicht erkannt, weil Nachbarlinien ähnlich lang sein mussten. Jetzt zählt auch ein kurzer Strich, der ganz neben einem langen liegt (mindestens ein Fünftel so lang, langer Strich höchstens 10 mm) – gedrehte Möbel aus langen Parallelen bleiben normale Linien.
- **Gemessen** (Linien in Schraffur-Flächen): Kellerplan image-4 589 statt 405, image-27 868 statt 781, image-37 269 statt 213, image-89/-94/-99 gleich. Mehr Linien landen auf SCHRAFFUR (image-4 1177 statt 780), ein Teil davon bleibt Einzellinie (Schraffurreste in verrauschten Wänden). Wenige Fehltreffer in nicht gelesener Handschrift (image-17: 35 statt 14 Striche auf SCHRAFFUR, keine Fläche). Objekte, Abdeckung, offene Enden gleich oder besser.

## 0.32.0 – 15.11.2026
### Schraffur-Flächen auch in der Zeichenfläche und im SVG
- Regelmäßige Schraffuren erscheinen jetzt schon in der Zeichenfläche als **Fläche mit Linienmuster** – genau so, wie sie im DXF/DWG als HATCH ankommen (dieselben Flächen, derselbe Winkel und Abstand). Ein Klick wählt die ganze Schraffur, Entf löscht sie, Rückgängig holt sie zurück. Der Layer SCHRAFFUR blendet Flächen und übrige Einzellinien gemeinsam aus.
- Der **SVG-Export** gibt dieselben Flächen als Umriss mit Linienmuster (`<pattern>`) aus statt als Einzellinien.
- Neuer Schalter **Ansicht → Schraffur als Fläche**: aus = Einzellinien in Zeichenfläche, DXF und SVG.
### Schraffurlinien bis zur Wandkante
- Schraffur endet im Scan oft kurz vor der Wandkante – auf weißem Papier, die Tintenprüfung von „Lücken schließen“ greift dort nicht. Jetzt zieht Traceify ein freies Schraffurende bis zur Kante in seiner Richtung (höchstens 2,5 mm und nicht weiter, als die Linie lang ist), wenn mindestens zwei weitere Schraffurlinien im Umkreis von 8 mm an derselben Kante enden – auch wenn die Kante im Scan in mehrere Stücke zerfallen ist. Ziel ist nie eine andere Schraffurlinie.
- **Gemessen:** offene Enden image-89 98 statt 140, image-94 96 statt 114, image-4 1928 statt 1947, image-27 1515 statt 1535; Objekte und Abdeckung gleich, Wahrheits-Prüfstand (simuliert und echte Plots) unverändert.
- Prüfstand: Spalte „Schraffur“ (Linien auf SCHRAFFUR, Zahl der Flächen) und „Einzellinien“ (Anteil, der nicht in einer Fläche aufgeht).

## 0.31.0 – 15.11.2026
### Abgerundete Ecken werden wieder spitz
- Das Skelett rundet rechtwinklige Ecken dicker Striche ab, die Kreisanpassung machte daraus kleine Bögen (Radius 1–3 mm, um 90°). Im Original-CAD-Plan liegen dort zwei Linien – das war die Hauptquelle falscher Bögen. Jetzt prüft Traceify je kleinem Bogen den Schnittpunkt der Tangenten an beiden Enden: Liegt dort Tinte und laufen beide Tangentenstücke zu mindestens 70 % über Tinte, werden daraus zwei Linien über die Ecke (fast achsparallel → exakt waagrecht/senkrecht). Echte Bögen (Türschwenk, Rundungen) haben eine leere Ecke und bleiben – in den simulierten Plänen ging kein echter Bogen verloren.
- **Gemessen:** Bögen simuliert PLAN2_EG 141 statt 189 (Original 90), PLAN2_OG1 142 statt 212, PLAN3_DG 54 statt 69 (Original 0); echte Plots EG 86 statt 147, UG 120 statt 151; Testscans z. B. image-27 141 statt 548, image-4 97 statt 351. Trefferquote und Genauigkeit gleich bis −0,1 Punkte, weniger offene Enden, Texte unverändert. Dafür 1–5 % mehr Objekte (ein Bogen wird zu zwei Linien), Ortho bis −1 Punkt (neue Eckstücke an schrägen Details zählen als schräge Linien).
- Untersucht und verworfen: zusätzlich verlangen, dass die Geraden hinter den Bogenenden weiterlaufen – die meisten Ecken haben kurze Schenkel, der Gewinn fiel fast ganz weg.

## 0.30.0 – 15.11.2026
### Zeichnungsmaßstab aus den Maßketten
- Traceify kennt jetzt für jede erkannte Maßzahl die gezeichnete Länge ihrer Maßlinie. Stimmen mindestens fünf Maße überein, ergibt sich daraus der Zeichnungsmaßstab (echte Allplan-Plots: 1:200 aus 70 bzw. 37 Maßen) – auch wenn nirgends „M 1:200“ steht. Exportiert wird dann in Originalgröße.
- Die Maßketten haben Vorrang vor einer „M 1:100“-Angabe im Plan (die kann zu einem Detail gehören); weichen beide ab, steht es im Info-Fenster („aus Maßketten, Plan nennt 1:100“). Ein von Hand gesetzter Maßstab bleibt unangetastet, Pläne ohne erkannte Maßketten (die neun Testscans) ebenso.
- Erkennung, Geometrie und Texte unverändert (alle Prüfstände gleich).

## 0.29.0 – 15.11.2026
### Türmaße auch ohne erkannten Stern
- Laufen die Zahlen einer Tür über beide Maßbegrenzungen (UG: „1.01“ / „2.12⁵“ bis in die Wände), erkennt die Sternsuche oft keinen der beiden Sterne – der Schablonen-Leser hatte keinen Ausgangspunkt. Jetzt sucht Traceify auf den Zeilen bekannter Sterne auch nach von Ziffern überdeckten Sternen (Schrägstrich, waagrechter und senkrechter Strich durch einen Punkt) und nimmt sie als Ausgangspunkt. Kreuzungen in Schraffuren, die dabei mitgefunden werden, sortiert die Lage- und Längenprobe des Lesers aus.
- Breite und Höhe derselben Tür dürfen sich überlappen (EG: „1.88⁵“ über „2.37⁵“); bisher blieb nur eine von beiden.
- **Gemessen** (echte 300-dpi-Plots, je gedrucktem Text nach Lage): PLAN1_EG 140 statt 137, PLAN1_UG 96 statt 89 („1.01“, „2.12⁵“, „2.26“, „1.95⁵“). Wörter echt 129 statt 125 von 208, falsch 37 statt 35 (EG „40“ und „1.11“ ohne Hochziffer). Simuliert 536 / 199 statt 533 / 198, neun Testscans unverändert.
- Untersucht und verworfen: Ziffernhöhe ±1 px absuchen – EG +2/−1 und neue Fehllesung „86⁵“, UG unverändert, dreifache Zeit. Höhe unter der Linie über einen Plan-Wortschatz – „2.12⁵“ kommt im EG nirgends sicher gelesen vor.

## 0.28.0 – 15.11.2026
### Türmaße per Ziffern-Schablone (mit Fable erarbeitet)
- **„88⁵“ über einer Tür wird gelesen:** Breite (über der Linie) und Höhe (darunter) stehen eng zwischen zwei Sternen, überlappen sich und laufen über den rechten Stern – Tesseract scheitert daran. Traceify baut jetzt aus den sicher gelesenen Maßzahlen desselben Plans **Ziffern-Schablonen** (gleiche Schrift, gleiche Größe) und gleicht die Ziffern neben einem bekannten Stern damit ab; Stern- und Linientinte zählen nicht mit. Die gelesene Breite muss zur Lage passen (Zahl mittig zwischen Stern und der Stelle im Abstand Breite × Maßstab, dort ein Querstrich). Hochziffer nur „⁵“. Die Höhe darunter wird mit strengen Schwellen gelesen.
- **Gemessen** (echte 300-dpi-Plots, je gedrucktem Text nach Lage): PLAN1_EG 137 statt 116 („88⁵“ 18 von 19), PLAN1_UG 89 statt 80 („1.01“, „2.12⁵“, „3.01“/„3.00“); kein bisher richtiger Text verloren. Wörter echt EG 63 statt 60, UG 60 statt 57, falsche gleich (13 / 20). Simuliert 533 / 198 statt 530 / 197 (nur PLAN1_EG geändert). Neun Testscans unverändert, etwa 3 s mehr je Plan mit Türmaßen.
- Noch offen: Höhe unter der Linie im EG („2.12⁵“, überlappt mit der Breite), UG-Türen, deren beide Sterne von den Zahlen überdeckt sind. Die Schwellen sind an zwei Plots eingestellt.

## 0.27.0 – 15.11.2026
### Kleine Maße über zwei engen Maßbegrenzungen
- **„24“ über „✳✳“:** Ist ein Maß so kurz, dass die Zahl nicht zwischen die beiden Sterne passt (Wandputz, Anschläge: 24, 25, 30 cm), setzt Allplan sie darüber – oft breiter als das Sternpaar und dicht an Nachbarschrift. Traceify sucht über jedem engen Sternpaar Ziffern in der Schrifthöhe der übrigen Maßzahlen, liest sie gezielt und übernimmt sie nur, wenn die Zahl zum Abstand der Sterne passt (Maßstab aus den Maßen selbst, seit 0.25.0). Eine andere Hochziffer als ⁵ wird dabei verworfen – sie stammt bei so kleinen Maßen fast immer aus Nachbarschrift (im Original 117 × ⁵, 1 × ³).
- **Gemessen** (echte 300-dpi-Plots, je gedrucktem Text nach Lage): PLAN1_EG 116 statt 112, PLAN1_UG 80 statt 71; Wörter EG 60 statt 58 bei 13 statt 15 falschen, UG 20 statt 21 falsche. Simulierte Pläne 530 / 197 statt 528 / 200, neun Testscans unverändert, Laufzeit einzeln gemessen unverändert.
- Sehr viele Leseausschnitte werden jetzt in Blöcken an Tesseract gegeben (ein Blatt darf höchstens 32 767 Pixel hoch sein).
- Nicht gelöst: Maße, die im Plot übereinander gedruckt sind (UG „15“/„25“/„10“ als Knäuel), und Türmaße als berührendes Paar („88⁵“ / „2.12⁵“).

## 0.26.0 – 15.11.2026
### Maßzahlen als Bemaßung (DIMENSION) im DXF
- **Erkannte Maßketten werden echte CAD-Bemaßungen:** Eine Maßzahl, die zwischen zwei erkannten Maßbegrenzungen mittig steht, wird im DXF/DWG als gedrehtes Linearmaß (DIMENSION) ausgegeben – Maßlinie von Stern zu Stern, Schrägstriche als Begrenzung, die Zahl wie gelesen mittig in der Linie (Allplan-Stil), waagrecht und senkrecht. Im CAD lässt sich das Maß so als Ganzes auswählen und abfragen. Die gezeichnete Maßlinie aus dem Scan bleibt zusätzlich als Linie erhalten.
- Die Maßlinie hängt am Text: Verschieben, Drehen oder Ausrichten (Schräglage) nimmt sie mit. DXF R12 kennt keine Bemaßungsobjekte, dort bleibt es ein Text.
- Liegt an der Stelle schon dieselbe Zahl aus der normalen Texterkennung, wird sie durch die Lesung mit Maßlinie ersetzt.

## 0.25.0 – 15.11.2026
### Maßzahlen gegen die Länge ihres Maßsegments prüfen
- **Maßstab aus den Maßen selbst:** Aus den sicher gelesenen Maßzahlen und dem Abstand ihrer Maßbegrenzungen (Sterne) ermittelt Traceify, wie viele Pixel ein Meter im Plan hat – richtige Maße stimmen darin auf ±1 % überein (echter Plot 1:200 bei 300 dpi: 59 px/m). Damit lässt sich jede Maßzahl gegen ihr Segment prüfen; die Teilmaße einer Kette ergeben so von selbst das Gesamtmaß.
- **Unsicher gelesene Maße werden gerettet**, wenn genau eine Lesart auf ±1 % zum Segment passt, z. B. „14.40“ mit zu niedriger Konfidenz oder eine voll gelesene Hochziffer („1875“ → „1.87⁵“). Erst ab 1 m Segmentlänge – darunter trennt ein Pixel schon 2 cm („85“ / „88⁵“).
- Eine Zahl, die nicht in ihr Segment passen kann (Segment kürzer als zwei Drittel der Zahl), wird verworfen. Ein zu langes Segment beweist dagegen nichts: Verpasst die Erkennung Sterne, umfasst es mehrere Teilmaße.
- **Gemessen** (echte 300-dpi-Plots, je gedrucktem Text nach Lage): PLAN1_EG 112 statt 111, PLAN1_UG 71 wie bisher; Wörter 117 statt 116 von 208 bei gleich vielen falschen (38). Simulierte Pläne (528 / 200) und die neun Testscans unverändert.
- Untersucht und verworfen: Zahlen in einem zu langen Segment als Teilzahl verwerfen („10“ statt „7.10“) – trifft genauso richtige Maße in Ketten mit verpassten Sternen („43⁵“); 2 % Toleranz – übernimmt „2.29“ statt „2.25“.

## 0.24.0 – 14.11.2026
### Kurze Maße zwischen Sternen, Maßpaare über und unter der Linie
- **„✳74✳74✳“:** Bei kurzen Maßen lässt Allplan die Maßlinie ganz weg, die Zahl steht zwischen zwei Maßbegrenzungen. Traceify erkennt die Sterne (Schrägstrich mit Maß- und Hilfslinie durch die Mitte; Ziffern wie „4“ oder „7“ zählen nicht) und liest die Zahl dazwischen gezielt.
- **Zwei Zahlen direkt über und unter der Maßlinie** (z. B. Breite und Höhe einer Öffnung, „3.01“ / „3.00“) werden an der Linie getrennt und einzeln gelesen.
- **Hochziffern** („2.38⁵“) werden sicherer gelesen; die Zahlenlänge muss zur Breite passen, sonst wird nichts übernommen (keine Teilzahlen).
- **Gemessen** an den echten 300-dpi-Plots (je gedrucktem Text nach Lage): PLAN1_EG 111 statt 93, PLAN1_UG 71 statt 62; falsche Wörter 15 statt 16 und 21 statt 24. Simulierte Pläne 528 / 200 statt 527 / 202. Neun Testscans und Geometrie unverändert, Laufzeit etwa +3–7 %.

## 0.23.0 – 14.11.2026
### Maßzahlen in der Lücke der Maßlinie
- **„—— 6.70 ——“ wird jetzt gelesen:** Steht eine Maßzahl mittig in einer Lücke der Maßlinie (Allplan-Standard), sucht Traceify diese Lücke – waagrecht und senkrecht –, schneidet die Zahl ohne die Linienstücke aus und liest sie nur mit Ziffern. Bisher scheiterte Tesseract oft an den kurzen Linienstücken links und rechts der Zahl, selbst bei großen, freistehenden Maßen. Hochgestellte Ziffern („4.17⁵“) werden erkannt.
- Liegt an der Stelle schon eine verlesene Zahl („144“ statt „14.45“, „6 03“, „515“), wird sie ersetzt. Wörter bleiben unangetastet. Läuft über den Schalter „Maßzahlen nachlesen“.
- **Gemessen** an den echten 300-dpi-Plots der Original-CAD-Pläne (je gedrucktem Text nach Lage): PLAN1_EG 93 statt 87, PLAN1_UG 62 statt 54 Texte richtig; falsche Wörter 16 statt 18 und 24 statt 28. Simulierte Pläne (150 dpi): 527 statt 523 Wörter richtig, 202 statt 199 falsch. Neun Testscans und Geometrie unverändert, Laufzeit etwa +4 %.

### Für Entwickler
- `tools/zahlen_echt.py`: misst je gedrucktem Originaltext, ob er an derselben Stelle gelesen wird (genauer als die Wörter-Spalte des Wahrheits-Prüfstands, die wiederholte Maße nur einmal zählt).

## 0.22.0 – 14.11.2026
### Hinweis: kleine Schrift besser mit 300 dpi scannen
- Enthält ein Scan unter 200 dpi viel sehr kleine Schrift (unter 2 mm, z. B. Raumstempel), zeigt die Qualitätsampel „300 dpi empfohlen“, die Statusleiste nennt den Grund. Hintergrund: Solche Schrift ist bei 150 dpi nur etwa 7 Pixel hoch; beim Original-CAD-Plan mit 1,25-mm-Raumstempeln liest Traceify bei 300 dpi 45 statt 13 von 55 Wörtern. Vergrößern oder Graustufen-Lesen im Programm wurden gemessen und brachten ebenso viele Fehllesungen wie Treffer.

## 0.21.0 – 14.11.2026
### Dateien aufs Programmsymbol ziehen
- Eine Datei auf das Traceify-Symbol (Desktop, Startmenü, EXE) ziehen öffnet sie in Traceify. **Läuft Traceify schon, öffnet die Datei im offenen Fenster** – es startet kein zweites. Mehrere Dateien auf einmal: die erste unterstützte wird geöffnet (bisher passierte dann gar nichts).

### Maße mit hochgestellter Ziffer
- **Allplan-Schreibweise „2.38⁵“** (= 2,385 m): Tesseract liest die kleine Ziffer als „°“ oder „"“ oder verschluckt sie. Traceify sucht jetzt hinter jeder gelesenen Zahl nach einer kleinen, hochgestellten Ziffer, liest sie einzeln nach und übernimmt sie als Hochziffer. Die Hauptziffern bleiben unverändert; geht die Zahl direkt weiter („6“ + „19“), wird nichts angehängt.
- **Gemessen** an den Original-CAD-Plänen (Allplan): auf den echten 300-dpi-Plots von PLAN1 49 statt 43 und 49 statt 45 Wörter richtig, 18 statt 23 und 28 statt 31 falsch. Über alle 17 simulierten Pläne mit Wörterbuch-Fix 523 statt 511 Wörter richtig und 199 statt 209 falsch. Linien und Bögen bleiben gleich, die neun Testscans sind unverändert.

### Wörterbuch
- Sicher gelesene Wörter verlieren keinen echten Buchstaben mehr: „Klasse“ wurde bisher zu „Kasse“. Neu im Wörterbuch: Klasse, Klassenzimmer, Fachraum, Werkraum, Lehrer, Lehrerzimmer.

### Für Entwickler: Wahrheits-Prüfstand
- **DXF-Import korrigiert:** Allplan-Texte (MTEXT) kamen ohne Drehung an – alle senkrechten Maßzahlen lagen waagrecht – und hochgestellte Ziffern als „2.385^“. Jetzt mit Drehung (Richtungsvektor), Ausrichtung (z. B. Mitte), mehrzeilig und Hochziffern. Der simulierte Scan zeigt die Maße damit so wie der echte Plot; die bisherigen Wortzahlen des Prüfstands waren dadurch verfälscht.
- **Echte Scans gegen das Original:** `tools/wahrheit.py DXF_ORDNER --scans SCAN_ORDNER --massstab 200` misst Scans/Plots derselben Pläne (gleicher Dateiname). Die Original-Geometrie wird über Maßstab und Kreuzkorrelation auf den Scan gelegt; gezählt wird nur, was auf dem Scan auch zu sehen ist (ausgeblendete Layer zählen nicht als „fehlt“).
- `--jobs N` misst mehrere Pläne parallel.

## 0.20.0 – 13.11.2026
### Leicht schräge Linien bleiben schräg
- **Gerade ausrichten mit Blick in den Scan:** Bisher wurde jede Linie, die weniger als 3° von waagrecht/senkrecht abweicht, exakt auf die Achse gelegt. Bei Plänen mit bewusst leicht schräg gezeichneten Linien (z. B. Dachgeschoss, Dachaufsichten) lagen diese danach neben der Tinte. Jetzt wird eine Linie nur ausgerichtet, wenn sie danach weiter auf der Tinte liegt (oder nicht schlechter als vorher). Wände, die im Scan nur leicht wackeln, werden wie bisher exakt waagrecht und senkrecht.
- **Gemessen an Original-CAD-Plänen** (als Scan simuliert): beim Dachgeschoss-Plan Trefferquote 93,4 % statt 82,0 % und Genauigkeit 96,8 % statt 81,3 %; bei den übrigen Plänen gleich oder bis 0,8 Punkte besser. Die echten Scans bleiben unverändert.

## 0.19.0 – 13.11.2026
### Weniger falsche Bögen
- **Kleine Ecken werden keine Viertelkreise mehr:** Kurze Linienstücke – etwa wo eine Schraffurlinie auf eine Kante trifft oder an kleinen Wandecken – wurden bisher ohne Eckprüfung als Bogen ausgegeben. Jetzt werden auch sie auf Ecken geprüft; biegt das Stück nur kurz vor dem Anschluss ab, wird es eine gerade Linie bis zum Anschlusspunkt. Auf den neun Testplänen gibt es 20–64 % weniger Bögen, z. B. 584 statt 948 oder 385 statt 687; echte Türbögen bleiben erhalten.

### Kanten liegen genauer auf der Tinte
- Eine Kante, die über mehrere Abzweigungen hinweg zu einer Linie zusammengefügt wird, wird jetzt durch alle ihre Stützpunkte gelegt statt nur durch die beiden Enden. Ein vom Fangen verschobenes Ende stellt die Kante so nicht mehr schräg oder neben die Tinte; Ecken und Anschlüsse werden mitgeführt.
- **Gemessen an Original-CAD-Plänen** (als Scan simuliert, 1:100, 150 dpi): Trefferquote meist +0,5 bis +2,8 Punkte, Genauigkeit +0,3 bis +1,8 Punkte, z. B. 90,1 → 92,9 % und 95,2 → 96,2 % beim zweiten Obergeschoss.
- **Echte Scans:** 2–10 % weniger Objekte, weniger Splitter (z. B. 603 statt 690, 461 statt 607) und auf acht von neun Plänen weniger offene Enden (z. B. 114 statt 185, 1690 statt 1847). Abdeckung gleich oder besser.

## 0.18.0 – 13.11.2026
### Eng liegende Doppellinien bleiben getrennt
- **Ursache behoben:** Beim Zusammenfügen von Linienstücken über Abzweigungen wurden kurze, seitlich wegführende Stege (z. B. zur zweiten Linie einer Wandschicht oder Trockenbauwand) in die lange Linie übernommen. Das bog deren Ende zur Seite, die ganze Linie stand danach leicht schräg und verschmolz mit ihrer Nachbarlinie. Jetzt bleibt das Linienende auf der Achse; führt der Steg zu weiterer Geometrie, bleibt er als eigene kurze Verbindung stehen.
- **Gemessen an Original-CAD-Plänen** (als Scan simuliert, 1:100, 150 dpi): Trefferquote und Genauigkeit steigen um 2–5 Punkte, z. B. 86,4 → 90,8 % und 92,7 → 95,7 % beim Erdgeschoss, 91,1 → 95,5 % und 94,4 → 98,5 % beim Obergeschoss.
- **Echte Scans:** Auf allen neun Testplänen weniger offene Enden (bis 28 %), Abdeckung gleich oder besser. Auf vier Plänen entstehen durch die kurzen Verbindungsstege 5–7 % mehr Objekte.

### Neu für Entwickler: Wahrheits-Prüfstand
- `tools/wahrheit.py` simuliert aus Original-DXF-Plänen einen Scan und misst das Traceify-Ergebnis direkt gegen die Originalgeometrie (Trefferquote, Genauigkeit, Lagefehler in Papier-mm, Objekte, Bögen, Ortho-Anteil, Wörter). Der DXF-Import übernimmt dafür jetzt auch Bemaßungen (Maßlinien, Pfeile, Maßtext).

## 0.17.0 – 12.11.2026
### Schräge Gebäudeflügel exakt ausgerichtet
- **Zweite Bauachse:** Hat ein Plan einen schräg stehenden Gebäudeteil (z. B. 39° zum Rest), erkennt Traceify diese Richtung und richtet dessen Wände und Querwände parallel und rechtwinklig zueinander aus – so wie das bei den Hauptachsen schon der Fall war. Ecken bleiben verbunden, Schraffur zählt nicht als Bauachse. Ausgerichtet wird nur, wo sich eine Linie dabei höchstens um etwa 0,3 mm verschiebt: Flügel sind in Scans oft leicht verzogen, sonst würden Wandenden neben die Tinte wandern. Beim A1-Testplan liegen so 59 % der Linienlänge exakt auf einer Bauachse (vorher 54 %), die Abdeckung bleibt gleich. Pläne ohne schrägen Flügel bleiben unverändert.

### Schräge Schrift besser gelesen
- Schräge Beschriftungen werden zusätzlich aus dem **Graustufenbild** gelesen, die sicherere Lesart gewinnt. Das hilft bei kleiner, fetter Schrift, deren Buchstaben im Schwarz-Weiß-Bild zu Klecksen verschmelzen. Beim A1-Testplan kommen so u. a. „Pos 01 Handverkauf“ und „BR 850“ dazu; 85 Objekte, 24 Bögen und 47 offene Enden weniger (Splitter aus vorher ungelesener Schrift). Positionsnummern, deren Ziffern im Scan verschmiert sind („05“/„06“/„08“), bleiben unsicher.

### Weniger offene Enden
- **Lücken schließen mit Blick in den Scan:** Bis 0,8 mm (einstellbar) wird wie bisher immer verlängert, bis zum 2,5-Fachen (2 mm) jetzt auch, wenn der Scan auf der ganzen Lücke Tinte zeigt – dort endet das Skelett in dicken oder ausgefransten Strichen nur zu früh. Absichtliche weiße Lücken (Strichlinien, vor Maßzahlen, zwischen Buchstaben) bleiben offen. Auf allen neun Testplänen gibt es weniger offene Enden, z. B. 1554 statt 1636, 2218 statt 2324, 1870 statt 2013, 1310 statt 1388; Abdeckung und Genauigkeit bleiben gleich oder werden besser.

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
