# main.py
import argparse, time
from pathlib import Path

from taxonomy import list_leaf_paths, build_schema
from fs_ops import load_processed_hashes, file_sha256
from classify import classify_item
from ingest import is_supported_file


def run_once(
    inbox: Path,
    lib_root: Path,
    *,
    provider: str,
    min_conf: float,
    action: str,
    model: str,
    keep_alive,
    dry_run: bool,
):
    allowed = list_leaf_paths(lib_root)
    schema = build_schema(allowed)
    seen_hashes = load_processed_hashes(Path("./logs/processed.jsonl"))
    unsorted_dir = lib_root / "Unsorted_Review"

    processed = 0
    for p in sorted(inbox.iterdir()):
        if not p.is_file():
            continue

        h = file_sha256(p)
        if not dry_run and h in seen_hashes and action == "copy":
            print(f"[skip] {p.name} (bereits verarbeitet)")
            continue

        if not is_supported_file(p):
            # Nicht unterstützte Dateiendung - direkt in Unsorted_Review verschieben
            if dry_run:
                # Im Dry-Run nur simulieren, nicht tatsächlich verschieben
                dst = unsorted_dir / p.name
                processed += 1
                print(f"[dry-run] {p.name} -> {dst} (nicht unterstützte Dateiendung)")
            else:
                # Tatsächlich verschieben/kopieren
                try:
                    from fs_ops import move_or_copy

                    dst = move_or_copy(p, unsorted_dir, action)
                    processed += 1
                    print(
                        f"[unsorted] {p.name} -> {dst} (nicht unterstützte Dateiendung)"
                    )
                except Exception as ex:
                    print(f"[ERROR] {p.name} (Unsorted): {ex}")
            continue

        try:
            dst = classify_item(
                p,
                lib_root,
                allowed,
                schema,
                provider=provider,
                min_confidence=min_conf,
                action=action,
                model=model,
                keep_alive=keep_alive,
                dry_run=dry_run,
            )
            processed += 1
            tag = "dry-run" if dry_run else "ok"
            print(f"[{tag}] {p.name} -> {dst}")
        except Exception as ex:
            print(f"[ERROR] {p.name}: {ex}")
    return processed


def parse_args():
    ap = argparse.ArgumentParser(
        description="Dokumente (Bild/Word/ODT) einsortieren - wahlweise via Ollama oder OpenAI (Structured Outputs)."
    )
    ap.add_argument("--inbox", type=Path, required=True)
    ap.add_argument("--libroot", type=Path, required=True)
    ap.add_argument(
        "--provider",
        choices=["ollama", "openai"],
        default="ollama",
        help="LLM-Backend wählen",
    )
    ap.add_argument(
        "--model",
        type=str,
        default="qwen2.5vl:32b",
        help="Modellname (bei provider=openai z. B. gpt-4o-mini / gpt-5)",
    )
    ap.add_argument("--min-confidence", type=float, default=0.6)
    ap.add_argument("--action", choices=["move", "copy"], default="move")
    ap.add_argument(
        "--keep-alive",
        type=str,
        default="2h",
        help='Nur für Ollama relevant (z. B. "10m", "2h", "-1")',
    )
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--watch", action="store_true")
    return ap.parse_args()


def watch_mode(
    inbox: Path,
    lib_root: Path,
    *,
    provider: str,
    min_conf: float,
    action: str,
    model: str,
    keep_alive,
    dry_run: bool,
    interval: float = 3.0,
):
    print(f"[watch] Beobachte {inbox} (Intervall {interval}s) …  Abbruch: Ctrl+C")
    seen = set()
    while True:
        try:
            for p in inbox.iterdir():
                if p.is_file() and p not in seen:
                    time.sleep(0.2)
                    if not p.exists():
                        continue
                    run_once(
                        inbox,
                        lib_root,
                        provider=provider,
                        min_conf=min_conf,
                        action=action,
                        model=model,
                        keep_alive=keep_alive,
                        dry_run=dry_run,
                    )
                    seen.add(p)
        except KeyboardInterrupt:
            print("\n[watch] beendet.")
            return
        except Exception as e:
            print(f"[watch][warn] {e}")
        time.sleep(interval)


if __name__ == "__main__":
    args = parse_args()
    if args.watch:
        watch_mode(
            args.inbox,
            args.libroot,
            provider=args.provider,
            min_conf=args.min_confidence,
            action=args.action,
            model=args.model,
            keep_alive=args.keep_alive,
            dry_run=args.dry_run,
        )
    else:
        n = run_once(
            args.inbox,
            args.libroot,
            provider=args.provider,
            min_conf=args.min_confidence,
            action=args.action,
            model=args.model,
            keep_alive=args.keep_alive,
            dry_run=args.dry_run,
        )
        tag = "dry-run" if args.dry_run else "done"
        print(f"[{tag}] verarbeitet: {n}")
