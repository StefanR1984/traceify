"""Einstiegspunkt der gebündelten Anwendung (PyInstaller)."""
import multiprocessing

from traceify.__main__ import run

if __name__ == "__main__":
    multiprocessing.freeze_support()
    run()
