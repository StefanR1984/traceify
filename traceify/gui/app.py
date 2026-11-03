"""Startpunkt der Desktop-Anwendung."""
import os
import sys


def main() -> int:
    from PySide6.QtWidgets import QApplication

    from .main_window import MainWindow

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
    w = MainWindow()
    w.show()
    args = [a for a in sys.argv[1:] if os.path.isfile(a)]
    if args:
        w.open_file(args[0])
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
