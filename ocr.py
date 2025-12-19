"""Image-to-Text OCR module using Tesseract.

This module provides a small helper to extract text from images using
the Tesseract OCR binary via the `pytesseract` Python package.

It also includes a helpful pre-check that detects whether the Python
package and the Tesseract binary are available and returns clear
installation instructions when something is missing.
"""

import os
os.environ["TESSERACT_CMD"] = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


import io
from PIL import Image

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
except Exception:
    pytesseract = None


def _tesseract_check() -> tuple[bool, str]:
    """Check availability of pytesseract and the tesseract binary.

    Returns:
        (ok, message) where ok is True when OCR is available. If ok is
        False the message explains what to do to fix it.
    """
    if pytesseract is None:
        return False, "pytesseract Python package not installed. Run: pip install pytesseract"

    # Allow users to override binary path via environment variable
    env_cmd = os.environ.get("TESSERACT_CMD")
    default_windows = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    cmd = env_cmd or default_windows

    # If on Windows and default exists, set the pytesseract binary path
    if os.name == "nt" and os.path.isfile(cmd):
        pytesseract.pytesseract_cmd = cmd

    # Try to query the binary to ensure it works
    try:
        pytesseract.get_tesseract_version()
        return True, ""
    except Exception as e:
        hint = (
            "Tesseract binary not found or not working. Install Tesseract and ensure it's on PATH,\n"
            "or set the TESSERACT_CMD environment variable to the full path of tesseract.exe."
        )
        return False, f"{hint} (detail: {e})"


def extract_text_from_image(image_bytes: bytes) -> str:
    """Extract text from image bytes using Tesseract OCR.

    Args:
        image_bytes: Binary image data (jpg, png, etc.)

    Returns:
        Extracted text string.

    Raises:
        RuntimeError: If OCR is unavailable or extraction fails.
    """
    ok, msg = _tesseract_check()
    if not ok:
        raise RuntimeError(f"OCR unavailable: {msg}")

    try:
        image = Image.open(io.BytesIO(image_bytes))
        if image.mode != "RGB":
            image = image.convert("RGB")

        text = pytesseract.image_to_string(image)
        if not text or not text.strip():
            raise ValueError("No text found in image")

        return text.strip()

    except Exception as e:
        raise RuntimeError(f"OCR failed: {str(e)}")


def detect_language_from_text(text: str) -> str:
    """Detect language from extracted text.

    Simple heuristic: check for Arabic characters.
    """
    return "arabic" if any("\u0600" <= c <= "\u06FF" for c in text) else "english"
