from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from typing import Annotated

from backend import models
from backend.database import get_db
from sqlalchemy.orm import Session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: Annotated[Session, Depends(get_db)]):
    pass
