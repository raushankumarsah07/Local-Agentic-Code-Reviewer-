"""
Database engine and session management.
Supports SQLite out of the box and seamlessly switches to PostgreSQL
by changing the DATABASE_URL connection string in .env.
"""

from pathlib import Path
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.config import get_settings

settings = get_settings()

db_url = settings.DATABASE_URL

# If using SQLite with a relative or local file path, ensure the parent directory exists
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    # Extract path from sqlite:///path/to/file.db
    sqlite_file = db_url.replace("sqlite:///", "")
    if sqlite_file and sqlite_file != ":memory:":
        db_path = Path(sqlite_file)
        db_path.parent.mkdir(parents=True, exist_ok=True)

# Create engine
engine = create_engine(
    db_url,
    connect_args=connect_args,
    echo=False,
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for declarative SQLAlchemy models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that yields a scoped database session and guarantees cleanup.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize all database tables defined in SQLAlchemy models.
    """
    # Import models here to ensure they are registered with Base.metadata
    from app.db import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
