"""
Module: alignment_images
Description: Defines the ORM model for the `alignment_images` table, which stores
alignment image data associated with a work configuration.
"""
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Text, ForeignKey, SmallInteger

from db.base import Base

if TYPE_CHECKING:
    from .work_configs import WorkConfigs

class AlignmentImages(Base):
    """
    ORM model representing the `alignment_images` table.
    Stores information about alignment image paths, coordinates,
    and the relationship to the corresponding work configuration.
    """
    __tablename__ = "alignment_images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    work_config_id: Mapped[int] = mapped_column(Integer,ForeignKey("work_configs.id"), nullable=False, doc="ID cấu hình vật kiểm mà ảnh này thuộc về")

    image_path: Mapped[str] = mapped_column(Text, nullable=False, doc="Đường dẫn đến file ảnh căn chỉnh")
    alignment_coord: Mapped[str] = mapped_column(Text, nullable=False, doc="Tọa độ nhúng dữ liệu Prophesee lên ảnh (x1, y1: trên trái; x2, y2: dưới phải)")
    image_index: Mapped[int] = mapped_column(Integer, nullable=False, doc="Chỉ mục của ảnh để duy trì thứ tự")

    created_at: Mapped[str] = mapped_column(String, nullable=False, default=lambda: datetime.now().isoformat(), doc="Thời gian tạo bản ghi (ISO 8601)")
    updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Thời gian cập nhật cuối cùng")
    deleted_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Thời gian xóa")
    deleted: Mapped[bool] = mapped_column(SmallInteger, nullable=False, default=0, doc="Cài đặt đã bị xóa hay chưa")

    work_configs: Mapped["WorkConfigs"] = relationship(back_populates="alignment_images")

    def __repr__(self) -> str:
        return (
            f"AlignmentImages(id={self.id!r}, \
            work_config_id={self.work_config_id!r}, \
            image_path={self.image_path!r}, \
            alignment_coord={self.alignment_coord!r}, \
            index={self.image_index!r}"
        )
