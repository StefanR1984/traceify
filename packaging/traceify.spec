# -*- mode: python ; coding: utf-8 -*-
# PyInstaller-Bauplan für Traceify (Windows).
# Aufruf aus dem Projektordner:  pyinstaller --noconfirm packaging/traceify.spec
#
# Tesseract OCR wird NICHT über PyInstaller eingesammelt, sondern nach dem Build als Ordner
# dist/Traceify/tesseract/ neben die EXE kopiert (siehe .github/workflows/release.yml).
import os
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
ASSETS = os.path.join(ROOT, "traceify", "assets")

datas = [(ASSETS, "traceify/assets")]
datas += collect_data_files("ezdxf")
datas += collect_data_files("skimage", includes=["**/*.pyi"])  # lazy_loader-Stubs
binaries = []

hiddenimports = []
hiddenimports += collect_submodules("skimage.morphology")
hiddenimports += collect_submodules("traceify")
hiddenimports += ["pytesseract", "pymupdf", "PIL.ImageQt", "shapely"]
hiddenimports += collect_submodules("shapely")

excludes = ["tkinter", "matplotlib", "IPython", "pytest", "PyQt5", "PyQt6", "sklearn", "pandas",
            "lxml", "pyinstaller",
            "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.Qt3DCore",
            "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia", "PySide6.QtCharts",
            "PySide6.QtDataVisualization", "PySide6.QtPdf"]

icon = os.path.join(ASSETS, "traceify.ico")

a = Analysis(
    [os.path.join(SPECPATH, "launcher.py")],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=excludes,
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Traceify",
    icon=icon,
    console=False,
    upx=False,
    version=os.path.join(SPECPATH, "windows", "version_info.txt") if sys.platform == "win32"
    and os.path.exists(os.path.join(SPECPATH, "windows", "version_info.txt")) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="Traceify",
)

