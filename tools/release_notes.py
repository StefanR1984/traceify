"""Erzeugt release_notes.md aus dem passenden Abschnitt in CHANGELOG.md.

Aufruf:  python tools/release_notes.py 0.3.2 [ausgabe.md]
(In Python statt PowerShell, weil deutsche Anführungszeichen dort als
Zeichenketten-Begrenzer gelten.)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def section(version: str) -> str:
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as f:
        text = f.read()
    m = re.search(rf"^## {re.escape(version)}\b.*?$\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def main() -> int:
    v = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "release_notes.md"
    intro = (f"**Download:** `Traceify-Setup-{v}.exe` herunterladen und ausführen "
             f"(Windows 10/11, 64 Bit). Ohne Installation: `Traceify-Portable-{v}.zip` "
             "entpacken und `Traceify.exe` starten.\n\n"
             "> Die EXE ist noch nicht digital signiert. Zeigt Windows „Der Computer wurde "
             "durch Windows geschützt“, auf **Weitere Informationen → Trotzdem ausführen** "
             "klicken.\n")
    body = section(v) or "_Keine Änderungsnotizen gefunden._"
    with open(out, "w", encoding="utf-8") as f:
        f.write(intro + "\n" + body + "\n")
    print(open(out, encoding="utf-8").read())
    return 0


if __name__ == "__main__":
    sys.exit(main())
