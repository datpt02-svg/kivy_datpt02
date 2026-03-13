"""
Module: system_config
This module defines the SystemConfig model, which stores key-value configuration
pairs for global system settings such as language or debug mode.
"""

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String

from db.base import Base

class SystemConfig(Base):
    """
    ORM model representing a system-wide configuration entry.

    Attributes:
        key (str): Configuration key (e.g., 'DEBUG_MODE', 'LANGUAGE').
        value (str): Configuration value associated with the key.
    """
    __tablename__ = "system_config"

    key: Mapped[str] = mapped_column(String, primary_key=True, doc="Khóa cài đặt (ví dụ: 'DEBUG_MODE', 'LANGUAGE')")
    value: Mapped[str] = mapped_column(String, nullable=False, doc="Giá trị cài đặt")

    def __repr__(self) -> str:
        return f"<SystemConfig(key={self.key!r}, value={self.value!r})>"
