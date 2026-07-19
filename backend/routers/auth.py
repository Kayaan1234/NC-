
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, status, Request, Cookie, Response

from backend import models
from backend.schemas.auth import ForgotPasswordToken, RegisterRequest, RegisterResponse, LoginRequest, ResetPasswordRequest, TokenResponse, ResendVerificationResponse, VerifyEmailRequest, ForgotPasswordRequest, ValidateResetTokenRequest
from backend.database import get_db
from typing import Annotated
from sqlalchemy.orm import Session
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
import bcrypt

from backend.core.security import create_access_token, create_refresh_token, hash_token
from backend.core.cookies import set_refresh_cookie, clear_refresh_cookie
from backend.core.activity import has_active_refresh_token, touch_activity
from backend.core.config import settings
from backend.core.deps import get_current_user
from backend.core.outbox import enqueue_email
from backend.core.verification import issue_email_verification
from backend.core.limiter import limiter
from backend.models.EmailOutbox import EmailType


# Same body whether the email was free or already taken — see RegisterResponse.
GENERIC_REGISTER_MESSAGE = (
    "If those details are available, a verification email has been sent. "
    "Please check your inbox."
)



router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

# Precomputed once at import. login() runs bcrypt against this when the email is
# unknown, so the unknown-email and wrong-password paths cost the same — no
# timing oracle that reveals which emails are registered.
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(b"constant-time-login-dummy", bcrypt.gensalt())


                                                                                                                                                    
                                                                                                                                                                                                 
