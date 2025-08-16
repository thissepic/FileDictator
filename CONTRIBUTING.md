# Contributing to FileDictator

Thanks for your interest! Pull requests, issues, and suggestions are very welcome. 🚀

> ℹ️ Note: This project is meant as a **template/starting point**. Contributions to improve it are encouraged, but migration/integration may take time depending on availability.

---

## 🔧 How to Contribute

1. **Fork** this repository and create a feature branch:

   ```bash
   git checkout -b feature/my-feature
   ```
2. **Install dependencies** and test locally:

   ```bash
   pip install -r requirements.txt
   ```
3. Make sure your changes are **well documented** (README/Docs, concise comments, clean code).
4. Open a **PR** with:

   * a clear description
   * screenshots/GIFs (for UI changes)
   * short log snippets if relevant

---

## 📏 Guidelines

* Keep **README** and constants in `ingest.py` (image processing) in sync.
* Use **meaningful identifiers** (avoid 1–2 letter variables).
* Handle errors gracefully (no silent `except`).
* Prefer **small, focused PRs** over large ones.

---

## 🛠 Development Notes

* **LLM Providers**: `ollama_client.py`, `openai_client.py`
* **Ingest / Images**: `ingest.py`, `image_utils.py`
* **Search / Index**: `index_store.py`, `hybrid_search.py`
* **Web UI**: `webui/app.py`, `webui/templates/*`
* **Watcher**: `watcher.py`

---

## 🤝 Code of Conduct

By participating, you agree to abide by the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## 📄 License

By submitting a contribution, you agree that your work will be licensed under the **MIT License** of this project.
