
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, status


from backend import models
from backend.schemas.auth import RegisterRequest, AuthResponse, LoginRequest, TokenResponse, RefreshRequest
from backend.database import get_db
from typing import Annotated
from sqlalchemy.orm import Session
from sqlalchemy import select, update
import bcrypt
from uuid import UUID
import hashlib

from backend.core.security import create_access_token, create_refresh_token
from backend.core.config import settings
from backend.core.deps import get_current_user

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)





                                                                                                                                                    
                                                                                                                                                                                                 
@router.post("/register", response_model = AuthResponse)
def register(body : RegisterRequest, db: Annotated[Session, Depends(get_db)]): #session is a database session that is automatically provided by FastAPI's dependency injection system. It allows the function to interact with the database without having to manually create and manage a session.
    # Check if user already exists
    existing_user = db.execute(
        select(models.User).where((models.User.username == body.username) | (models.User.email == body.email))
    ).scalars().first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or email already registered")
    
    # Create new user
    new_user = models.User(
        username=body.username,
        email=body.email,
        hashed_password=bcrypt.hashpw(body.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # convert SQLAlchemy UUID type to python's uuid.UUID to satisfy type checker
    return AuthResponse(message="User registered successfully", user_id=UUID(str(new_user.id)), verified=False)

@router.post("/login", response_model = TokenResponse)
def login(body : LoginRequest, db: Annotated[Session, Depends(get_db)]):
    # Check if user exists
    user = db.execute(
        select(models.User).where(models.User.email == body.email)
    ).scalars().first()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    # Verify password
    if not bcrypt.checkpw(body.password.encode('utf-8'), user.hashed_password.encode('utf-8')):
        raise HTTPException(status_code=400, detail="Invalid email or password")
    
    access_token = create_access_token(str(user.id))
    refresh_token, refresh_token_hash = create_refresh_token(str(user.id))

    # Store refresh token hash in the database
    refresh_token_entry = models.RefreshToken(
        user_id=user.id,
        token_hash=refresh_token_hash,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.REFRESH_TIMEOUT_DAYS)
    )
    db.add(refresh_token_entry)
    db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)

@router.post("/refresh", response_model = TokenResponse)
def refresh(body : RefreshRequest, db : Annotated[Session, Depends(get_db)]):
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()

    result =  db.execute(
        select(models.RefreshToken).where(models.RefreshToken.token_hash == token_hash)
    )
    token = result.scalar_one_or_none()

    if not token or token.revoked or token.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    access_token = create_access_token(str(token.user_id))

    # optional: rotate the refresh token

    new_raw_token, new_raw_token_hash = create_refresh_token(str(token.user_id))
    token.revoked = True
    new_refresh = models.RefreshToken(
        user_id=token.user_id,
        token_hash=new_raw_token_hash,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.REFRESH_TIMEOUT_DAYS)
    )
    db.add(new_refresh)
    db.commit()

    return TokenResponse(access_token=access_token, refresh_token=new_raw_token)

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(body : RefreshRequest, current_user: Annotated[models.User, Depends(get_current_user)], db : Annotated[Session, Depends(get_db)]) -> None:
    token_hash = hashlib.sha256(body.refresh_token.encode()).hexdigest()
    db.execute(
        update(models.RefreshToken)
        .where(
            models.RefreshToken.token_hash == token_hash,
            models.RefreshToken.user_id == current_user.id,
        )
        .values(revoked = True)
    )
    db.commit()
    
