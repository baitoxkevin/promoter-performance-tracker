"""
Background Worker — Multi-threaded task queue for async OCR processing.

Uses ThreadPoolExecutor for parallel OCR processing and an in-memory
username cache to avoid full-table scans on every submission.

Thread safety for SQLite writes is ensured via a shared lock.
"""

import threading
import time
import os
import shutil
from pathlib import Path
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from rapidfuzz import fuzz, process

from database import SessionLocal, Submission, ValidUsername, Promoter
from ocr_service import process_image
from utils import get_storage_path
from config import UPLOAD_DIR, OCR_WORKERS

# ──────────────────────────────────────────────
# Parallelism & Thread Safety
# ──────────────────────────────────────────────
_MAX_WORKERS = OCR_WORKERS
_executor: Optional[ThreadPoolExecutor] = None
_db_lock = threading.Lock()  # Serializes SQLite writes across threads

# ──────────────────────────────────────────────
# In-Memory Username Cache (avoids full-table scan)
# ──────────────────────────────────────────────
_username_cache: List[str] = []
_username_cache_lock = threading.RLock()  # Reentrant lock — safe for nested acquisition


def _refresh_username_cache(db: Session):
    """Reload the full list of valid usernames from the database."""
    global _username_cache
    entries = db.query(ValidUsername.username).all()
    with _username_cache_lock:
        _username_cache = [e[0] for e in entries]


def _add_to_cache(username: str):
    """Append a newly-validated username to the in-memory cache."""
    with _username_cache_lock:
        _username_cache.append(username)


def remove_from_cache(username: str):
    """Remove a username from the in-memory cache (e.g., after admin deletion)."""
    with _username_cache_lock:
        if username in _username_cache:
            _username_cache.remove(username)
            print(f"[Worker] Removed '{username}' from username cache.")


def get_cached_usernames() -> List[str]:
    """Return a snapshot of the current username cache (thread-safe)."""
    with _username_cache_lock:
        return list(_username_cache)


def enqueue_ocr_task(submission_id: int):
    """Submit a submission ID to the worker pool for background processing."""
    if _executor is None:
        print("[Worker] Executor not started! Falling back to sync processing.")
        _process_submission(submission_id)
        return
    _executor.submit(_process_submission, submission_id)
    print(f"[Worker] Enqueued submission #{submission_id} (active threads may be processing)")


