"""Protokolldatei, Umgebungsbericht und „Problem melden“ (GitHub-Issue vorbefüllt)."""
from __future__ import annotations

import logging
import logging.handlers
import os
import platform
import sys
import urllib.parse

from . import __version__

REPO = "StefanR1984/traceify"
log = logging.getLogger("traceify")


def log_path() -> str:
    from .installer import user_data_dir
    return os.path.join(user_data_dir(), "traceify.log")


def setup_logging() -> None:
    if getattr(setup_logging, "_done", False):
        return
    setup_logging._done = True
    try:
        h = logging.handlers.RotatingFileHandler(log_path(), maxBytes=1_000_000, backupCount=2,
                                                 encoding="utf-8")
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root = logging.getLogger()
        root.addHandler(h)
        root.setLevel(logging.INFO)
    except OSError:
        return
    log.info("Traceify %s gestartet (%s, Python %s)", __version__, platform.platform(),
             platform.python_version())
    prev = sys.excepthook

    def hook(et, ev, tb):
        log.error("Unbehandelter Fehler", exc_info=(et, ev, tb))
        if prev:
            prev(et, ev, tb)
    sys.excepthook = hook


def log_tail(lines: int = 60) -> str:
    try:
        with open(log_path(), encoding="utf-8", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except OSError:
        return ""


def environment_report() -> str:
    from . import config, installer
    from .core.ocr import _tesseract_cmd, available_languages
    from .export.dwg import find_oda
    cfg = config.load()
    tess = _tesseract_cmd()
    rows = [
        f"Traceify: {__version__} ({'installierte EXE' if installer.FROZEN else 'Quellcode'})",
        f"System: {platform.platform()} ({platform.machine()})",
        f"Python: {platform.python_version()}",
        f"Tesseract: {tess or 'nicht gefunden'}"
        + (f" – Sprachen: {', '.join(l for l in available_languages() if l in ('deu', 'eng'))}"
           if tess else ""),
        f"ODA File Converter (DWG): {'ja' if find_oda() else 'nein'}",
        f"KI: {cfg.get('ki') or '-'}, Modell: {cfg.get('ollama_model') or '-'}",
    ]
    try:
        rows.append(f"KI-Server: {cfg.get('ki_server') or 'ollama'}")
        rows.append(f"Ollama erreichbar: {'ja' if installer.ollama_running(cfg.get('ollama_url') or installer.OLLAMA_URL) else 'nein'}")
    except Exception:
        pass
    return "\n".join(rows)


def issue_url(kind: str = "fehler", title: str = "", what: str = "", settings_json: str = "",
              include_log: bool = True) -> str:
    """Link zu einem neuen, vorbefüllten GitHub-Issue (Formularfelder per Query-Parameter)."""
    params = {"template": "fehler.yml" if kind == "fehler" else "idee.yml"}
    if title:
        params["title"] = title
    if kind == "fehler":
        params["umgebung"] = environment_report()
        if what:
            params["beschreibung"] = what
        extra = ""
        if settings_json:
            extra += "Einstellungen:\n" + settings_json[:2500] + "\n"
        if include_log:
            tail = log_tail(30)
            if tail:
                extra += "\nProtokoll (Ende):\n" + tail[-2500:]
        if extra:
            params["protokoll"] = extra
    elif what:
        params["idee"] = what
    url = f"https://github.com/{REPO}/issues/new?" + urllib.parse.urlencode(params)
    return url[:7900]  # Browser/GitHub-Grenze
