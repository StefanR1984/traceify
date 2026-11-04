"""DWG-Export über den kostenlosen ODA File Converter (Open Design Alliance).

Traceify schreibt zuerst eine DXF-Datei und lässt sie vom ODA File Converter
im Hintergrund nach DWG umwandeln. Der Converter muss separat installiert sein:
https://www.opendesign.com/guestfiles/oda_file_converter
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import tempfile

from ..core.model import Drawing
from .dxf import export_dxf

ODA_DOWNLOAD_URL = "https://www.opendesign.com/guestfiles/oda_file_converter"

# DXF-Version (Traceify) -> Ausgabeversion des ODA File Converters
ODA_VERSIONS = {"R12": "ACAD12", "R2000": "ACAD2000", "R2007": "ACAD2007",
                "R2010": "ACAD2010", "R2013": "ACAD2013", "R2018": "ACAD2018"}


def find_oda() -> str | None:
    """Pfad zur ODAFileConverter(.exe) oder None."""
    try:
        from .. import config
        p = config.load().get("oda_path")
        if p and os.path.isfile(p):
            return p
    except Exception:
        pass
    w = shutil.which("ODAFileConverter")
    if w:
        return w
    cands = []
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                 os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                 os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
        cands += glob.glob(os.path.join(base, "ODA", "ODAFileConverter*", "ODAFileConverter.exe"))
    cands += glob.glob("/usr/bin/ODAFileConverter*") + glob.glob("/opt/ODA*/ODAFileConverter*")
    cands = [c for c in cands if os.path.isfile(c)]
    return sorted(cands)[-1] if cands else None  # neueste Version


def available() -> bool:
    return find_oda() is not None


def export_dwg(d: Drawing, path: str, version: str = "R2018", visible_layers=None,
               oda: str | None = None, timeout: int = 120) -> None:
    oda = oda or find_oda()
    if not oda:
        raise RuntimeError("Für den DWG-Export wird der kostenlose ODA File Converter benötigt:\n"
                           + ODA_DOWNLOAD_URL)
    out_ver = ODA_VERSIONS.get(version, "ACAD2018")
    with tempfile.TemporaryDirectory(prefix="traceify_dwg_") as tmp:
        src_dir = os.path.join(tmp, "in")
        dst_dir = os.path.join(tmp, "out")
        os.makedirs(src_dir)
        os.makedirs(dst_dir)
        name = "zeichnung"
        export_dxf(d, os.path.join(src_dir, name + ".dxf"), version, visible_layers)
        # Aufruf: Eingabeordner Ausgabeordner Version Typ Rekursiv Prüfen [Filter]
        cmd = [oda, src_dir, dst_dir, out_ver, "DWG", "0", "1", "*.DXF"]
        kw = {}
        if os.name == "nt":
            kw["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, **kw)
        produced = glob.glob(os.path.join(dst_dir, "*.dwg")) + \
            glob.glob(os.path.join(dst_dir, "*.DWG"))
        if not produced:
            msg = (r.stdout or "") + (r.stderr or "")
            errs = glob.glob(os.path.join(dst_dir, "*.err"))
            if errs:
                with open(errs[0], encoding="utf-8", errors="replace") as f:
                    msg += f.read()
            raise RuntimeError("Der ODA File Converter hat keine DWG erzeugt.\n" + msg.strip()[:800])
        shutil.move(produced[0], path)
