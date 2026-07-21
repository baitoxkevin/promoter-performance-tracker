"""
Upload Route — Async "receive first, process later" architecture.

  1. Receives uploaded screenshots + promoter info
  2. Upserts the promoter record
  3. Saves images to disk & creates "pending" DB records
  4. Enqueues each submission for background OCR processing
  5. Returns immediately with a batch_id for status polling

Batch status endpoint allows frontend to poll processing progress.
"""

import os
import uuid
import time
import random
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db, Promoter, Submission
from models import (
    BatchUploadResponse,
    BatchStatusResponse,
    SubmissionResult,
    MySubmissionItem,
    MySubmissionsRequest,
    MySubmissionsResponse,
)
from worker import enqueue_ocr_task
from utils import get_storage_path, generate_filename
from config import MAX_FILE_SIZE_MB, MAX_FILES_PER_UPLOAD, UPLOAD_DIR

router = APIRouter()


def get_random_avatar(gender: str, db: Session) -> str:
    """Pick a random avatar, preferring unused ones to avoid duplicates on leaderboard."""
    avatar_pool = [f"/avatars/avatar_m{i}.png" for i in range(1, 9)] if gender == "male" else [f"/avatars/avatar_f{i}.png" for i in range(1, 9)]
    
    assigned_avatars = [r[0] for r in db.query(Promoter.avatar).filter(Promoter.avatar != None).all()]
    
    unused = [a for a in avatar_pool if a not in assigned_avatars]
    
    if unused:
        return random.choice(unused)
    else:
        freq = {a: 0 for a in avatar_pool}
        for a in assigned_avatars:
            if a in freq:
                freq[a] += 1
        
        sorted_avatars = sorted(avatar_pool, key=lambda a: freq[a])
        min_freq = freq[sorted_avatars[0]]
        least_used = [a for a in avatar_pool if freq[a] == min_freq]
        return random.choice(least_used)


