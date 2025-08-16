# ollama_client.py
from typing import Any, Tuple
import ollama


class OllamaError(RuntimeError):
    pass


def chat_structured(
    model: str,
    system: str,
    user_content: str,
    image_paths: list[str] | None,
    format_schema: dict | str | None,
    *,
    temperature: float = 0.0,
    keep_alive: str | int | None = "2h",
    extra_options: dict | None = None,
) -> Tuple[str, dict]:
    """
    Aufruf über die offizielle ollama-Python-Library (kein RAW).
    Gibt (content, meta) zurück, wobei meta die Metriken enthält, soweit verfügbar.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_content},
    ]
    if image_paths:
        messages[-1]["images"] = image_paths

    options = {"temperature": temperature}
    if extra_options:
        options.update(extra_options)

    kwargs: dict[str, Any] = {"options": options}
    if format_schema is not None:
        kwargs["format"] = format_schema
    if keep_alive is not None:
        kwargs["keep_alive"] = keep_alive  # hält nur das Modell warm, keine History

    try:
        resp = ollama.chat(model=model, messages=messages, **kwargs)
    except Exception as e:
        raise OllamaError(f"Ollama chat() fehlgeschlagen: {e}") from e
    # Content extrahieren
    content = ""
    if isinstance(resp, dict):
        content = (resp.get("message", {}) or {}).get("content", "") or ""
    else:
        content = getattr(getattr(resp, "message", None), "content", "") or ""
    if not content:
        raise OllamaError("Leere Modellantwort erhalten.")

    # Relevante Metriken/Meta (optional vorhanden)
    keys = [
        "model",
        "created_at",
        "done",
        "done_reason",
        "total_duration",
        "load_duration",
        "prompt_eval_count",
        "prompt_eval_duration",
        "eval_count",
        "eval_duration",
    ]
    meta = {
        k: (resp.get(k) if isinstance(resp, dict) else getattr(resp, k, None))
        for k in keys
    }
    return content, meta
