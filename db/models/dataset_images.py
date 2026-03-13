"""
Module: dataset_images
Description: Defines the ORM model for the `dataset_images` table,
which stores image records belonging to specific datasets.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, Text, ForeignKey, String, SmallInteger

from db.base import Base

if TYPE_CHECKING:
    from .datasets import Datasets

class DatasetImages(Base):
    """
    ORM model representing the `dataset_images` table.
    Stores information about images that belong to datasets,
    including their source path, usage type, and metadata timestamps.
    """
    __tablename__ = "dataset_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[int] = mapped_column(Integer, ForeignKey("datasets.id"), nullable=False, doc="ID bộ dữ liệu mà ảnh này thuộc về")

    image_source_path: Mapped[str] = mapped_column(Text, nullable=False, doc="Đường dẫn ảnh gốc")
    usage_type: Mapped[str] = mapped_column(String, nullable=False, doc="Loại sử dụng (0: OK, 1: NG, 2: Other)")

    created_at: Mapped[str] = mapped_column(String, nullable=False, default=lambda: datetime.now().isoformat(), doc="Thời gian tạo bản ghi (ISO 8601)")
    updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Thời gian cập nhật cuối cùng")
    deleted_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Thời gian xóa")
    deleted: Mapped[bool] = mapped_column(SmallInteger, nullable=False, default=0, doc="Cài đặt đã bị xóa hay chưa")

    datasets: Mapped["Datasets"] = relationship(back_populates="dataset_images")

    def __repr__(self) -> str:
        return f"<DatasetImages(id={self.id}, dataset_id={self.dataset_id})>"
