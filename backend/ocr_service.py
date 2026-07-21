import os
import re
import time
import json
import hashlib
import threading
import numpy as np
import cv2
from PIL import Image, ImageEnhance
from typing import Optional, Tuple, Dict, Any, List
from openai import OpenAI
from rapidocr_onnxruntime import RapidOCR

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL, OCR_MAX_DIMENSION, OCR_SKIP_DESKEW

# Initialize DeepSeek Client only if API key is provided
client: Optional[OpenAI] = None
if DEEPSEEK_API_KEY.strip():
    client = OpenAI(
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
    )


# Lazy-loaded singleton RapidOCR reader
_ocr_engine: Optional[RapidOCR] = None

def get_ocr_engine() -> RapidOCR:
    """Return the singleton RapidOCR engine instance."""
    global _ocr_engine
    if _ocr_engine is None:
        print("[OCR] Initializing RapidOCR engine...")
        _ocr_engine = RapidOCR()
        print("[OCR] RapidOCR engine initialized successfully.")
    return _ocr_engine

# List of common layout/header/system text to penalize
PENALIZED_WORDS = {
    "profile", "my profile", "settings", "edit", "logout", "back", "home", 
    "me", "faq", "faqs", "contact", "support", "help", "version", "transaction",
    "history", "points", "rewards", "vouchers", "voucher", "account", "details",
    "member", "status", "level", "loyalty", "successful", "success", "fail", 
    "failed", "register", "registration", "welcome", "signups", "signup", "promoter",
    "bites", "purveyor", "food", "notification", "copy", "copied", "membership",
    "events", "event"
}

