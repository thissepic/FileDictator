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
    Resize an image to at most max_dimension on the longest side.

    Args:
        image_path: path to the original image file
        max_dimension: maximum dimension in pixels (default: 1024)
        quality: JPEG quality for output (default: 95)

    Returns:
        (temporary path to resized image, cleanup function)
    """
    try:
        with Image.open(image_path) as img:
            # current dimensions
            width, height = img.size

            # check if resizing is necessary
            if width <= max_dimension and height <= max_dimension:
                # no resize needed, return original
                return image_path, lambda: None

            # preserve aspect ratio
            if width > height:
                new_width = max_dimension
                new_height = int(height * (max_dimension / width))
            else:
                new_height = max_dimension
                new_width = int(width * (max_dimension / height))

            # resize
            resized_img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # create temporary file
            temp_dir = tempfile.mkdtemp(prefix="docsort_resized_")
            temp_path = Path(temp_dir) / f"resized_{image_path.name}"

            # save resized image
            if image_path.suffix.lower() in [".jpg", ".jpeg"]:
                resized_img.save(temp_path, "JPEG", quality=quality, optimize=True)
            elif image_path.suffix.lower() == ".png":
                resized_img.save(temp_path, "PNG", optimize=True)
            else:
                # fallback to JPEG for other formats
                temp_path = temp_path.with_suffix(".jpg")
                resized_img.save(temp_path, "JPEG", quality=quality, optimize=True)

            # define cleanup function
            def cleanup():
                try:
                    if temp_path.exists():
                        temp_path.unlink()
                    if temp_dir and os.path.exists(temp_dir):
                        # remove all files in directory, if present
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
        # on failure, return original
        print(f"Warning: image resize failed for {image_path}: {e}")
        return image_path, lambda: None


def resize_images_batch(
    image_paths: list[str], max_dimension: int = 1024
) -> Tuple[list[str], callable]:
    """
    Resize a list of images to at most max_dimension.

    Args:
        image_paths: list of image paths
        max_dimension: maximum dimension in pixels (default: 1024)

    Returns:
        (list of resized image paths, cleanup function)
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

    # combined cleanup
    def combined_cleanup():
        for cleanup in cleanup_functions:
            try:
                cleanup()
            except Exception:
                pass

    return resized_paths, combined_cleanup
