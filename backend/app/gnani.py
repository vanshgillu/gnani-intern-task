from dataclasses import dataclass
from typing import Any

import httpx

from app.config import get_settings

TERMINAL_JOB_STATUSES = {
    "COMPLETED",
    "PARTIAL_FAILURE",
    "FAILED",
    "START_FAILED",
    "CANCELLED",
}

# batch api doesn't support gu-IN / pa-IN
SUPPORTED_LANGUAGES = {
    "bn-IN": "Bengali",
    "en-IN": "English",
    "hi-IN": "Hindi",
    "kn-IN": "Kannada",
    "ml-IN": "Malayalam",
    "mr-IN": "Marathi",
    "ta-IN": "Tamil",
    "te-IN": "Telugu",
}


class GnaniError(Exception):
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable


@dataclass
class Transcript:
    text: str
    language_code: str | None
    duration_seconds: float | None


def _client() -> httpx.AsyncClient:
    s = get_settings()
    return httpx.AsyncClient(
        base_url=s.gnani_base_url,
        headers={"X-API-Key-ID": s.gnani_api_key},
        timeout=60,
    )


def _raise_for_error(resp: httpx.Response, action: str) -> None:
    if resp.is_success:
        return
    try:
        body = resp.json()
    except ValueError:
        body = resp.text
    if isinstance(body, dict):
        detail = body.get("detail", body)
        if isinstance(detail, dict):
            body = detail.get("message") or detail.get("error") or detail
        else:
            body = detail
    raise GnaniError(
        f"Gnani {action} failed ({resp.status_code}): {body}",
        retryable=resp.status_code == 429 or resp.status_code >= 500,
    )


async def create_job(audio_url: str, language_code: str) -> str:
    payload = {
        "config": {
            "model": get_settings().gnani_model,
            "language_code": language_code,
            "mode": "transcribe",
        },
        "source": {
            "type": "cloud_storage",
            "auth": {"mode": "public"},
            "paths": [audio_url],
        },
    }
    async with _client() as client:
        resp = await client.post("/stt/v3/batch/jobs", json=payload)
    _raise_for_error(resp, "create job")
    return resp.json()["job_id"]


async def start_job(job_id: str) -> None:
    async with _client() as client:
        resp = await client.post(f"/stt/v3/batch/jobs/{job_id}/start")
    # 409 = already started
    if resp.status_code == 409:
        return
    _raise_for_error(resp, "start job")


async def get_job(job_id: str) -> dict[str, Any]:
    async with _client() as client:
        resp = await client.get(f"/stt/v3/batch/jobs/{job_id}")
    _raise_for_error(resp, "get job")
    return resp.json()


async def fetch_transcript(job: dict[str, Any]) -> Transcript:
    job_id = job["job_id"]
    async with _client() as client:
        resp = await client.get(f"/stt/v3/batch/jobs/{job_id}/files")
        _raise_for_error(resp, "list job files")
        files = resp.json().get("data", [])

        done = next(
            (f for f in files if f.get("status") == "COMPLETED" and f.get("transcript_url")),
            None,
        )
        if done is None:
            reason = next((f.get("error_message") for f in files if f.get("error_message")), None)
            raise GnaniError(
                reason
                or job.get("cancel_reason")
                or f"Transcription ended with status {job.get('status')}"
            )

        # presigned s3 url, don't send the api key
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as raw:
            t = await raw.get(done["transcript_url"])
        _raise_for_error(t, "download transcript")
        data = t.json()

    text = (data.get("full_transcript") or "").strip()
    if not text:
        raise GnaniError("Gnani returned an empty transcript")
    duration = data.get("duration_seconds")
    return Transcript(
        text=text,
        language_code=data.get("language_code"),
        duration_seconds=float(duration) if duration is not None else None,
    )
