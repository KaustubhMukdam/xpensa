"""
ocr_service.py — Receipt OCR pipeline for xpensa.

Uses the Anthropic Claude API (vision) to extract structured data from receipt images.
This replaces EasyOCR to avoid heavy model downloads on Render's free tier.

Flow:
  1. Employee uploads receipt image → POST /api/v1/ocr/extract
  2. Image is saved to Supabase Storage → returns { task_id, receipt_url }
  3. BackgroundTask runs Claude vision → extracts fields
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
import base64
import time
import re
from datetime import datetime
from typing import Optional
import httpx

# ── In-memory task store (TTL: 10 minutes) ───────────────────────────────────
# { task_id: { "status": "processing|done|error", "result": {...}, "created_at": float } }
_tasks: dict[str, dict] = {}
_TASK_TTL = 600  # 10 minutes


def _cleanup_old_tasks() -> None:
    """Remove tasks older than TTL to prevent memory leak."""
    now = time.time()
    expired = [k for k, v in _tasks.items() if now - v["created_at"] > _TASK_TTL]
    for k in expired:
        del _tasks[k]


def create_task() -> str:
    """Create a new task and return its ID."""
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
    """Get task state. Returns None if not found or expired."""
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


# ── Claude Vision OCR ─────────────────────────────────────────────────────────

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

# Instructions for Claude to extract receipt data
_SYSTEM_PROMPT = """You are a receipt data extractor. Extract structured information from receipt images.

Always respond with ONLY a valid JSON object, no markdown, no explanation. Use this exact schema:
{
  "amount": <number, the total amount paid>,
  "currency": "<3-letter ISO 4217 code, infer from receipt symbols: ₹=INR, $=USD, €=EUR, £=GBP>",
  "date": "<YYYY-MM-DD format>",
  "description": "<merchant name and brief purpose, max 100 chars>",
  "category": "<one of: travel, meals, equipment, accommodation, miscellaneous>"
}

Rules:
- amount: extract the TOTAL (final amount paid, including tax). If unclear, use the largest amount shown.
- currency: infer from currency symbols, country context, or receipt header. Default to USD if unknown.
- date: use the transaction/receipt date. If year is ambiguous, use current year.
- description: include merchant name (e.g. "McDonald's - Team lunch") or "Unknown merchant" if unreadable.
- category: infer from merchant type (restaurant=meals, airline/cab/hotel=travel/accommodation, etc.)
- If a field cannot be determined, use: amount=0, currency="USD", date="<today>", description="Receipt", category="miscellaneous"
"""


async def run_ocr_with_claude(
    task_id: str,
    image_bytes: bytes,
    media_type: str,
    anthropic_api_key: str,
) -> None:
    """
    Runs Claude vision OCR on the image bytes.
    Updates task state on completion or error.
    Called as a FastAPI BackgroundTask.
    """
    try:
        # Encode image as base64
        image_b64 = base64.standard_b64encode(image_bytes).decode("utf-8")

        payload = {
            "model": "claude-opus-4-5",
            "max_tokens": 512,
            "system": _SYSTEM_PROMPT,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Extract the receipt data from this image and return only the JSON object.",
                        },
                    ],
                }
            ],
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                ANTHROPIC_API_URL,
                json=payload,
                headers={
                    "x-api-key": anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
            )
            response.raise_for_status()
            data = response.json()

        # Extract text from response
        raw_text = data["content"][0]["text"].strip()

        # Strip any accidental markdown fences
        raw_text = re.sub(r"```(?:json)?", "", raw_text).strip().rstrip("`").strip()

        import json
        result = json.loads(raw_text)

        # Validate and sanitise
        today = datetime.utcnow().strftime("%Y-%m-%d")
        sanitised = {
            "amount": float(result.get("amount") or 0),
            "currency": str(result.get("currency") or "USD").upper()[:3],
            "date": str(result.get("date") or today),
            "description": str(result.get("description") or "Receipt")[:200],
            "category": str(result.get("category") or "miscellaneous").lower(),
        }

        # Validate date format
        try:
            datetime.strptime(sanitised["date"], "%Y-%m-%d")
        except ValueError:
            sanitised["date"] = today

        # Validate category
        valid_categories = {"travel", "meals", "equipment", "accommodation", "miscellaneous"}
        if sanitised["category"] not in valid_categories:
            sanitised["category"] = "miscellaneous"

        _set_task_done(task_id, sanitised)

    except httpx.HTTPStatusError as e:
        _set_task_error(task_id, f"Claude API error: {e.response.status_code}")
    except Exception as e:
        _set_task_error(task_id, f"OCR failed: {str(e)[:200]}")


# ── Supabase Storage upload helper ────────────────────────────────────────────

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

    # Construct public URL
    public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{path}"
    return public_url