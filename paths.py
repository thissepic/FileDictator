# paths.py
from pathlib import Path
import os, sys


def canon(p: Path) -> Path:
    """
    Return an absolute, canonical path:
    - expands ~
    - resolves .. and symlinks where possible
    - does not fail or change abruptly if the file does not yet exist (strict=False)
    """
    p = Path(p).expanduser()
    try:
        return p.resolve(strict=False)  # prefer resolve() over absolute()
    except Exception:
        return p.absolute()  # fallback