@router.post("/register", response_model = RegisterResponse)
@limiter.limit(settings.RATE_LIMIT_EMAIL_SEND)
def register(request: Request, body : RegisterRequest, db: Annotated[Session, Depends(get_db)]): #session is a database session that is automatically provided by FastAPI's dependency injection system. It allows the function to interact with the database without having to manually create and manage a session.
    # NOTE: kept as a sync `def` route on purpose. The DB session and bcrypt are
    # both blocking; FastAPI runs sync routes in a threadpool, so they don't block
    # the event loop. An `async def` here would block it.

    # Username uniqueness IS disclosed (400): usernames are public identifiers,
    # and the signup form needs to tell the user to pick another. Email existence
    # is NOT disclosed — that's the enumeration-sensitive vector (see below).
    username_taken = db.execute(
        select(models.User).where(models.User.username == body.username)
    ).scalars().first()
    if username_taken:
        raise HTTPException(status_code=400, detail="Username already taken")

    # Hash unconditionally, before the email branch, so both the "email free" and
    # "email taken" paths pay the bcrypt cost. bcrypt dominates the response time,
    # so it masks the smaller delta from the extra DB work the create path does —
    # the two paths aren't identical, but there's no usable timing oracle
    # (mirrors login()'s dummy-hash defense).
    hashed_password = bcrypt.hashpw(body.password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    existing_email = db.execute(
        select(models.User).where(models.User.email == body.email)
    ).scalars().first()
    if existing_email:
        # Do NOT reveal that the address is taken. Return the same generic body
        # as a fresh signup and notify the real owner out-of-band; an attacker
        # probing the API sees nothing, the account owner gets a heads-up. The
        # notice is enqueued (durable) rather than fired as a BackgroundTask.
        enqueue_email(db, EmailType.ACCOUNT_EXISTS, {"to_email": body.email})
        db.commit()
        return RegisterResponse(message=GENERIC_REGISTER_MESSAGE)

    new_user = models.User(
        username=body.username,
        email=body.email,
        hashed_password=hashed_password,
    )
    db.add(new_user)
    try:
        db.commit()
    except IntegrityError:
        # Two concurrent registrations can both pass the checks above and race to
        # insert; the unique constraint catches the loser here instead of 500ing.
        # Re-check the username (public) so a genuine username clash still gets a
        # clear 400; otherwise it was an email race — stay generic, notify owner.
        db.rollback()
        raced_username = db.execute(
            select(models.User).where(models.User.username == body.username)
        ).scalars().first()
        if raced_username:
            raise HTTPException(status_code=400, detail="Username already taken")
        enqueue_email(db, EmailType.ACCOUNT_EXISTS, {"to_email": body.email})
        db.commit()
        return RegisterResponse(message=GENERIC_REGISTER_MESSAGE)
    db.refresh(new_user)

    issue_email_verification(new_user, db)

    return RegisterResponse(message=GENERIC_REGISTER_MESSAGE)

@router.post("/login")
@limiter.limit(settings.RATE_LIMIT_AUTH)
def login(response: Response, request: Request, body: LoginRequest, db: Annotated[Session, Depends(get_db)]):
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
    touch_activity(user)
    db.add(refresh_token_entry)
    db.commit()

    # Refresh token leaves ONLY as an httpOnly cookie — never in the body — so
    # page JS can't read it and an XSS bug can't exfiltrate it. The access token
    # still goes in the body for the client to hold in memory.
    set_refresh_cookie(response, refresh_token)

    return {"access_token": access_token, "user_id": str(user.id), "verified": user.verified}

@router.post("/refresh")
@limiter.limit(settings.RATE_LIMIT_TOKEN)
def refresh(request: Request, response: Response, db: Annotated[Session, Depends(get_db)], refresh_token: Annotated[str | None, Cookie()] = None):
    # The refresh token arrives only via the httpOnly cookie set at login. No
    # cookie (logged out, expired, or a cross-site request that SameSite=Strict
    # stripped) is indistinguishable from a bad token: same 401.
    if refresh_token is None:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    token_hash = hash_token(refresh_token)

    # with_for_update: rotation is read-check-then-revoke, so two concurrent
    # refreshes presenting the SAME cookie would both read revoked=False and both
    # mint a new token — a double-spend that in-process locks can't stop across
    # scaled-out instances. Row-locking the token here serializes them in the DB:
    # the second waits for the first to commit, then re-reads revoked=True below
    # and 401s. The check MUST stay after the lock is acquired (it does).
    result = db.execute(
        select(models.RefreshToken)
        .where(models.RefreshToken.token_hash == token_hash)
        .with_for_update()
    )
    token = result.scalar_one_or_none()

    if not token or token.revoked or token.expires_at < datetime.now(timezone.utc).replace(tzinfo=None):
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    access_token = create_access_token(str(token.user_id))

    # Rotate the refresh token: revoke the presented one and mint a fresh one, so
    # a leaked token is single-use.
    new_raw_token, new_raw_token_hash = create_refresh_token(str(token.user_id))
    token.revoked = True
    new_refresh = models.RefreshToken(
        user_id=token.user_id,
        token_hash=new_raw_token_hash,
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=settings.REFRESH_TIMEOUT_DAYS)
    )
    db.add(new_refresh)
    # Ongoing activity heartbeat: refresh happens whenever the short-lived
    # access token expires, so it's the signal that the user is still active.
    touch_activity(token.user)
    db.commit()

    set_refresh_cookie(response, new_raw_token)

    return {"access_token": access_token, "user_id": str(token.user_id), "verified": token.user.verified}
@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, db: Annotated[Session, Depends(get_db)], refresh_token: Annotated[str | None, Cookie()] = None) -> None:
    # Authenticated by possession of the httpOnly refresh cookie, NOT the Bearer
    # access token. The access token expires in minutes, but only the server can
    # clear an httpOnly cookie — so requiring a live access token would let a
    # "logout" 401 while a valid refresh token stays alive in the DB for days.
    # Safe against CSRF because SameSite=Strict is what guards this endpoint.
    # Idempotent: a missing/unknown/already-revoked token still clears the cookie
    # and returns 204.
    if refresh_token is not None:
        token = db.execute(
            select(models.RefreshToken).where(models.RefreshToken.token_hash == hash_token(refresh_token))
        ).scalar_one_or_none()
        if token is not None and not token.revoked:
            token.revoked = True
            # Flush so the revoke is visible to the EXISTS check, then recompute
            # is_active from the *remaining* valid tokens — other devices may
            # still hold a live session, so we don't blindly set it False.
            db.flush()
            token.user.is_active = has_active_refresh_token(db, token.user_id)
            db.commit()

    clear_refresh_cookie(response)

