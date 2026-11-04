"""KI-Funktionen über eine lokale Ollama-Installation."""
from .assistant import (Assistant, apply_suggestion, correct_texts, describe_state,
                        encode_image, read_unrecognized, render_overlay, suggest_settings)
from .ollama_client import (RECOMMENDED_MODELS, OllamaClient, OllamaError,
                            parse_json)

__all__ = ["Assistant", "OllamaClient", "OllamaError", "RECOMMENDED_MODELS", "apply_suggestion",
           "correct_texts", "default_client", "describe_state", "encode_image", "parse_json",
           "read_unrecognized", "render_overlay", "suggest_settings"]


def default_client():
    from .. import config
    cfg = config.load()
    return OllamaClient(cfg.get("ollama_url") or "http://127.0.0.1:11434",
                        cfg.get("ollama_timeout") or 300), cfg.get("ollama_model") or "gemma3:4b"
