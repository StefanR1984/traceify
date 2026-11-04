"""Update-Prüfung und -Installation über die GitHub-Releases (nur Standardbibliothek).

Ablauf beim echten Update:
  1. ``check()``      – neueste Release-Version von GitHub holen und vergleichen
  2. ``download()``   – Setup.exe mit Fortschritt in einen Temp-Ordner laden und prüfen
                        (Dateigröße, SHA-256 aus der GitHub-API, EXE-Kennung „MZ“)
  3. ``launch_installer()`` – Setup still starten; es wartet, bis Traceify beendet ist,
                        installiert drüber und startet Traceify danach neu.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

from . import __version__

REPO = "StefanR1984/traceify"
API_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_URL = f"https://github.com/{REPO}/releases/latest"
CHECK_INTERVAL = 24 * 3600


@dataclass
class UpdateInfo:
    version: str
    url: str            # Release-Seite
    setup_url: str      # direkter Download der Setup.exe (falls vorhanden)
    notes: str
    setup_name: str = ""     # Dateiname der Setup.exe
    setup_size: int = 0      # Größe laut GitHub (0 = unbekannt)
    setup_sha256: str = ""   # Prüfsumme laut GitHub (leer = unbekannt)


class UpdateError(Exception):
    pass


class Cancelled(UpdateError):
    pass


def parse_version(v: str) -> tuple:
    nums = re.findall(r"\d+", v or "")
    return tuple(int(n) for n in nums[:3]) + (0,) * (3 - len(nums[:3]))


def is_newer(remote: str, local: str = __version__) -> bool:
    return parse_version(remote) > parse_version(local)


def fetch_latest(timeout: float = 6) -> Optional[UpdateInfo]:
    req = urllib.request.Request(API_URL, headers={"Accept": "application/vnd.github+json",
                                                   "User-Agent": f"Traceify/{__version__}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    return parse_release(data)


def parse_release(data: dict) -> UpdateInfo:
    tag = data.get("tag_name", "")
    asset = next((a for a in data.get("assets", [])
                  if a.get("name", "").lower().startswith("traceify-setup")
                  and a.get("name", "").lower().endswith(".exe")), {})
    digest = asset.get("digest") or ""
    sha = digest.split(":", 1)[1].lower() if digest.lower().startswith("sha256:") else ""
    return UpdateInfo(tag.lstrip("vV."), data.get("html_url") or RELEASES_URL,
                      asset.get("browser_download_url", ""), (data.get("body") or "")[:4000],
                      asset.get("name", ""), int(asset.get("size") or 0), sha)


def check(force: bool = False) -> Optional[UpdateInfo]:
    """Neuere Version oder None. Ohne force höchstens einmal pro Tag (Zeitstempel in config)."""
    from . import config
    cfg = config.load()
    if not force:
        if cfg.get("update_check") is False:
            return None
        if time.time() - float(cfg.get("update_last_check") or 0) < CHECK_INTERVAL:
            return None
    try:
        info = fetch_latest()
    except Exception:
        return None
    finally:
        config.save({"update_last_check": time.time()})
    if info and is_newer(info.version):
        if not force and cfg.get("update_skip") == info.version:
            return None
        return info
    return None


# ---------------------------------------------------------------- Installation

def can_self_update() -> bool:
    """Nur die per Setup installierte Windows-EXE kann sich selbst aktualisieren.

    Portable ZIP und Start aus dem Quellcode bekommen weiterhin nur den Download-Link.
    """
    if os.name != "nt" or not getattr(sys, "frozen", False):
        return False
    app_dir = os.path.dirname(os.path.abspath(sys.executable))
    return any(f.lower().startswith("unins") and f.lower().endswith(".exe")
               for f in os.listdir(app_dir))


def download_dir() -> str:
    d = os.path.join(tempfile.gettempdir(), "Traceify-Update")
    os.makedirs(d, exist_ok=True)
    return d


def _safe_name(info: UpdateInfo) -> str:
    name = os.path.basename(info.setup_name or f"Traceify-Setup-{info.version}.exe")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return name if name.lower().endswith(".exe") else name + ".exe"


def download(info: UpdateInfo, dest_dir: Optional[str] = None,
             progress: Optional[Callable[[int, int], None]] = None,
             cancelled: Optional[Callable[[], bool]] = None,
             timeout: float = 30) -> str:
    """Lädt die Setup.exe herunter, prüft sie und gibt den Pfad zurück.

    progress(geladen, gesamt) – gesamt ist 0, wenn unbekannt.
    cancelled() – liefert True, wenn der Nutzer abbricht (wirft dann ``Cancelled``).
    """
    if not info.setup_url:
        raise UpdateError("Im Release ist keine Setup-Datei enthalten.")
    if not info.setup_url.lower().startswith("https://"):
        raise UpdateError("Unsichere Download-Adresse (kein https).")
    dest_dir = dest_dir or download_dir()
    target = os.path.join(dest_dir, _safe_name(info))
    # fertige, gültige Datei aus einem früheren Versuch wiederverwenden
    if os.path.exists(target) and info.setup_sha256:
        try:
            verify(target, info)
            if progress:
                progress(info.setup_size, info.setup_size)
            return target
        except UpdateError:
            pass
    part = target + ".part"
    req = urllib.request.Request(info.setup_url, headers={
        "Accept": "application/octet-stream", "User-Agent": f"Traceify/{__version__}"})
    h = hashlib.sha256()
    done = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0) or info.setup_size
            while True:
                if cancelled and cancelled():
                    raise Cancelled("Download abgebrochen.")
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                h.update(chunk)
                done += len(chunk)
                if progress:
                    progress(done, total)
        verify(part, info, sha256=h.hexdigest())
        os.replace(part, target)
    except BaseException:
        try:
            os.remove(part)
        except OSError:
            pass
        raise
    return target


def verify(path: str, info: UpdateInfo, sha256: Optional[str] = None) -> None:
    """Wirft ``UpdateError``, wenn die Datei nicht zum Release passt."""
    size = os.path.getsize(path)
    if size < 1024:
        raise UpdateError("Die heruntergeladene Datei ist unvollständig.")
    if info.setup_size and size != info.setup_size:
        raise UpdateError(f"Dateigröße stimmt nicht ({size} statt {info.setup_size} Bytes).")
    with open(path, "rb") as f:
        if f.read(2) != b"MZ":
            raise UpdateError("Die heruntergeladene Datei ist kein Windows-Programm.")
    if info.setup_sha256:
        if sha256 is None:
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            sha256 = h.hexdigest()
        if sha256.lower() != info.setup_sha256.lower():
            raise UpdateError("Prüfsumme (SHA-256) stimmt nicht – Download beschädigt.")


def installer_args(setup: str, pid: Optional[int] = None) -> list:
    """Befehlszeile für das stille Update per Inno Setup.

    /UPDATE und /WAITPID werden vom Setup-Skript (traceify.iss) ausgewertet:
    warten, bis Traceify beendet ist, und danach Traceify neu starten.
    """
    log = os.path.join(os.path.dirname(setup), "update-setup.log")
    return [setup, "/SILENT", "/SP-", "/SUPPRESSMSGBOXES", "/NORESTART",
            "/CLOSEAPPLICATIONS", "/NORESTARTAPPLICATIONS", f"/LOG={log}",
            "/UPDATE=1", f"/WAITPID={pid if pid is not None else os.getpid()}"]


def launch_installer(setup: str, popen=subprocess.Popen) -> None:
    """Startet das Setup unabhängig von Traceify. Danach muss Traceify sich beenden."""
    kw = {}
    if os.name == "nt":
        kw["creationflags"] = (getattr(subprocess, "DETACHED_PROCESS", 0)
                               | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
        kw["close_fds"] = True
    popen(installer_args(setup), **kw)
