"""Wörterbuch für Planbegriffe: verstümmelte OCR-Wörter korrigieren.

Tesseract liest kleine oder schräge Schrift auf groben Scans oft knapp daneben
(„Schiafen“, „Kuche“, „Deckenhohe“, „Sichtvah!“). Hier werden solche Wörter mit einer Liste
typischer Planbegriffe und den Wörtern verglichen, die im selben Plan schon sicher gelesen
wurden. Der Vergleich kennt die typischen OCR-Verwechslungen (i/l/1/!, v/w, e/c/o, rn/m,
Umlaute) und korrigiert nur, wenn genau ein Begriff klar am besten passt.

Zahlen werden nie verändert – eine falsch „korrigierte“ Maßzahl wäre schlimmer als keine.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional, Set, Tuple

# Typische Begriffe auf Bauplänen (Raumnamen, Bauteile, Angaben, Abkürzungen). Groß-/
# Kleinschreibung so, wie sie im Plan üblicherweise steht.
PLAN_WORDS = """
Wohnen Wohnzimmer Wohnraum Wohnküche Essen Essplatz Esszimmer Kochen Küche Kochnische
Schlafen Schlafzimmer Eltern Kind Kinder Kinderzimmer Gast Gästezimmer Gäste Zimmer
Arbeiten Arbeitszimmer Büro Studio Hobby Hobbyraum Spielen Bibliothek Ankleide
Bad Badezimmer Dusche Duschbad WC Gäste-WC Toilette Waschen Waschraum Waschküche
Hauswirtschaft Hauswirtschaftsraum Hausarbeitsraum HWR Abstellraum Abstellkammer Abstell
Speisekammer Speis Vorrat Vorratsraum Vorräte Lager Lagerraum Archiv Technik Technikraum
Heizung Heizraum Heizöl Öltank Tankraum Brennstoff Koks Kohle Keller Kellerraum
Kellergeschoss Privatkeller Fahrradkeller Fahrräder Waschmaschine Trockenraum Trocknen
Werkstatt Garage Carport Stellplatz Einfahrt Zufahrt Hof Garten Terrasse Balkon Loggia
Dachterrasse Wintergarten Veranda Freisitz Eingang Hauseingang Windfang Diele Flur Gang
Korridor Halle Foyer Vorraum Vorplatz Treppe Treppenhaus Treppenraum Podest Aufzug
Schacht Abluftschacht Lüftungsschacht Installationsschacht Kamin Schornstein Dach
Dachboden Speicher Spitzboden Galerie Empore Luftraum Erdgeschoss Obergeschoss
Untergeschoss Dachgeschoss Souterrain Geschoss Grundriss Ansicht Schnitt Lageplan Detail
Maßstab Fläche Flächen Nutzfläche Wohnfläche Grundfläche Gesamtfläche Betriebsfläche
Verkehrsfläche Flächenaufstellung Raum Räume Raumhöhe Deckenhöhe Lichte Höhe Brüstung
Brüstungshöhe Sturz Fenster Tür Türen Haustür Schiebetür Tor Garagentor Wand Wände
Außenwand Innenwand Trennwand Decke Deckensprung Unterzug Stütze Pfeiler Fundament
Bodenplatte Boden Fußboden Estrich Fliesen Fliese Granitfliese Parkett Teppich Belag
Dämmung Mauerwerk Beton Stahlbeton Ziegel Kalksandstein Holz Stahl Glas Putz
Abdichtung Entwässerung Bodenablauf Rinne Lüftung Entlüftung Belüftung Abluft Zuluft
Gasabzug Rohr Leitung Anschluss Steckdose Heizkörper Radiator Kessel Speicher Boiler
Achse Bestand Neubau Abbruch Umbau Anbau Planung Entwurf Genehmigung Bauherr Architekt
Personal Personalraum Aufenthalt Aufenthaltsraum Sozialraum Umkleide Pausenraum
Labor Rezeptur Notdienst Beratung Verkauf Verkaufsraum Handverkauf Offizin Sichtwahl
Freiwahl Arbeitsplatz Kasse Theke Tresen Schübe Regal Regale Schrank Schränke
Helferinnen Mitarbeiter Empfang Anmeldung Wartezimmer Warteraum Behandlung
Behandlungsraum Sprechzimmer Praxis Sonstige Brennbare Flüssigkeiten Gefahrstoffe
Müll Mülltonnen Fahrrad Kinderwagen Spielplatz Wiese Rasen Pflaster Gehweg Straße
Grenze Grundstück Nachbar Norden Süden Osten Westen Höhe Breite Tiefe Länge
Fertigmaß Rohbaumaß Rohbau Ausbau Oberkante Unterkante Fertigfußboden Rohfußboden
unter über und mit ohne für bis von neu alt
""".split()

# Abkürzungen: nur vor einer Zahl und nur bei sehr kleinem Abstand korrigiert
ABBREV = ["Pos", "Nr", "BR", "RH", "OK", "UK", "FFB", "RFB", "NFL", "WFL", "qm", "m²",
          "cm", "mm", "Ø", "DN", "BRH", "STH", "Achse"]

# OCR-Verwechslungen. FORM: Zeichen, die sich in Schrift kaum unterscheiden (auch bei sicher
# gelesenem Text plausibel). VOKAL u. Ä.: nur bei unsicher gelesenem Text
_FORM = ["il1!|jIíì", "vwVW", "eé", "uü", "aä", "oö", "o0O", "sß", "cC", "zZ"]
_LOOSE = _FORM + ["tfl", "eco", "aoe", "uvn", "bh", "gq9", "kK", "s5S", "B8", "z2"]
_THIN = set("il1!|.'’,:;-")             # dünne Zeichen gehen im Scan leicht verloren
_PAIRS = {("rn", "m"), ("ii", "ü"), ("ii", "u"), ("cl", "d"), ("vv", "w"), ("li", "h"),
          ("il", "u"), ("in", "m"), ("ri", "n")}
_ALPHA = re.compile(r"^[A-Za-zÄÖÜäöüßéèí!|]+[.:]?$")
_DIGITS = re.compile(r"\d")
# Endungen: „Garagen“, „Details“, „Zimmern“ sind gebeugte Formen, keine Lesefehler
_SUFFIXES = ("e", "n", "en", "er", "ern", "es", "s", "ns", "ens", "nen")


def _fold(s: str) -> str:
    return (s.lower().replace("ä", "a").replace("ö", "o").replace("ü", "u")
            .replace("ß", "ss"))


def _sub(a: str, b: str, loose: bool) -> Tuple[float, int]:
    """Kosten (Betrag, „echter Fehler“ 0/1) für Zeichen a statt b."""
    if a == b:
        return 0.0, 0
    al, bl = a.lower(), b.lower()
    if al == bl:
        return 0.05, 0
    for c in (_LOOSE if loose else _FORM):
        if al in c and bl in c:
            return 0.4, 0
    return 1.0, 1


def _indel(ch: str) -> Tuple[float, int]:
    return (0.5, 0) if ch in _THIN else (1.0, 1)


def distance(a: str, b: str, loose: bool = True) -> Tuple[float, int]:
    """Gewichtete Editierdistanz (gelesen a, Begriff b): (Kosten, Anzahl echter Fehler).

    Typische OCR-Verwechslungen kosten wenig und zählen nicht als echter Fehler; ebenso
    zwei Zeichen für eines (rn → m, ii → ü) und fehlende/zusätzliche dünne Zeichen (i, l, !)."""
    a, b = a.lower(), b.lower()
    n, m = len(a), len(b)
    INF = (1e9, 99)

    def add(x, y):
        return (x[0] + y[0], x[1] + y[1])
    D = [[INF] * (m + 1) for _ in range(n + 1)]
    D[0][0] = (0.0, 0)
    for i in range(n + 1):
        for j in range(m + 1):
            if i == j == 0:
                continue
            best = INF
            if i > 0:
                best = min(best, add(D[i - 1][j], _indel(a[i - 1])))
            if j > 0:
                best = min(best, add(D[i][j - 1], _indel(b[j - 1])))
            if i > 0 and j > 0:
                best = min(best, add(D[i - 1][j - 1], _sub(a[i - 1], b[j - 1], loose)))
            if i > 1 and j > 0 and (a[i - 2:i], b[j - 1]) in _PAIRS:
                best = min(best, add(D[i - 2][j - 1], (0.4, 0)))
            if j > 1 and i > 0 and (b[j - 2:j], a[i - 1]) in _PAIRS:
                best = min(best, add(D[i - 1][j - 2], (0.4, 0)))
            D[i][j] = best
    return D[n][m]


def _budget(n: int) -> int:
    """Erlaubte echte Fehler je Wortlänge."""
    return 0 if n <= 7 else 1 if n <= 11 else 2


class Lexicon:
    """Wortliste mit schneller Vorauswahl nach Länge."""

    def __init__(self, words: Iterable[str] = (), with_plan_words: bool = True):
        self.words: Dict[str, str] = {}      # fold → Schreibweise
        if with_plan_words:
            self.add(PLAN_WORDS)
        self.abbrev = {a.lower(): a for a in ABBREV}
        self.add(words)

    def add(self, words: Iterable[str]) -> None:
        for w in words:
            w = w.strip(".,:;")
            if len(w) >= 3 and not _DIGITS.search(w):
                self.words.setdefault(_fold(w), w)

    def add_own(self, words: Iterable[str]) -> None:
        """Wörter aus dem Plan selbst aufnehmen – aber keine, die einem bekannten Begriff zum
        Verwechseln ähneln (dann hat die OCR sich sicher verlesen, z. B. „Schiafen“)."""
        for w in words:
            if w in self or self.inflected(w):
                continue
            if self.best(w, loose=False) is not None:
                continue
            self.add([w])

    def __contains__(self, w: str) -> bool:
        return _fold(w.strip(".,:;")) in self.words

    def inflected(self, w: str) -> bool:
        """Gebeugte Form eines bekannten Begriffs („Garagen“, „Details“)?"""
        f = _fold(w.strip(".,:;"))
        return any(f[:-len(sx)] in self.words and len(f) - len(sx) >= 4
                   for sx in _SUFFIXES if f.endswith(sx))

    def best(self, w: str, loose: bool = True) -> Optional[Tuple[str, float]]:
        """Bester Eintrag für ein (verstümmeltes) Wort, wenn er eindeutig genug passt.

        loose=False (sicher gelesener Text): nur Formverwechslungen wie i/l/!, rn/m, ii/ü –
        kein Vokaltausch, keine echten Fehler. Gibt (Begriff, relative Kosten) oder None."""
        core = w.strip(".,:;")
        if len(core) < 4 or _DIGITS.search(core):
            return None
        f = _fold(core)
        if f in self.words:
            return self.words[f], 0.0
        if self.inflected(core):
            return None
        L = len(core)
        cands = []
        for k, v in self.words.items():
            if abs(len(k) - L) > 2 or len(v) < 4:
                continue
            cost, full = distance(core, v, loose)
            limit = _budget(max(L, len(v))) if loose else 0
            if full > limit:
                continue
            if min(L, len(v)) <= 5 and cost > 0.5:
                continue                  # kurze Wörter: höchstens eine Verwechslung
            rel = cost / max(len(v), L)
            # mit echtem Fehler nur, wenn der Rest sehr gut passt
            if rel > (0.2 if full or max(L, len(v)) <= 6 else 0.25):
                continue
            cands.append((rel, cost, v))
        if not cands:
            return None
        cands.sort()
        rel, cost, v = cands[0]
        # eindeutig: der zweitbeste ist klar schlechter
        if len(cands) > 1 and cands[1][0] - rel < 0.06 and cands[1][2].lower() != v.lower():
            return None
        return v, rel


def _case_like(src: str, word: str) -> str:
    """Schreibweise des Treffers an die gelesene anpassen (GROSS / Groß / klein)."""
    letters = [c for c in src if c.isalpha()]
    if len(letters) > 1 and sum(c.isupper() for c in letters) >= 0.6 * len(letters):
        return word.upper()
    if letters and letters[0].isupper():
        return word[0].upper() + word[1:]
    return word


def correct(text: str, lex: Lexicon, sure: bool = False) -> Tuple[str, int, int]:
    """Korrigiert die Wörter eines Textes.

    sure: Text wurde sicher gelesen – dann nur Formverwechslungen und fehlende Umlaute.
    Gibt (Text, Anzahl Wörter, davon im Wörterbuch bzw. eindeutig korrigiert) zurück –
    gezählt werden nur Wörter aus Buchstaben (ab 3 Zeichen)."""
    toks = text.split(" ")
    out: List[str] = []
    n_words = n_known = 0
    for i, t in enumerate(toks):
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        core = t.rstrip(".,:;")
        tail = t[len(core):]
        if not core or not _ALPHA.match(t):
            out.append(t)
            continue
        # Abkürzung vor einer Zahl (z. B. „Poe 05“ → „Pos 05“)
        if len(core) <= 3 and nxt and nxt[:1].isdigit():
            fix = None if sure else _abbrev(core, lex)
            known = fix is not None or core.lower() in lex.abbrev
            out.append((fix or core) + tail)
            if len(core) >= 3:
                n_words += 1
                n_known += known
            continue
        if len(core) < 3:
            out.append(t)
            continue
        n_words += 1
        if core in lex:
            n_known += 1
            ref = lex.words[_fold(core)]
            regular = core.isupper() or core.islower() or core.istitle()
            # nur fehlende Umlaute ergänzen („Kuche“ → „Küche“), „ss“ bleibt „ss“
            if ref.lower() != core.lower() and ref.lower().replace("ß", "ss") != core.lower():
                out.append(_case_like(core, ref) + tail)
            elif not regular:
                out.append(_case_like(core, core) + tail)
            else:
                out.append(t)
            continue
        if lex.inflected(core):
            n_known += 1
            out.append(t)
            continue
        hit = lex.best(core, loose=not sure)
        if hit is None:
            out.append(t)
            continue
        n_known += 1
        out.append(_case_like(core, hit[0]) + tail)
    return " ".join(out), n_words, n_known


def _abbrev(core: str, lex: Lexicon) -> Optional[str]:
    if core.lower() in lex.abbrev:
        return lex.abbrev[core.lower()]
    best = None
    for k, v in lex.abbrev.items():
        if len(k) != len(core) or k[0] != core[0].lower():
            continue
        d, full = distance(core, v)
        if full <= 1 and d <= 1.4 and (best is None or d < best[0]):
            best = (d, v)
    return best[1] if best else None


def from_texts(texts: Iterable[str], min_len: int = 5) -> Set[str]:
    """Wörter aus sicher gelesenen Texten (für das planeigene Wörterbuch)."""
    out = set()
    for t in texts:
        for w in t.split():
            w = w.strip(".,:;()")
            if len(w) >= min_len and w.isalpha():
                out.add(w)
    return out
