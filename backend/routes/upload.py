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
from models import BatchUploadResponse, BatchStatusResponse, SubmissionResult
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
                image_path="__skipped__",
                status="ocr_failed",
                ocr_raw_text=f"File too large ({file_size_mb:.1f}MB). Max is {MAX_FILE_SIZE_MB}MB.",
            )
            db.add(submission)
            db.commit()
            continue

        # Check if HEIC/HEIF file
        filename_lower = upload_file.filename.lower() if upload_file.filename else ""
        content_type = upload_file.content_type.lower() if upload_file.content_type else ""
        is_heic = filename_lower.endswith((".heic", ".heif")) or content_type in ("image/heic", "image/heif")

        # Generate filename and save to disk
        filename = generate_filename(None)  # No username yet

        if is_heic:
            try:
                from pillow_heif import register_heif_opener
                from PIL import Image
                import io
                
                print(f"[Upload] Converting HEIC upload '{upload_file.filename}' to JPEG on backend...")
                register_heif_opener()
                image = Image.open(io.BytesIO(contents))
                
                # Convert to JPEG bytes
                out_buffer = io.BytesIO()
                image.convert("RGB").save(out_buffer, format="JPEG", quality=85)
                contents = out_buffer.getvalue()
                
                # Change filename extension to .jpg
                filename = filename.rsplit(".", 1)[0] + ".jpg"
            except Exception as e:
                print(f"[Upload] Backend HEIC conversion failed: {e}")

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
