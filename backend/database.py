from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from backend.core.config import settings

# check_same_thread is a SQLite-only connect arg; Postgres (psycopg) rejects it.
connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) #control whether changes are automatically committed to the database or not. If autocommit is set to True, changes will be committed automatically after each statement. If set to False, you need to explicitly call commit() to save changes. 

class Base(DeclarativeBase): # declarative base class for defining database models
    pass

def get_db(): #context manager that provides a database session for use in a with statement. It creates a new session, yields it to the caller, and then closes the session when the with block is exited.
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

