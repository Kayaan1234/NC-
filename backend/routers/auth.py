
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends


from backend import models
from backend.schemas.auth import RegisterRequest, AuthResponse, LoginRequest, TokenResponse
from backend.database import get_db
from typing import Annotated
from sqlalchemy.orm import Session
from sqlalchemy import select
import bcrypt
from uuid import UUID

from backend.core.security import create_access_token, create_refresh_token
from backend.core.config import settings

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
        expires_at=datetime.utcnow() + timedelta(days=settings.REFRESH_TIMEOUT_DAYS)
    )
    db.add(refresh_token_entry)
    db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token)