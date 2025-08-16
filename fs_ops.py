# fs_ops.py
import base64, hashlib, json, shutil, time
from pathlib import Path
from typing import Literal

Action = Literal["move", "copy"]


def b64_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("ascii")


def file_sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def unique_dest_path(dst_dir: Path, filename: str) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    target = dst_dir / filename
    if not target.exists():
        return target
    stem, suffix = target.stem, target.suffix
    i = 1
    while True:
        candidate = dst_dir / f"{stem} ({i}){suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def move_or_copy(src: Path, dst_dir: Path, mode: Action) -> Path:
    dst_dir.mkdir(parents=True, exist_ok=True)
    target = unique_dest_path(dst_dir, src.name)
    if mode == "move":
        shutil.move(str(src), str(target))
    else:
        shutil.copy2(str(src), str(target))
    return target


def append_log(logfile: Path, record: dict) -> None:
    logfile.parent.mkdir(parents=True, exist_ok=True)
    with logfile.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps({"ts": int(time.time()), **record}, ensure_ascii=False) + "\n"
        )


def load_processed_hashes(logfile: Path) -> set[str]:
    """
    Parse processed.jsonl without dry-run entries for idempotency (only real moves/copies).
    """
    if not logfile.exists():
        return set()
    hashes = set()
    with logfile.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                if obj.get("dry_run") is True:
                    continue
                h = obj.get("hash")
                if h:
                    hashes.add(h)
            except Exception:
                continue
    return hashes


def is_image_file(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png"}
