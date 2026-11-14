"""Eine laufende Traceify-Instanz: Dateien, die auf das Programmsymbol gezogen werden
(oder per „Öffnen mit“ kommen), öffnen im bereits offenen Fenster statt in einem zweiten."""
from __future__ import annotations

import getpass
import re

from PySide6.QtCore import QByteArray
from PySide6.QtNetwork import QLocalServer, QLocalSocket


def server_name() -> str:
    try:
        user = getpass.getuser()
    except Exception:
        user = "nutzer"
    return "Traceify-" + re.sub(r"\W", "_", user)


def forward(paths, name: str | None = None, timeout_ms: int = 1000) -> bool:
    """Schickt Dateipfade an eine laufende Instanz. True, wenn sie angenommen wurden."""
    sock = QLocalSocket()
    sock.connectToServer(name or server_name())
    if not sock.waitForConnected(timeout_ms):
        return False
    sock.write(QByteArray("\n".join(paths).encode("utf-8")))
    ok = sock.waitForBytesWritten(timeout_ms)
    sock.disconnectFromServer()
    if sock.state() != QLocalSocket.UnconnectedState:
        sock.waitForDisconnected(timeout_ms)
    return ok


def listen(on_paths, name: str | None = None, parent=None) -> QLocalServer | None:
    """Nimmt Pfade anderer Starts an und ruft on_paths(liste) auf. None, wenn schon belegt."""
    name = name or server_name()
    srv = QLocalServer(parent)
    if not srv.listen(name):
        # Rest eines abgestürzten Laufs (unter Windows selten) – freigeben und neu versuchen
        QLocalServer.removeServer(name)
        if not srv.listen(name):
            return None

    def accept():
        while srv.hasPendingConnections():
            c = srv.nextPendingConnection()
            buf = bytearray()

            def read(c=c, buf=buf):
                buf.extend(bytes(c.readAll()))

            def done(c=c, buf=buf):
                try:
                    read()
                except RuntimeError:     # Socket von Qt schon freigegeben – Daten sind da
                    pass
                paths = [p for p in buf.decode("utf-8", "replace").split("\n") if p]
                c.deleteLater()
                if paths:
                    on_paths(paths)

            c.readyRead.connect(read)
            c.disconnected.connect(done)

    srv.newConnection.connect(accept)
    return srv
