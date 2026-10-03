import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import pipeline, storage
from app.auth import current_user
from app.config import get_settings
from app.db import get_session
from app.gnani import SUPPORTED_LANGUAGES
from app.models import AudioFile, FileStatus, User

router = APIRouter(prefix="/api", tags=["files"])

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".mp4", ".flac", ".ogg", ".opus", ".m4a", ".aac", ".webm", ".amr"}


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    size_bytes: int
    language_code: str
    status: FileStatus
    gnani_status: str | None
    transcript: str | None
    detected_language: str | None
    duration_seconds: float | None
    summary: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime


class LanguageOut(BaseModel):
    code: str
    name: str


@router.get("/languages", response_model=list[LanguageOut])
async def list_languages() -> list[LanguageOut]:
    return [LanguageOut(code=c, name=n) for c, n in SUPPORTED_LANGUAGES.items()]


def _validate_language(language_code: str) -> str:
    codes = [c.strip() for c in language_code.split(",") if c.strip()]
    if not 1 <= len(codes) <= 3 or any(c not in SUPPORTED_LANGUAGES for c in codes):
        raise HTTPException(
            400, "language_code must be 1-3 comma-separated codes from /api/languages"
        )
    return ",".join(codes)


def _validate_filename(filename: str) -> tuple[str, str]:
    name = Path(filename or "audio").name
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400, f"Unsupported file type '{ext or '?'}'. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )
    return name, ext


def _check_size(size: int) -> None:
    max_mb = get_settings().max_upload_mb
    if size <= 0:
        raise HTTPException(400, "File is empty")
    if size > max_mb * 1024 * 1024:
        raise HTTPException(413, f"File exceeds {max_mb} MB limit")


def _storage_path(user: User, file_id: uuid.UUID, ext: str) -> str:
    return f"{user.id}/{file_id}{ext}"


class UploadUrlIn(BaseModel):
    filename: str
    size_bytes: int
    language_code: str = "en-IN"


class UploadUrlOut(BaseModel):
    file_id: uuid.UUID
    upload_url: str


class FileCreateIn(BaseModel):
    file_id: uuid.UUID
    filename: str
    language_code: str = "en-IN"


@router.post("/files/upload-url", response_model=UploadUrlOut)
async def create_upload_url(body: UploadUrlIn, user: User = Depends(current_user)) -> UploadUrlOut:
    _validate_language(body.language_code)
    _, ext = _validate_filename(body.filename)
    _check_size(body.size_bytes)

    file_id = uuid.uuid4()
    try:
        url = await storage.create_upload_url(_storage_path(user, file_id, ext))
    except Exception as exc:
        raise HTTPException(502, f"Could not create upload URL: {exc}") from exc
    return UploadUrlOut(file_id=file_id, upload_url=url)


@router.post("/files", response_model=FileOut, status_code=201)
async def register_file(
    body: FileCreateIn,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> AudioFile:
    language_code = _validate_language(body.language_code)
    filename, ext = _validate_filename(body.filename)
    storage_path = _storage_path(user, body.file_id, ext)

    if await session.get(AudioFile, body.file_id):
        raise HTTPException(409, "File already registered")
    info = await storage.object_info(storage_path)
    if info is None:
        raise HTTPException(400, "Upload not found in storage")
    size = int(info.get("size") or (info.get("metadata") or {}).get("size") or 0)
    _check_size(size)

    row = AudioFile(
        id=body.file_id,
        user_id=user.id,
        filename=filename,
        content_type=info.get("content_type") or (info.get("metadata") or {}).get("mimetype"),
        size_bytes=size,
        storage_path=storage_path,
        language_code=language_code,
        status=FileStatus.UPLOADED,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)

    pipeline.schedule(row.id)
    return row


@router.get("/files", response_model=list[FileOut])
async def list_files(
    user: User = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> list[AudioFile]:
    rows = await session.scalars(
        select(AudioFile)
        .where(AudioFile.user_id == user.id)
        .order_by(AudioFile.created_at.desc())
    )
    return list(rows)


@router.post("/files/{file_id}/retry", response_model=FileOut)
async def retry_file(
    file_id: uuid.UUID,
    user: User = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> AudioFile:
    row = await session.get(AudioFile, file_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404, "File not found")
    if row.status != FileStatus.FAILED:
        raise HTTPException(409, "Only failed files can be retried")
    row.status = FileStatus.UPLOADED if row.transcript is None else FileStatus.TRANSCRIBED
    row.error = None
    await session.commit()
    await session.refresh(row)
    pipeline.schedule(row.id)
    return row
