"""
Module: detection_results
This module defines the DetectionResults model, which stores information about
detection outcomes, including related configuration, model, and file paths.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, Text, ForeignKey, String, SmallInteger

from db.base import Base

if TYPE_CHECKING:
    from .work_configs import WorkConfigs
    from .trained_models import TrainedModels

class DetectionResults(Base):
    """
    ORM model representing the detection result of a specific inspection.

    Attributes:
        id (int): Primary key of the detection result.
        detected_at (str): Timestamp (ISO 8601) when the detection occurred.
        work_config_id (int): Foreign key to the work configuration used.
        trained_model_id (int): Foreign key to the trained model used.
        judgment (int): Detection outcome — 0: OK, 1: NG.
        thumbnail_path (str): File path to the thumbnail image.
        his_img_path (str): File path to the original input data.
        heatmap_path (str | None): Optional file path to the generated heatmap.
        created_at (str): Creation timestamp.
        updated_at (str | None): Last update timestamp.
        deleted_at (str | None): Deletion timestamp.
        deleted (bool): Soft delete flag (0: active, 1: deleted).
    """
    __tablename__ = "detection_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    detected_at: Mapped[str] = mapped_column(String, nullable=False, default=lambda: datetime.now().isoformat(), doc="Thời gian phát hiện (ISO 8601)")

    work_config_id: Mapped[int] = mapped_column(Integer, ForeignKey("work_configs.id"), nullable=False, doc="ID cấu hình vật kiểm đã sử dụng")
    trained_model_id: Mapped[int] = mapped_column(Integer, ForeignKey("trained_models.id"), nullable=False, doc="ID mô hình đã huấn luyện được sử dụng")

    judgment: Mapped[int] = mapped_column(Integer, nullable=False, doc="0: OK, 1: NG")
    thumbnail_path: Mapped[str] = mapped_column(Text, nullable=False, doc="Đường dẫn ảnh thu nhỏ")
    his_img_path: Mapped[str] = mapped_column(Text, nullable=False, doc="Đường dẫn dữ liệu gốc")
    heatmap_path: Mapped[str] = mapped_column(Text, nullable=False, doc="Đường dẫn dữ ảnh heatmap")

    created_at: Mapped[str] = mapped_column(String, nullable=False, default=lambda: datetime.now().isoformat())
    updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    deleted_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    deleted: Mapped[bool] = mapped_column(SmallInteger, nullable=False, default=0, doc="Cài đặt đã bị xóa hay chưa")

    work_configs: Mapped["WorkConfigs"] = relationship(back_populates="detection_results")
    trained_models: Mapped["TrainedModels"] = relationship(back_populates="detection_results")

    def __repr__(self) -> str:
        return f"<DetectionResults(id={self.id}, judgment={self.judgment})>"
