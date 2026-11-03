"""Schlanker Client für die lokale Ollama-REST-API (nur Standardbibliothek)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, Iterable, List, Optional


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, url: str = "http://127.0.0.1:11434", timeout: float = 300):
        self.url = url.rstrip("/")
        self.timeout = timeout

    # ------------------------------------------------------------ intern
    def _req(self, path: str, payload: Optional[dict] = None, timeout: Optional[float] = None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request(self.url + path, data=data,
                                     headers={"Content-Type": "application/json"},
                                     method="POST" if data is not None else "GET")
        try:
            return urllib.request.urlopen(req, timeout=timeout or self.timeout)
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read()).get("error", str(e))
            except Exception:
                msg = str(e)
            raise OllamaError(msg) from None
        except urllib.error.URLError as e:
            raise OllamaError(f"Ollama nicht erreichbar unter {self.url} ({e.reason})") from None

    def _json(self, path, payload=None, timeout=None) -> dict:
        with self._req(path, payload, timeout) as r:
            return json.load(r)

    # ------------------------------------------------------------ API
    def available(self) -> bool:
        try:
            self.version()
            return True
        except Exception:
            return False

    def version(self) -> str:
        return self._json("/api/version", timeout=3).get("version", "?")

    def list_models(self) -> List[dict]:
        return self._json("/api/tags", timeout=10).get("models", [])

    def model_names(self) -> List[str]:
        return [m["name"] for m in self.list_models()]

    def capabilities(self, model: str) -> List[str]:
        """z. B. ['completion', 'vision'] – leer, wenn die Ollama-Version es nicht meldet."""
        try:
            info = self._json("/api/show", {"model": model}, timeout=20)
        except OllamaError:
            return []
        caps = info.get("capabilities") or []
        if not caps:
            fam = " ".join(info.get("details", {}).get("families") or [])
            if "clip" in fam or "mllama" in fam:
                caps = ["completion", "vision"]
        return caps

    def has_vision(self, model: str) -> bool:
        caps = self.capabilities(model)
        if caps:
            return "vision" in caps
        return any(k in model for k in ("vision", "vl", "llava", "gemma3", "minicpm-v", "moondream"))

    def pull(self, model: str, progress: Optional[Callable[[int, str], None]] = None,
             should_stop: Optional[Callable[[], bool]] = None) -> None:
        with self._req("/api/pull", {"model": model, "stream": True}, timeout=7200) as r:
            for line in r:
                if should_stop and should_stop():
                    raise OllamaError("Abgebrochen")
                ev = json.loads(line)
                if "error" in ev:
                    raise OllamaError(ev["error"])
                if progress:
                    pct = int(ev["completed"] * 100 / ev["total"]) if ev.get("total") and \
                        ev.get("completed") else -1
                    progress(pct, ev.get("status", ""))

    def delete(self, model: str) -> None:
        req = urllib.request.Request(self.url + "/api/delete", method="DELETE",
                                     data=json.dumps({"model": model}).encode(),
                                     headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=30).close()

    def chat(self, model: str, messages: List[dict], fmt=None, temperature: float = 0.2,
             on_token: Optional[Callable[[str], None]] = None, num_ctx: int = 8192) -> str:
        """Chat-Anfrage. messages: [{'role','content','images':[b64,…]}]. fmt: None|'json'|Schema."""
        payload = {"model": model, "messages": messages, "stream": bool(on_token),
                   "options": {"temperature": temperature, "num_ctx": num_ctx},
                   "keep_alive": "15m"}
        if fmt is not None:
            payload["format"] = fmt
        if not on_token:
            return self._json("/api/chat", payload).get("message", {}).get("content", "")
        out = []
        with self._req("/api/chat", payload) as r:
            for line in r:
                ev = json.loads(line)
                if "error" in ev:
                    raise OllamaError(ev["error"])
                tok = ev.get("message", {}).get("content", "")
                if tok:
                    out.append(tok)
                    on_token(tok)
                if ev.get("done"):
                    break
        return "".join(out)


def parse_json(text: str):
    """Robustes JSON-Parsen auch bei Modellen, die Text drumherum schreiben."""
    text = (text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except Exception:
        pass
    for open_c, close_c in (("{", "}"), ("[", "]")):
        a, b = text.find(open_c), text.rfind(close_c)
        if a != -1 and b > a:
            try:
                return json.loads(text[a:b + 1])
            except Exception:
                continue
    raise OllamaError("Antwort der KI war kein gültiges JSON")


RECOMMENDED_MODELS: Iterable[tuple] = (
    ("gemma3:4b", "Bild + Text, ca. 3,3 GB – schnell, Standard"),
    ("qwen2.5vl:7b", "Bild + Text, ca. 6 GB – sehr gute Texterkennung"),
    ("gemma3:12b", "Bild + Text, ca. 8 GB – genauer, braucht mehr RAM/GPU"),
    ("llama3.2-vision:11b", "Bild + Text, ca. 8 GB"),
    ("qwen2.5:7b", "nur Text, ca. 4,7 GB – Chat/Befehle"),
)
