import os
import uuid
import logging
import aiofiles

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

from app.config import settings
from app.api.deps import require_user
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/upload", tags=["Upload"])

ALLOWED_TYPES = {
    "image/jpeg", "image/png", "image/gif", "image/webp",
    "application/pdf",
    "text/plain",
    "application/zip", "application/x-rar-compressed",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


@router.post("")
async def upload_file(
    file: UploadFile = File(...),
    current_user: User = Depends(require_user),
):
    if file.content_type and file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail=f"File type {file.content_type} not allowed")

    content = await file.read()
    if len(content) > settings.max_upload_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.max_upload_size_mb}MB limit")

    upload_dir = settings.upload_dir
    os.makedirs(upload_dir, exist_ok=True)

    ext = file.filename.split(".")[-1] if "." in (file.filename or "") else "bin"
    filename = f"{uuid.uuid4().hex}.{ext}"
    filepath = os.path.join(upload_dir, filename)

    async with aiofiles.open(filepath, "wb") as f:
        await f.write(content)

    url = f"/uploads/{filename}"
    return {"url": url, "filename": file.filename, "size": len(content)}
