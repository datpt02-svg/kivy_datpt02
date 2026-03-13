"""
engine.py

Provides SQLAlchemy database engine setup for the application.

This module defines the database connection string and creates the
SQLAlchemy engine instance. The database is stored in a "db" folder
within the application's base directory.

Typical usage example:
    from db.engine import engine

    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        print(result.fetchone())
"""
import os
import sys
from sqlalchemy import create_engine

def app_base_dir():
    """Get the application's base directory."""
    if getattr(sys, "frozen", False):
        # Folder containing the packaged executable (e.g., evs-ui.exe)
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")

db_dir = os.path.join(app_base_dir(), "db")
os.makedirs(db_dir, exist_ok=True)

db_path = os.path.join(db_dir, "dimmer.db")
SQLALCHEMY_DATABASE_URL = f"sqlite:///{db_path}"

engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=False, future=True)
