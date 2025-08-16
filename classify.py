# classify.py
import json, time
from pathlib import Path
from jsonschema import validate, ValidationError

from fs_ops import move_or_copy, append_log, file_sha256
from prompts import SYSTEM_PROMPT, build_user_prompt
from taxonomy import REVIEW_FOLDER
from ollama_client import chat_structured, OllamaError
from openai_client import responses_parse_structured, OpenAIError
from ingest import ingest_file
from schemas import build_docsort_model
from index_store import upsert_document
from embedder_local import embed_texts_ollama
from paths import canon


def _ns_to_ms(ns):
    try:
        return round(ns / 1_000_000, 2) if ns is not None else None
    except Exception:
        return None


def _ollama_metrics(meta: dict, wall_ms: float) -> dict:
    return {
        "provider": "ollama",
        "latency_ms": round(wall_ms, 2),
        "model": meta.get("model"),
        "ollama_total_ms": _ns_to_ms(meta.get("total_duration")),
        "ollama_load_ms": _ns_to_ms(meta.get("load_duration")),
        "ollama_prompt_eval_ms": _ns_to_ms(meta.get("prompt_eval_duration")),
        "ollama_eval_ms": _ns_to_ms(meta.get("eval_duration")),
        "ollama_prompt_eval_count": meta.get("prompt_eval_count"),
        "ollama_eval_count": meta.get("eval_count"),
    }


def _openai_metrics(meta: dict) -> dict:
    return {
        "provider": "openai",
        "latency_ms": meta.get("latency_ms"),
        "model": meta.get("model"),
        "openai_input_tokens": meta.get("usage_input_tokens"),
        "openai_output_tokens": meta.get("usage_output_tokens"),
        "openai_total_tokens": meta.get("usage_total_tokens"),
    }


def _build_representation(
    title: str, final_rel_path: str, tags: list[str], caption: str | None, excerpt: str
) -> str:
    parts = [f"title: {title}", f"path: {final_rel_path}", f"tags: {', '.join(tags)}"]
    if caption:
        parts.append(f"caption: {caption}")
    if excerpt:
        parts.append(f"excerpt:\n{excerpt}")
    return "\n".join(parts)


def classify_item(
    src_path: Path,
    lib_root: Path,
    allowed_paths: list[str],
    schema: dict,
    *,
    provider: str = "ollama",  # "ollama" | "openai"
    min_confidence: float = 0.6,
    action: str = "move",
    model: str = "gemma3:27b",
    keep_alive: str | int | None = "2h",
    dry_run: bool = False,
) -> Path:
    # 1) Ingest (text + optional images)
    excerpt, image_paths, cleanup = ingest_file(src_path)
    try:
        # 2) Build prompt (with optional excerpt)
        user_prompt = build_user_prompt(src_path.name, allowed_paths, excerpt or None)
        log_path = (
            Path("./logs/dryrun.jsonl") if dry_run else Path("./logs/processed.jsonl")
        )

        # 2) Provider-specific call (both without history)
        if provider == "openai":
            # Dynamically build Pydantic model from allowed paths
            DocSortModel = build_docsort_model(allowed_paths)
            parsed, meta = responses_parse_structured(
                model=model,
                system_prompt=SYSTEM_PROMPT,
                user_text=user_prompt,
                image_paths=image_paths or None,
                pyd_model=DocSortModel,
            )
            target_rel = parsed.target_path
            confidence = float(parsed.confidence)
            reason = parsed.reason
            alternatives = getattr(parsed, "alternatives", [])
            tags = parsed.tags
            caption = getattr(parsed, "caption", None)
            metrics = _openai_metrics(meta)
        else:
            t0 = time.perf_counter()
            raw_json, meta = chat_structured(
                model=model,
                system=SYSTEM_PROMPT,
                user_content=user_prompt,
                image_paths=image_paths or None,
                format_schema=schema,
                temperature=0.0,
                keep_alive=keep_alive,
            )
            wall_ms = (time.perf_counter() - t0) * 1000.0
            obj = json.loads(raw_json)
            validate(instance=obj, schema=schema)
            target_rel = obj["target_path"]
            confidence = float(obj["confidence"])
            reason = obj.get("reason", "")
            alternatives = obj.get("alternatives", [])
            tags = obj.get("tags", [])
            caption = obj.get("caption", None)
            metrics = _ollama_metrics(meta, wall_ms)

        tgt_dir = lib_root / (
            REVIEW_FOLDER if confidence < min_confidence else target_rel
        )

        if dry_run:
            planned = tgt_dir / src_path.name

            # In dry-run: embed source path, but use planned target path in metadata
            dst_abs = canon(planned)
            rep_text = _build_representation(
                title=dst_abs.name,
                final_rel_path="",  # do not embed final path
                tags=tags,
                caption=caption,
                excerpt=excerpt or "",
            )

            doc_id = file_sha256(src_path)
            upsert_document(
                doc_id=doc_id,
                final_path=str(dst_abs),
                title=dst_abs.name,
                tags=tags,
                caption=caption,
                excerpt=excerpt or "",
                represent_text=rep_text,
                embed_fn=lambda texts: embed_texts_ollama(texts, model="bge-m3:567m"),
            )

            append_log(
                log_path,
                {
                    "dry_run": True,
                    "file": str(src_path),
                    "planned_dst": str(dst_abs),
                    "result": "ok",
                    "target_rel": target_rel,
                    "confidence": confidence,
                    "reason": reason,
                    "alternatives": alternatives,
                    "tags": tags,
                    "caption": caption,
                    **metrics,
                },
            )
            return dst_abs

        dst = move_or_copy(src_path, tgt_dir, action)  # type: ignore[arg-type]

        # direct indexing
        dst_abs = canon(dst)
        # Representation without path:
        rep_text = _build_representation(
            title=dst_abs.name,
            final_rel_path="",
            tags=tags,
            caption=caption,
            excerpt=excerpt or "",
        )

        doc_id = file_sha256(dst_abs)
        upsert_document(
            doc_id=doc_id,
            final_path=str(dst_abs),
            title=dst_abs.name,
            tags=tags,
            caption=caption,
            excerpt=excerpt or "",
            represent_text=rep_text,
            embed_fn=lambda texts: embed_texts_ollama(texts, model="bge-m3:567m"),
        )

        append_log(
            log_path,
            {
                "file": str(src_path),
                "dst": str(dst_abs),
                "hash": doc_id,
                "result": "ok",
                "target_rel": target_rel,
                "confidence": confidence,
                "reason": reason,
                "alternatives": alternatives,
                "tags": tags,
                "caption": caption,
                **metrics,
            },
        )
        return dst_abs
    finally:
        try:
            cleanup()
        except Exception:
            pass
