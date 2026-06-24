
from fastapi import APIRouter, HTTPException, Depends


from backend import models
from backend.schemas.auth import RegisterRequest, AuthResponse
from backend.database import get_db
from typing import Annotated
from sqlalchemy.orm import Session
from sqlalchemy import select
import bcrypt

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

    return AuthResponse(message="User registered successfully", user_id=new_user.id, verified=False)