"""KI-Funktionen über eine lokale Ollama-Installation."""
from .assistant import (Assistant, apply_suggestion, correct_texts, describe_state,
                        encode_image, read_unrecognized, render_overlay, suggest_settings)
from .ollama_client import (RECOMMENDED_MODELS, OllamaClient, OllamaError,
                            parse_json)
from .openai_client import RECOMMENDED_VLLM_MODELS, OpenAICompatClient

__all__ = ["Assistant", "OllamaClient", "OllamaError", "OpenAICompatClient", "RECOMMENDED_MODELS",
           "RECOMMENDED_VLLM_MODELS", "SERVER_KINDS", "apply_suggestion", "make_client",
           "model_key", "server_label",
           "correct_texts", "default_client", "describe_state", "encode_image", "parse_json",
           "read_unrecognized", "render_overlay", "suggest_settings"]


SERVER_KINDS = {"ollama": "Ollama", "openai": "vLLM / OpenAI-kompatibel"}


def server_label(cfg: dict) -> str:
    return SERVER_KINDS.get(cfg.get("ki_server") or "ollama", "Ollama")


def make_client(cfg: dict):
    """KI-Client passend zur Einstellung „ki_server“ (Ollama oder OpenAI-kompatibel/vLLM)."""
    timeout = cfg.get("ollama_timeout") or 300
    if (cfg.get("ki_server") or "ollama") == "openai":
        return OpenAICompatClient(cfg.get("openai_url") or "http://127.0.0.1:8000/v1", timeout,
                                  cfg.get("openai_key") or "")
    return OllamaClient(cfg.get("ollama_url") or "http://127.0.0.1:11434", timeout)


def model_key(cfg: dict) -> str:
    """Config-Schlüssel des gewählten Modells – je Server getrennt gespeichert."""
    return "openai_model" if (cfg.get("ki_server") or "ollama") == "openai" else "ollama_model"


def default_client(overrides: dict = None):
    """Client und Modell aus der Konfiguration; overrides (z. B. aus der Kommandozeile)
    gelten nur für diesen Aufruf und werden nicht gespeichert."""
    from .. import config
    cfg = config.load()
    cfg.update({k: v for k, v in (overrides or {}).items() if v not in (None, "")})
    model = cfg.get(model_key(cfg)) or ("gemma3:4b" if model_key(cfg) == "ollama_model" else "")
    return make_client(cfg), model
