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
import time
import shutil
import tempfile
import random
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from rapidfuzz import fuzz, process

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
    Process a single uploaded screenshot through the full high-speed OCR pipeline.
    Includes OpenCV preprocessing, RapidOCR, Rule Engine, and fuzzy duplicate checking.
    """
    total_start = time.time()

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

        # ── Step 3: Run OCR and extract username using the new pipeline ──
        ocr_result = process_image(str(temp_path))
        username = ocr_result["extracted_username"]
        raw_text = ocr_result["ocr_raw_text"]
        ocr_time = ocr_result["ocr_time"]
        rule_time = ocr_result["rule_time"]
        ocr_confidence = ocr_result["ocr_confidence"]
        candidate_score = ocr_result["candidate_score"]
        llm_used = ocr_result["llm_used"]

        if username is None:
            # OCR failed or no username detected → route to duplicate/failed folder
            filename = generate_filename(None)
            dest_folder = get_storage_path(promoter.name, is_duplicate=True)
            relative_path = save_uploaded_image(temp_path, dest_folder, filename)

            total_time = time.time() - total_start
            submission = Submission(
                promoter_id=promoter.id,
                extracted_username=None,
                image_path=relative_path,
                status="ocr_failed",
                ocr_raw_text=raw_text,
                ocr_time=ocr_time,
                rule_time=rule_time,
                matching_time=0.0,
                total_time=total_time,
                ocr_confidence=ocr_confidence,
                candidate_score=candidate_score,
                matched_name=None,
                similarity=0.0,
                llm_used=llm_used,
            )
            db.add(submission)
            db.commit()

            return SubmissionResult(
                filename=upload_file.filename or "unknown",
                status="ocr_failed",
                extracted_username=None,
                message="Could not detect username. Please retake a clearer screenshot.",
            )

        # ── Step 4: Fuzzy Match Duplicate Check using RapidFuzz ──
        match_start = time.time()
        
        # Retrieve all globally validated usernames for fuzzy comparison
        all_valid_entries = db.query(ValidUsername).all()
        
        best_match_name = None
        best_score = 0.0
        
        if all_valid_entries:
            usernames = [entry.username for entry in all_valid_entries]
            # Use token_sort_ratio to catch permutations/typos (e.g. LOO CHUN OIAN vs LOO CHUN QIAN)
            fuzz_res = process.extractOne(
                username, 
                usernames, 
                scorer=fuzz.token_sort_ratio
            )
            if fuzz_res:
                best_match_name, score_val, _ = fuzz_res
                # Also compute set ratio to handle partial/inclusion matching
                set_ratio = fuzz.token_set_ratio(username, best_match_name)
                best_score = max(score_val, set_ratio)

        matching_time = time.time() - match_start

        # Duplicate threshold is 92% similarity
        if best_score >= 92.0:
            # Duplicate found → route to duplicate folder
            filename = generate_filename(username)
            dest_folder = get_storage_path(promoter.name, is_duplicate=True)
            relative_path = save_uploaded_image(temp_path, dest_folder, filename)

            total_time = time.time() - total_start
            submission = Submission(
                promoter_id=promoter.id,
                extracted_username=username,
                image_path=relative_path,
                status="duplicate",
                ocr_raw_text=raw_text,
                ocr_time=ocr_time,
                rule_time=rule_time,
                matching_time=matching_time,
                total_time=total_time,
                ocr_confidence=ocr_confidence,
                candidate_score=candidate_score,
                matched_name=best_match_name,
                similarity=best_score,
                llm_used=llm_used,
            )
            db.add(submission)
            db.commit()

            return SubmissionResult(
                filename=upload_file.filename or "unknown",
                status="duplicate",
                extracted_username=username,
                message=f"Duplicate! Username '{username}' matched existing '{best_match_name}' ({best_score:.1f}% similarity).",
            )

        # ── Step 5: New username — save to valid folder ──
        filename = generate_filename(username)
        dest_folder = get_storage_path(promoter.name, is_duplicate=False)
        relative_path = save_uploaded_image(temp_path, dest_folder, filename)

        total_time = time.time() - total_start
        submission = Submission(
            promoter_id=promoter.id,
            extracted_username=username,
            image_path=relative_path,
            status="valid",
            ocr_raw_text=raw_text,
            ocr_time=ocr_time,
            rule_time=rule_time,
            matching_time=matching_time,
            total_time=total_time,
            ocr_confidence=ocr_confidence,
            candidate_score=candidate_score,
            matched_name=best_match_name,
            similarity=best_score,
            llm_used=llm_used,
        )
        db.add(submission)
        db.flush()  # Get submission.id before committing

        try:
            # Insert into valid_usernames
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
            # Database unique constraint fail (race condition fallback)
            db.rollback()

            # Move file to duplicate directory
            src_path = UPLOAD_DIR / relative_path
            dup_folder = get_storage_path(promoter.name, is_duplicate=True)
            dup_dest = dup_folder / filename
            if src_path.exists():
                shutil.move(str(src_path), str(dup_dest))
            new_relative_path = str(dup_dest.relative_to(UPLOAD_DIR))

            # Re-write duplicate submission record
            submission.image_path = new_relative_path
            submission.status = "duplicate"
            submission.similarity = 100.0  # Exact match constraint hit
            db.add(submission)
            db.commit()

            return SubmissionResult(
                filename=upload_file.filename or "unknown",
                status="duplicate",
                extracted_username=username,
                message=f"Duplicate! Username '{username}' was registered by another promoter.",
            )

    finally:
        # Always clean up temporary file
        if temp_path and temp_path.exists():
            os.unlink(temp_path)


def get_random_avatar(gender: str) -> str:
    num = random.randint(1, 4)
    if gender == "male":
        return f"/avatars/avatar_m{num}.png"
    else:
        return f"/avatars/avatar_f{num}.png"


@router.post("/upload", response_model=UploadResponse)
async def upload_screenshots(
    promoter_name: str = Form(..., min_length=1, max_length=100),
    ic_number: str = Form(..., min_length=1, max_length=50),
    gender: str = Form(None),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """
    Upload one or more screenshots for OCR processing.

    Form fields:
      - promoter_name: The promoter's full name
      - ic_number: The promoter's IC number (used as unique identifier)
      - gender: "male" or "female" (optional)
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
            avatar=get_random_avatar(selected_gender),
        )
        db.add(promoter)
        db.commit()
        db.refresh(promoter)
    else:
        # Update name if the promoter changed it
        if promoter.name != promoter_name.strip():
            promoter.name = promoter_name.strip()
        
        # If gender changed or if no avatar is assigned, assign new random avatar
        if not promoter.avatar or (gender and promoter.gender != selected_gender):
            promoter.gender = selected_gender
            promoter.avatar = get_random_avatar(selected_gender)
        
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
