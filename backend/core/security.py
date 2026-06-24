import jwt
from datetime import datetime, timedelta

from backend.core.config import settings


def create_access_token(user_id: str)-> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.TIMEOUT_MINUTES)
    payload = {
        "sub": user_id,
        "exp": expire
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)

