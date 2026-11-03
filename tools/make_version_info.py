"""Schreibt packaging/windows/version_info.txt (Dateieigenschaften der Traceify.exe)."""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def version() -> str:
    with open(os.path.join(ROOT, "traceify", "__init__.py"), encoding="utf-8") as f:
        return re.search(r'__version__\s*=\s*"([^"]+)"', f.read()).group(1)


def main() -> int:
    v = version()
    nums = [int(x) for x in re.findall(r"\d+", v)[:3]] + [0, 0, 0, 0]
    t = tuple(nums[:4])
    text = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={t}, prodvers={t}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040704B0', [
      StringStruct('CompanyName', 'Traceify'),
      StringStruct('FileDescription', 'Traceify - Raster und PDF nach CAD/CNC'),
      StringStruct('FileVersion', '{v}'),
      StringStruct('InternalName', 'Traceify'),
      StringStruct('LegalCopyright', 'GNU AGPL v3 or later'),
      StringStruct('OriginalFilename', 'Traceify.exe'),
      StringStruct('ProductName', 'Traceify'),
      StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [1031, 1200])])
  ]
)
"""
    out = os.path.join(ROOT, "packaging", "windows", "version_info.txt")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(v)
    return 0


if __name__ == "__main__":
    sys.exit(main())
