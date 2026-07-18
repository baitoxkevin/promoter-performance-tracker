"""
Utility functions for file management and data formatting.

Handles:
  - Promoter name sanitization for folder names
  - Storage path routing (valid vs duplicate folders)
  - Unique filename generation with timestamp + UUID
  - Image compression via Pillow
  - IC number masking for privacy
"""

import re
import uuid
import shutil
from pathlib import Path
from datetime import datetime

from PIL import Image

from config import UPLOAD_DIR


def sanitize_name(name: str) -> str:
    """
    Sanitize a promoter name for safe use in filesystem folder names.
    Removes special characters, replaces spaces with underscores.
    """
    # Remove any characters that aren't alphanumeric, spaces, hyphens, or underscores
    sanitized = re.sub(r"[^\w\s\-]", "", name)
    # Collapse whitespace and replace with underscores
    sanitized = re.sub(r"\s+", "_", sanitized).strip("_")
    return sanitized or "Unknown"


def get_storage_path(promoter_name: str, is_duplicate: bool) -> Path:
    """
    Determine the correct storage folder for an uploaded image.

    Valid uploads   → /uploads/Promoter_{Name}/
    Duplicates/fail → /uploads/duplicate-Promoter_{Name}/
    """
    sanitized = sanitize_name(promoter_name)
    if is_duplicate:
        folder_name = f"duplicate-Promoter_{sanitized}"
    else:
        folder_name = f"Promoter_{sanitized}"

    folder_path = UPLOAD_DIR / folder_name
    folder_path.mkdir(parents=True, exist_ok=True)
    return folder_path


def generate_filename(username: str | None) -> str:
    """
    Generate a unique, descriptive filename for the uploaded image.
    Format: {YYYYMMDD}_{HHMMSS}_{username}_{short_uuid}.jpg
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_username = sanitize_name(username) if username else "unknown"
    # Short UUID suffix prevents collisions from rapid uploads
    unique_id = uuid.uuid4().hex[:6]
    return f"{timestamp}_{safe_username}_{unique_id}.jpg"


def save_uploaded_image(source_path: Path, dest_folder: Path, filename: str) -> str:
    """
    Save an image to the destination folder with downscaling (max side 1600px)
    and JPEG compression (quality 80% to optimize space).
    Falls back to raw copy if Pillow fails.
    """
    dest_path = dest_folder / filename

    try:
        with Image.open(source_path) as img:
            # Downscale if longest side is > 1600px
            width, height = img.size
            if max(width, height) > 1600:
                if width > height:
                    new_w = 1600
                    new_h = int(height * (1600 / width))
                else:
                    new_h = 1600
                    new_w = int(width * (1600 / height))
                img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            # Convert RGBA/palette images to RGB for JPEG compatibility
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            
            # Save as JPEG with 80% quality
            img.save(dest_path, "JPEG", quality=80, optimize=True)
    except Exception as e:
        print(f"[Utils] Image compression failed: {e}. Copying raw file.")
        shutil.copy2(source_path, dest_path)

    # Return path relative to UPLOAD_DIR for database storage
    return str(dest_path.relative_to(UPLOAD_DIR))
def mask_ic_number(ic_number: str) -> str:
    """
    Mask an IC number for display, showing only the last 4 characters.
    Example: "A12345678" → "*****5678"
    """
    if len(ic_number) <= 4:
        return "****"
    return "*" * (len(ic_number) - 4) + ic_number[-4:]
