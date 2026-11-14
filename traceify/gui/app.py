"""Startpunkt der Desktop-Anwendung."""
import os
import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from .main_window import MainWindow

    from ..support import setup_logging
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Traceify")
    app.setOrganizationName("Traceify")
    app.setStyle("Fusion")
    from PySide6.QtGui import QIcon
    icon = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "traceify.png")
    if os.path.exists(icon):
        app.setWindowIcon(QIcon(icon))
    if os.name == "nt":  # eigenes Taskleisten-Icon statt Python-Icon
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Traceify.Desktop")
        except Exception:
            pass
    from .single import forward, listen
    args = [os.path.abspath(a) for a in sys.argv[1:] if os.path.isfile(a)]
    if args and forward(args):
        return 0                   # läuft schon: Datei dort öffnen, kein zweites Fenster
    w = MainWindow()
    w._single = listen(w.open_dropped, parent=w)
    w.show()
    if args:
        w.open_dropped(args)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
