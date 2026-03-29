"""
app/routers/ocr.py — Receipt OCR endpoints

Uses free pytesseract (Google Tesseract) instead of the Claude API.
No API key required. Requires system package: apt-get install tesseract-ocr
Add to requirements.txt: pytesseract==0.3.13, Pillow==11.1.0

Endpoints:
  POST /api/v1/ocr/extract   → upload receipt image, returns task_id + receipt_url
  GET  /api/v1/ocr/status/{task_id} → poll for OCR result
"""

import uuid
from fastapi import APIRouter, HTTPException, UploadFile, File, status, BackgroundTasks
from fastapi.responses import JSONResponse

from app.core.dependencies import CurrentUser
from app.core.config import settings
from app.services import ocr_service

router = APIRouter()

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
    summary="Employee: Upload receipt image and start OCR (free, no API key)",
)
async def extract_receipt(
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    file: UploadFile = File(..., description="Receipt image (JPEG, PNG, WEBP — max 5MB)"),
):
    content_type = (file.content_type or "").lower()
    if content_type not in _ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported file type '{content_type}'. Use JPEG, PNG, or WEBP.",
        )
    media_type = _ALLOWED_TYPES[content_type]

    image_bytes = await file.read()
    if len(image_bytes) > _MAX_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large ({len(image_bytes) // 1024}KB). Maximum is 5MB.",
        )
    if len(image_bytes) == 0:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file uploaded.")

    ext = content_type.split("/")[-1].replace("jpeg", "jpg")
    filename = f"{uuid.uuid4()}.{ext}"

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
        receipt_url = None

    task_id = ocr_service.create_task()

    background_tasks.add_task(
        ocr_service.run_ocr_with_tesseract,  # ← free Tesseract, no API key
        task_id=task_id,
        image_bytes=image_bytes,
        media_type=media_type,
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
)
def get_ocr_status(task_id: str, current_user: CurrentUser):
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