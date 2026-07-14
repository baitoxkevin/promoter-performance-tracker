"""
Upload Route — The core pipeline that handles:
  1. Receiving uploaded screenshots + promoter info
  2. Upserting the promoter record
  3. Running OCR on each image
  4. Checking for duplicate usernames (DB UNIQUE constraint)
  5. Routing images to the correct storage folder
  6. Returning per-file results to the frontend
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from database import get_db, Promoter, Submission, ValidUsername
from models import UploadResponse, SubmissionResult
from ocr_service import process_image
from utils import get_storage_path, generate_filename, save_uploaded_image
from config import MAX_FILE_SIZE_MB, MAX_FILES_PER_UPLOAD, UPLOAD_DIR

router = APIRouter()


async def _process_single_file(
    upload_file: UploadFile,
    promoter: Promoter,
    db: Session,
) -> SubmissionResult:
    """
    Process a single uploaded screenshot through the full OCR pipeline.
    This is extracted as a helper to keep the main route handler clean.
    """
    # ── Step 1: Read file contents and validate size ──
    contents = await upload_file.read()
    file_size_mb = len(contents) / (1024 * 1024)

    if file_size_mb > MAX_FILE_SIZE_MB:
        return SubmissionResult(
            filename=upload_file.filename or "unknown",
            status="ocr_failed",
            message=f"File too large ({file_size_mb:.1f}MB). Max is {MAX_FILE_SIZE_MB}MB.",
        )

    # ── Step 2: Save to temporary file for OCR processing ──
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(contents)
            temp_path = Path(tmp.name)

        # ── Step 3: Run OCR and extract username ──
        username, raw_text = process_image(str(temp_path))

        if username is None:
            # OCR failed or no username detected → route to duplicate folder
            filename = generate_filename(None)
            dest_folder = get_storage_path(promoter.name, is_duplicate=True)
            relative_path = save_uploaded_image(temp_path, dest_folder, filename)

            submission = Submission(
                promoter_id=promoter.id,
                extracted_username=None,
                image_path=relative_path,
                status="ocr_failed",
                ocr_raw_text=raw_text,
            )
            db.add(submission)
            db.commit()

            return SubmissionResult(
                filename=upload_file.filename or "unknown",
                status="ocr_failed",
                extracted_username=None,
                message="Could not detect username. Please retake a clearer screenshot.",
            )

        # ── Step 4: Check if this username already exists ──
        existing = (
            db.query(ValidUsername)
            .filter(ValidUsername.username == username)
            .first()
        )

        if existing:
            # Known duplicate → route to duplicate folder
            filename = generate_filename(username)
            dest_folder = get_storage_path(promoter.name, is_duplicate=True)
            relative_path = save_uploaded_image(temp_path, dest_folder, filename)

            submission = Submission(
                promoter_id=promoter.id,
                extracted_username=username,
                image_path=relative_path,
                status="duplicate",
                ocr_raw_text=raw_text,
            )
            db.add(submission)
            db.commit()

            return SubmissionResult(
                filename=upload_file.filename or "unknown",
                status="duplicate",
                extracted_username=username,
                message=f"Duplicate! Username '{username}' was already submitted.",
            )

        # ── Step 5: New username — save to valid folder ──
        filename = generate_filename(username)
        dest_folder = get_storage_path(promoter.name, is_duplicate=False)
        relative_path = save_uploaded_image(temp_path, dest_folder, filename)

        submission = Submission(
            promoter_id=promoter.id,
            extracted_username=username,
            image_path=relative_path,
            status="valid",
            ocr_raw_text=raw_text,
        )
        db.add(submission)
        db.flush()  # Get submission.id before committing

        try:
            # Insert into valid_usernames — UNIQUE constraint is our safety net
            valid_entry = ValidUsername(
                username=username,
                submission_id=submission.id,
                promoter_id=promoter.id,
            )
            db.add(valid_entry)
            db.commit()

            return SubmissionResult(
                filename=upload_file.filename or "unknown",
                status="valid",
                extracted_username=username,
                message=f"Success! Username '{username}' registered.",
            )

        except IntegrityError:
            # Race condition: another concurrent request inserted the same
            # username between our SELECT check and this INSERT.
            # This is extremely rare with SQLite but we handle it gracefully.
            db.rollback()

            # Move the file from the valid folder to the duplicate folder
            src_path = UPLOAD_DIR / relative_path
            dup_folder = get_storage_path(promoter.name, is_duplicate=True)
            dup_dest = dup_folder / filename
            if src_path.exists():
                shutil.move(str(src_path), str(dup_dest))
            new_relative_path = str(dup_dest.relative_to(UPLOAD_DIR))

            # Create a new submission record marked as duplicate
            dup_submission = Submission(
                promoter_id=promoter.id,
                extracted_username=username,
                image_path=new_relative_path,
                status="duplicate",
                ocr_raw_text=raw_text,
            )
            db.add(dup_submission)
            db.commit()

            return SubmissionResult(
                filename=upload_file.filename or "unknown",
                status="duplicate",
                extracted_username=username,
                message=f"Duplicate! Username '{username}' was submitted by another promoter.",
            )

    finally:
        # Always clean up the temporary file
        if temp_path and temp_path.exists():
            os.unlink(temp_path)


@router.post("/upload", response_model=UploadResponse)
async def upload_screenshots(
    promoter_name: str = Form(..., min_length=1, max_length=100),
    ic_number: str = Form(..., min_length=1, max_length=50),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload one or more screenshots for OCR processing.

    Form fields:
      - promoter_name: The promoter's full name
      - ic_number: The promoter's IC number (used as unique identifier)
      - files: One or more image files (JPEG/PNG)

    Each image goes through:
      1. OCR text extraction
      2. Username pattern matching
      3. Duplicate check against the database
      4. Routing to valid or duplicate storage folder
    """
    # Validate file count
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")
    if len(files) > MAX_FILES_PER_UPLOAD:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum is {MAX_FILES_PER_UPLOAD} per upload.",
        )

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
        )
        db.add(promoter)
        db.commit()
        db.refresh(promoter)
    else:
        # Update name if the promoter changed it
        if promoter.name != promoter_name.strip():
            promoter.name = promoter_name.strip()
            db.commit()

    # ── Process each file through the OCR pipeline ──
    results: List[SubmissionResult] = []
    for upload_file in files:
        result = await _process_single_file(upload_file, promoter, db)
        results.append(result)

    return UploadResponse(
        success=True,
        results=results,
        promoter_name=promoter.name,
    )
