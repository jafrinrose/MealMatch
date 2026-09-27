import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageOps

# Phone photos of receipts often have 10-12 px text; Tesseract reads it far more
# reliably at roughly twice that. Larger upscales started merging lines.
OCR_TARGET_LONG_SIDE = 2000
OCR_MAX_UPSCALE = 2.0
# Every image is converted to a prepared PNG before Tesseract reads it.
RECEIPT_IMAGE_TYPES = {".jpg", ".jpeg", ".png", ".webp"}


def find_tesseract() -> str:
    """
    Locates the Tesseract binary. Servers started outside a login shell often
    lack Homebrew on PATH, so the usual install locations are checked as well.
    """

    candidates = [
        os.getenv("MEALMATCH_TESSERACT_PATH", ""),
        shutil.which("tesseract") or "",
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
    ]

    for candidate in candidates:
        if candidate and os.access(candidate, os.X_OK):
            return candidate

    raise RuntimeError(
        "Tesseract OCR is not installed. Install it with 'brew install tesseract', "
        "or set MEALMATCH_TESSERACT_PATH to the tesseract binary."
    )


def prepare_for_ocr(image_path: str, output_path: str) -> None:
    """Upright, greyscale, contrast-stretched and upscaled copy of the receipt."""

    with Image.open(image_path) as source:
        image = ImageOps.exif_transpose(source).convert("L")
    scale = min(OCR_MAX_UPSCALE, OCR_TARGET_LONG_SIDE / max(image.size))
    if scale > 1.05:
        image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    ImageOps.autocontrast(image, cutoff=1).save(output_path)


def run_tesseract(image_path: str) -> list[str]:
    """
    Runs the Tesseract command-line OCR engine.
    This extracts raw text from a receipt image.
    """

    file_extension = Path(image_path).suffix.lower()

    if file_extension not in RECEIPT_IMAGE_TYPES:
        raise ValueError(
            "Unsupported image format for OCR. Please upload a JPG, PNG or WebP receipt image."
        )

    with tempfile.TemporaryDirectory() as workdir:
        prepared_path = os.path.join(workdir, "receipt.png")
        prepare_for_ocr(image_path, prepared_path)

        command = [
            find_tesseract(),
            prepared_path,
            "stdout",
            "-l",
            "eng",
            "--psm",
            "6",
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
        )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip())

    lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    return lines


def extract_receipt_text(image_path: str) -> dict:
    """
    OCR stage only:
    image path -> raw text lines.
    receipt_parsing.py then picks out the item lines and ai_services.py names them.
    """

    raw_text_lines = run_tesseract(image_path)

    return {
        "raw_text_lines": raw_text_lines,
    }