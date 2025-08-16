# paths.py
from pathlib import Path
import os, sys


def canon(p: Path) -> Path:
    """
    Liefert einen *absoluten, kanonischen* Pfad:
    - expandiert ~
    - löst .. / Symlinks soweit möglich
    - ändert NICHT schlagartig, wenn Datei (noch) nicht existiert (strict=False)
    """
    p = Path(p).expanduser()
    try:
        return p.resolve(strict=False)  # pathlib empfiehlt resolve() statt absolute()
    except Exception:
        return p.absolute()  # Fallback