def _process_submission(submission_id: int):
    """
    Process a single pending submission through the OCR pipeline.
    Runs in any worker thread with its own DB session.
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
            with _db_lock:
                submission.status = "ocr_failed"
                submission.ocr_raw_text = "Promoter record not found."
                db.commit()
            return

        # Build the full image path
        image_full_path = str(UPLOAD_DIR / submission.image_path)

        if not os.path.exists(image_full_path):
            print(f"[Worker] Image file not found: {image_full_path}, marking as ocr_failed.")
            with _db_lock:
                submission.status = "ocr_failed"
                submission.ocr_raw_text = "Image file not found on disk."
                db.commit()
            return

        total_start = time.time()

        # ── Run OCR (CPU-bound, GIL released — safe to run in parallel) ──
        try:
            ocr_result = process_image(image_full_path)
        except Exception as e:
            print(f"[Worker] OCR crashed for submission #{submission_id}: {e}")
            with _db_lock:
                submission.status = "ocr_failed"
                submission.ocr_raw_text = f"OCR engine error: {str(e)}"
                submission.total_time = time.time() - total_start
                db.commit()
            return

        username = ocr_result["extracted_username"]
        member_id = ocr_result.get("member_id")
        raw_text = ocr_result["ocr_raw_text"]
        ocr_time = ocr_result["ocr_time"]
        rule_time = ocr_result["rule_time"]
        ocr_confidence = ocr_result["ocr_confidence"]
        candidate_score = ocr_result["candidate_score"]
        llm_used = ocr_result["llm_used"]

        # Update OCR fields on submission
        submission.member_id = member_id  # Recorded even if the name wasn't detected
        submission.ocr_raw_text = raw_text
        submission.ocr_time = ocr_time
        submission.rule_time = rule_time
        submission.ocr_confidence = ocr_confidence
        submission.candidate_score = candidate_score
        submission.llm_used = llm_used

        if username is None:
            _move_image(submission, promoter.name, is_duplicate=True, db=db)
            with _db_lock:
                submission.status = "ocr_failed"
                submission.matching_time = 0.0
                submission.total_time = time.time() - total_start
                db.commit()
            print(f"[Worker] Submission #{submission_id}: OCR failed (no username detected)")
            return

        submission.extracted_username = username
        submission.full_name = username

        # ── Duplicate detection ──
        # The member ID is the authoritative unique key. When we have one, it is
        # the ONLY thing that decides a duplicate — two different member IDs are
        # two different people even if they share a name (e.g. two "Siang"s).
        # Fuzzy name matching is only a fallback for when OCR couldn't read an ID.
        if member_id:
            existing = (
                db.query(ValidUsername)
                .filter(ValidUsername.member_id == member_id)
                .first()
            )
            submission.matching_time = 0.0
            if existing:
                submission.matched_name = existing.username
                submission.similarity = 100.0
                _move_image(submission, promoter.name, is_duplicate=True, db=db)
                with _db_lock:
                    submission.status = "duplicate"
                    submission.total_time = time.time() - total_start
                    db.commit()
                print(f"[Worker] Submission #{submission_id}: DUPLICATE member ID '{member_id}' already registered to '{existing.username}'")
                return
            # member ID present and unique → not a duplicate; skip name matching
        else:
            # ── No member ID read → fall back to fuzzy name matching ──
            match_start = time.time()
            with _username_cache_lock:
                if not _username_cache:
                    _refresh_username_cache(db)

            usernames = get_cached_usernames()

            best_match_name = None
            best_score = 0.0

            if usernames:
                fuzz_res = process.extractOne(username, usernames, scorer=fuzz.token_sort_ratio)
                if fuzz_res:
                    best_match_name, score_val, _ = fuzz_res
                    set_ratio = fuzz.token_set_ratio(username, best_match_name)
                    best_score = max(score_val, set_ratio)

            submission.matching_time = time.time() - match_start
            submission.matched_name = best_match_name
            submission.similarity = best_score

            # Duplicate threshold: 92%
            if best_score >= 92.0:
                _move_image(submission, promoter.name, is_duplicate=True, db=db)
                with _db_lock:
                    submission.status = "duplicate"
                    submission.total_time = time.time() - total_start
                    db.commit()
                print(f"[Worker] Submission #{submission_id}: DUPLICATE '{username}' matched '{best_match_name}' ({best_score:.1f}%)")
                return

        # ── New valid username ──
        _move_image(submission, promoter.name, is_duplicate=False, db=db)
        submission.total_time = time.time() - total_start

        with _db_lock:
            try:
                valid_entry = ValidUsername(
                    username=username,
                    member_id=member_id,
                    submission_id=submission.id,
                    promoter_id=promoter.id,
                )
                db.add(valid_entry)
                submission.status = "valid"
                db.commit()
                # Update in-memory cache on success
                _add_to_cache(username)
                print(f"[Worker] Submission #{submission_id}: VALID '{username}' registered.")

            except IntegrityError:
                db.rollback()
                # Race condition: username was inserted by another worker
                _move_image(submission, promoter.name, is_duplicate=True, db=db)
                submission.status = "duplicate"
                submission.similarity = 100.0
                db.commit()
                print(f"[Worker] Submission #{submission_id}: DUPLICATE (DB constraint) '{username}'")

    except Exception as e:
        print(f"[Worker] Unexpected error processing submission #{submission_id}: {e}")
        import traceback
        traceback.print_exc()
        try:
            with _db_lock:
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


def start_worker():
    """Start the ThreadPoolExecutor for parallel OCR processing."""
    global _executor
    if _executor is not None:
        print("[Worker] Executor already running.")
        return

    _executor = ThreadPoolExecutor(max_workers=_MAX_WORKERS)
    # Pre-warm the username cache on startup
    db = SessionLocal()
    try:
        _refresh_username_cache(db)
        print(f"[Worker] Username cache loaded: {len(_username_cache)} entries.")
    finally:
        db.close()
    print(f"[Worker] ThreadPoolExecutor started with {_MAX_WORKERS} workers.")
