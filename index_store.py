# index_store.py
from __future__ import annotations
import json, sqlite3, faiss, numpy as np
from pathlib import Path
from typing import List, Optional

from search_normalize import de_variants

DB_PATH = Path("./search/docs.sqlite")
VEC_PATH = Path("./search/vec.faiss")
BASE = DB_PATH.parent
BASE.mkdir(parents=True, exist_ok=True)


# -----------------------------
# SQLite (docs + FTS5)
# -----------------------------
def _connect():
    con = sqlite3.connect(DB_PATH)
    # docs: doc_id = SHA256 hex, doc_id_i = i64 (first 8 bytes)
    con.execute(
        """
    CREATE TABLE IF NOT EXISTS docs(
      doc_id   TEXT PRIMARY KEY,
      doc_id_i INTEGER UNIQUE,
      path     TEXT,
      title    TEXT,
      tags     TEXT,
      caption  TEXT,
      excerpt  TEXT
    )"""
    )
    con.execute(
        """
    CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
        title, tags, caption, text, path,
        tokenize = "unicode61 remove_diacritics 2 tokenchars '-'",
        prefix='2 3 4'
    )"""
    )
    return con


def _fts_upsert(
    con: sqlite3.Connection,
    rowid: int,
    title: str,
    tags: str,
    caption: str,
    text: str,
    path: str,
):
    con.execute("DELETE FROM docs_fts WHERE rowid=?", (rowid,))
    con.execute(
        "INSERT INTO docs_fts(rowid,title,tags,caption,text,path) VALUES (?,?,?,?,?,?)",
        (rowid, title, tags, caption, text, path),
    )


# -----------------------------
# ID conversion (SHA256 -> i64)
# -----------------------------
def sha256_to_i64(sha_hex: str) -> int:
    """
    Take the first 8 bytes (16 hex chars) of the SHA256 and map
    them to a signed int64 (two's complement if needed).
    """
    v = int(sha_hex[:16], 16)  # 0 .. 2^64-1  (unsigned)
    if v >= (1 << 63):  # in signed-Bereich mappen
        v -= 1 << 64  # Two's-complement
    return v  # passt in SQLite INTEGER (signed 64-bit)


# -----------------------------
# FAISS index (IDMap2 over IndexFlatIP)
# -----------------------------
def _open_index(dim: Optional[int] = None):
    if VEC_PATH.exists():
        return faiss.read_index(str(VEC_PATH))
    if dim is None:
        raise ValueError("Initial build requires 'dim'.")
    base = faiss.IndexFlatIP(dim)  # IP + normalization = cosine
    return faiss.IndexIDMap2(base)  # stable 64-bit IDs
    # Docs: add_with_ids / remove_ids / reconstruct via IDMap2.  # noqa
    # https://faiss.ai/cpp_api/file/IndexIDMap_8h.html | https://faiss.ai/cpp_api/struct/structfaiss_1_1IndexIDMap2Template.html


def _save_index(index) -> None:
    faiss.write_index(index, str(VEC_PATH))


def _normalize(X: np.ndarray) -> np.ndarray:
    X = X.astype("float32")
    X /= np.linalg.norm(X, axis=1, keepdims=True) + 1e-12
    return X


# -----------------------------
# Public API
# -----------------------------
def upsert_document(
    *,
    doc_id: str,  # SHA256 hex (Inhalt)
    final_path: str,
    title: str,
    tags: List[str],
    caption: Optional[str],
    excerpt: str,
    represent_text: str,  # WICHTIG: OHNE Pfad!
    embed_fn,  # callable: List[str] -> np.ndarray (1 x dim), unnormalisiert ok
) -> None:
    """Upsert into SQLite (docs + FTS5) and FAISS (IDMap2)."""
    doc_id_i = sha256_to_i64(doc_id)

    # 1) SQLite upsert
    con = _connect()
    con.execute(
        """
        INSERT INTO docs(doc_id, doc_id_i, path, title, tags, caption, excerpt)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(doc_id) DO UPDATE SET
          doc_id_i=excluded.doc_id_i,
          path=excluded.path, title=excluded.title, tags=excluded.tags,
          caption=excluded.caption, excerpt=excluded.excerpt
    """,
        (doc_id, doc_id_i, final_path, title, " ".join(tags), caption or "", excerpt),
    )
    rowid = con.execute("SELECT rowid FROM docs WHERE doc_id=?", (doc_id,)).fetchone()[
        0
    ]
    tags_norm = " ".join(sorted({t for tag in tags for t in de_variants(tag)}))
    # also expand title variants for FTS
    title_norm = " ".join(sorted(de_variants(title)))
    _fts_upsert(con, rowid, title_norm, tags_norm, caption or "", excerpt, final_path)
    con.commit()
    con.close()

    # 2) Embedding -> FAISS add_with_ids (remove existing id first)
    vec = embed_fn([represent_text])  # (1, d)
    if vec.shape[0] != 1:
        raise ValueError("embed_fn must return exactly 1 vector")
    vec = _normalize(vec)
    index = _open_index(dim=vec.shape[1] if not VEC_PATH.exists() else None)
    try:
        index.remove_ids(np.array([doc_id_i], dtype="int64"))
    except Exception:
        pass
    # add_with_ids: stable 64-bit IDs
    index.add_with_ids(vec.astype("float32"), np.array([doc_id_i], dtype="int64"))
    _save_index(index)


def delete_document(doc_id: str) -> None:
    """Remove document from FAISS + SQLite/FTS5."""
    con = _connect()
    row = con.execute(
        "SELECT doc_id_i, rowid FROM docs WHERE doc_id=?", (doc_id,)
    ).fetchone()
    if not row:
        con.close()
        return
    doc_id_i, rowid = int(row[0]), int(row[1])
    con.execute("DELETE FROM docs_fts WHERE rowid=?", (rowid,))
    con.execute("DELETE FROM docs WHERE rowid=?", (rowid,))
    con.commit()
    con.close()

    if VEC_PATH.exists():
        index = faiss.read_index(str(VEC_PATH))
        index.remove_ids(np.array([doc_id_i], dtype="int64"))
        _save_index(index)


def update_path_only(doc_id: str, new_path: str) -> None:
    """Update only path in SQLite/FTS5 (no re-embedding)."""
    con = _connect()
    con.execute("UPDATE docs SET path=? WHERE doc_id=?", (new_path, doc_id))
    rowid, title, tags, caption, excerpt = con.execute(
        "SELECT rowid, title, tags, caption, excerpt FROM docs WHERE doc_id=?",
        (doc_id,),
    ).fetchone()
    _fts_upsert(con, rowid, title, tags, caption, excerpt, new_path)
    con.commit()
    con.close()
