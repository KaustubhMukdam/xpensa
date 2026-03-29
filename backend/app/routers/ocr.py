"""
app/routers/ocr.py — Receipt OCR endpoints

Endpoints:
  POST /api/v1/ocr/extract   → upload receipt image, returns task_id + receipt_url
  GET  /api/v1/ocr/status/{task_id} → poll for OCR result

Usage flow:
  1. Frontend POSTs multipart form with image file
  2. Backend uploads to Supabase Storage (non-blocking)
  3. BackgroundTask runs Claude vision OCR
  4. Frontend polls /status/{task_id} every 2 seconds
  5. On "done", frontend auto-fills expense form

Notes:
  - Requires ANTHROPIC_API_KEY in .env
  - Requires Supabase 'receipts' bucket (public read, service-key write)
  - Accepted formats: JPEG, PNG, WEBP, GIF (Claude vision supported)
  - Max file size: 5MB (enforced here)
"""

import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, status, BackgroundTasks
from fastapi.responses import JSONResponse

from app.core.dependencies import CurrentUser, DBSession
from app.core.config import settings
from app.services import ocr_service

router = APIRouter()

# Allowed MIME types for Claude vision
_ALLOWED_TYPES = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "image/gif": "image/gif",
}

_MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post(
    "/extract",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Employee: Upload receipt image and start OCR",
    response_description="Returns task_id for polling and receipt_url for storage",
)
async def extract_receipt(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    file: UploadFile = File(..., description="Receipt image (JPEG, PNG, WEBP, GIF — max 5MB)"),
):
    """
    Accepts a receipt image upload.
    - Validates file type and size
    - Uploads to Supabase Storage
    - Kicks off Claude vision OCR as a background task
    - Returns immediately with task_id + receipt_url

    Frontend should poll /status/{task_id} every 2s until status == "done".
    """
    # ── Validate content type ────────────────────────────────────────────────
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{content_type}'. Use JPEG, PNG, WEBP, or GIF.",
        )
    media_type = _ALLOWED_TYPES[content_type]

    # ── Read and validate size ───────────────────────────────────────────────
    image_bytes = await file.read()
    if len(image_bytes) > _MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({len(image_bytes) // 1024}KB). Maximum is 5MB.",
        )
    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded.",
        )

    # ── Generate unique filename ─────────────────────────────────────────────
    ext = content_type.split("/")[-1].replace("jpeg", "jpg")
    filename = f"{uuid.uuid4()}.{ext}"

    # ── Upload to Supabase Storage ───────────────────────────────────────────
    receipt_url = None
    try:
        receipt_url = await ocr_service.upload_receipt_to_supabase(
            image_bytes=image_bytes,
            filename=filename,
            company_id=str(current_user.company_id),
            supabase_url=settings.SUPABASE_URL,
            supabase_service_key=settings.SUPABASE_SERVICE_KEY,
        )
    except Exception:
        # Non-fatal: OCR can still run without a persisted URL
        # Frontend will just not have a receipt_url to store
        receipt_url = None

    # ── Create OCR task ──────────────────────────────────────────────────────
    task_id = ocr_service.create_task()

    # ── Launch OCR in background ─────────────────────────────────────────────
    # NOTE: BackgroundTasks in FastAPI run after the response is sent.
    # The task has access to image_bytes in memory — no temp file needed.
    background_tasks.add_task(
        ocr_service.run_ocr_with_claude,
        task_id=task_id,
        image_bytes=image_bytes,
        media_type=media_type,
        anthropic_api_key=_get_anthropic_key(),
    )

    return JSONResponse(
        status_code=status.HTTP_202_ACCEPTED,
        content={
            "task_id": task_id,
            "receipt_url": receipt_url,
            "message": "OCR started. Poll /status/{task_id} for results.",
        },
    )


@router.get(
    "/status/{task_id}",
    summary="Employee: Poll OCR task status",
    response_description="Task status and extracted data when done",
)
def get_ocr_status(
    task_id: str,
    current_user: CurrentUser,
):
    """
    Returns the current status of an OCR task.

    Responses:
      - status: "processing" → keep polling
      - status: "done" → result contains extracted fields
      - status: "error" → OCR failed, error contains reason
      - 404 → task not found or expired (TTL: 10 minutes)

    Result shape (when done):
      {
        "amount": 850.0,
        "currency": "INR",
        "date": "2026-03-29",
        "description": "McDonald's - Team lunch",
        "category": "meals"
      }
    """
    task = ocr_service.get_task(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found or expired. Tasks expire after 10 minutes.",
        )

    return {
        "task_id": task_id,
        "status": task["status"],
        "result": task.get("result"),
        "error": task.get("error"),
    }


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_anthropic_key() -> str:
    """
    Gets the Anthropic API key from settings.
    Add ANTHROPIC_API_KEY to your .env file.
    Get one at: https://console.anthropic.com/
    """
    key = getattr(settings, "ANTHROPIC_API_KEY", None)
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OCR service is not configured. Set ANTHROPIC_API_KEY in environment.",
        )
    return key