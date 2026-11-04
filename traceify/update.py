"""Update-Prüfung über die GitHub-Releases (nur Standardbibliothek)."""
from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass
from typing import Optional

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
    tag = data.get("tag_name", "")
    setup = next((a.get("browser_download_url", "") for a in data.get("assets", [])
                  if a.get("name", "").lower().startswith("traceify-setup")), "")
    return UpdateInfo(tag.lstrip("vV."), data.get("html_url") or RELEASES_URL, setup,
                      (data.get("body") or "")[:4000])


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
