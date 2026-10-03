import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_session
from app.models import User

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_MAX_AGE = 365 * 24 * 60 * 60


class UserOut(BaseModel):
    id: uuid.UUID
    is_new: bool


def _cookie_user_id(request: Request) -> uuid.UUID | None:
    raw = request.cookies.get(get_settings().cookie_name)
    try:
        return uuid.UUID(raw) if raw else None
    except ValueError:
        return None


@router.post("/guest", response_model=UserOut)
async def guest_login(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> UserOut:
    user_id = _cookie_user_id(request)
    if user_id and await session.get(User, user_id):
        is_new = False
    else:
        user = User()
        session.add(user)
        await session.commit()
        user_id, is_new = user.id, True

    settings = get_settings()
    response.set_cookie(
        settings.cookie_name,
        str(user_id),
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
    )
    return UserOut(id=user_id, is_new=is_new)


async def current_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> User:
    user_id = _cookie_user_id(request)
    user = await session.get(User, user_id) if user_id else None
    if user is None:
        raise HTTPException(status_code=401, detail="Not logged in")
    return user
