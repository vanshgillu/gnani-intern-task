from urllib.parse import quote

import httpx

from app.config import get_settings


def _headers() -> dict[str, str]:
    key = get_settings().supabase_service_key
    headers = {"apikey": key}
    # new sb_secret_ keys only work in the apikey header
    if key.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {key}"
    return headers


def _base() -> str:
    return get_settings().supabase_url.rstrip("/") + "/storage/v1"


async def ensure_bucket() -> None:
    bucket = get_settings().supabase_bucket
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{_base()}/bucket/{bucket}", headers=_headers())
        if resp.status_code == 200:
            return
        resp = await client.post(
            f"{_base()}/bucket",
            headers=_headers(),
            json={"id": bucket, "name": bucket, "public": False},
        )
        if resp.status_code >= 400 and "already exists" not in resp.text.lower():
            resp.raise_for_status()


async def create_upload_url(path: str) -> str:
    bucket = get_settings().supabase_bucket
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_base()}/object/upload/sign/{bucket}/{quote(path)}", headers=_headers()
        )
        resp.raise_for_status()
        return _base() + resp.json()["url"]


async def object_info(path: str) -> dict | None:
    bucket = get_settings().supabase_bucket
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(f"{_base()}/object/info/{bucket}/{quote(path)}", headers=_headers())
    if resp.status_code in (400, 404):
        return None
    resp.raise_for_status()
    return resp.json()


async def signed_url(path: str, expires_in: int) -> str:
    bucket = get_settings().supabase_bucket
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_base()}/object/sign/{bucket}/{quote(path)}",
            headers=_headers(),
            json={"expiresIn": expires_in},
        )
        resp.raise_for_status()
        signed = resp.json()["signedURL"]
    return _base() + signed
