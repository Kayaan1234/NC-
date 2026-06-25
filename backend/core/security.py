import jwt
from datetime import datetime, timedelta, timezone
import secrets
from backend.core.config import settings
import hashlib


def create_access_token(user_id: str)-> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.TIMEOUT_MINUTES)
    payload = {
        "sub": user_id,
        "exp": expire
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def create_refresh_token(user_id: str)-> tuple[str, str]:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    return raw_token, token_hash

def verify_refresh_token(raw_token: str, token_hash: str) -> bool:
    return hashlib.sha256(raw_token.encode()).hexdigest() == token_hash

def verify_access_token(token : str) -> str | None:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require":["exp","sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    else:
        return payload.get("sub")
