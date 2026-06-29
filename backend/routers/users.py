from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends


from backend import models
from backend.schemas.auth import UserPublic

from typing import Annotated


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

    
    
