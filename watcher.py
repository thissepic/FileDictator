# watcher.py  — robuste Move-Erkennung + Debounce
from __future__ import annotations
from pathlib import Path
import time, hashlib, argparse, threading

from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import (
    FileSystemEventHandler,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
)

from ingest import ingest_file, is_supported_file
from embedder_local import embed_texts_ollama
from index_store import upsert_document, delete_document, update_path_only, DB_PATH
from paths import canon

import sqlite3

EMB_MODEL = "bge-m3:567m"


# --------- Utils ----------
def file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1_048_576), b""):
            h.update(chunk)
    return h.hexdigest()


def db_get_doc_id_by_path(path: str) -> str | None:
    con = sqlite3.connect(str(DB_PATH))
    row = con.execute("SELECT doc_id FROM docs WHERE path=?", (path,)).fetchone()
    con.close()
    return row[0] if row else None


def db_has_doc_id(doc_id: str) -> bool:
    con = sqlite3.connect(str(DB_PATH))
    row = con.execute("SELECT 1 FROM docs WHERE doc_id=?", (doc_id,)).fetchone()
    con.close()
    return bool(row)


def wait_file_ready(p: Path, timeout=3.0, interval=0.1) -> bool:
    """
    Warten, bis Datei 'stabil' ist: Größe bleibt zwischen zwei Checks gleich
    (vermeidet Hash/Read bei noch laufenden Moves/Kopien).
    """
    end = time.time() + timeout
    prev = (-1, -1.0)
    while time.time() < end:
        try:
            stat = p.stat()
            sig = (stat.st_size, stat.st_mtime)
            if sig == prev:
                return True
            prev = sig
        except FileNotFoundError:
            pass
        time.sleep(interval)
    return p.exists()


# --------- Event-Handler ----------
class Handler(FileSystemEventHandler):
    def __init__(self, libroot: Path):
        super().__init__()
        self.libroot = libroot
        self._recent = {}  # path -> expiry_ts
        self._lock = threading.Lock()

    # --- Debounce-Helfer ---
    def _mark_recent(self, path: str, ttl=2.0):
        with self._lock:
            self._recent[path] = time.time() + ttl

    def _is_recent(self, path: str) -> bool:
        now = time.time()
        with self._lock:
            # cleanup expired
            for k in list(self._recent.keys()):
                if self._recent[k] < now:
                    del self._recent[k]
            return path in self._recent

    # --- index helpers ---
    def _index_new(self, p: Path):
        excerpt, _images, cleanup = ingest_file(p)
        try:
            rep = f"title: {p.name}\ntags: \ncaption: \nexcerpt:\n{excerpt or ''}"  # OHNE path
            doc_id = file_sha256(p)
            upsert_document(
                doc_id=doc_id,
                final_path=str(p),
                title=p.name,
                tags=[],
                caption="",
                excerpt=excerpt or "",
                represent_text=rep,
                embed_fn=lambda texts: embed_texts_ollama(texts, model=EMB_MODEL),
            )
            print(f"[indexed] {p}")
        finally:
            try:
                cleanup()
            except Exception:
                pass

    def _treat_created_as_move_or_new(self, p: Path):
        """Bei on_created: erst prüfen, ob es eigentlich ein Move ist."""
        if not wait_file_ready(p):
            # Datei evtl. gleich weg/umbenannt; nichts tun
            return
        try:
            h = file_sha256(p)
        except Exception as e:
            print(f"[warn] hashing failed for {p}: {e}")
            return

        if db_has_doc_id(h):
            # bereits bekannt -> Move: nur Pfad updaten
            try:
                update_path_only(h, str(p))
                print(f"[move-detected@created] path -> {p}")
                # Markiere als recent, um Doppelfeuer zu dämpfen
                self._mark_recent(str(p))
                return
            except Exception as e:
                print(f"[warn] update_path_only failed, fallback to index: {e}")

        # sonst wirklich neu
        self._index_new(p)

    # --- Event Callbacks ---
    def on_moved(self, event: DirMovedEvent | FileMovedEvent):
        if event.is_directory:
            return
        src = canon(Path(event.src_path))
        dst = canon(Path(event.dest_path))
        if not is_supported_file(dst):
            return

        # Primärweg: via alter Pfad doc_id bestimmen
        old_doc = db_get_doc_id_by_path(str(src))
        if old_doc:
            # Nur Pfad updaten (Move)
            update_path_only(old_doc, str(dst))
            self._mark_recent(str(dst))
            print(f"[move] {src.name} -> {dst}")
            return

        # Fallback: created-as-move
        self._treat_created_as_move_or_new(dst)

    def on_created(self, event: DirCreatedEvent | FileCreatedEvent):
        if event.is_directory:
            return
        p = canon(Path(event.src_path))
        if not is_supported_file(p):
            return

        # Wenn gerade durch on_moved abgehandelt, ignorieren
        if self._is_recent(str(p)):
            # already handled as move
            return

        # created kann ein Move aus anderem Verzeichnis/Volume sein
        self._treat_created_as_move_or_new(p)

    def on_deleted(self, event: DirDeletedEvent | FileDeletedEvent):
        if event.is_directory:
            return
        # doc_id via DB über alten Pfad
        con = sqlite3.connect(str(DB_PATH))
        row = con.execute(
            "SELECT doc_id FROM docs WHERE path=?", (str(canon(Path(event.src_path))),)
        ).fetchone()
        con.close()
        if row:
            delete_document(row[0])
            print(f"[delete] {event.src_path}")

    def on_modified(self, event: DirModifiedEvent | FileModifiedEvent):
        if event.is_directory:
            return
        p = Path(event.src_path)
        if not is_supported_file(p):
            return
        if not wait_file_ready(p):
            return

        # Inhalt geändert? -> Re-embed (doc_id = content-hash ändert sich!)
        new_id = file_sha256(p)
        con = sqlite3.connect(str(DB_PATH))
        row = con.execute("SELECT doc_id FROM docs WHERE path=?", (str(p),)).fetchone()
        con.close()
        if row and row[0] != new_id:
            delete_document(row[0])  # altes raus
            self._index_new(p)  # neues rein
            print(f"[modify+reindex] {p}")


def main():
    ap = argparse.ArgumentParser(
        description="Watch LIBROOT und spiegele Änderungen in FAISS + FTS5"
    )
    ap.add_argument("--libroot", required=True, type=Path)
    ap.add_argument(
        "--polling",
        action="store_true",
        help="PollingObserver (z. B. für Netzlaufwerke)",
    )
    args = ap.parse_args()

    libroot = args.libroot.expanduser().resolve()
    if not libroot.exists() or not libroot.is_dir():
        raise SystemExit(f"LIBROOT nicht gefunden: {libroot}")

    obs = PollingObserver() if args.polling else Observer()
    obs.schedule(Handler(libroot), str(libroot), recursive=True)
    obs.start()
    print(
        f"[watch] {libroot}  ({'polling' if args.polling else 'native'})  –  Ctrl+C zum Beenden"
    )
    try:
        while True:
            time.sleep(1)
    finally:
        obs.stop()
        obs.join()


if __name__ == "__main__":
    main()
