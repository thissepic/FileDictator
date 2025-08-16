# FileDictator – AI-Powered Filing & Search (Ollama + OpenAI)

Automatically sort documents and images into a predefined folder structure – either locally with **Ollama** or via **OpenAI Structured Outputs**. Includes **full-text & vector search** (SQLite FTS5 + FAISS) and a simple Web UI.

> ⚡️ This repo is a **template/starting point** you can adapt to your use case. Contributions are welcome, but integration time may vary depending on availability.

---

## ✨ Features

* Automatic classification into existing **leaf folders only**
* Two providers: **Ollama** (local) or **OpenAI** (cloud) – no chat history
* Supports images & common document formats:
  `.jpg/.jpeg/.png, .docx, .odt, .pdf, .ppt/.pptx, .txt`
* Image handling: resize (max 1024px, Pillow), PDF rasterization (PyMuPDF), PPTX extraction (python-pptx)
* Tags + optional captions from the model
* **Dry-Run mode** (no file writes) & INBOX watch mode
* Persistent hybrid search: SQLite (FTS5) + FAISS vector index
* File watcher for LIBROOT (move/delete/re-index)

---

## 🚀 Requirements

* Python **3.10+**
* **OpenAI**: `OPENAI_API_KEY` in `.env`
* **Ollama**: Installed Ollama + models

  * VLM: `qwen2.5vl:32b` (default)
  * Embeddings: `bge-m3:567m`

---

## ⚙️ Installation

```bash
pip install -r requirements.txt
```

Optional `.env` for OpenAI:

```bash
# .env
OPENAI_API_KEY=sk-...
```

### Pull Ollama Models

```bash
ollama pull qwen2.5vl:32b
ollama pull bge-m3:567m
```

---

## ▶️ Usage

### Run with Ollama

```bash
python main.py \
  --inbox "./INBOX" \
  --libroot "./LIBROOT" \
  --action move \
  --min-confidence 0.6 \
  --model "qwen2.5vl:32b" \
  --keep-alive "2h"
```

### Run with OpenAI

```bash
python main.py \
  --provider openai \
  --model "gpt-4o-mini" \
  --inbox "./INBOX" \
  --libroot "./LIBROOT" \
  --action move \
  --min-confidence 0.6
```

---

## 🧪 Dry-Run (no filesystem access)

```bash
python main.py \
  --inbox "./INBOX" \
  --libroot "./LIBROOT" \
  --dry-run \
  --keep-alive "-1"
```

---

## 👀 Watch Mode (auto-scan INBOX)

```bash
python main.py --inbox "./INBOX" --libroot "./LIBROOT" --watch
```

---

## 🌐 Web UI

```bash
uvicorn webui.app:app --reload --host 0.0.0.0 --port 8000
```

* Open `/` in your browser
* Enter `INBOX` + `LIBROOT` to start a session
* Hybrid search (FAISS + FTS5) included

---

## 🔄 File Change Watcher

Mirror file changes in LIBROOT to the search indices:

```bash
python watcher.py --libroot "./LIBROOT"
```

For network drives (force polling):

```bash
python watcher.py --libroot "./LIBROOT" --polling
```

---

## 📜 Logs

* `./logs/processed.jsonl`: results of productive runs (hash, target, confidence, reason, metrics)
* `./logs/dryrun.jsonl`: dry-run results (planned targets, no writes)

Duplicate detection: with `--action copy`, already processed files (by content hash) are skipped.

---

## ⚙️ Configuration

* Target paths limited to existing **leaf folders** in `LIBROOT`
* Auto-creates `Unsorted_Review` (always allowed)
* Files below `--min-confidence` → stored in `Unsorted_Review`
* Unsupported file types → moved (or virtually in dry-run) to `Unsorted_Review`
* Providers: `--provider ollama|openai`, models per backend
* Search indices:

  * SQLite + FTS5 → `./search/docs.sqlite`
  * FAISS → `./search/vec.faiss`

---

## 🗣️ Prompts

`prompts.py` defines the `SYSTEM_PROMPT` and `build_user_prompt` used for classification.

* The default is tailored to German users and a school‑like folder taxonomy.
* Adapt both prompts to your specific use case and your users’ language (e.g., English, multilingual).
* Ensure the instructions reflect your allowed target folders and that the expected output language (tags, caption, reason) is clear.
* Keep the output strictly aligned with the schema (target_path, confidence, reason, tags, caption).

---

## 🔐 Security & Privacy

* Models can **only write to allowed paths** (no free-form paths)
* Final storage path is **not embedded** for privacy
* Embeddings include only: title, tags, caption, text snippet

---

## 🤝 Contributing

Contributions are welcome – PRs, bug reports, and feature ideas.

Please provide:

* clear reproduction steps
* short log excerpts (`logs/*.jsonl`)

See:

* [CONTRIBUTING.md](CONTRIBUTING.md)
* [CODE\_OF\_CONDUCT.md](CODE_OF_CONDUCT.md)

---

## 📄 License

Licensed under **Apache-2.0**.
See [LICENSE](LICENSE) for details.
