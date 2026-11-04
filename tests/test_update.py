"""Echter Updater: Release lesen, Setup laden und prüfen, stilles Setup starten."""
import hashlib
import io
import os

import pytest

from traceify import update

PAYLOAD = b"MZ" + bytes(range(256)) * 2000          # ~512 KB „EXE“
SHA = hashlib.sha256(PAYLOAD).hexdigest()


class FakeResp(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def info(**kw):
    d = dict(version="9.9.9", url="https://github.com/x/releases/tag/v9.9.9",
             setup_url="https://github.com/x/Traceify-Setup-9.9.9.exe", notes="",
             setup_name="Traceify-Setup-9.9.9.exe", setup_size=len(PAYLOAD), setup_sha256=SHA)
    d.update(kw)
    return update.UpdateInfo(**d)


@pytest.fixture
def served(monkeypatch):
    calls = []

    def fake_urlopen(req, timeout=0):
        calls.append(req.full_url)
        return FakeResp(PAYLOAD)
    monkeypatch.setattr(update.urllib.request, "urlopen", fake_urlopen)
    return calls


def test_parse_release_digest_and_asset():
    i = update.parse_release({
        "tag_name": "v1.2.3", "html_url": "https://h", "body": "Neu",
        "assets": [{"name": "Traceify-1.2.3-portable.zip", "browser_download_url": "https://z"},
                   {"name": "Traceify-Setup-1.2.3.exe", "browser_download_url": "https://s",
                    "size": 1234, "digest": "sha256:ABCDEF"}]})
    assert (i.version, i.setup_url, i.setup_size, i.setup_sha256) == ("1.2.3", "https://s",
                                                                       1234, "abcdef")
    assert update.parse_release({"tag_name": "v1.0.0"}).setup_url == ""


def test_download_ok_with_progress(tmp_path, served):
    seen = []
    p = update.download(info(), str(tmp_path), progress=lambda d, t: seen.append((d, t)))
    assert open(p, "rb").read() == PAYLOAD
    assert os.path.basename(p) == "Traceify-Setup-9.9.9.exe"
    assert seen[-1] == (len(PAYLOAD), len(PAYLOAD)) and len(seen) > 1
    assert not os.path.exists(p + ".part")
    # zweiter Aufruf nutzt die bereits geprüfte Datei
    update.download(info(), str(tmp_path))
    assert len(served) == 1


@pytest.mark.parametrize("kw, msg", [
    (dict(setup_sha256="0" * 64), "Prüfsumme"),
    (dict(setup_size=5), "Dateigröße"),
    (dict(setup_url="http://unsicher/x.exe"), "https"),
    (dict(setup_url=""), "keine Setup"),
])
def test_download_rejects(tmp_path, served, kw, msg):
    with pytest.raises(update.UpdateError, match=msg):
        update.download(info(**kw), str(tmp_path))
    assert not [f for f in os.listdir(tmp_path)]   # nichts liegen gelassen


def test_download_not_exe(tmp_path, monkeypatch):
    monkeypatch.setattr(update.urllib.request, "urlopen",
                        lambda req, timeout=0: FakeResp(b"<html>" * 500))
    with pytest.raises(update.UpdateError, match="kein Windows-Programm"):
        update.download(info(setup_size=0, setup_sha256=""), str(tmp_path))


def test_download_cancel(tmp_path, served):
    with pytest.raises(update.Cancelled):
        update.download(info(), str(tmp_path), cancelled=lambda: True)
    assert not os.listdir(tmp_path)


def test_installer_args_and_launch(tmp_path):
    setup = str(tmp_path / "Traceify-Setup-9.9.9.exe")
    args = update.installer_args(setup, pid=4711)
    assert args[0] == setup and "/SILENT" in args and "/UPDATE=1" in args
    assert "/WAITPID=4711" in args
    got = []
    update.launch_installer(setup, popen=lambda a, **kw: got.append(a))
    assert got[0][0] == setup and f"/WAITPID={os.getpid()}" in got[0]


def test_can_self_update_only_installed_exe():
    assert update.can_self_update() is (os.name == "nt" and False)   # Quellcode-Start: nie


def test_iss_has_update_hooks():
    iss = open(os.path.join(os.path.dirname(__file__), "..", "packaging", "windows",
                            "traceify.iss"), encoding="utf-8").read()
    assert "IsAppUpdate" in iss and "WAITPID" in iss and "runasoriginaluser" in iss
