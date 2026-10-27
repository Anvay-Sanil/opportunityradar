import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException
from jose import JWTError, jwt

from app.config import settings


def create_unsubscribe_token(user_id: uuid.UUID) -> str:
    return jwt.encode(
        {"sub": str(user_id), "purpose": "digest-unsubscribe",
         "exp": datetime.now(timezone.utc) + timedelta(days=365)},
        settings.supabase_jwt_secret, algorithm=settings.jwt_algorithm,
    )


def unsubscribe_user_id(token: str) -> uuid.UUID:
    try:
        payload = jwt.decode(token, settings.supabase_jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("purpose") != "digest-unsubscribe":
            raise ValueError("Wrong token purpose")
        return uuid.UUID(payload["sub"])
    except (JWTError, ValueError, TypeError, KeyError, AttributeError):
        raise HTTPException(status_code=400, detail="This unsubscribe link is invalid or expired")
