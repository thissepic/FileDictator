# embedder_local.py
import numpy as np, ollama


def embed_texts_ollama(texts: list[str], model: str = "bge-m3:567m") -> np.ndarray:
    r = ollama.embed(model=model, input=texts)  # {"embeddings":[...]}
    return np.asarray(r["embeddings"], dtype="float32")
