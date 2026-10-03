import asyncio
import logging
import time
import uuid

import httpx
from sqlalchemy import select

from app import gnani, storage
from app.config import get_settings
from app.db import SessionLocal
from app.models import ACTIVE_STATUSES, AudioFile, FileStatus
from app.summarizer import summarize

log = logging.getLogger(__name__)

SIGNED_URL_TTL_SECONDS = 24 * 60 * 60
MAX_POLL_INTERVAL_SECONDS = 120

_tasks: dict[uuid.UUID, asyncio.Task] = {}


def schedule(file_id: uuid.UUID) -> None:
    if (task := _tasks.get(file_id)) and not task.done():
        return
    task = asyncio.create_task(_run(file_id))
    _tasks[file_id] = task
    task.add_done_callback(lambda _: _tasks.pop(file_id, None))


async def resume_pending() -> None:
    async with SessionLocal() as session:
        ids = (
            await session.scalars(
                select(AudioFile.id).where(AudioFile.status.in_(ACTIVE_STATUSES))
            )
        ).all()
    for file_id in ids:
        log.info("Resuming processing for file %s", file_id)
        schedule(file_id)


async def _update(file_id: uuid.UUID, **fields) -> AudioFile:
    async with SessionLocal() as session:
        row = await session.get(AudioFile, file_id)
        for key, value in fields.items():
            setattr(row, key, value)
        await session.commit()
        return row


async def _run(file_id: uuid.UUID) -> None:
    try:
        async with SessionLocal() as session:
            row = await session.get(AudioFile, file_id)
        if row is None:
            return
        if row.transcript is None:
            row = await _transcribe(row)
        if row.summary is None:
            await _update(file_id, status=FileStatus.SUMMARIZING, error=None)
            summary = await summarize(row.transcript)
            await _update(file_id, summary=summary, status=FileStatus.COMPLETED)
        else:
            await _update(file_id, status=FileStatus.COMPLETED)
    except Exception as exc:
        log.exception("Processing failed for file %s", file_id)
        await _update(file_id, status=FileStatus.FAILED, error=str(exc) or type(exc).__name__)


async def _transcribe(row: AudioFile) -> AudioFile:
    settings = get_settings()
    job_id = row.gnani_job_id
    if job_id is None:
        await _update(row.id, status=FileStatus.TRANSCRIBING, gnani_status="SUBMITTING", error=None)
        url = await storage.signed_url(row.storage_path, SIGNED_URL_TTL_SECONDS)
        job_id = await gnani.create_job(url, row.language_code)
        await _update(row.id, gnani_job_id=job_id, gnani_status="CREATED")
        await gnani.start_job(job_id)
    else:
        await _update(row.id, status=FileStatus.TRANSCRIBING, error=None)

    deadline = time.monotonic() + settings.gnani_timeout_seconds
    interval = settings.gnani_poll_interval_seconds
    status = "UNKNOWN"
    while True:
        try:
            job = await gnani.get_job(job_id)
        except (gnani.GnaniError, httpx.TransportError) as exc:
            if isinstance(exc, gnani.GnaniError) and not exc.retryable:
                raise
            interval = min(interval * 2, MAX_POLL_INTERVAL_SECONDS)
            log.warning("Polling Gnani job %s failed (%s); retrying in %ss", job_id, exc, interval)
        else:
            interval = settings.gnani_poll_interval_seconds
            status = job.get("status", "UNKNOWN")
            await _update(row.id, gnani_status=status)
            if status in gnani.TERMINAL_JOB_STATUSES:
                break
        if time.monotonic() > deadline:
            raise gnani.GnaniError(f"Timed out waiting for Gnani job {job_id} (last status {status})")
        await asyncio.sleep(interval)

    try:
        transcript = await gnani.fetch_transcript(job)
    except gnani.GnaniError:
        # finished jobs can't be restarted, so retry should create a new one
        await _update(row.id, gnani_job_id=None)
        raise
    return await _update(
        row.id,
        transcript=transcript.text,
        detected_language=transcript.language_code,
        duration_seconds=transcript.duration_seconds,
        status=FileStatus.TRANSCRIBED,
    )
