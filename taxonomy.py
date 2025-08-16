from pathlib import Path

REVIEW_FOLDER = "Unsorted_Review"


def list_leaf_paths(lib_root: Path) -> list[str]:
    lib_root = lib_root.resolve()
    allowed = []
    for p in lib_root.rglob("*"):
        if p.is_dir():
            # Leaf = kein Unterordner
            try:
                if not any(child.is_dir() for child in p.iterdir()):
                    rel = str(p.relative_to(lib_root)).replace("\\", "/")
                    # versteckte & leere Pfadteile meiden
                    if rel and not any(part.startswith(".") for part in rel.split("/")):
                        allowed.append(rel)
            except PermissionError:
                continue
    # Review-Ordner sicherstellen
    review = lib_root / REVIEW_FOLDER
    review.mkdir(parents=True, exist_ok=True)
    if REVIEW_FOLDER not in allowed:
        allowed.append(REVIEW_FOLDER)
    return sorted(set(allowed))


def build_schema(allowed_leaf_paths: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "target_path": {"type": "string", "enum": allowed_leaf_paths},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reason": {"type": "string"},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 12,
            },
            "caption": {"type": "string"},
            "alternatives": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["target_path", "confidence", "reason", "tags"],
        "additionalProperties": False,
    }
