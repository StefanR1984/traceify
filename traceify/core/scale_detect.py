"""Zeichnungsmaßstab („M 1:100“, „Maßstab 1:50“, „SCALE 1:20“) aus erkannten Texten lesen."""
from __future__ import annotations

import re
from typing import Iterable, Optional

_WITH_PREFIX = re.compile(
    r"(?:\bM\b|\bMST\b|MA(?:SS|ß)STAB|\bSCALE\b|\bMASST\b)\.?\s*[:=]?\s*1\s*[:/]\s*(\d{1,5}(?:[.,]\d)?)",
    re.IGNORECASE)
_PLAIN = re.compile(r"(?<![\d.,/:])1\s*:\s*(\d{1,5})(?![\d.,:])")

COMMON = {1, 2, 2.5, 5, 10, 20, 25, 50, 75, 100, 125, 200, 250, 500, 1000, 2000, 2500, 5000,
          10000, 25000, 50000}


def find_scale(texts: Iterable[str]) -> Optional[float]:
    """Gibt N für „1:N“ zurück (z. B. 100) oder None.

    Bevorzugt Angaben mit Präfix (M, Maßstab, Scale). „1:N“ ohne Präfix wird nur
    akzeptiert, wenn N ein üblicher Maßstab ist und genau ein solcher Wert vorkommt.
    """
    texts = [t for t in texts if t]
    for t in texts:
        m = _WITH_PREFIX.search(t)
        if m:
            n = float(m.group(1).replace(",", "."))
            if 0 < n <= 100000:
                return n
    plain = set()
    for t in texts:
        for m in _PLAIN.finditer(t):
            n = float(m.group(1))
            if n in COMMON and n > 1:
                plain.add(n)
    if len(plain) == 1:
        return plain.pop()
    return None


def format_scale(n: float) -> str:
    return f"1:{int(n) if float(n).is_integer() else n}"
