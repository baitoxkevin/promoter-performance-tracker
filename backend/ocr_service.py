"""
OCR Service — EasyOCR and DeepSeek LLM username extraction.

We switch back to EasyOCR (deep learning scene text detection) because Tesseract
struggles heavily with screen moiré patterns, low contrast, and photo angles.
EasyOCR CRAFT model reads screen-photo text with extreme robustness.

The pipeline:
  1. Run EasyOCR on the full screenshot.
  2. Send the raw text to DeepSeek API with a highly intelligent layout-aware prompt.
  3. Fall back to local Regex pattern matching if the API fails.
"""

import json
import re
from typing import Optional, Tuple

import easyocr
from openai import OpenAI

from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL

# Initialize DeepSeek Client
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL,
)

# Lazy-loaded singleton EasyOCR reader
_reader: Optional[easyocr.Reader] = None


def get_reader() -> easyocr.Reader:
    """
    Return the singleton EasyOCR reader instance.
    """
    global _reader
    if _reader is None:
        print("[OCR] Initializing EasyOCR reader (supports English + Latin scripts)...")
        _reader = easyocr.Reader(["en"])
        print("[OCR] EasyOCR reader initialized successfully.")
    return _reader


def extract_text_from_image(image_path: str) -> str:
    """
    Run EasyOCR on the FULL image.
    """
    reader = get_reader()
    # detail=0 returns just text strings; paragraph=True groups nearby text blocks
    results = reader.readtext(image_path, detail=0, paragraph=True)
    return "\n".join(results)


def extract_username_fallback(ocr_text: str) -> Optional[str]:
    """
    Local Regex-based fallback pattern matching on the full text if DeepSeek API fails.
    """
    if not ocr_text or not ocr_text.strip():
        return None

    # Pattern 1: @username
    match = re.search(r"@([A-Za-z0-9_.\-]{3,30})", ocr_text)
    if match:
        return match.group(1)

    # Pattern 2: Label-value pairs (Username, Nickname, Name, ID, display name, etc.)
    match = re.search(
        r"(?:username|user\s*name|user\s*id|user|display\s*name|nick\s*name|id|account|name|nama)"
        r"\s*[:：]\s*"
        r"([A-Za-z0-9\s_.\-]{3,50})",
        ocr_text,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).strip()

    # Pattern 3: Standalone name-like line (prefer lines containing letters and spaces)
    # Search the top half of the text in fallback
    lines = [line.strip() for line in ocr_text.strip().split("\n") if line.strip()]
    for line in lines[:8]:  # Limit fallback search to first 8 non-empty lines
        if 3 <= len(line) <= 50 and not any(char.isdigit() for char in line):
            if re.match(r"^[A-Za-z][A-Za-z\s_.\-]{2,49}$", line):
                # Avoid capturing common layout headers
                if line.lower() not in ["profile", "my profile", "settings", "home", "me", "bites"]:
                    return line

    return None


