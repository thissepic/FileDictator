# hybrid_search.py
from __future__ import annotations
import argparse, json, sqlite3, faiss, numpy as np
from pathlib import Path
from typing import List, Tuple, Dict, Any

BASE = Path("./search")
DB_PATH = BASE / "docs.sqlite"
VEC_PATH = BASE / "vec.faiss"

from embedder_local import embed_texts_ollama
from search_normalize import expand_fts_query


def _normalize(X: np.ndarray) -> np.ndarray:
    X = X.astype("float32")
    X /= np.linalg.norm(X, axis=1, keepdims=True) + 1e-12
    return X


def _dense_search(query: str, k: int, emb_model: str) -> List[Tuple[int, float]]:
    if not VEC_PATH.exists():
        raise FileNotFoundError(f"FAISS index missing: {VEC_PATH}")
    index = faiss.read_index(str(VEC_PATH))
    q = embed_texts_ollama([query], model=emb_model)
    q = _normalize(q)
    D, I = index.search(q, k)  # I: FAISS labels (doc_id_i), D: scores (IP ~ cosine)
    out = []
    for lbl, s in zip(I[0], D[0]):
        if lbl == -1:
            continue
        out.append((int(lbl), float(s)))
    return out


def _sparse_search(query: str, k: int) -> List[Tuple[int, float]]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"SQLite DB missing: {DB_PATH}")
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    try:
        fts_q = expand_fts_query(query, for_prefix=True)
        rows = cur.execute(
            "SELECT rowid, bm25(docs_fts, 5.0,8.0,2.0,1.0,0.1) AS r "
            "FROM docs_fts WHERE docs_fts MATCH ? ORDER BY r LIMIT ?",
            (fts_q, k),
        ).fetchall()
    except sqlite3.OperationalError:
        rows = cur.execute(
            "SELECT rowid, rank FROM docs_fts WHERE docs_fts MATCH ? ORDER BY rank LIMIT ?",
            (query, k),
        ).fetchall()
    # Map rowid -> doc_id_i
    out: List[Tuple[int, float]] = []
    for rowid, score in rows:
        did_i = cur.execute(
            "SELECT doc_id_i FROM docs WHERE rowid=?", (rowid,)
        ).fetchone()
        if did_i and did_i[0] is not None:
            out.append((int(did_i[0]), float(score) if score is not None else 0.0))
    con.close()
    return out


def _rrf(
    rank_lists: List[List[Tuple[int, float]]], k: int = 60
) -> List[Tuple[int, float]]:
    scores: Dict[int, float] = {}
    for lst in rank_lists:
        for rank, (idx, _s) in enumerate(lst):
            scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def _fetch_docs_by_ids(doc_id_is: List[int]) -> Dict[int, dict]:
    if not doc_id_is:
        return {}
    con = sqlite3.connect(DB_PATH)
    qmarks = ",".join("?" for _ in doc_id_is)
    rows = con.execute(
        f"SELECT doc_id_i, doc_id, path, title, tags, caption, excerpt FROM docs WHERE doc_id_i IN ({qmarks})",
        doc_id_is,
    ).fetchall()
    con.close()
    out = {}
    for did_i, did, path, title, tags, caption, excerpt in rows:
        out[int(did_i)] = {
            "doc_id": did,
            "path": path,
            "title": title,
            "tags": (tags or "").split(),
            "caption": caption or "",
            "excerpt": excerpt or "",
        }
    return out


def hybrid_search(query: str, k: int = 20, emb_model: str = "bge-m3:567m"):
    dense = _dense_search(query, k, emb_model)
    sparse = _sparse_search(query, k)
    fused = _rrf([dense, sparse])[:k]  # [(doc_id_i, rrf_score)]
    meta = _fetch_docs_by_ids([did_i for did_i, _ in fused])

    results = []
    for did_i, score in fused:
        d = meta.get(did_i)
        if not d:
            continue
        d["rrf_score"] = round(float(score), 6)
        results.append(d)
    return results


def main():
    ap = argparse.ArgumentParser(
        description="Hybrid search (FAISS + SQLite FTS5) with RRF"
    )
    ap.add_argument("--q", required=True)
    ap.add_argument("--k", type=int, default=20)
    ap.add_argument("--emb-model", default="bge-m3:567m")
    args = ap.parse_args()
    print(
        json.dumps(
            hybrid_search(args.q, k=args.k, emb_model=args.emb_model),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
