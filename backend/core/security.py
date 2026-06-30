import jwt
from datetime import datetime, timedelta, timezone
import secrets
from backend.core.config import settings
import hashlib


def hash_token(raw_token: str) -> str:
    """SHA-256 of an opaque token. We only ever persist this digest, never the
    raw token, so a DB leak can't be replayed against the verify endpoint."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_access_token(user_id: str)-> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.TIMEOUT_MINUTES)
    payload = {
        "sub": user_id,
        "exp": expire
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

def generate_verification_token() -> tuple[str, str]:
    """Returns (raw_token, token_hash). The raw token goes in the email link;
    only the hash is stored in the email_tokens table."""
    raw_token = secrets.token_urlsafe(32)
    return raw_token, hash_token(raw_token)

def create_refresh_token(user_id: str)-> tuple[str, str]:
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_token(raw_token)
    return raw_token, token_hash

def verify_refresh_token(raw_token: str, token_hash: str) -> bool:
    return hash_token(raw_token) == token_hash

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