def extract_username_with_llm(ocr_text: str) -> Optional[str]:
    """
    Call DeepSeek API to parse the full OCR text and intelligently extract the registered user's name.
    """
    system_prompt = (
        "You are an expert, highly intelligent parser for mobile app profile screenshots. "
        "You specialize in identifying registered user names from raw OCR text by understanding the screen layout context."
    )
    
    prompt = (
        "Analyze the following full raw OCR text extracted from a mobile app profile screenshot.\n"
        "Your task is to identify and extract the actual registered user's name or username.\n\n"
        "INSTRUCTIONS:\n"
        "1. Understand Layout Context: App profile screens typically contain:\n"
        "   - An app/brand name at the top (e.g., 'bites', 'The Food Purveyor').\n"
        "   - A profile section showing the User's Name (e.g., Malay names like 'Siti Nor Hajar Sheikh Obit', Chinese names like 'Yan Ling' or 'Tan Wei Shen', Indian names, or English names).\n"
        "   - The name is usually followed immediately by a barcode, member ID number (digits), phone number, email, or a 'Member Since' date.\n"
        "2. Strict Exclusion Filter: Do NOT extract brand names, page headers, menu choices, or system links. Under no circumstances should you return:\n"
        "   - App/Company names (e.g., 'bites', 'The Food Purveyor')\n"
        "   - Layout headers (e.g., 'My Profile', 'Account Details', 'Settings', 'Vouchers')\n"
        "   - Menu list choices (e.g., 'FAQs', 'Contact Us', 'Support', 'Terms', 'Logout')\n"
        "3. Output Format: Return a valid JSON array of strings containing the name. Format: [\"Name\"].\n"
        "4. If no registered user's name is found, return an empty array: [].\n"
        "5. Output ONLY the JSON array. Do not wrap in markdown fences (like ```json), and do not provide any explanation.\n\n"
        f"Raw OCR text:\n---\n{ocr_text}\n---"
    )

    try:
        response = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=60,
            timeout=12.0,  # 12s timeout for full text analysis
        )
        
        content = response.choices[0].message.content
        if not content:
            return None
        
        # Clean potential markdown block wrapping (e.g. ```json ... ```)
        content_clean = content.strip()
        if content_clean.startswith("```"):
            content_clean = re.sub(r"^```(?:json)?\n", "", content_clean)
            content_clean = re.sub(r"\n```$", "", content_clean)
            content_clean = content_clean.strip()

        # Parse the JSON response
        names = json.loads(content_clean)
        if isinstance(names, list) and len(names) > 0:
            name = str(names[0]).strip()
            
            # Guard against LLM hallucinating example names from system prompt instructions
            hallucination_examples = ["siti nor hajar sheikh obit", "yan ling", "tan wei shen"]
            if name.lower() in hallucination_examples:
                # Clean alphabetic only check to prevent matching on tiny partial gibberish
                clean_ocr = re.sub(r'[^a-zA-Z]', '', ocr_text).lower()
                clean_name = re.sub(r'[^a-zA-Z]', '', name).lower()
                if clean_name not in clean_ocr:
                    print(f"[OCR] Guard: Rejected hallucinated name '{name}' not found in Raw OCR text.")
                    return None
            
            if name:
                return name
        return None

    except Exception as e:
        print(f"[OCR] DeepSeek API call or JSON parse failed: {str(e)}. Falling back to regex.")
        return None


def is_plausible_layout(text: str) -> bool:
    """
    Check if the raw OCR text contains common layout keywords.
    If it contains at least one of these keywords, it's a plausible orientation.
    """
    keywords = [
        "member", "since", "bites", "profile", "setting", "history", 
        "transaction", "contact", "faq", "voucher", "purveyor", "version",
        "account", "loyalty", "rewards", "points"
    ]
    text_lower = text.lower()
    return any(kw in text_lower for kw in keywords)


def preprocess_image_for_ocr(image_path: str) -> str:
    """
    Enhance image contrast and sharpness to improve OCR accuracy on noisy screen photos.
    Saves the preprocessed image to a temp file and returns its path.
    """
    try:
        from PIL import Image, ImageEnhance
        import os
        
        dir_name = os.path.dirname(image_path)
        base_name = os.path.basename(image_path)
        temp_prep_path = os.path.join(dir_name, "prep_" + base_name)
        
        with Image.open(image_path) as img:
            # 1. Convert to grayscale to remove color channel moiré/rainbow noise
            gray = img.convert('L')
            
            # 2. Upscale 1.5x (using Lanczos filter) to make text details larger and easier to segment
            width, height = gray.size
            resized = gray.resize((int(width * 1.5), int(height * 1.5)), Image.Resampling.LANCZOS)
            
            # 3. Enhance contrast (increase by 1.8x to make dark text stand out against light backgrounds)
            contrast_enhancer = ImageEnhance.Contrast(resized)
            contrast_img = contrast_enhancer.enhance(1.8)
            
            # 4. Enhance sharpness (increase by 1.5x to sharpen blurred text strokes)
            sharpness_enhancer = ImageEnhance.Sharpness(contrast_img)
            sharp_img = sharpness_enhancer.enhance(1.5)
            
            sharp_img.save(temp_prep_path)
            print(f"[OCR] Image preprocessed and saved to: {temp_prep_path}")
            return temp_prep_path
    except Exception as e:
        print(f"[OCR] Preprocessing failed: {e}. Using original image.")
        return image_path


