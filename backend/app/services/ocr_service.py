"""
app/services/ocr_service.py — Receipt OCR pipeline for xpensa.

Uses pytesseract (Google Tesseract OCR) — completely FREE, no API key needed.

Requirements (add to requirements.txt):
  pytesseract==0.3.13
  Pillow==11.1.0

System dependency (add to Dockerfile or Render build):
  apt-get install -y tesseract-ocr

Render.com: add a render.yaml build step or use a Dockerfile.
  Dockerfile example:
    RUN apt-get update && apt-get install -y tesseract-ocr && rm -rf /var/lib/apt/lists/*

Flow:
  1. Employee uploads receipt image → POST /api/v1/ocr/extract
  2. Image is saved to Supabase Storage → returns { task_id, receipt_url }
  3. BackgroundTask runs Tesseract OCR → extracts fields via regex
  4. Employee polls GET /api/v1/ocr/status/{task_id} until status == "done"
  5. Frontend auto-fills the expense form with extracted data

Extracted fields:
  - amount (float)
  - currency (ISO 4217, e.g. "INR", "USD")
  - date (YYYY-MM-DD)
  - description (merchant name + purpose)
  - category (travel / meals / equipment / miscellaneous)
"""

import uuid
import re
import time
import io
from datetime import datetime
from typing import Optional
import httpx

# ── In-memory task store (TTL: 10 minutes) ───────────────────────────────────
_tasks: dict[str, dict] = {}
_TASK_TTL = 600  # 10 minutes


def _cleanup_old_tasks() -> None:
    now = time.time()
    expired = [k for k, v in _tasks.items() if now - v["created_at"] > _TASK_TTL]
    for k in expired:
        del _tasks[k]


def create_task() -> str:
    _cleanup_old_tasks()
    task_id = str(uuid.uuid4())
    _tasks[task_id] = {
        "status": "processing",
        "result": None,
        "error": None,
        "created_at": time.time(),
    }
    return task_id


def get_task(task_id: str) -> Optional[dict]:
    task = _tasks.get(task_id)
    if not task:
        return None
    if time.time() - task["created_at"] > _TASK_TTL:
        del _tasks[task_id]
        return None
    return task


def _set_task_done(task_id: str, result: dict) -> None:
    if task_id in _tasks:
        _tasks[task_id]["status"] = "done"
        _tasks[task_id]["result"] = result


def _set_task_error(task_id: str, error: str) -> None:
    if task_id in _tasks:
        _tasks[task_id]["status"] = "error"
        _tasks[task_id]["error"] = error


# ── Tesseract OCR Pipeline ────────────────────────────────────────────────────

