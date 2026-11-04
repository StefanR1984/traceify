"""Traceify – automatische Einrichtung aller Komponenten.

Nur Standardbibliothek: Dieses Skript läuft mit dem System-Python, bevor
irgendetwas installiert ist. Es wird von den Startdateien aufgerufen und kann
auch aus der Anwendung heraus genutzt werden (Menü Werkzeuge → Komponenten).

Schritte:
  1. Virtuelle Python-Umgebung (.venv) anlegen
  2. Python-Bibliotheken installieren (requirements.txt)
  3. Tesseract OCR installieren (falls nicht vorhanden)
  4. Sprachdaten Deutsch/Englisch herunterladen (Ordner tessdata)
  5. Ollama installieren und ein KI-Modell laden (optional, wird einmal gefragt)
  6. config.json schreiben

Aufruf:  python traceify/installer.py [--ja] [--ohne-ki] [--modell NAME] [--nur-pruefen]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

IS_WIN = os.name == "nt"
IS_MAC = sys.platform == "darwin"
IS_LINUX = sys.platform.startswith("linux")
FROZEN = bool(getattr(sys, "frozen", False))  # als EXE/App gepackt (PyInstaller)

if FROZEN:
    APP_DIR = os.path.dirname(os.path.abspath(sys.executable))
else:
    APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def user_data_dir() -> str:
    """Beschreibbarer Ordner für Einstellungen und Daten (auch bei Installation in Programme)."""
    if IS_WIN:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "Traceify")
    elif IS_MAC:
        d = os.path.expanduser("~/Library/Application Support/Traceify")
    else:
        d = os.path.join(os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config"),
                         "traceify")
    os.makedirs(d, exist_ok=True)
    return d


VENV_DIR = os.path.join(APP_DIR, ".venv")
CONFIG_PATH = os.path.join(user_data_dir(), "config.json")
TESSDATA_DIR = os.path.join(user_data_dir(), "tessdata")
REQ_PATH = os.path.join(APP_DIR, "requirements.txt")


def bundled_tesseract():
    """In der Windows-EXE mitgeliefertes Tesseract: (tesseract.exe, tessdata) oder (None, None)."""
    roots = [APP_DIR, getattr(sys, "_MEIPASS", "")]
    for r in roots:
        exe = os.path.join(r, "tesseract", "tesseract.exe" if IS_WIN else "tesseract")
        if r and os.path.isfile(exe):
            td = os.path.join(r, "tesseract", "tessdata")
            return exe, (td if os.path.isdir(td) else None)
    return None, None

TESSERACT_WIN_URL = ("https://github.com/tesseract-ocr/tesseract/releases/download/5.5.3/"
                     "tesseract-ocr-w64-setup-5.5.3.20260724.exe")
TESSDATA_URL = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/{lang}.traineddata"
TESS_LANGS = ["eng", "deu"]
OLLAMA_WIN_URL = "https://ollama.com/download/OllamaSetup.exe"
OLLAMA_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "gemma3:4b"

LOG = print  # wird von der GUI ersetzt


# ---------------------------------------------------------------- Hilfen
def log(msg: str) -> None:
    LOG(msg)


def load_config() -> dict:
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


def run(cmd, check=True, **kw) -> int:
    log("  > " + (cmd if isinstance(cmd, str) else " ".join(cmd)))
    r = subprocess.run(cmd, **kw)
    if check and r.returncode != 0:
        raise RuntimeError(f"Befehl fehlgeschlagen ({r.returncode})")
    return r.returncode


def have(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def download(url: str, dest: str, label: str = "") -> None:
    log(f"  Lade {label or os.path.basename(dest)} …")
    tmp = dest + ".part"
    req = urllib.request.Request(url, headers={"User-Agent": "Traceify-Installer"})
    with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done, last = 0, 0.0
        while True:
            chunk = r.read(1 << 16)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total and time.time() - last > 1:
                last = time.time()
                log(f"    {done * 100 // total:3d} %  ({done // 1048576} / {total // 1048576} MB)")
    os.replace(tmp, dest)


def ask(question: str, default: bool, auto: bool | None) -> bool:
    if auto is not None:
        return auto
    if not sys.stdin or not sys.stdin.isatty():
        return default
    hint = "[J/n]" if default else "[j/N]"
    try:
        a = input(f"{question} {hint} ").strip().lower()
    except EOFError:
        return default
    return default if not a else a in ("j", "ja", "y", "yes")


def winget(pkg_id: str) -> bool:
    if not have("winget"):
        return False
    rc = run(["winget", "install", "-e", "--id", pkg_id, "--silent",
              "--accept-package-agreements", "--accept-source-agreements"], check=False)
    return rc == 0 or rc == -1978335189  # bereits installiert


def sudo_prefix():
    if IS_WIN or (hasattr(os, "geteuid") and os.geteuid() == 0):
        return []
    return ["sudo"] if have("sudo") else []


def linux_install(pkgs_apt, pkgs_dnf=None, pkgs_pacman=None) -> bool:
    s = sudo_prefix()
    if have("apt-get"):
        run(s + ["apt-get", "update"], check=False)
        return run(s + ["apt-get", "install", "-y"] + pkgs_apt, check=False) == 0
    if have("dnf") and pkgs_dnf:
        return run(s + ["dnf", "install", "-y"] + pkgs_dnf, check=False) == 0
    if have("pacman") and pkgs_pacman:
        return run(s + ["pacman", "-S", "--noconfirm"] + pkgs_pacman, check=False) == 0
    return False


# ---------------------------------------------------------- 1+2 Python
def venv_python() -> str:
    return os.path.join(VENV_DIR, "Scripts" if IS_WIN else "bin",
                        "python.exe" if IS_WIN else "python")


def ensure_venv() -> str:
    py = venv_python()
    if os.path.exists(py):
        return py
    log("Lege Python-Umgebung an …")
    try:
        run([sys.executable, "-m", "venv", VENV_DIR])
    except Exception:
        if IS_LINUX:
            log("  venv-Modul fehlt – installiere python3-venv …")
            v = f"{sys.version_info.major}.{sys.version_info.minor}"
            linux_install([f"python{v}-venv", "python3-venv"])
            shutil.rmtree(VENV_DIR, ignore_errors=True)
            run([sys.executable, "-m", "venv", VENV_DIR])
        else:
            raise
    return py


def ensure_packages(py: str) -> None:
    with open(REQ_PATH, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    marker = os.path.join(VENV_DIR, ".requirements.sha256")
    try:
        if open(marker).read().strip() == digest:
            log("Python-Bibliotheken: aktuell ✓")
            return
    except OSError:
        pass
    log("Installiere Python-Bibliotheken (einmalig, einige Minuten) …")
    run([py, "-m", "pip", "install", "--upgrade", "pip", "-q"], check=False)
    run([py, "-m", "pip", "install", "-r", REQ_PATH])
    with open(marker, "w") as f:
        f.write(digest)
    if IS_LINUX:  # Qt benötigt unter Linux einige Systembibliotheken
        if have("apt-get") and subprocess.run(["dpkg", "-s", "libxcb-cursor0"],
                                              capture_output=True).returncode != 0:
            log("Installiere Qt-Systembibliotheken …")
            linux_install(["libxcb-cursor0", "libxkbcommon-x11-0", "libegl1"])
    log("Python-Bibliotheken: installiert ✓")


# ---------------------------------------------------------- 3 Tesseract
def find_tesseract() -> str | None:
    b, _ = bundled_tesseract()
    if b:
        return b
    cfg = load_config().get("tesseract_cmd")
    cands = [cfg] if cfg else []
    w = shutil.which("tesseract")
    if w:
        cands.append(w)
    if IS_WIN:
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
            cands.append(os.path.join(base, "Tesseract-OCR", "tesseract.exe"))
    else:
        cands += ["/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract", "/usr/bin/tesseract"]
    for c in cands:
        if c and os.path.isfile(c):
            return c
    return None


def install_tesseract() -> str | None:
    log("Tesseract OCR wird installiert …")
    if IS_WIN:
        if not winget("UB-Mannheim.TesseractOCR"):
            exe = os.path.join(tempfile.gettempdir(), "tesseract-setup.exe")
            download(TESSERACT_WIN_URL, exe, "Tesseract-Installer")
            log("  Installer läuft (ggf. Administrator-Abfrage bestätigen) …")
            run([exe, "/S"], check=False)
    elif IS_MAC:
        if ensure_brew():
            run(["brew", "install", "tesseract"], check=False)
    elif IS_LINUX:
        linux_install(["tesseract-ocr"], ["tesseract"], ["tesseract"])
    return find_tesseract()


def ensure_tesseract(auto: bool | None = True) -> str | None:
    t = find_tesseract()
    if not t and ask("Tesseract (Texterkennung) fehlt. Jetzt installieren?", True, auto):
        try:
            t = install_tesseract()
        except Exception as exc:
            log(f"  Fehler: {exc}")
    log(f"Tesseract: {t} ✓" if t else "Tesseract: nicht verfügbar – OCR bleibt deaktiviert ✗")
    return t


def ensure_tessdata() -> str:
    os.makedirs(TESSDATA_DIR, exist_ok=True)
    for lang in TESS_LANGS:
        dest = os.path.join(TESSDATA_DIR, f"{lang}.traineddata")
        if os.path.exists(dest) and os.path.getsize(dest) > 100_000:
            continue
        try:
            download(TESSDATA_URL.format(lang=lang), dest, f"Sprachdaten {lang}")
        except Exception as exc:
            log(f"  Sprachdaten {lang} konnten nicht geladen werden: {exc}")
    have_langs = [l for l in TESS_LANGS if os.path.exists(os.path.join(TESSDATA_DIR, f"{l}.traineddata"))]
    log(f"OCR-Sprachdaten: {', '.join(have_langs) or 'keine'} ✓")
    return TESSDATA_DIR


def ensure_brew() -> bool:
    if have("brew") or os.path.exists("/opt/homebrew/bin/brew"):
        if not have("brew"):
            os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ["PATH"]
        return True
    log("Homebrew wird installiert (Passwort-Abfrage möglich) …")
    run('/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"',
        shell=True, check=False)
    if os.path.exists("/opt/homebrew/bin/brew"):
        os.environ["PATH"] = "/opt/homebrew/bin:" + os.environ["PATH"]
    return have("brew")


# ---------------------------------------------------------- 5 Ollama
def ollama_running(url: str = OLLAMA_URL) -> bool:
    try:
        with urllib.request.urlopen(url + "/api/version", timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def find_ollama() -> str | None:
    w = shutil.which("ollama")
    if w:
        return w
    cands = []
    if IS_WIN:
        cands.append(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Ollama", "ollama.exe"))
    elif IS_MAC:
        cands += ["/Applications/Ollama.app/Contents/Resources/ollama", "/opt/homebrew/bin/ollama",
                  "/usr/local/bin/ollama"]
    else:
        cands += ["/usr/local/bin/ollama", "/usr/bin/ollama"]
    return next((c for c in cands if os.path.isfile(c)), None)


def install_ollama() -> str | None:
    log("Ollama wird installiert …")
    if IS_WIN:
        if not winget("Ollama.Ollama"):
            exe = os.path.join(tempfile.gettempdir(), "OllamaSetup.exe")
            download(OLLAMA_WIN_URL, exe, "Ollama-Installer")
            run([exe, "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES"], check=False)
    elif IS_MAC:
        if ensure_brew():
            run(["brew", "install", "--cask", "ollama"], check=False)
            run(["open", "-a", "Ollama"], check=False)
    else:
        run("curl -fsSL https://ollama.com/install.sh | sh", shell=True, check=False)
    return find_ollama()


def start_ollama(exe: str | None = None) -> bool:
    if ollama_running():
        return True
    exe = exe or find_ollama()
    if not exe:
        return False
    log("Starte Ollama-Dienst …")
    kw = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if IS_WIN:
        kw["creationflags"] = 0x00000008 | 0x00000200  # DETACHED_PROCESS | NEW_PROCESS_GROUP
    else:
        kw["start_new_session"] = True
    try:
        subprocess.Popen([exe, "serve"], **kw)
    except Exception as exc:
        log(f"  Start fehlgeschlagen: {exc}")
        return False
    for _ in range(30):
        if ollama_running():
            return True
        time.sleep(1)
    return False


def installed_models(url: str = OLLAMA_URL) -> list:
    try:
        with urllib.request.urlopen(url + "/api/tags", timeout=5) as r:
            return [m["name"] for m in json.load(r).get("models", [])]
    except Exception:
        return []


def pull_model(model: str, url: str = OLLAMA_URL) -> bool:
    log(f"Lade KI-Modell {model} (einmalig, mehrere GB) …")
    req = urllib.request.Request(url + "/api/pull", data=json.dumps({"model": model}).encode(),
                                 headers={"Content-Type": "application/json"})
    last = 0.0
    try:
        with urllib.request.urlopen(req, timeout=3600) as r:
            for line in r:
                ev = json.loads(line)
                if "error" in ev:
                    log(f"  Fehler: {ev['error']}")
                    return False
                if ev.get("total") and time.time() - last > 2:
                    last = time.time()
                    log(f"    {ev.get('completed', 0) * 100 // ev['total']:3d} %  {ev.get('status', '')}")
    except Exception as exc:
        log(f"  Download fehlgeschlagen: {exc}")
        return False
    log(f"KI-Modell {model}: bereit ✓")
    return True


def ensure_ollama(cfg: dict, auto: bool | None, model: str | None) -> None:
    if cfg.get("ki") == "nein" and auto is None:
        log("KI (Ollama): deaktiviert (in config.json mit \"ki\": \"ja\" wieder aktivieren)")
        return
    exe = find_ollama()
    if not exe and not ollama_running():
        want = ask("KI-Funktionen nutzen? Dafür wird Ollama installiert (lokal, kostenlos).",
                   True, auto)
        cfg["ki"] = "ja" if want else "nein"
        save_config(cfg)
        if not want:
            return
        exe = install_ollama()
    cfg["ki"] = "ja"
    if not start_ollama(exe):
        log("Ollama: nicht erreichbar – KI-Funktionen erst nach Start von Ollama verfügbar ✗")
        return
    log("Ollama: läuft ✓")
    model = model or cfg.get("ollama_model") or DEFAULT_MODEL
    cfg["ollama_model"] = model
    have_models = installed_models()
    if any(m == model or m.split(":")[0] == model for m in have_models):
        log(f"KI-Modell {model}: vorhanden ✓")
    elif ask(f"KI-Modell {model} (ca. 3–8 GB) jetzt herunterladen?", True, auto):
        pull_model(model)
    save_config(cfg)


# ---------------------------------------------------------- Hauptablauf
def _tess_langs() -> list:
    dirs = [TESSDATA_DIR, bundled_tesseract()[1]]
    return [l for l in TESS_LANGS
            if any(d and os.path.exists(os.path.join(d, f"{l}.traineddata")) for d in dirs)]


def status() -> dict:
    """Kurzer Zustandsbericht (für den Komponenten-Dialog)."""
    langs = _tess_langs()
    return {
        "Programm": "gebündelte Version" if FROZEN else
        ("Python-Umgebung " + VENV_DIR if os.path.exists(venv_python()) else None),
        "Tesseract": find_tesseract(),
        "OCR-Sprachdaten": ", ".join(langs) if langs else None,
        "Ollama installiert": find_ollama(),
        "Ollama läuft": ollama_running(load_config().get("ollama_url", OLLAMA_URL)),
        "KI-Modelle": ", ".join(installed_models(load_config().get("ollama_url", OLLAMA_URL))) or None,
        "ODA File Converter (DWG)": _oda(),
    }


def _oda():
    try:
        from .export.dwg import find_oda
        return find_oda()
    except Exception:
        return None


def setup(auto: bool | None = None, with_ai: bool | None = None, model: str | None = None,
          python_env: bool = True) -> dict:
    log(f"=== Traceify-Einrichtung ({platform.system()} {platform.machine()}, "
        f"Python {platform.python_version()}) ===")
    if sys.version_info < (3, 10):
        raise SystemExit("Python 3.10 oder neuer wird benötigt.")
    cfg = load_config()
    if python_env and not FROZEN:
        py = ensure_venv()
        ensure_packages(py)
    t = ensure_tesseract(True if auto is None else auto)
    if t:
        cfg["tesseract_cmd"] = t
        bundled_data = bundled_tesseract()[1]
        cfg["tessdata_dir"] = bundled_data if (bundled_data and t == bundled_tesseract()[0]) \
            else ensure_tessdata()
    save_config(cfg)
    if with_ai is not False:
        ensure_ollama(cfg, with_ai if with_ai is not None else auto, model)
    cfg.setdefault("ollama_url", OLLAMA_URL)
    save_config(cfg)
    log("=== Einrichtung abgeschlossen ===")
    return cfg


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Traceify einrichten")
    p.add_argument("--ja", action="store_true", help="alle Fragen mit Ja beantworten")
    p.add_argument("--ohne-ki", action="store_true", help="Ollama nicht installieren")
    p.add_argument("--modell", help=f"KI-Modell (Standard: {DEFAULT_MODEL})")
    p.add_argument("--nur-pruefen", action="store_true", help="nur Zustand anzeigen")
    a, _rest = p.parse_known_args(argv)  # übrige Argumente gehören der Anwendung
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass
    if a.nur_pruefen:
        for k, v in status().items():
            print(f"{k:20s} {'✓ ' + str(v) if v else '✗ fehlt'}")
        return 0
    try:
        setup(auto=True if a.ja else None, with_ai=False if a.ohne_ki else None, model=a.modell)
    except Exception as exc:
        print(f"\nFEHLER bei der Einrichtung: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
