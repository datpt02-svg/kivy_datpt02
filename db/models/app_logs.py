"""
Module: app_logs
Description: Defines the ORM model for the `app_logs` table,
which stores application log entries including message,
level, timestamp, and optional exception details.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Integer, Text, String

from db.base import Base


class AppLogs(Base):
    """
    ORM model representing the `app_logs` table.
    Stores application log entries with their timestamp,
    level, message, and exception information.
    """
    __tablename__ = "app_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[str] = mapped_column(String, nullable=False, default=lambda: datetime.now().isoformat(), doc="Thời gian log được tạo (ISO 8601)")
    level: Mapped[str] = mapped_column(String, nullable=False, doc="Cấp độ log")
    logger_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Tên logger nguồn")
    message: Mapped[str] = mapped_column(Text, nullable=False, doc="Nội dung thông điệp log")
    exception_info: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Chi tiết ngoại lệ")

    def __repr__(self) -> str:
        return f"<AppLogs(id={self.id}, level={self.level!r})>"