def _preprocess_image(image_bytes: bytes) -> "Image.Image":  # type: ignore[name-defined]
    """
    Preprocess the image for better OCR accuracy:
    - Convert to grayscale
    - Increase contrast
    - Resize if too small
    """
    try:
        from PIL import Image, ImageEnhance, ImageFilter
    except ImportError:
        raise RuntimeError("Pillow is not installed. Add 'Pillow==11.1.0' to requirements.txt")

    img = Image.open(io.BytesIO(image_bytes))

    # Convert to RGB if RGBA/palette mode
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")

    # Resize if too small (Tesseract works better with larger images)
    min_dim = 1000
    w, h = img.size
    if w < min_dim or h < min_dim:
        scale = min_dim / min(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

    # Convert to grayscale
    img = img.convert("L")

    # Enhance contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)

    # Mild sharpening
    img = img.filter(ImageFilter.SHARPEN)

    return img


def _extract_text_from_image(image_bytes: bytes) -> str:
    """Run Tesseract OCR and return extracted text."""
    try:
        import pytesseract
    except ImportError:
        raise RuntimeError(
            "pytesseract is not installed. Add 'pytesseract==0.3.13' to requirements.txt "
            "and install tesseract-ocr system package."
        )

    img = _preprocess_image(image_bytes)

    # Use page segmentation mode 6 (uniform block of text — good for receipts)
    config = "--psm 6 -l eng"
    text = pytesseract.image_to_string(img, config=config)
    return text


# ── Amount extraction ─────────────────────────────────────────────────────────

# Currency symbol → ISO code mapping
_SYMBOL_MAP = {
    "₹": "INR", "rs": "INR", "rs.": "INR", "inr": "INR",
    "$": "USD", "usd": "USD",
    "€": "EUR", "eur": "EUR",
    "£": "GBP", "gbp": "GBP",
    "¥": "JPY", "jpy": "JPY", "cny": "CNY",
    "a$": "AUD", "aud": "AUD",
    "c$": "CAD", "cad": "CAD",
    "s$": "SGD", "sgd": "SGD",
    "chf": "CHF", "aed": "AED", "sar": "SAR", "qar": "QAR",
    "brl": "BRL", "mxn": "MXN", "krw": "KRW", "thb": "THB",
    "myr": "MYR", "php": "PHP", "nzd": "NZD", "hkd": "HKD",
}

_AMOUNT_PATTERNS = [
    # "Total: ₹ 1,234.56" or "TOTAL 1234.56"
    r"(?:total|grand\s*total|amount\s*due|amount\s*paid|net\s*total|subtotal|bill\s*amount)"
    r"\s*[:\-]?\s*"
    r"([₹$€£¥]|rs\.?|inr|usd|eur|gbp)?\s*"
    r"([\d,]+\.?\d*)",

    # "₹ 850" or "$ 42.50" (standalone currency + number)
    r"([₹$€£¥])\s*([\d,]+\.?\d*)",

    # "1,234.56" (largest standalone number — fallback)
    r"\b([\d,]{2,}\.?\d{2})\b",
]


def _parse_amount_and_currency(text: str) -> tuple[float, str]:
    """Extract total amount and currency from OCR text."""
    text_lower = text.lower()

    # Detect currency from symbols in the full text
    detected_currency = "USD"
    for sym, code in _SYMBOL_MAP.items():
        if sym in text_lower:
            detected_currency = code
            break

    # Also check for ISO codes mentioned explicitly
    for sym, code in _SYMBOL_MAP.items():
        if len(sym) == 3 and re.search(r"\b" + sym + r"\b", text_lower):
            detected_currency = code
            break

    # Try amount patterns from most specific to least
    amounts: list[float] = []
    for pattern in _AMOUNT_PATTERNS:
        for match in re.finditer(pattern, text_lower, re.IGNORECASE):
            groups = match.groups()
            # Last group is always the numeric part
            num_str = groups[-1].replace(",", "")
            try:
                amounts.append(float(num_str))
            except ValueError:
                pass

    if amounts:
        # Use the maximum amount found (most likely to be the total)
        return max(amounts), detected_currency

    return 0.0, detected_currency


# ── Date extraction ───────────────────────────────────────────────────────────

_DATE_PATTERNS = [
    # DD/MM/YYYY or DD-MM-YYYY
    (r"\b(\d{1,2})[/\-\.](\d{1,2})[/\-\.](\d{4})\b", "dmy"),
    # YYYY/MM/DD or YYYY-MM-DD
    (r"\b(\d{4})[/\-\.](\d{1,2})[/\-\.](\d{1,2})\b", "ymd"),
    # DD Month YYYY (e.g. "15 Jan 2024")
    (r"\b(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{4})\b", "dmy_text"),
    # Month DD, YYYY (e.g. "January 15, 2024")
    (r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+(\d{1,2}),?\s+(\d{4})\b", "mdy_text"),
]

_MONTH_MAP = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _parse_date(text: str) -> str:
    """Extract and normalise date from OCR text to YYYY-MM-DD."""
    text_lower = text.lower()
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    current_year = datetime.utcnow().year

    for pattern, fmt in _DATE_PATTERNS:
        m = re.search(pattern, text_lower)
        if not m:
            continue
        try:
            if fmt == "dmy":
                d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
            elif fmt == "ymd":
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            elif fmt == "dmy_text":
                d = int(m.group(1))
                mo = _MONTH_MAP.get(m.group(2)[:3], 1)
                y = int(m.group(3))
            elif fmt == "mdy_text":
                mo = _MONTH_MAP.get(m.group(1)[:3], 1)
                d = int(m.group(2))
                y = int(m.group(3))
            else:
                continue

            # Sanity check
            if 1 <= mo <= 12 and 1 <= d <= 31 and 2000 <= y <= current_year + 1:
                return f"{y:04d}-{mo:02d}-{d:02d}"
        except (ValueError, IndexError):
            continue

    return today_str


# ── Description / merchant extraction ────────────────────────────────────────

def _parse_description(text: str) -> str:
    """
    Try to extract a merchant name from the first few non-empty lines.
    Receipt headers usually contain the merchant name.
    """
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return "Receipt"

    # Heuristic: the merchant name is usually in the first 1-3 lines,
    # is reasonably short, and contains mostly letters.
    for line in lines[:4]:
        # Skip lines that look like addresses, phone numbers, or dates
        if re.search(r"\d{5,}|\b(?:tel|phone|gst|tax|date)\b", line.lower()):
            continue
        # Skip lines that are mostly numbers or symbols
        alpha_ratio = sum(c.isalpha() or c.isspace() for c in line) / max(len(line), 1)
        if alpha_ratio > 0.5 and len(line) >= 3:
            return line[:100]  # Cap at 100 chars

    return lines[0][:100] if lines else "Receipt"


# ── Category inference ────────────────────────────────────────────────────────

_CATEGORY_KEYWORDS = {
    "meals": [
        "restaurant", "cafe", "coffee", "food", "eat", "dining", "bistro",
        "hotel restaurant", "mcdonalds", "kfc", "pizza", "burger", "sushi",
        "swiggy", "zomato", "dominos", "subway", "starbucks", "tea", "snack",
        "canteen", "mess", "tiffin", "lunch", "dinner", "breakfast", "biryani",
    ],
    "travel": [
        "taxi", "cab", "uber", "ola", "auto", "rickshaw", "bus", "train",
        "flight", "airline", "airport", "boarding", "metro", "subway",
        "toll", "fuel", "petrol", "diesel", "transport", "parking", "irctc",
        "indigo", "spicejet", "air india", "makemytrip", "goibibo",
    ],
    "accommodation": [
        "hotel", "inn", "lodge", "resort", "motel", "hostel", "airbnb",
        "room", "stay", "oyo", "treebo", "fabhotel", "accommodation",
    ],
    "equipment": [
        "electronics", "laptop", "computer", "phone", "mobile", "tablet",
        "printer", "keyboard", "mouse", "monitor", "headphone", "cable",
        "office supply", "stationery", "pen", "paper", "ink", "toner",
        "amazon", "flipkart", "croma", "reliance digital",
    ],
}


def _infer_category(text: str, description: str) -> str:
    """Infer expense category from OCR text and description."""
    combined = (text + " " + description).lower()
    scores: dict[str, int] = {cat: 0 for cat in _CATEGORY_KEYWORDS}

    for category, keywords in _CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in combined:
                scores[category] += 1

    best = max(scores, key=lambda c: scores[c])
    if scores[best] > 0:
        return best
    return "miscellaneous"


# ── Main OCR runner ───────────────────────────────────────────────────────────

async def run_ocr_with_tesseract(
    task_id: str,
    image_bytes: bytes,
    media_type: str,  # kept for API compatibility, not used
) -> None:
    """
    Runs Tesseract OCR on the image bytes.
    Updates task state on completion or error.
    Called as a FastAPI BackgroundTask.
    """
    try:
        # Extract raw text
        raw_text = _extract_text_from_image(image_bytes)

        # Parse fields
        amount, currency = _parse_amount_and_currency(raw_text)
        date_str = _parse_date(raw_text)
        description = _parse_description(raw_text)
        category = _infer_category(raw_text, description)

        today = datetime.utcnow().strftime("%Y-%m-%d")

        sanitised = {
            "amount": round(amount, 2),
            "currency": currency[:3].upper(),
            "date": date_str if date_str else today,
            "description": description[:200] if description else "Receipt",
            "category": category,
        }

        _set_task_done(task_id, sanitised)

    except RuntimeError as e:
        # pytesseract or PIL not installed
        _set_task_error(task_id, str(e))
    except Exception as e:
        _set_task_error(task_id, f"OCR failed: {str(e)[:200]}")


# ── Supabase Storage upload helper (unchanged) ────────────────────────────────

async def upload_receipt_to_supabase(
    image_bytes: bytes,
    filename: str,
    company_id: str,
    supabase_url: str,
    supabase_service_key: str,
) -> str:
    """
    Uploads receipt image to Supabase Storage.
    Returns the public URL of the uploaded file.

    Bucket name: 'receipts' (must be created in Supabase dashboard with public access)
    Path: receipts/{company_id}/{filename}
    """
    bucket = "receipts"
    path = f"{company_id}/{filename}"
    upload_url = f"{supabase_url}/storage/v1/object/{bucket}/{path}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            upload_url,
            content=image_bytes,
            headers={
                "Authorization": f"Bearer {supabase_service_key}",
                "Content-Type": "image/jpeg",
                "x-upsert": "true",
            },
        )
        response.raise_for_status()

    public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{path}"
    return public_url