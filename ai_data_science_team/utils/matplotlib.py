"""Image processing utilities with security hardening.

Security measures:
- Memory limits to prevent decompression bombs
- EXIF metadata stripping for privacy
- Image size validation
- Safe image loading with verification

Reference: https://github.com/python-pillow/Pillow/blob/main/docs/references/security.rst
"""

import base64  # noqa: E402, F401
from io import BytesIO  # noqa: E402, F401
from typing import Any, Optional, Tuple  # noqa: E402, F401

import matplotlib.pyplot as plt  # noqa: E402, F401
from PIL import Image  # noqa: E402, F401

Image.MAX_IMAGE_PIXELS = 100_000_000

MAX_IMAGE_SIZE_MB = 50
MAX_IMAGE_DIMENSION = 20000


def strip_exif_metadata(img: Image.Image) -> Image.Image:
    """Remove EXIF metadata from image for privacy.

    EXIF data can contain:
    - GPS coordinates
    - Device information
    - Timestamps
    - Camera settings

    Returns a new image without EXIF data.
    """
    data = list(img.getdata())
    img_without_exif = Image.new(img.mode, img.size)
    img_without_exif.putdata(data)

    return img_without_exif


def validate_image_size(img: Image.Image) -> None:
    """Validate image dimensions to prevent memory exhaustion.

    Raises ValueError if image is too large.
    """
    width, height = img.size
    if width > MAX_IMAGE_DIMENSION or height > MAX_IMAGE_DIMENSION:
        raise ValueError(
            f"Image dimensions ({width}x{height}) exceed maximum allowed "
            f"({MAX_IMAGE_DIMENSION}x{MAX_IMAGE_DIMENSION})"
        )

    total_pixels = width * height
    max_pixels = Image.MAX_IMAGE_PIXELS or 100_000_000
    if total_pixels > max_pixels:
        raise ValueError(
            f"Image has {total_pixels:,} pixels, exceeding maximum {max_pixels:,} pixels"
        )


def safe_load_image(file_bytes: bytes, max_size_mb: int = MAX_IMAGE_SIZE_MB) -> Image.Image:
    """Safely load an image with security checks.

    Security measures:
    - Size limit before loading
    - Decompression bomb detection
    - Image verification before full load
    - EXIF stripping

    Returns the loaded and sanitized image.
    Raises ValueError for security violations.
    """
    if len(file_bytes) > max_size_mb * 1024 * 1024:
        raise ValueError(f"Image exceeds maximum size of {max_size_mb}MB")

    if len(file_bytes) == 0:
        raise ValueError("Image data is empty")

    buf = BytesIO(file_bytes)

    try:
        img = Image.open(buf)
        img.verify()
    except Image.DecompressionBombError:
        raise ValueError("Decompression bomb detected - image rejected")
    except Exception as e:
        raise ValueError(f"Invalid image: {e}")

    buf.seek(0)

    try:
        img = Image.open(buf)
        img.load()
    except Image.DecompressionBombError:
        raise ValueError("Decompression bomb detected - image rejected")
    except Exception as e:
        raise ValueError(f"Failed to load image: {e}")

    validate_image_size(img)

    img = strip_exif_metadata(img)

    return img


def matplotlib_from_base64(
    encoded: str,
    title: Optional[str] = None,
    figsize: Tuple[int, int] = (8, 6),
) -> Tuple[Any, Any]:
    """Convert a base64-encoded image to a matplotlib plot.

    Security measures:
    - Memory limits for decompression bombs
    - EXIF metadata stripping
    - Image size validation

    Parameters
    ----------
    encoded : str
        The base64-encoded image string.
    title : str, optional
        A title for the plot. Default is None.
    figsize : tuple, optional
        Figure size (width, height) for the plot. Default is (8, 6).

    Returns
    -------
    fig, ax : tuple
        The matplotlib figure and axes objects.

    Raises
    ------
    ValueError
        If the image is invalid, too large, or a decompression bomb.
    """
    try:
        img_data = base64.b64decode(encoded, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64 encoding: {e}")

    img = safe_load_image(img_data)

    fig, ax = plt.subplots(figsize=figsize)

    ax.imshow(img)
    ax.axis("off")

    if title:
        ax.set_title(title)

    plt.show()

    return fig, ax


__all__ = [
    "strip_exif_metadata",
    "validate_image_size",
    "safe_load_image",
    "matplotlib_from_base64",
    "MAX_IMAGE_SIZE_MB",
    "MAX_IMAGE_DIMENSION",
]
