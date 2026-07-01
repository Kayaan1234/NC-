
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks

from backend import models
from backend.schemas.auth import RegisterRequest, AuthResponse, LoginRequest, TokenResponse, RefreshRequest, ResendVerificationResponse, VerifyEmailRequest, ForgotPasswordRequest
from backend.database import get_db, SessionLocal
from typing import Annotated
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
import bcrypt
from uuid import UUID
import hashlib

from backend.core.security import create_access_token, create_refresh_token, hash_token
from backend.core.config import settings
from backend.core.deps import get_current_user
from backend.core.verification import issue_email_verification, issue_password_reset

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

# Precomputed once at import. login() runs bcrypt against this when the email is
# unknown, so the unknown-email and wrong-password paths cost the same — no
# timing oracle that reveals which emails are registered.
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"constant-time-login-dummy", bcrypt.gensalt())


                                                                                                                                                    
                                                                                                                                                                                                 
@router.post("/register", response_model = AuthResponse)
def register(body : RegisterRequest, db: Annotated[Session, Depends(get_db)], background_tasks: BackgroundTasks): #session is a database session that is automatically provided by FastAPI's dependency injection system. It allows the function to interact with the database without having to manually create and manage a session.
    # NOTE: kept as a sync `def` route on purpose. The DB session and bcrypt are
    # both blocking; FastAPI runs sync routes in a threadpool, so they don't block
    # the event loop. An `async def` here would block it.

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
    try:
        db.commit()
    except IntegrityError:
        # Two concurrent registrations can both pass the check above and race to
        # insert; the unique constraint catches the loser here instead of 500ing.
        db.rollback()
        raise HTTPException(status_code=400, detail="Username or email already registered")
    db.refresh(new_user)

    issue_email_verification(new_user, db, background_tasks)

    # convert SQLAlchemy UUID type to python's uuid.UUID to satisfy type checker
    return AuthResponse(message="User registered successfully", user_id=UUID(str(new_user.id)), verified=False)

@router.post("/login", response_model = TokenResponse)
def login(body : LoginRequest, db: Annotated[Session, Depends(get_db)]):
    user = db.execute(
        select(models.User).where(models.User.email == body.email)
    ).scalars().first()

    # Always run bcrypt — against a dummy hash when the email is unknown — so the
    # two failure paths take the same time and can't be used to probe which
    # emails exist. The result is ignored when there's no user.
    hashed = user.hashed_password.encode('utf-8') if user else _DUMMY_PASSWORD_HASH
    password_ok = bcrypt.checkpw(body.password.encode('utf-8'), hashed)
    if user is None or not password_ok:
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
    
@router.post("/resend-verification")
def resend_verification(background_tasks: BackgroundTasks, current_user: Annotated[models.User,Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    if current_user.verified:
        raise HTTPException(status_code=400, detail="Email is already verified")

    issue_email_verification(current_user, db, background_tasks)
    return ResendVerificationResponse(message="Verification email sent")


@router.post("/verify", response_model=ResendVerificationResponse)
def verify_email(body: VerifyEmailRequest, db: Annotated[Session, Depends(get_db)]):
    # POST (not GET): the SPA reads ?token= from the link and posts it here, so
    # email scanners/preview bots that pre-fetch the link can't consume the
    # single-use token, and the token never lands in server access logs.
    token_hash = hash_token(body.token)

    email_token = db.execute(
        select(models.EmailToken).where(models.EmailToken.token_hash == token_hash)
    ).scalars().first()

    if (
        not email_token
        or email_token.purpose != models.EmailTokenPurpose.VERIFY_EMAIL
        or email_token.used_at is not None
        or email_token.expires_at < datetime.now(timezone.utc).replace(tzinfo=None)
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    user = db.get(models.User, email_token.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    email_token.used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    user.verified = True
    db.commit()

    return ResendVerificationResponse(message="Email verified")

def _process_forgot_password(email: str) -> None:
    """Look up the email and, if it belongs to a real user, mint+send a reset
    link. Runs entirely inside a BackgroundTask (after the response is flushed),
    so the DB lookup, token write, and email send never affect response timing.

    Uses its own SessionLocal() — the request's get_db() session is already
    closed by the time this executes. Any failure is swallowed by design (see
    the try/except): the client got its generic 200 and must not be able to
    infer anything from a later error either."""
    db = SessionLocal()
    try:
        user = db.execute(
            select(models.User).where(models.User.email == email)
        ).scalars().first()
        if user:
            issue_password_reset(user, db)
    except Exception:
        db.rollback()
    finally:
        db.close()


@router.post("/forgot-password")
def forgot_password(body: ForgotPasswordRequest, background_tasks: BackgroundTasks):
    # Do the lookup + issue off the request path so the existing-email and
    # unknown-email cases are indistinguishable by response time. Returning the
    # same generic body without a timing tell is what actually prevents email
    # enumeration here — the generic message alone doesn't, since a synchronous
    # DB write for real users would leak their existence through latency.
    background_tasks.add_task(_process_forgot_password, body.email)

    return ResendVerificationResponse(message="If the email is registered, a password reset link has been sent")
