# openai_client.py
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple, Type
from openai import OpenAI
from pydantic import BaseModel
from dotenv import load_dotenv
import base64, mimetypes, os, time

load_dotenv()  # lädt OPENAI_API_KEY aus .env


class OpenAIError(RuntimeError):
    pass


def _to_data_url(path: str) -> str:
    mime, _ = mimetypes.guess_type(path)
    if not mime:
        ext = os.path.splitext(path)[1].lower()
        mime = "image/png" if ext == ".png" else "image/jpeg"
    b64 = base64.b64encode(open(path, "rb").read()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _build_user_content(
    user_text: str, image_paths: Optional[List[str]]
) -> List[Dict[str, Any]]:
    parts: List[Dict[str, Any]] = [{"type": "input_text", "text": user_text}]
    for p in image_paths or []:
        # Base64-Data-URL direkt im Input — von den OpenAI-Dokus gestützt
        parts.append({"type": "input_image", "image_url": _to_data_url(p)})
    return parts


def responses_parse_structured(
    *,
    model: str,
    system_prompt: str,
    user_text: str,
    image_paths: Optional[List[str]],
    pyd_model: Type[BaseModel],
    timeout_s: int = 300,
) -> Tuple[BaseModel, Dict[str, Any]]:
    """
    Structured Outputs via client.responses.parse(..., text_format=pyd_model)
    Gibt (parsed_object, meta) zurück.
    """
    try:
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"), timeout=timeout_s)
        t0 = time.perf_counter()
        resp = client.responses.parse(
            model=model,
            input=[
                {
                    "role": "system",
                    "content": system_prompt,
                },
                {
                    "role": "user",
                    "content": _build_user_content(user_text, image_paths),
                },
            ],
            text_format=pyd_model,
        )
        wall_ms = (time.perf_counter() - t0) * 1000.0
    except Exception as e:
        raise OpenAIError(f"OpenAI responses.parse() fehlgeschlagen: {e}") from e

    parsed = getattr(resp, "output_parsed", None)
    if parsed is None:
        raise OpenAIError("output_parsed fehlt / konnte nicht geparst werden")

    # Token-/Nutzungsdaten (wenn vorhanden)
    d = getattr(resp, "to_dict", lambda: {})()
    usage = d.get("usage", {}) if isinstance(d, dict) else {}
    meta = {
        "model": getattr(resp, "model", None) or d.get("model"),
        "latency_ms": round(wall_ms, 2),
        "usage_input_tokens": usage.get("input_tokens"),
        "usage_output_tokens": usage.get("output_tokens"),
        "usage_total_tokens": usage.get("total_tokens"),
    }
    return parsed, meta