def preprocess_image(image_path: str) -> Tuple[np.ndarray, float]:
    """
    Perform advanced image preprocessing using OpenCV:
      1. Resize so that the longest edge is at most 1600px.
      2. Convert to grayscale.
      3. Apply Contrast Limited Adaptive Histogram Equalization (CLAHE) for contrast.
      4. Perform Deskewing to straighten text.
    """
    start_time = time.time()
    
    # Read image using OpenCV
    img = cv2.imread(image_path)
    if img is None:
        raise ValueError(f"Failed to read image from path: {image_path}")
        
    h, w = img.shape[:2]
    
    # 1. Resize to configured max side (480 cloud, 640 local)
    max_side = OCR_MAX_DIMENSION
    if max(h, w) > max_side:
        if w > h:
            new_w = max_side
            new_h = int(h * (max_side / w))
        else:
            new_h = max_side
            new_w = int(w * (max_side / h))
        img = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        h, w = new_h, new_w

    # 2. Grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 3. Contrast enhancement using CLAHE
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(gray)

    # 4. Deskewing (skipped on cloud for speed)
    angle = 0.0
    if not OCR_SKIP_DESKEW:
        # Downsample 4x before angle detection for speed
        ds_factor = 4
        small = cv2.resize(contrast, (w // ds_factor, h // ds_factor), interpolation=cv2.INTER_AREA)
        coords = np.column_stack(np.where(small < 100))
        if len(coords) > 0:
            rect = cv2.minAreaRect(coords)
            angle = rect[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            if 0.5 <= abs(angle) <= 15:
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                contrast = cv2.warpAffine(
                    contrast, M, (w, h),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REPLICATE
                )

    preprocess_time = time.time() - start_time
    print(f"[OCR] Preprocessed image in {preprocess_time:.3f}s. Deskew: {'skipped' if OCR_SKIP_DESKEW else f'{angle:.2f}°'}")
    return contrast, preprocess_time

def run_rapid_ocr(processed_img: np.ndarray) -> Tuple[List[Dict[str, Any]], float]:
    """Run RapidOCR on the preprocessed image array."""
    start_time = time.time()
    engine = get_ocr_engine()
    
    # RapidOCR accepts numpy arrays directly
    result, elapse = engine(processed_img)
    
    ocr_lines = []
    if result:
        for box, text, confidence in result:
            ocr_lines.append({
                "text": text.strip(),
                "confidence": float(confidence),
                "box": box
            })
            
    ocr_time = time.time() - start_time
    return ocr_lines, ocr_time

# LLM response cache — keyed by OCR text hash, avoids redundant API calls
# Max 100 entries, stores (username, None) pairs where None means "no name found"
_llm_cache: Dict[str, Optional[str]] = {}
_llm_cache_lock = threading.Lock()
_LLM_CACHE_MAX = 100

def _cache_key(text: str) -> str:
    """Short hash of OCR text for cache lookups."""
    return hashlib.md5(text.encode("utf-8")).hexdigest()[:12]


def extract_username_with_llm(ocr_text: str) -> Optional[str]:
    """Fallback: Call DeepSeek LLM to extract the username from OCR raw text."""
    # ── Guard: skip empty or very short OCR text ──
    stripped = ocr_text.strip()
    if len(stripped) < 10:
        print(f"[OCR-LLM] OCR text too short ({len(stripped)} chars), skipping LLM fallback.")
        return None

    # ── Check cache first ──
    key = _cache_key(stripped)
    with _llm_cache_lock:
        if key in _llm_cache:
            cached = _llm_cache[key]
            print(f"[OCR-LLM] Cache HIT — returning cached result: '{cached}'")
            return cached

    system_prompt = (
        "You are an expert, highly intelligent parser for mobile app profile screenshots. "
        "You specialize in identifying registered user names from raw OCR text by understanding the screen layout context."
    )
    
    prompt = (
        "Analyze the following full raw OCR text extracted from a mobile app profile screenshot.\n"
        "Your task is to identify and extract the actual registered user's name or username.\n\n"
        "INSTRUCTIONS:\n"
        "1. Identify the registered user's name (e.g. 'LOO CHUN QIAN', 'Jessica', 'Yan Ling').\n"
        "2. Exclude app headers, system labels, points, or status texts.\n"
        "3. Output format: Return a valid JSON array of strings containing the name. Format: [\"Name\"].\n"
        "4. If no registered name is found, return an empty array: [].\n"
        "5. Output ONLY the JSON array. Do not wrap in markdown fences and do not explain.\n\n"
        f"Raw OCR text:\n---\n{ocr_text}\n---"
    )

    if not client:
        print("[OCR-LLM] DeepSeek client is not initialized (missing API key). Bypassing LLM fallback.")
        return None

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=60,
            timeout=3.0,
        )
        
        content = response.choices[0].message.content
        if not content:
            return None
        
        content_clean = content.strip()
        if content_clean.startswith("```"):
            content_clean = re.sub(r"^```(?:json)?\n", "", content_clean)
            content_clean = re.sub(r"\n```$", "", content_clean)
            content_clean = content_clean.strip()

        names = json.loads(content_clean)
        result = str(names[0]).strip() if (isinstance(names, list) and len(names) > 0) else None
        # Write to cache
        with _llm_cache_lock:
            if len(_llm_cache) >= _LLM_CACHE_MAX:
                # Evict oldest entry (first key, simple FIFO eviction)
                _llm_cache.pop(next(iter(_llm_cache)))
            _llm_cache[key] = result
        return result
    except Exception as e:
        print(f"[OCR-LLM] DeepSeek call failed: {e}")
        # Cache failures too (as None) to avoid repeated failing calls
        with _llm_cache_lock:
            if len(_llm_cache) >= _LLM_CACHE_MAX:
                _llm_cache.pop(next(iter(_llm_cache)))
            _llm_cache[key] = None
        return None

def evaluate_candidates(ocr_lines: List[Dict[str, Any]]) -> Tuple[Optional[str], int]:
    """
    Rule Engine: Analyze the extracted OCR text lines and select the best promoter name candidate.
    
    Rules & Scoring:
      +30: Line is immediately below or adjacent to a "Welcome" prefix line.
      +20: Line is immediately below a "Name" / "Username" / "姓名" / "Nama" label line.
      +25: Line is followed within 2 lines by member metadata (ID, Member Since, etc.).
      +15: Line matches 2~5 Chinese characters.
      +15: Line matches 1~6 English words (letters/spaces only).
      -30: Contains digits.
      -20: Contains URL/links.
      -20: Word token intersection matches PENALIZED_WORDS.
      -20: All uppercase random characters.
    """
    candidates = []
    
    for i, line in enumerate(ocr_lines):
        text = line["text"]
        clean_text = text.strip()
        
        # Skip empty lines or single characters
        if len(clean_text) < 2 or len(clean_text) > 50:
            continue
            
        score = 0
        text_lower = clean_text.lower()

        # Lines that are exactly a UI/button/label word (e.g. "Copy", "Membership")
        # or any "Membership No."-style label can never be the name — skip them
        # outright so adjacency bonuses can't rescue them
        if text_lower in PENALIZED_WORDS or "membership" in text_lower:
            continue

        # Check context patterns by scanning surrounding lines
        # Check preceding line (if any)
        if i > 0:
            prev_text = ocr_lines[i-1]["text"].lower()
            if any(kw in prev_text for kw in ["welcome", "selamat datang", "welcome back", "welcome,"]):
                score += 30
            elif any(kw in prev_text for kw in ["name", "username", "nickname", "姓名", "nama", "user", "membership"]):
                score += 20
                
        # Check if the current line has a prefix (e.g. "Name: LOO CHUN QIAN" or "Welcome, Jessica")
        if text_lower.startswith("welcome"):
            score += 30
            # Strip the prefix to evaluate the name itself
            clean_text = re.sub(r"^welcome\s*[,!:\-]?\s*", "", clean_text, flags=re.IGNORECASE).strip()
        elif re.search(r"^(?:name|username|nickname|姓名|nama)\s*[:：\-]\s*", clean_text, re.IGNORECASE):
            score += 20
            clean_text = re.sub(r"^(?:name|username|nickname|姓名|nama)\s*[:：\-]\s*", "", clean_text, flags=re.IGNORECASE).strip()
            
        # Re-evaluate length after prefix stripping
        if len(clean_text) < 2:
            continue

        # Check succeeding lines for member metadata/ID markers (Bonus points)
        # Name is usually followed by Member ID or Member Since or points.
        # Only name-like lines free of UI words earn this bonus — otherwise
        # labels/buttons/menus sitting above the member number or near metadata
        # keywords (e.g. "Copy", "My Transaction History") hijack it.
        tokens = set(re.findall(r"[a-z]+", text_lower))
        is_name_like = bool(
            re.match(r"^[\u4e00-\u9fa5]{2,5}$", clean_text)
            or re.match(r"^[A-Za-z]+(?:\s+[A-Za-z]+){0,5}$", clean_text)
        ) and not tokens.intersection(PENALIZED_WORDS)
        if is_name_like:
            for offset in [1, 2]:
                if i + offset < len(ocr_lines):
                    next_text = ocr_lines[i+offset]["text"].lower()
                    if any(kw in next_text for kw in ["member since", "since", "member id", "points", "loyalty"]):
                        score += 25
                        break
                    elif next_text.strip().isdigit() and len(next_text.strip()) >= 5:
                        score += 20
                        break

        # Language Format Scoring
        # 1. Chinese Name (2~5 characters)
        if re.match(r"^[\u4e00-\u9fa5]{2,5}$", clean_text):
            score += 15
        # 2. English Name (1~6 words, letters/spaces only)
        elif re.match(r"^[A-Za-z]+(?:\s+[A-Za-z]+){0,5}$", clean_text):
            score += 15
            
        # Penalty Rules
        # 1. Contains digits
        if any(c.isdigit() for c in clean_text):
            score -= 30
        # 2. Contains URLs
        if any(kw in text_lower for kw in [".com", ".net", ".org", "http", "www", "/"]):
            score -= 20
        # 3. Penalized layout / menu keywords (word token intersection check)
        if tokens.intersection(PENALIZED_WORDS):
            score -= 20
        # 4. All uppercase random/garbage characters
        if clean_text.isupper() and len(clean_text.split()) == 1 and len(clean_text) > 8:
            score -= 20
            
        candidates.append((clean_text, score))
        
    if not candidates:
        return None, 0
        
    # Sort candidates by score descending
    candidates.sort(key=lambda x: x[1], reverse=True)
    best_candidate, best_score = candidates[0]
    return best_candidate, best_score

def extract_member_id(ocr_lines: List[Dict[str, Any]]) -> Optional[str]:
    """
    Find the member/membership ID: a digit-only line (5-12 digits after
    stripping spaces/dashes), preferring one adjacent to a 'member' label.
    """
    candidates = []
    for i, line in enumerate(ocr_lines):
        digits = re.sub(r"[\s\-]", "", line["text"].strip())
        if digits.isdigit() and 5 <= len(digits) <= 12:
            score = 0
            for offset in (-2, -1, 1):
                j = i + offset
                if 0 <= j < len(ocr_lines) and "member" in ocr_lines[j]["text"].lower():
                    score += 10
                    break
            candidates.append((digits, score))

    if not candidates:
        return None
    candidates.sort(key=lambda c: c[1], reverse=True)
    return candidates[0][0]


def process_image(image_path: str) -> Dict[str, Any]:
    """
    Fully-rewritten High-Speed OCR Pipeline:
      1. Preprocess image (resize to 1600px, grayscale, CLAHE contrast, adaptive thresh, median blur, deskew).
      2. Run RapidOCR (PaddleOCR ONNX) -> extremely fast.
      3. Run Rule Engine -> Score candidates.
      4. Fallback to LLM only if score < 10, no candidate found, or OCR confidence is extremely low (< 0.45).
      5. Time every phase and return stats.
    """
    total_start = time.time()
    
    # ── Phase 1: Preprocessing ──
    try:
        processed_img, prep_time = preprocess_image(image_path)
    except Exception as e:
        print(f"[OCR] Preprocessing error: {e}. Falling back to raw image read.")
        # Fallback to standard grayscale read
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        processed_img = img if img is not None else np.zeros((320, 320), dtype=np.uint8)
        prep_time = 0.0
        
    # ── Phase 2: OCR ──
    ocr_lines, ocr_time = run_rapid_ocr(processed_img)
    
    # Compute average OCR confidence
    avg_confidence = np.mean([line["confidence"] for line in ocr_lines]) if ocr_lines else 0.0
    
    # ── Phase 3: Rule Engine ──
    rule_start = time.time()
    extracted_name, candidate_score = evaluate_candidates(ocr_lines)
    member_id = extract_member_id(ocr_lines)
    rule_time = time.time() - rule_start
    
    llm_used = False
    
    # Combine full raw text for debugging and LLM fallback
    raw_text = "\n".join([line["text"] for line in ocr_lines])
    
    # ── Phase 4: Optional LLM Fallback ──
    # Trigger LLM if score is too low, no candidate extracted, or OCR confidence is terrible
    if extracted_name is None or candidate_score < 10 or avg_confidence < 0.45:
        if DEEPSEEK_API_KEY:
            print(f"[OCR] Rule engine failed/weak (name='{extracted_name}', score={candidate_score}, conf={avg_confidence:.2f}). Triggering LLM fallback...")
            llm_start = time.time()
            llm_name = extract_username_with_llm(raw_text)
            llm_time = time.time() - llm_start
            
            if llm_name:
                print(f"[OCR-LLM] Successfully extracted name via LLM: '{llm_name}' in {llm_time:.3f}s")
                extracted_name = llm_name
                candidate_score = 50  # Arbitrary high score for successful LLM extraction
                llm_used = True
                # Add LLM time to rule_time for tracking
                rule_time += llm_time
        else:
            print(f"[OCR] Rule engine weak, but DEEPSEEK_API_KEY is not set. Bypassing LLM.")

    total_time = time.time() - total_start
    
    # Print summary performance metrics
    print(f"[OCR-Pipeline] Completed in {total_time:.3f}s (OCR: {ocr_time:.3f}s, Prep: {prep_time:.3f}s, Rule: {rule_time:.3f}s). Extracted: '{extracted_name}', LLM: {llm_used}")
    
    return {
        "extracted_username": extracted_name,
        "member_id": member_id,
        "ocr_raw_text": raw_text,
        "ocr_time": prep_time + ocr_time, # Combine prep + ocr engine execution times
        "rule_time": rule_time,
        "ocr_confidence": avg_confidence,
        "candidate_score": candidate_score,
        "llm_used": llm_used,
        "total_time": total_time
    }