@router.post("/resend-verification")
@limiter.limit(settings.RATE_LIMIT_EMAIL_SEND)
def resend_verification(request: Request, current_user: Annotated[models.User,Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]):
    if current_user.verified:
        raise HTTPException(status_code=400, detail="Email is already verified")

    issue_email_verification(current_user, db)
    return ResendVerificationResponse(message="Verification email sent")


@router.post("/verify", response_model=ResendVerificationResponse)
@limiter.limit(settings.RATE_LIMIT_TOKEN)
def verify_email(request: Request, body: VerifyEmailRequest, db: Annotated[Session, Depends(get_db)]):
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

@router.post("/forgot-password")
@limiter.limit(settings.RATE_LIMIT_EMAIL_SEND)
def forgot_password(request: Request, body: ForgotPasswordRequest, db: Annotated[Session, Depends(get_db)]):
    # Enqueue a resolve row carrying ONLY the raw email — no user lookup happens
    # here. The request therefore does the exact same single INSERT whether or not
    # the address is registered, so response time can't be used to enumerate
    # accounts. The worker's drainer resolves the address, applies the reset
    # cooldown, mints the token, and enqueues the actual reset email — all off the
    # request path, and durably (a dropped BackgroundTask used to lose it).
    enqueue_email(db, EmailType.FORGOT_PASSWORD_REQUEST, {"email": body.email})
    db.commit()

    return ResendVerificationResponse(message="If the email is registered, a password reset link has been sent")

def _load_valid_reset_token(token: str, db: Session) -> models.EmailToken:
    """Look up a RESET_PASSWORD token and 400 unless it's live and unused.

    Shared by /reset-password (which then consumes it) and
    /reset-password/validate (which only checks it), so the landing page can
    show 'link expired' vs. the form before the user types anything, using the
    exact same criteria the consume path enforces."""
    token_hash = hash_token(token)

    email_token = db.execute(
        select(models.EmailToken).where(models.EmailToken.token_hash == token_hash)
    ).scalars().first()

    if (
        not email_token
        or email_token.purpose != models.EmailTokenPurpose.RESET_PASSWORD
        or email_token.used_at is not None
        or email_token.expires_at < datetime.now(timezone.utc).replace(tzinfo=None)
    ):
        raise HTTPException(status_code=400, detail="Invalid or expired password reset link")

    return email_token


@router.post("/reset-password/validate", response_model=ResendVerificationResponse)
@limiter.limit(settings.RATE_LIMIT_TOKEN)
def validate_reset_token(request: Request, body: ValidateResetTokenRequest, db: Annotated[Session, Depends(get_db)]):
    # Read-only: the landing page calls this on load to decide between the
    # 'link expired' screen and the new-password form, without consuming the
    # single-use token (a preview/scanner hitting it must not burn it either).
    _load_valid_reset_token(body.token, db)
    return ResendVerificationResponse(message="Reset link is valid")


@router.post("/reset-password", response_model=ResendVerificationResponse)
@limiter.limit(settings.RATE_LIMIT_TOKEN)
def reset_password(request: Request, response: Response, body: ForgotPasswordToken, db: Annotated[Session, Depends(get_db)]):
    email_token = _load_valid_reset_token(body.token, db)

    user = db.get(models.User, email_token.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Mark the token as used and update the user's password
    email_token.used_at = datetime.now(timezone.utc).replace(tzinfo=None)
    user.hashed_password = bcrypt.hashpw(body.new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Kill every session, so a stolen refresh token stops working the moment the password changes. Done in the same transaction as the password write: if
    # the revocation failed on its own commit, the password would have changed while old sessions stayed alive — so both land together or neither does.
    db.execute(
        update(models.RefreshToken).where(models.RefreshToken.user_id == user.id).values(revoked=True)
    )
    # Every session was just revoked, so there's no live session left.
    user.is_active = False
    db.commit()

    # Usually hit logged-out (email link), but if this browser happens to hold a
    # now-revoked session cookie, clear it too — consistent with the other
    # revoke-all paths (/users/me/password, delete account).
    clear_refresh_cookie(response)

    return ResendVerificationResponse(message="Password has been reset successfully")