@router.post("/upload", response_model=BatchUploadResponse)
async def upload_screenshots(
    promoter_name: str = Form(..., min_length=1, max_length=100),
    ic_number: str = Form(..., min_length=1, max_length=50),
    gender: str = Form(None),
    event: str = Form(None, max_length=100),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload one or more screenshots for async OCR processing.

    Files are saved to disk immediately and queued for background processing.
    Returns a batch_id that can be used to poll processing status.
    """
    # Validate file count
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum is {MAX_FILES_PER_UPLOAD} per upload.",
        )

    # Normalize gender input
    selected_gender = "female"
    if gender and gender.strip().lower() == "male":
        selected_gender = "male"

    # Event/activation tag (optional, free text — e.g. "MyTown Concourse")
    event_tag = event.strip() if event and event.strip() else None

    # ── Upsert promoter (find by IC number or create) ──
    promoter = (
        db.query(Promoter)
        .filter(Promoter.ic_number == ic_number.strip())
        .first()
    )
    if not promoter:
        promoter = Promoter(
            name=promoter_name.strip(),
            ic_number=ic_number.strip(),
            gender=selected_gender,
            avatar=get_random_avatar(selected_gender, db),
        )
        db.add(promoter)
        db.commit()
        db.refresh(promoter)
    else:
        if promoter.name != promoter_name.strip():
            promoter.name = promoter_name.strip()
        
        if not promoter.avatar or (gender and promoter.gender != selected_gender):
            promoter.gender = selected_gender
            promoter.avatar = get_random_avatar(selected_gender, db)
        
        db.commit()

    # ── Generate batch ID ──
    batch_id = str(uuid.uuid4())

    # ── Save each file to disk and create pending submissions ──
    # Use a "pending" subfolder under the promoter's directory
    pending_folder = get_storage_path(promoter.name, is_duplicate=False)
    pending_folder.mkdir(parents=True, exist_ok=True)

    submission_ids = []
    for upload_file in files:
        # Read file contents
        contents = await upload_file.read()
        file_size_mb = len(contents) / (1024 * 1024)

        if file_size_mb > MAX_FILE_SIZE_MB:
            # Create a failed submission directly (no need to queue)
            submission = Submission(
                promoter_id=promoter.id,
                batch_id=batch_id,
                extracted_username=None,
                event=event_tag,
                image_path="__skipped__",
                status="ocr_failed",
                ocr_raw_text=f"File too large ({file_size_mb:.1f}MB). Max is {MAX_FILE_SIZE_MB}MB.",
            )
            db.add(submission)
            db.commit()
            continue

        # Generate filename and save to disk
        filename = generate_filename(None)  # No username yet
        dest_path = pending_folder / filename

        with open(dest_path, "wb") as f:
            f.write(contents)

        # Relative path for DB storage
        relative_path = str(dest_path.relative_to(UPLOAD_DIR))

        # Create pending submission record
        submission = Submission(
            promoter_id=promoter.id,
            batch_id=batch_id,
            extracted_username=None,
            event=event_tag,
            image_path=relative_path,
            status="pending",
        )
        db.add(submission)
        db.flush()  # Get the ID
        submission_ids.append(submission.id)

    db.commit()

    # ── Enqueue all submissions for background processing ──
    for sid in submission_ids:
        enqueue_ocr_task(sid)

    return BatchUploadResponse(
        success=True,
        batch_id=batch_id,
        total_files=len(files),
        message=f"Upload successful! {len(files)} file(s) queued for OCR processing.",
        promoter_name=promoter.name,
    )


@router.get("/batch/{batch_id}/status", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    db: Session = Depends(get_db),
):
    """
    Poll the processing status of a batch upload.
    Returns the current state of each file in the batch.
    """
    submissions = (
        db.query(Submission)
        .filter(Submission.batch_id == batch_id)
        .order_by(Submission.id)
        .all()
    )

    if not submissions:
        raise HTTPException(status_code=404, detail="Batch not found.")

    results = []
    for sub in submissions:
        # Build user-facing message based on status
        if sub.status == "pending":
            message = "Processing..."
        elif sub.status == "valid":
            if sub.member_id:
                message = f"Success! '{sub.extracted_username}' (Member ID: {sub.member_id}) registered."
            else:
                message = f"Success! Username '{sub.extracted_username}' registered."
        elif sub.status == "duplicate":
            if sub.matched_name:
                message = f"Duplicate! '{sub.extracted_username}' matched '{sub.matched_name}' ({sub.similarity:.1f}%)."
            else:
                message = f"Duplicate! Username '{sub.extracted_username}' was already registered."
        elif sub.status == "ocr_failed":
            message = sub.ocr_raw_text or "Could not detect username."
        else:
            message = "Unknown status."

        results.append(SubmissionResult(
            filename=Path(sub.image_path).name if sub.image_path != "__skipped__" else "skipped",
            status=sub.status,
            extracted_username=sub.extracted_username,
            full_name=sub.full_name,
            member_id=sub.member_id,
            message=message,
        ))

    completed = sum(1 for r in results if r.status != "pending")
    pending = sum(1 for r in results if r.status == "pending")

    return BatchStatusResponse(
        batch_id=batch_id,
        total=len(results),
        completed=completed,
        pending=pending,
        results=results,
    )


# In-memory rate limiter for history lookups — deters IC-number enumeration.
#
# Keyed only on values a caller CANNOT forge to buy more throughput:
#   • a global cap  — bounds the total enumeration rate regardless of source
#   • a per-IC cap  — bounds hammering any single person's history
# Client IP is deliberately NOT used: the backend is reachable directly via
# the tunnel, where X-Forwarded-For / X-Nf-Client-Connection-Ip can be spoofed
# per request, so an IP-keyed limiter is trivially bypassed.
_global_hits: list = []
_per_ic_hits: dict = {}
_GLOBAL_LIMIT = 120     # total lookups per window (all callers combined)
_PER_IC_LIMIT = 10      # lookups per window for any single IC number
_LOOKUP_WINDOW = 60.0   # seconds


def _lookup_rate_limited(ic_key: str) -> bool:
    """Return True if this lookup should be rejected. Runs in the event loop
    (no await between check and record), so the section is effectively atomic."""
    global _global_hits
    now = time.time()

    _global_hits = [t for t in _global_hits if now - t < _LOOKUP_WINDOW]
    ic_hits = [t for t in _per_ic_hits.get(ic_key, []) if now - t < _LOOKUP_WINDOW]

    if len(_global_hits) >= _GLOBAL_LIMIT or len(ic_hits) >= _PER_IC_LIMIT:
        return True

    _global_hits.append(now)
    ic_hits.append(now)
    _per_ic_hits[ic_key] = ic_hits

    # Bound memory: drop IC buckets that have fully aged out
    if len(_per_ic_hits) > 5000:
        stale = [k for k, v in _per_ic_hits.items() if not any(now - t < _LOOKUP_WINDOW for t in v)]
        for k in stale:
            _per_ic_hits.pop(k, None)

    return False


@router.post("/my-submissions", response_model=MySubmissionsResponse)
async def my_submissions(
    payload: MySubmissionsRequest,
    db: Session = Depends(get_db),
):
    """
    A promoter's own submission history, looked up by IC number.
    Powers the "My Uploads" view in the frontend.
    POST body keeps the IC out of URLs / access logs; the global + per-IC
    rate limit deters brute-force enumeration of IC numbers.
    """
    ic = payload.ic_number.strip()
    if _lookup_rate_limited(ic):
        raise HTTPException(status_code=429, detail="Too many lookups. Please try again in a minute.")

    promoter = (
        db.query(Promoter)
        .filter(Promoter.ic_number == ic)
        .first()
    )
    if not promoter:
        return MySubmissionsResponse(
            promoter_name=None, total=0, valid=0, duplicate=0, failed=0, submissions=[]
        )

    subs = (
        db.query(Submission)
        .filter(Submission.promoter_id == promoter.id)
        .order_by(Submission.created_at.desc())
        .limit(200)
        .all()
    )

    items = [
        MySubmissionItem(
            id=s.id,
            status=s.status,
            full_name=s.full_name or s.extracted_username,
            member_id=s.member_id,
            event=s.event,
            image_url=None if s.image_path == "__skipped__" else f"/uploads/{s.image_path}",
            created_at=s.created_at.isoformat() if s.created_at else "",
        )
        for s in subs
    ]

    return MySubmissionsResponse(
        promoter_name=promoter.name,
        total=len(items),
        valid=sum(1 for i in items if i.status == "valid"),
        duplicate=sum(1 for i in items if i.status == "duplicate"),
        failed=sum(1 for i in items if i.status == "ocr_failed"),
        submissions=items,
    )
