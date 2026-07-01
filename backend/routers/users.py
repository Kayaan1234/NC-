from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from sqlalchemy.exc import IntegrityError
import bcrypt
from backend.database import get_db
from backend import models
from backend.schemas.auth import *
from sqlalchemy.orm import Session
from typing import Annotated
from fastapi import status
from sqlalchemy import select, update
from backend.core.verification import issue_email_verification

from uuid import UUID

from backend.core.deps import get_current_user
from backend.core.config import settings


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)

@router.get("/me", response_model=UserPublic)
def get_current_user_route(current_user : Annotated[models.User, Depends(get_current_user)]):
    return UserPublic(id = UUID(str(current_user.id)), username=current_user.username, email = current_user.email, verified = current_user.verified)

    
@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    body: DeleteAccountRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
) -> None:
    if not bcrypt.checkpw(body.current_password.encode('utf-8'), current_user.hashed_password.encode('utf-8')):
        raise HTTPException(status_code=400, detail="Incorrect password")

    db.delete(current_user)
    db.commit()
    

@router.patch("/me/password", response_model=ResetPasswordResponse)
def reset_password(
    body: ResetPasswordRequest,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    if not bcrypt.checkpw(body.current_password.encode('utf-8'), current_user.hashed_password.encode('utf-8')):
        raise HTTPException(status_code=400, detail="Incorrect current password")

    current_user.hashed_password = bcrypt.hashpw(body.new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    # Kill every session, so a stolen refresh token stops working the moment the
    # password changes. Done in the same transaction as the password write: if
    # the revocation failed on its own commit, the password would have changed
    # while old sessions stayed alive — so both land together or neither does.
    db.execute(
        update(models.RefreshToken).where(models.RefreshToken.user_id == current_user.id).values(revoked=True)
    )
    db.commit()

    return ResetPasswordResponse(message="Password updated successfully")

#Future work - update so you can send email to old user email to let a user know that an email has been changed
@router.patch("/me/email", response_model=ResendVerificationResponse)
def update_email(
    body: UpdateEmailRequest,
    background_tasks: BackgroundTasks,
    current_user: Annotated[models.User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)]
):
    if not bcrypt.checkpw(body.current_password.encode('utf-8'), current_user.hashed_password.encode('utf-8')):
        raise HTTPException(status_code=400, detail="Incorrect password")

    if body.new_email == current_user.email:
        # No-op change would needlessly flip verified=False and re-send.
        raise HTTPException(status_code=400, detail="New email must be different from your current email")

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    change_cooldown = timedelta(hours=settings.EMAIL_CHANGE_COOLDOWN_HOURS)
    if current_user.email_changed_at is not None:
        elapsed = now - current_user.email_changed_at
        if elapsed < change_cooldown:
            retry_after = int((change_cooldown - elapsed).total_seconds())
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="You can only change your email once per day. Please try again later.",
                headers={"Retry-After": str(retry_after)},
            )

    existing = db.execute(
        select(models.User).where(models.User.email == body.new_email)
    ).scalars().first()
    if existing and existing.id != current_user.id:
        raise HTTPException(status_code=400, detail="Email already in use")

    current_user.email = body.new_email
    current_user.verified = False
    current_user.email_changed_at = now
    # Stage the change; issue_email_verification commits it atomically with the
    # new token. enforce_cooldown=False: the once-per-day change limit above
    # already governs this path, so the 10-min resend throttle must not block
    # the verification email for a legitimate change. A unique-constraint race
    # on the new email surfaces here as IntegrityError -> clean 400, not a 500.
    try:
        issue_email_verification(current_user, db, background_tasks, enforce_cooldown=False)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Email already in use")
    return ResendVerificationResponse(message="Email updated, verification email sent")


