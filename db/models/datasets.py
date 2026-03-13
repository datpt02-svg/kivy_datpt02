"""
Module: datasets
Description: Defines the ORM model for the `datasets` table,
which stores dataset metadata, relations to work configurations,
dataset images, and trained models.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, Text, ForeignKey, Boolean, String, SmallInteger, Index

from db.base import Base

if TYPE_CHECKING:
    from .work_configs import WorkConfigs
    from .dataset_images import DatasetImages
    from .trained_models import TrainedModels

class Datasets(Base):
    """
    ORM model representing the `datasets` table.
    Stores dataset information and maintains relationships
    with work configurations, dataset images, and trained models.
    """
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, doc="Tên bộ dữ liệu")

    work_config_id: Mapped[int] = mapped_column(Integer, ForeignKey("work_configs.id"), nullable=False, doc="Liên kết đến work_config đã tạo ra dataset này")

    is_trained: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, doc="Mô hình đã được huấn luyện với bộ dữ liệu này chưa")

    created_at: Mapped[str] = mapped_column(String, nullable=False, default=lambda: datetime.now().isoformat(), doc="Thời gian tạo bản ghi (ISO 8601)")
    updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Thời gian cập nhật cuối cùng")
    deleted_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Thời gian xóa")
    deleted: Mapped[bool] = mapped_column(SmallInteger, nullable=False, default=0, doc="Cài đặt đã bị xóa hay chưa")

    work_configs: Mapped["WorkConfigs"] = relationship(back_populates="datasets")
    dataset_images: Mapped[list["DatasetImages"]] = relationship(back_populates="datasets", cascade="all, delete-orphan")
    trained_models: Mapped[list["TrainedModels"]] = relationship(doc="Danh sách mô hình đã huấn luyện với bộ dữ liệu này")
    __table_args__ = (
        Index('datasets_unique_name', 'name', unique=True, sqlite_where=deleted == 0),
    )

    def __repr__(self) -> str:
        return f"<Datasets(id={self.id}, name={self.name!r})>"
