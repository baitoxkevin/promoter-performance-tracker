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
            if name:
                return name
        return None

    except Exception as e:
        print(f"[OCR] DeepSeek API call or JSON parse failed: {str(e)}. Falling back to regex.")
        return None


def process_image(image_path: str) -> Tuple[Optional[str], str]:
    """
    OCR & Extraction Pipeline:
      1. Run EasyOCR on the FULL image (no cropping).
      2. Call DeepSeek API on the full raw text using layout-aware prompt.
      3. Fall back to regex if needed.
      4. If failed, rotate 180 degrees (upside down) and retry.
    """
    try:
        raw_text = extract_text_from_image(image_path)
        if not raw_text.strip():
            return None, "Empty text extracted from image."

        # 1. Attempt LLM extraction on the full text
        username = extract_username_with_llm(raw_text)
        
        # 2. Fall back to regex if LLM failed
        if not username:
            username = extract_username_fallback(raw_text)

        # 3. If extraction failed, try rotating the image 180 degrees (upside down) and retrying
        if not username:
            print(f"[OCR] Username extraction failed. Trying 180 degree rotation fallback...")
            try:
                from PIL import Image
                import os
                
                dir_name = os.path.dirname(image_path)
                base_name = os.path.basename(image_path)
                temp_rotated_path = os.path.join(dir_name, "rotated_" + base_name)
                
                with Image.open(image_path) as img:
                    rotated_img = img.rotate(180)
                    rotated_img.save(temp_rotated_path)
                
                print(f"[OCR] Rotated image saved to: {temp_rotated_path}. Running OCR on rotated image.")
                rotated_raw_text = extract_text_from_image(temp_rotated_path)
                
                # Clean up the temp rotated image file
                try:
                    if os.path.exists(temp_rotated_path):
                        os.remove(temp_rotated_path)
                except Exception as cleanup_err:
                    print(f"[OCR] Temp rotated image cleanup error: {cleanup_err}")
                
                if rotated_raw_text.strip():
                    rotated_username = extract_username_with_llm(rotated_raw_text)
                    if not rotated_username:
                        rotated_username = extract_username_fallback(rotated_raw_text)
                    
                    if rotated_username:
                        print(f"[OCR] Successfully extracted username '{rotated_username}' from rotated image!")
                        return rotated_username, rotated_raw_text
            except Exception as rotation_err:
                print(f"[OCR] Rotation fallback failed: {rotation_err}")

        return username, raw_text
    except Exception as e:
        error_msg = f"OCR pipeline error: {str(e)}"
        print(f"[OCR] {error_msg}")
        return None, error_msg
