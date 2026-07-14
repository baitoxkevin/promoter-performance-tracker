"""
Pydantic schemas for API request/response validation.
These models define the shape of data flowing through the API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List


# ──────────────────────────────────────────────
# Upload Endpoint
# ──────────────────────────────────────────────

class SubmissionResult(BaseModel):
    """Result for a single uploaded file after OCR processing."""
    filename: str
    status: str                           # "valid" | "duplicate" | "ocr_failed"
    extracted_username: Optional[str] = None
    message: str


class UploadResponse(BaseModel):
    """Response returned after processing all uploaded files."""
    success: bool
    results: List[SubmissionResult]
    promoter_name: str


# ──────────────────────────────────────────────
# Leaderboard Endpoint
# ──────────────────────────────────────────────

class LeaderboardEntry(BaseModel):
    """A single row in the leaderboard ranking."""
    rank: int
    promoter_name: str
    ic_number_masked: str   # Only last 4 digits shown for privacy
    valid_count: int


class LeaderboardResponse(BaseModel):
    """Full leaderboard data with aggregate statistics."""
    entries: List[LeaderboardEntry]
    total_promoters: int
    total_valid: int
    total_submissions: int
    last_updated: str


# ──────────────────────────────────────────────
# Admin Endpoints
# ──────────────────────────────────────────────

class AdminLoginRequest(BaseModel):
    """Admin login request with PIN."""
    pin: str = Field(..., min_length=1, max_length=20)


class AdminLoginResponse(BaseModel):
    """Admin login result with optional session token."""
    success: bool
    token: Optional[str] = None
    message: str


class AdminSubmission(BaseModel):
    """Detailed submission record for admin dashboard view."""
    id: int
    promoter_name: str
    ic_number: str
    extracted_username: Optional[str]
    status: str
    image_path: str
    created_at: str


class AdminStatsResponse(BaseModel):
    """Admin dashboard with aggregate stats and filterable submissions."""
    total_promoters: int
    total_submissions: int
    total_valid: int
    total_duplicate: int
    total_ocr_failed: int
    submissions: List[AdminSubmission]
