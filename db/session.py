"""
session.py

Provides SQLAlchemy session management utilities for database access.

This module defines a `SessionLocal` factory bound to the application's
database engine, and a context-managed generator function `get_db()` that
ensures database sessions are properly opened and closed.

Typical usage example:
    from db.session import get_db

    with get_db() as db:
        db.query(MyModel).all()
"""
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker
from .engine import engine


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

@contextmanager
def get_db():
    """
    Provide a transactional scope around a series of database operations.

    This function yields a SQLAlchemy session object that is automatically
    closed when the context exits, ensuring proper resource cleanup.

    Yields:
        Session: A SQLAlchemy database session instance.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
