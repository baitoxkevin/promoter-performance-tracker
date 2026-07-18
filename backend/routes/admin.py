"""
Admin Routes — PIN-based authentication and dashboard data.

Security model:
  - Admin enters PIN "1234" to authenticate.
  - Server returns a random session token (stored in-memory).
  - All subsequent admin API calls must include the token in the Authorization header.
  - Tokens expire after 24 hours.

Note: This is a simple auth scheme suitable for internal tools.
For production, consider JWT tokens or OAuth.
"""

import secrets
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from sqlalchemy import func

from database import get_db, Promoter, Submission, ValidUsername
from models import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminStatsResponse,
    AdminSubmission,
    BatchDeleteRequest,
)
from config import ADMIN_PIN, ADMIN_TOKEN_EXPIRY

router = APIRouter()

# ──────────────────────────────────────────────
# In-memory token store (maps token → creation timestamp)
# For production, use Redis or a database table.
# ──────────────────────────────────────────────
_admin_tokens: dict[str, float] = {}


def _generate_admin_token() -> str:
    """Generate a cryptographically secure session token."""
    token = secrets.token_hex(32)
    _admin_tokens[token] = time.time()
    return token


def verify_admin_token(authorization: Optional[str] = Header(None)) -> bool:
    """
    FastAPI dependency that verifies the admin token from the Authorization header.
    Expected format: "Bearer <token>"
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required.")

    token = authorization.replace("Bearer ", "")

    if token not in _admin_tokens:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    # Check token expiry
    created_at = _admin_tokens[token]
    if time.time() - created_at > ADMIN_TOKEN_EXPIRY:
        del _admin_tokens[token]
        raise HTTPException(status_code=401, detail="Token expired. Please log in again.")

    return True


# ──────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────

@router.post("/admin/login", response_model=AdminLoginResponse)
async def admin_login(request: AdminLoginRequest):
    """
    Authenticate admin with PIN code.
    Returns a session token on success.
    """
    if request.pin == ADMIN_PIN:
        token = _generate_admin_token()
        return AdminLoginResponse(
            success=True,
            token=token,
            message="Login successful.",
        )

    return AdminLoginResponse(
        success=False,
        token=None,
        message="Invalid PIN. Please try again.",
    )


@router.get("/admin/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    status_filter: Optional[str] = None,
    promoter_filter: Optional[str] = None,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Get admin dashboard statistics and filtered submission list.

    Query params:
      - status_filter: Filter by submission status (valid|duplicate|ocr_failed)
      - promoter_filter: Search by promoter name (partial match)
    """
    # ── Aggregate counts ──
    total_promoters = db.query(func.count(Promoter.id)).scalar() or 0
    total_submissions = db.query(func.count(Submission.id)).scalar() or 0
    total_valid = (
        db.query(func.count(Submission.id))
        .filter(Submission.status == "valid")
        .scalar()
        or 0
    )
    total_duplicate = (
        db.query(func.count(Submission.id))
        .filter(Submission.status == "duplicate")
        .scalar()
        or 0
    )
    total_ocr_failed = (
        db.query(func.count(Submission.id))
        .filter(Submission.status == "ocr_failed")
        .scalar()
        or 0
    )

    # ── Build filtered submission query ──
    query = (
        db.query(Submission, Promoter)
        .join(Promoter, Promoter.id == Submission.promoter_id)
        .order_by(Submission.created_at.desc())
    )

    # Apply optional filters
    if status_filter and status_filter in ("valid", "duplicate", "ocr_failed"):
        query = query.filter(Submission.status == status_filter)

    if promoter_filter:
        query = query.filter(Promoter.name.ilike(f"%{promoter_filter}%"))

    # Limit to 200 most recent for performance
    submissions_data = query.limit(200).all()

    # ── Build response ──
    submissions = []
    for sub, promoter in submissions_data:
        submissions.append(
            AdminSubmission(
                id=sub.id,
                promoter_name=promoter.name,
                ic_number=promoter.ic_number,
                extracted_username=sub.extracted_username,
                status=sub.status,
                image_path=sub.image_path,
                created_at=sub.created_at.isoformat() if sub.created_at else "",
                ocr_time=sub.ocr_time,
                rule_time=sub.rule_time,
                matching_time=sub.matching_time,
                total_time=sub.total_time,
                ocr_confidence=sub.ocr_confidence,
                candidate_score=sub.candidate_score,
                matched_name=sub.matched_name,
                similarity=sub.similarity,
                llm_used=bool(sub.llm_used) if sub.llm_used is not None else False,
            )
        )

    return AdminStatsResponse(
        total_promoters=total_promoters,
        total_submissions=total_submissions,
        total_valid=total_valid,
        total_duplicate=total_duplicate,
        total_ocr_failed=total_ocr_failed,
        submissions=submissions,
    )


