"""
OCR Service — isolated so the extraction engine can be swapped without
touching any other part of the codebase.

Pipeline:
  raw bytes → preprocess (OpenCV) → OCR (Tesseract) → extract number → confidence score
"""

import re
import io
import logging
import numpy as np
import cv2
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)


def extract_glucose_value(image_bytes: bytes) -> dict:
    """
    Main entry point.
    Returns:
        {
            "success": bool,
            "value": int | None,
            "confidence": float,   # 0.0 – 1.0
            "raw_text": str,
            "error": str | None,
        }
    """
    try:
        img = _preprocess(image_bytes)
        raw_text = _run_tesseract(img)
        return _extract_number(raw_text)
    except Exception as exc:
        logger.exception("OCR pipeline failed")
        return {"success": False, "value": None, "confidence": 0.0, "raw_text": "", "error": str(exc)}


# ── Preprocessing ─────────────────────────────────────────────────────────────

def _preprocess(image_bytes: bytes) -> np.ndarray:
    """Convert raw bytes to a cleaned, upscaled grayscale image."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    if img is None:
        # Try PIL fallback
        pil = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Upscale for better OCR accuracy
    scale = 3
    scaled = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # Denoise
    denoised = cv2.fastNlMeansDenoising(scaled, h=10)

    # Adaptive threshold handles varied lighting on glucometer screens
    thresh = cv2.adaptiveThreshold(
        denoised, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=11,
        C=2,
    )

    return thresh


# ── OCR ───────────────────────────────────────────────────────────────────────

def _run_tesseract(img: np.ndarray) -> str:
    """Run Tesseract, restricted to digits and decimal point."""
    config = (
        "--psm 6 "          # assume uniform block of text
        "--oem 3 "          # LSTM engine
        "-c tessedit_char_whitelist=0123456789."
    )
    return pytesseract.image_to_string(img, config=config)


# ── Number extraction ─────────────────────────────────────────────────────────

# Plausible glucose range (mg/dL)
_MIN_GLUCOSE = 20
_MAX_GLUCOSE = 600

# Pattern: 2-3 digit integer, optionally followed by one decimal
_NUMBER_RE = re.compile(r"\b(\d{2,3}(?:\.\d)?)\b")


def _extract_number(raw_text: str) -> dict:
    """
    Find glucose-range numbers in OCR text and return the best candidate.
    Confidence is higher when exactly one plausible number is found.
    """
    matches = _NUMBER_RE.findall(raw_text)
    candidates = [float(m) for m in matches if _MIN_GLUCOSE <= float(m) <= _MAX_GLUCOSE]

    if not candidates:
        return {
            "success": False,
            "value": None,
            "confidence": 0.0,
            "raw_text": raw_text,
            "error": "No plausible glucose value found in image",
        }

    # Pick the first plausible value (glucometers display one large number)
    value = int(candidates[0])
    confidence = 0.95 if len(candidates) == 1 else 0.72

    return {
        "success": True,
        "value": value,
        "confidence": confidence,
        "raw_text": raw_text,
        "error": None,
    }
