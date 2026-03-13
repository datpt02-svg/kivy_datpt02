"""
Module: generate_datas
This module defines the GenerateDatas model, which stores information about
generated data directories linked to a specific work configuration.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, Text, ForeignKey, String, SmallInteger

from db.base import Base

if TYPE_CHECKING:
    from .work_configs import WorkConfigs

class GenerateDatas(Base):
    """
    ORM model representing a record of generated data linked to a work configuration.

    Attributes:
        id (int): Primary key of the generated data record.
        work_config_id (int): Foreign key to the associated work configuration.
        data_dir (str): Path to the directory containing generated data.
        created_at (str): Timestamp when the record was created (ISO 8601).
        updated_at (str | None): Timestamp of the last update.
        deleted_at (str | None): Timestamp when the record was deleted.
        deleted (bool): Soft delete flag (0: active, 1: deleted).
    """
    __tablename__ = "generate_datas"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_config_id: Mapped[int] = mapped_column(Integer, ForeignKey("work_configs.id"), nullable=False, unique=False, doc="ID cấu hình vật kiểm đã sử dụng để tạo dữ liệu")

    data_dir: Mapped[str] = mapped_column(Text, nullable=False, unique=False, doc="Đường dẫn đến thư mục chứa dữ liệu đã tạo ra")

    created_at: Mapped[str] = mapped_column(String, nullable=False, default=lambda: datetime.now().isoformat(), doc="Thời gian tạo bản ghi (ISO 8601)")
    updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Thời gian cập nhật cuối cùng")
    deleted_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Thời gian xóa")
    deleted: Mapped[bool] = mapped_column(SmallInteger, nullable=False, default=0, doc="Cài đặt đã bị xóa hay chưa")

    work_configs: Mapped["WorkConfigs"] = relationship(back_populates="generate_datas")

    def __repr__(self) -> str:
        return f"<GenerateDatas(id={self.id}, work_config_id={self.work_config_id}, data_dir={self.data_dir!r})>"
