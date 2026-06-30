from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated

from uuid import UUID

from backend import models
from backend.database import get_db
from backend.core.security import verify_access_token
from sqlalchemy.orm import Session
from sqlalchemy import select

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    user_id = verify_access_token(token)
    if user_id is None:
        raise credentials_exception

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise credentials_exception

    user = db.execute(
        select(models.User).where(models.User.id == user_uuid)
        ).scalars().first()
    if user is None:
        raise credentials_exception

    return user


def require_verified_user(
    current_user: Annotated[models.User, Depends(get_current_user)],
) -> models.User:
    """Like get_current_user, but rejects unverified accounts with 403.

    Use this (not get_current_user) on any endpoint that must be gated behind a
    verified email — it enforces the gate server-side so a client can't reach
    protected resources by calling the API directly. 403, not 401: the caller is
    authenticated, just not permitted yet."""
    if not current_user.verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email address not verified",
        )
    return current_user

