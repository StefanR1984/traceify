"""Zentrale Konfiguration (config.json im Programmordner, vom Installer geschrieben)."""
from __future__ import annotations

import json

from .installer import CONFIG_PATH  # Benutzerordner (auch für die EXE)

DEFAULTS = {
    "tesseract_cmd": None,
    "tessdata_dir": None,
    "ki": None,                      # "ja" / "nein"
    "ollama_url": "http://127.0.0.1:11434",
    "ollama_model": "gemma3:4b",
    "ollama_timeout": 300,
}


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save(updates: dict) -> dict:
    cfg = load()
    cfg.update(updates)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except OSError:
        pass
    return cfg
