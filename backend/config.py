"""
Configuration module for the Promoter Performance Tracker.
All configurable constants are centralized here for easy modification.
"""

from pathlib import Path

# ──────────────────────────────────────────────
# Directory paths
# ──────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"

# Ensure the uploads root directory exists on startup
UPLOAD_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
DATABASE_URL = f"sqlite:///{BASE_DIR / 'promoter_tracker.db'}"

import os
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv(BASE_DIR / ".env")

# ──────────────────────────────────────────────
# Tesseract & DeepSeek OCR Configuration
# ──────────────────────────────────────────────
TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"



# ──────────────────────────────────────────────
# Admin Authentication
# ──────────────────────────────────────────────
ADMIN_PIN = "1234"
# Admin session token expiry in seconds (24 hours)
ADMIN_TOKEN_EXPIRY = 86400

# ──────────────────────────────────────────────
# Upload Constraints
# ──────────────────────────────────────────────
MAX_FILE_SIZE_MB = 5
MAX_FILES_PER_UPLOAD = 10