def process_image(image_path: str) -> Tuple[Optional[str], str]:
    """
    OCR & Extraction Pipeline:
      1. Preprocess image (enhance contrast, sharpen, grayscale, resize).
      2. Run EasyOCR on the preprocessed image.
      3. If layout is plausible, attempt extraction (LLM + Regex).
      4. If failed or layout not plausible, try rotations (180, 270, 90) on the preprocessed image.
      5. Returns the extracted name and the best raw text.
    """
    try:
        from PIL import Image
        import os
    except ImportError:
        pass

    # Preprocess first
    enhanced_path = preprocess_image_for_ocr(image_path)

    best_text = ""
    username = None
    last_raw_text = ""
    
    # Try orientations: 0 (original), 180 (upside down), 270 (90 deg clockwise), 90 (90 deg counter-clockwise)
    orientations = [0, 180, 270, 90]
    
    for angle in orientations:
        temp_rotated_path = None
        try:
            if angle == 0:
                current_path = enhanced_path
            else:
                dir_name = os.path.dirname(enhanced_path)
                base_name = os.path.basename(enhanced_path)
                temp_rotated_path = os.path.join(dir_name, f"rotated_{angle}_{base_name}")
                
                with Image.open(enhanced_path) as img:
                    rotated_img = img.rotate(angle, expand=True)
                    rotated_img.save(temp_rotated_path)
                current_path = temp_rotated_path
            
            raw_text = extract_text_from_image(current_path)
            if angle == 0:
                best_text = raw_text
                
            # Clean up temp rotated file immediately
            if temp_rotated_path:
                try:
                    if os.path.exists(temp_rotated_path):
                        os.remove(temp_rotated_path)
                except Exception as cleanup_err:
                    print(f"[OCR] Temp rotated cleanup error for angle {angle}: {cleanup_err}")
            
            if not raw_text.strip():
                continue
                
            # Heuristic check
            if is_plausible_layout(raw_text):
                print(f"[OCR] Orientation {angle}° looks plausible. Extracting...")
                username = extract_username_with_llm(raw_text)
                if not username:
                    username = extract_username_fallback(raw_text)
                
                if username:
                    print(f"[OCR] Successful extraction at {angle}°: '{username}'")
                    last_raw_text = raw_text
                    break
            else:
                print(f"[OCR] Orientation {angle}° text layout is not plausible. Skipping LLM.")
                if len(raw_text) > len(best_text):
                    best_text = raw_text

        except Exception as err:
            print(f"[OCR] Rotation error for angle {angle}: {err}")
            if temp_rotated_path:
                try:
                    if os.path.exists(temp_rotated_path):
                        os.remove(temp_rotated_path)
                except:
                    pass

    # Clean up the main preprocessed image if we created a temp one
    if enhanced_path != image_path:
        try:
            if os.path.exists(enhanced_path):
                os.remove(enhanced_path)
        except Exception as cleanup_err:
            print(f"[OCR] Preprocessed image cleanup error: {cleanup_err}")

    # If we broke out with a username, return it
    if username:
        return username, last_raw_text

    # Final fallback on best text if all orientations failed
    print("[OCR] All rotation heuristics failed. Running final fallback extraction on original text.")
    username = extract_username_with_llm(best_text)
    if not username:
        username = extract_username_fallback(best_text)
    return username, best_text