@router.delete("/admin/submission/{submission_id}")
async def delete_submission(
    submission_id: int,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Delete a submission by ID.
    If the submission was 'valid', this also deletes the username from valid_usernames
    to release the unique constraint.
    Also deletes the physical image file on disk.
    """
    submission = db.query(Submission).filter(Submission.id == submission_id).first()
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found.")

    # 1. Delete from valid_usernames if it exists
    db.query(ValidUsername).filter(ValidUsername.submission_id == submission_id).delete()

    # 2. Try deleting physical file on disk
    try:
        from config import UPLOAD_DIR
        file_path = UPLOAD_DIR / submission.image_path
        
        # Release any open Python file descriptors
        import gc
        gc.collect()
        
        if file_path.exists() and file_path.is_file():
            try:
                file_path.unlink()
            except PermissionError:
                # Fallback retry for Windows file locks
                import time
                time.sleep(0.1)
                gc.collect()
                file_path.unlink()
    except Exception as e:
        print(f"[Admin] Failed to delete image file: {str(e)}")

    # 3. Delete submission record
    db.delete(submission)
    db.commit()

    return {"success": True, "message": "Submission deleted successfully."}


@router.post("/admin/submissions/batch-delete")
async def delete_submissions_batch(
    request: BatchDeleteRequest,
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Delete multiple submissions by ID.
    Releases username constraints from valid_usernames and deletes files on disk.
    """
    deleted_count = 0
    errors = []
    
    # Fetch all submissions to delete
    submissions = db.query(Submission).filter(Submission.id.in_(request.ids)).all()
    
    for sub in submissions:
        # Delete from valid_usernames
        db.query(ValidUsername).filter(ValidUsername.submission_id == sub.id).delete()
        
        # Delete file on disk
        try:
            from config import UPLOAD_DIR
            file_path = UPLOAD_DIR / sub.image_path
            
            import gc
            gc.collect()
            
            if file_path.exists() and file_path.is_file():
                try:
                    file_path.unlink()
                except PermissionError:
                    import time
                    time.sleep(0.1)
                    gc.collect()
                    file_path.unlink()
        except Exception as e:
            err_msg = f"Failed to delete file for submission {sub.id}: {str(e)}"
            print(f"[Admin] {err_msg}")
            errors.append(err_msg)
            
        # Delete record
        db.delete(sub)
        deleted_count += 1
        
    db.commit()
    return {
        "success": True, 
        "message": f"Successfully deleted {deleted_count} submissions.",
        "errors": errors
    }


@router.get("/admin/promoters")
async def get_admin_promoters(
    db: Session = Depends(get_db),
    _: bool = Depends(verify_admin_token),
):
    """
    Retrieve all promoters, including their name, IC number, and gender.
    """
    promoters = db.query(Promoter).order_by(Promoter.name.asc()).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "ic_number": p.ic_number,
            "gender": p.gender or "unknown",
            "avatar": p.avatar,
            "created_at": p.created_at.isoformat() if p.created_at else "",
        }
        for p in promoters
    ]

