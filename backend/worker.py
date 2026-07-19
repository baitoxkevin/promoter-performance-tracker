"""
Background Worker — In-memory task queue for async OCR processing.

Uses a simple threading.Thread + queue.Queue pattern to process
uploaded images one at a time in the background, without needing
external dependencies like Celery or Redis.

This is ideal for Render free tier with SQLite (no concurrent writes).
"""

import threading
import queue
import time
import os
import shutil
from pathlib import Path
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from rapidfuzz import fuzz, process

from database import SessionLocal, Submission, ValidUsername, Promoter
from ocr_service import process_image
from utils import get_storage_path, generate_filename
from config import UPLOAD_DIR

# ──────────────────────────────────────────────
# Task Queue
# ──────────────────────────────────────────────
_task_queue: queue.Queue = queue.Queue()
_worker_thread: Optional[threading.Thread] = None


def enqueue_ocr_task(submission_id: int):
    """Add a submission ID to the processing queue."""
    _task_queue.put(submission_id)
    print(f"[Worker] Enqueued submission #{submission_id} (queue size: {_task_queue.qsize()})")


def _process_submission(submission_id: int):
    """
    Process a single pending submission through the OCR pipeline.
    This runs in the background thread with its own DB session.
    """
    db: Session = SessionLocal()
    try:
        # Fetch the submission
        submission = db.query(Submission).filter(Submission.id == submission_id).first()
        if not submission:
            print(f"[Worker] Submission #{submission_id} not found, skipping.")
            return

        if submission.status != "pending":
            print(f"[Worker] Submission #{submission_id} already processed (status={submission.status}), skipping.")
            return

        # Get the promoter for folder routing
        promoter = db.query(Promoter).filter(Promoter.id == submission.promoter_id).first()
        if not promoter:
            print(f"[Worker] Promoter not found for submission #{submission_id}, marking as ocr_failed.")
            submission.status = "ocr_failed"
            submission.ocr_raw_text = "Promoter record not found."
            db.commit()
            return

        # Build the full image path
        image_full_path = str(UPLOAD_DIR / submission.image_path)

        if not os.path.exists(image_full_path):
            print(f"[Worker] Image file not found: {image_full_path}, marking as ocr_failed.")
            submission.status = "ocr_failed"
            submission.ocr_raw_text = "Image file not found on disk."
            db.commit()
            return

        total_start = time.time()

        # ── Run OCR ──
        try:
            ocr_result = process_image(image_full_path)
        except Exception as e:
            print(f"[Worker] OCR crashed for submission #{submission_id}: {e}")
            submission.status = "ocr_failed"
            submission.ocr_raw_text = f"OCR engine error: {str(e)}"
            submission.total_time = time.time() - total_start
            db.commit()
            return

        username = ocr_result["extracted_username"]
        raw_text = ocr_result["ocr_raw_text"]
        ocr_time = ocr_result["ocr_time"]
        rule_time = ocr_result["rule_time"]
        ocr_confidence = ocr_result["ocr_confidence"]
        candidate_score = ocr_result["candidate_score"]
        llm_used = ocr_result["llm_used"]

        # Update OCR fields on submission
        submission.ocr_raw_text = raw_text
        submission.ocr_time = ocr_time
        submission.rule_time = rule_time
        submission.ocr_confidence = ocr_confidence
        submission.candidate_score = candidate_score
        submission.llm_used = llm_used

        if username is None:
            # OCR failed to detect username
            # Move image to duplicate/failed folder
            _move_image(submission, promoter.name, is_duplicate=True, db=db)
            submission.status = "ocr_failed"
            submission.matching_time = 0.0
            submission.total_time = time.time() - total_start
            db.commit()
            print(f"[Worker] Submission #{submission_id}: OCR failed (no username detected)")
            return

        submission.extracted_username = username

        # ── Fuzzy Match Duplicate Check ──
        match_start = time.time()
        all_valid_entries = db.query(ValidUsername).all()

        best_match_name = None
        best_score = 0.0

        if all_valid_entries:
            usernames = [entry.username for entry in all_valid_entries]
            fuzz_res = process.extractOne(
                username,
                usernames,
                scorer=fuzz.token_sort_ratio
            )
            if fuzz_res:
                best_match_name, score_val, _ = fuzz_res
                set_ratio = fuzz.token_set_ratio(username, best_match_name)
                best_score = max(score_val, set_ratio)

        matching_time = time.time() - match_start
        submission.matching_time = matching_time
        submission.matched_name = best_match_name
        submission.similarity = best_score

        # Duplicate threshold: 92%
        if best_score >= 92.0:
            _move_image(submission, promoter.name, is_duplicate=True, db=db)
            submission.status = "duplicate"
            submission.total_time = time.time() - total_start
            db.commit()
            print(f"[Worker] Submission #{submission_id}: DUPLICATE '{username}' matched '{best_match_name}' ({best_score:.1f}%)")
            return

        # ── New valid username ──
        _move_image(submission, promoter.name, is_duplicate=False, db=db)
        submission.total_time = time.time() - total_start

        try:
            valid_entry = ValidUsername(
                username=username,
                submission_id=submission.id,
                promoter_id=promoter.id,
            )
            db.add(valid_entry)
            submission.status = "valid"
            db.commit()
            print(f"[Worker] Submission #{submission_id}: VALID '{username}' registered.")

        except IntegrityError:
            db.rollback()
            # Race condition: username was inserted by another submission
            _move_image(submission, promoter.name, is_duplicate=True, db=db)
            submission.status = "duplicate"
            submission.similarity = 100.0
            db.commit()
            print(f"[Worker] Submission #{submission_id}: DUPLICATE (DB constraint) '{username}'")

    except Exception as e:
        print(f"[Worker] Unexpected error processing submission #{submission_id}: {e}")
        try:
            submission = db.query(Submission).filter(Submission.id == submission_id).first()
            if submission and submission.status == "pending":
                submission.status = "ocr_failed"
                submission.ocr_raw_text = f"Worker error: {str(e)}"
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _move_image(submission: Submission, promoter_name: str, is_duplicate: bool, db: Session):
    """
    Move the image from its current pending location to the correct
    valid/duplicate folder, and update the submission's image_path.
    """
    current_path = UPLOAD_DIR / submission.image_path
    if not current_path.exists():
        return

    dest_folder = get_storage_path(promoter_name, is_duplicate=is_duplicate)
    filename = current_path.name
    dest_path = dest_folder / filename

    # Avoid overwriting
    if dest_path.exists():
        stem = dest_path.stem
        suffix = dest_path.suffix
        dest_path = dest_folder / f"{stem}_{int(time.time())}{suffix}"

    shutil.move(str(current_path), str(dest_path))
    submission.image_path = str(dest_path.relative_to(UPLOAD_DIR))


def _worker_loop():
    """Main loop for the background worker thread."""
    print("[Worker] Background OCR worker started.")
    while True:
        try:
            submission_id = _task_queue.get(block=True)  # Block until a task arrives
            print(f"[Worker] Processing submission #{submission_id}...")
            _process_submission(submission_id)
            _task_queue.task_done()
        except Exception as e:
            print(f"[Worker] Worker loop error: {e}")


def start_worker():
    """Start the background worker thread (daemon, auto-dies with main process)."""
    global _worker_thread
    if _worker_thread is not None and _worker_thread.is_alive():
        print("[Worker] Worker already running.")
        return

    _worker_thread = threading.Thread(target=_worker_loop, daemon=True, name="ocr-worker")
    _worker_thread.start()
    print("[Worker] Background OCR worker thread started.")
