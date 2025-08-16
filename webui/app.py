from __future__ import annotations
from pathlib import Path
from typing import Annotated, List
import io, sys, traceback

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates

# --- Euer bestehendes Projekt ---
# Sortieren / Klassifizieren
from taxonomy import list_leaf_paths, build_schema
from ingest import is_supported_file, ingest_file
from classify import classify_item  # ruft Tags + Index-Update bereits auf

# Suche (Hybrid)
from hybrid_search import hybrid_search

app = FastAPI()
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# -----------------------
# FESTE KONFIGURATION
# -----------------------
PROVIDER_DEFAULT = "ollama"  # "ollama" | "openai"
MODEL_OLLAMA = "qwen2.5vl:32b"
MODEL_OPENAI = "gpt-5-mini-2025-08-07"  # bei Bedarf anpassen
MIN_CONFIDENCE = 0.6
KEEP_ALIVE = "10m"  # nur Ollama
ACTION_DEFAULT = "move"  # "move" | "copy"
DRY_RUN_DEFAULT = False

EMB_MODEL = "bge-m3:567m"


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            # Infos für die UI (read-only Hinweise)
            "cfg": {
                "MODEL_OLLAMA": MODEL_OLLAMA,
                "MODEL_OPENAI": MODEL_OPENAI,
                "MIN_CONFIDENCE": MIN_CONFIDENCE,
                "KEEP_ALIVE": KEEP_ALIVE,
                "EMB_MODEL": EMB_MODEL,
                "ACTION_DEFAULT": ACTION_DEFAULT,
                "DRY_RUN_DEFAULT": DRY_RUN_DEFAULT,
                "PROVIDER_DEFAULT": PROVIDER_DEFAULT,
            },
        },
    )


# --- Dateien sortieren ---
@app.post("/sort/run", response_class=HTMLResponse)
def sort_run(
    request: Request,
    inbox: Annotated[str, Form(...)],
    libroot: Annotated[str, Form(...)],
    provider: Annotated[str, Form()] = "ollama",  # "ollama" | "openai"
):
    inbox_p = Path(inbox).expanduser()
    lib_p = Path(libroot).expanduser()

    if not inbox_p.exists() or not inbox_p.is_dir():
        return templates.TemplateResponse(
            "_partials.html",
            {"request": request, "sort_error": f"INBOX nicht gefunden: {inbox_p}"},
        )
    if not lib_p.exists() or not lib_p.is_dir():
        return templates.TemplateResponse(
            "_partials.html",
            {"request": request, "sort_error": f"LIBROOT nicht gefunden: {lib_p}"},
        )

    # Allowed leaf paths & JSON-Schema
    allowed = list_leaf_paths(lib_p)
    schema = build_schema(allowed)

    model = MODEL_OPENAI if provider == "openai" else MODEL_OLLAMA

    processed, logs = 0, []
    for p in sorted(inbox_p.iterdir()):
        if not is_supported_file(p):
            continue
        try:
            dst = classify_item(
                src_path=p,
                lib_root=lib_p,
                allowed_paths=allowed,
                schema=schema,
                provider=provider,  # nur Switch
                min_confidence=MIN_CONFIDENCE,  # fest
                action=ACTION_DEFAULT,  # fest
                model=model,  # fest je Provider
                keep_alive=KEEP_ALIVE,  # fest (nur Ollama relevant)
                dry_run=DRY_RUN_DEFAULT,  # fest
            )
            processed += 1
            logs.append(f"[ok] {p.name} -> {dst}")
        except Exception as ex:
            tb = traceback.format_exc(limit=1)
            logs.append(f"[ERROR] {p.name}: {ex}\n{tb}")

    return templates.TemplateResponse(
        "_partials.html",
        {"request": request, "sort_logs": logs, "sort_count": processed},
    )


# --- Dateien finden (Hybrid-Suche) ---
@app.post("/search/run", response_class=HTMLResponse)
def search_run(
    request: Request,
    q: Annotated[str, Form(...)],
    k: Annotated[int, Form()] = 20,
):
    try:
        results = hybrid_search(q, k=k, emb_model=EMB_MODEL)  # festes Embedding-Modell
    except Exception as ex:
        return templates.TemplateResponse(
            "_partials.html",
            {"request": request, "search_error": f"Suche fehlgeschlagen: {ex}"},
        )

    return templates.TemplateResponse(
        "_partials.html",
        {"request": request, "search_results": results, "q": q, "k": k},
    )
