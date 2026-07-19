from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from backend.core.config import settings

if settings.DATABASE_URL.startswith("sqlite"):
    # check_same_thread is a SQLite-only connect arg; Postgres (psycopg) rejects
    # it. SQLite's func.now() already returns UTC, so no timezone pin is needed.
    # SQLite uses its own pool class and rejects pool_size/max_overflow, so those
    # (see the else branch) are Postgres-only.
    connect_args = {"check_same_thread": False}
    pool_kwargs = {}
else:
    # Pin the Postgres session timezone to UTC. Otherwise the session inherits the
    # server's zone (this deployment's is Europe/London), and every
    # server_default=func.now() column is stored in local wall-clock time while the
    # app writes datetime.now(timezone.utc) everywhere else. The two are an hour
    # apart under BST (zero in winter, so it hides), which silently skews any
    # comparison between them — most visibly the email verification/reset resend
    # cooldowns, which stretch to ~70 minutes. libpq reads `-c timezone=utc` from
    # the options string. See SCALABILITY_AUDIT.md.
    connect_args = {"options": "-c timezone=utc"}
    # Bound connections per process so autoscaled API instances + the worker stay
    # within RDS max_connections; recycle so RDS idle-reaping/failover doesn't
    # leave stale connections checked into the pool. See config.py DB_POOL_*.
    pool_kwargs = {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        "pool_recycle": settings.DB_POOL_RECYCLE_SECONDS,
    }
engine = create_engine(
    settings.DATABASE_URL, connect_args=connect_args, pool_pre_ping=True, **pool_kwargs
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine) #control whether changes are automatically committed to the database or not. If autocommit is set to True, changes will be committed automatically after each statement. If set to False, you need to explicitly call commit() to save changes. 

class Base(DeclarativeBase): # declarative base class for defining database models
    pass

def get_db(): #context manager that provides a database session for use in a with statement. It creates a new session, yields it to the caller, and then closes the session when the with block is exited.
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

