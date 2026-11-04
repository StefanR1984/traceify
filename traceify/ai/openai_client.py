"""Client für OpenAI-kompatible KI-Server (nur Standardbibliothek).

Damit lassen sich statt Ollama auch **vLLM**, LM Studio, llama.cpp-Server, LocalAI u. a.
nutzen – alles, was ``/v1/models`` und ``/v1/chat/completions`` anbietet. Die Schnittstelle
ist dieselbe wie bei ``OllamaClient``, der Rest von Traceify merkt keinen Unterschied:

* Bilder (``messages[i]["images"]`` als base64-PNG) werden als ``image_url`` mitgeschickt
* ``fmt`` (JSON-Schema oder ``"json"``) wird zu ``response_format``; lehnt der Server das
  ab, wird schrittweise ohne Vorgabe gefragt (die Antwort wird ohnehin robust geparst)
* Modelle legt der Server beim Start fest – „Laden“/„Löschen“ gibt es hier nicht
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Callable, List, Optional

from .ollama_client import OllamaError

VISION_HINTS = ("vl", "vision", "llava", "gemma-3", "gemma3", "pixtral", "internvl", "minicpm-v",
                "qwen2-vl", "qwen2.5-vl", "qwen3-vl", "molmo", "idefics", "phi-3.5-vision",
                "phi-4-multimodal", "moondream", "smolvlm", "mistral-small-3")


class OpenAICompatClient:
    """vLLM & Co. über die OpenAI-kompatible REST-API."""
    kind = "openai"
    can_pull = False

    def __init__(self, url: str = "http://127.0.0.1:8000/v1", timeout: float = 300,
                 api_key: str = ""):
        url = (url or "").rstrip("/")
        if not url.endswith("/v1"):
            url += "/v1"
        self.url = url
        self.timeout = timeout
        self.api_key = api_key or ""
        self._server = None

    # ------------------------------------------------------------ intern
    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _req(self, path: str, payload: Optional[dict] = None, timeout: Optional[float] = None,
             base: Optional[str] = None):
        data = json.dumps(payload).encode() if payload is not None else None
        req = urllib.request.Request((base or self.url) + path, data=data, headers=self._headers(),
                                     method="POST" if data is not None else "GET")
        try:
            return urllib.request.urlopen(req, timeout=timeout or self.timeout)
        except urllib.error.HTTPError as e:
            try:
                body = json.loads(e.read())
                err = body.get("error", body)
                msg = err.get("message", str(err)) if isinstance(err, dict) else str(err)
            except Exception:
                msg = str(e)
            raise _HttpError(e.code, msg) from None
        except urllib.error.URLError as e:
            raise OllamaError(f"KI-Server nicht erreichbar unter {self.url} ({e.reason})") from None

    def _json(self, path, payload=None, timeout=None, base=None) -> dict:
        with self._req(path, payload, timeout, base) as r:
            return json.load(r)

    # ------------------------------------------------------------ API
    def available(self) -> bool:
        try:
            self.list_models()
            return True
        except Exception:
            return False

    def version(self) -> str:
        """Servername und Version, z. B. „vLLM 0.11.0“ (sonst „OpenAI-kompatibel“)."""
        root = self.url[:-3] if self.url.endswith("/v1") else self.url
        try:
            v = self._json("/version", timeout=3, base=root).get("version")
            if v:
                return f"vLLM {v}"
        except Exception:
            pass
        self.list_models()           # wirft, wenn der Server nicht erreichbar ist
        return "OpenAI-kompatibel"

    def list_models(self) -> List[dict]:
        data = self._json("/models", timeout=10).get("data", [])
        return [{"name": m.get("id", ""), **m} for m in data if m.get("id")]

    def model_names(self) -> List[str]:
        return [m["name"] for m in self.list_models()]

    def capabilities(self, model: str) -> List[str]:
        return ["completion", "vision"] if self.has_vision(model) else ["completion"]

    def has_vision(self, model: str) -> bool:
        m = model.lower()
        return any(h in m for h in VISION_HINTS)

    def pull(self, model: str, progress: Optional[Callable[[int, str], None]] = None,
             should_stop: Optional[Callable[[], bool]] = None) -> None:
        raise OllamaError("Beim vLLM-/OpenAI-Server legt der Server die Modelle beim Start fest "
                          "(z. B. „vllm serve Qwen/Qwen2.5-VL-7B-Instruct“) – Laden ist hier "
                          "nicht möglich.")

    def delete(self, model: str) -> None:
        raise OllamaError("Modelle können auf einem vLLM-/OpenAI-Server nicht gelöscht werden.")

    @staticmethod
    def convert_messages(messages: List[dict]) -> List[dict]:
        """Ollama-Nachrichten (content + images) -> OpenAI-Format (Inhaltsteile)."""
        out = []
        for m in messages:
            imgs = m.get("images") or []
            if not imgs:
                out.append({"role": m["role"], "content": m.get("content", "")})
                continue
            parts = [{"type": "text", "text": m.get("content", "")}]
            for b64 in imgs:
                parts.append({"type": "image_url",
                              "image_url": {"url": "data:image/png;base64," + b64}})
            out.append({"role": m["role"], "content": parts})
        return out

    @staticmethod
    def response_formats(fmt) -> list:
        """Vorgaben für response_format, von streng nach locker (None = keine)."""
        if fmt is None:
            return [None]
        if isinstance(fmt, dict):
            return [{"type": "json_schema",
                     "json_schema": {"name": "antwort", "schema": fmt, "strict": False}},
                    {"type": "json_object"}, None]
        return [{"type": "json_object"}, None]

    def chat(self, model: str, messages: List[dict], fmt=None, temperature: float = 0.2,
             on_token: Optional[Callable[[str], None]] = None, num_ctx: int = 8192) -> str:
        base = {"model": model, "messages": self.convert_messages(messages),
                "temperature": temperature, "max_tokens": 2048, "stream": bool(on_token)}
        last = None
        for rf in self.response_formats(fmt):
            payload = dict(base)
            if rf is not None:
                payload["response_format"] = rf
            try:
                if not on_token:
                    res = self._json("/chat/completions", payload)
                    return (res.get("choices") or [{}])[0].get("message", {}).get("content") or ""
                return self._stream(payload, on_token)
            except _HttpError as e:
                last = e
                # 400/422: Server kennt die Formatvorgabe nicht – lockerer nochmal versuchen
                if e.code in (400, 422) and rf is not None:
                    continue
                raise OllamaError(str(e)) from None
        raise OllamaError(str(last))

    def _stream(self, payload: dict, on_token: Callable[[str], None]) -> str:
        out = []
        with self._req("/chat/completions", payload) as r:
            for raw in r:
                line = raw.decode("utf-8", "replace").strip()
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    break
                ev = json.loads(data)
                if "error" in ev:
                    raise OllamaError(str(ev["error"]))
                tok = ((ev.get("choices") or [{}])[0].get("delta") or {}).get("content") or ""
                if tok:
                    out.append(tok)
                    on_token(tok)
        return "".join(out)


class _HttpError(OllamaError):
    def __init__(self, code: int, msg: str):
        super().__init__(f"HTTP {code}: {msg}")
        self.code = code


RECOMMENDED_VLLM_MODELS = (
    ("Qwen/Qwen2.5-VL-7B-Instruct", "Bild + Text – sehr gute Texterkennung (ca. 16 GB GPU)"),
    ("Qwen/Qwen2.5-VL-3B-Instruct", "Bild + Text – kleiner (ca. 8 GB GPU)"),
    ("google/gemma-3-12b-it", "Bild + Text – genauer (ca. 24 GB GPU)"),
)
