# image_utils.py
from __future__ import annotations
from pathlib import Path
from typing import Tuple
from PIL import Image
import tempfile
import os


def resize_image_to_max_dimension(
    image_path: Path, max_dimension: int = 1024, quality: int = 95
) -> Tuple[Path, callable]:
    """
    Skaliert ein Bild auf maximal max_dimension Pixel an der längsten Kante.

    Args:
        image_path: Pfad zur ursprünglichen Bilddatei
        max_dimension: Maximale Dimension in Pixeln (Standard: 1024)
        quality: JPEG-Qualität für die Ausgabe (Standard: 95)

    Returns:
        Tuple aus (temporärer Pfad zum skalierten Bild, Cleanup-Funktion)
    """
    try:
        with Image.open(image_path) as img:
            # Aktuelle Dimensionen ermitteln
            width, height = img.size

            # Prüfen, ob Skalierung notwendig ist
            if width <= max_dimension and height <= max_dimension:
                # Keine Skalierung nötig, Original zurückgeben
                return image_path, lambda: None

            # Seitenverhältnis beibehalten
            if width > height:
                new_width = max_dimension
                new_height = int(height * (max_dimension / width))
            else:
                new_height = max_dimension
                new_width = int(width * (max_dimension / height))

            # Bild skalierten
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Temporäre Datei erstellen
            temp_dir = tempfile.mkdtemp(prefix="docsort_resized_")
            temp_path = Path(temp_dir) / f"resized_{image_path.name}"

            # Skaliertes Bild speichern
            if image_path.suffix.lower() in [".jpg", ".jpeg"]:
                resized_img.save(temp_path, "JPEG", quality=quality, optimize=True)
            elif image_path.suffix.lower() == ".png":
                resized_img.save(temp_path, "PNG", optimize=True)
            else:
                # Fallback auf JPEG für andere Formate
                temp_path = temp_path.with_suffix(".jpg")
                resized_img.save(temp_path, "JPEG", quality=quality, optimize=True)

            # Cleanup-Funktion definieren
            def cleanup():
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                    if temp_dir and os.path.exists(temp_dir):
                        # Alle Dateien im Verzeichnis löschen, falls vorhanden
                        for file_path in Path(temp_dir).glob("*"):
                            try:
                                if file_path.is_file():
                                    file_path.unlink()
                            except Exception:
                                pass
                        os.rmdir(temp_dir)
                except Exception:
                    pass

            return temp_path, cleanup

    except Exception as e:
        # Bei Fehlern Original zurückgeben
        print(f"Warnung: Bildskalierung fehlgeschlagen für {image_path}: {e}")
        # Sicherstellen, dass der Pfad als String zurückgegeben wird
        return image_path, lambda: None


def resize_images_batch(
    image_paths: list[str], max_dimension: int = 1024
) -> Tuple[list[str], callable]:
    """
    Skaliert eine Liste von Bildern auf maximal max_dimension Pixel.

    Args:
        image_paths: Liste von Bildpfaden
        max_dimension: Maximale Dimension in Pixeln (Standard: 1024)

    Returns:
        Tuple aus (Liste der skalierten Bildpfade, Cleanup-Funktion)
    """
    if not image_paths:
        return [], lambda: None

    resized_paths = []
    cleanup_functions = []

    for img_path in image_paths:
        resized_path, cleanup = resize_image_to_max_dimension(
            Path(img_path), max_dimension
        )
        # Sicherstellen, dass der Pfad als String zurückgegeben wird
        resized_paths.append(str(resized_path))
        cleanup_functions.append(cleanup)

    # Kombinierte Cleanup-Funktion
    def combined_cleanup():
        for cleanup in cleanup_functions:
            try:
                cleanup()
            except Exception:
                pass

    return resized_paths, combined_cleanup
