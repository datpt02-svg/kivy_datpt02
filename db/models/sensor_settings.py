"""
Module: sensor_settings
This module defines the SensorSettings model, which stores configuration data
for Prophesee sensors, including calibration, motion, and pattern parameters.
"""

from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Text, Index, SmallInteger

from db.base import Base

if TYPE_CHECKING:
    from .work_configs import WorkConfigs

class SensorSettings(Base):
    """
    ORM model representing the configuration and calibration data of a Prophesee sensor.

    Attributes:
        id (int): Primary key of the sensor setting record.
        name (str): Name of the Prophesee sensor setting (unique when not deleted).
        intrinsic_path (str): Path to the JSON file for lens calibration.
        bias_path (str | None): Optional path to the bias file.
        perspective_path (str): Path to the JSON file for angle/orientation calibration.
        speed_path (str): Path to the JSON file for motion calibration.
        pattern_cols (int): Number of columns in the dot pattern.
        pattern_rows (int): Number of rows in the dot pattern.
        created_at (str): Creation timestamp (ISO 8601).
        updated_at (str | None): Last update timestamp (ISO 8601).
        deleted_at (str | None): Deletion timestamp (ISO 8601).
        deleted (bool): Soft delete flag (0 = active, 1 = deleted).
        work_configs (list[WorkConfigs]): Related work configurations using this sensor.
    """
    __tablename__ = "sensor_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, doc="Tên cài đặt Prophesee")

    intrinsic_path: Mapped[str] = mapped_column(Text, nullable=False, doc="Đường dẫn đến file JSON cài đặt hiệu chỉnh ống kính")
    bias_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Đường dẫn file bias (có thể không cần)")
    perspective_path: Mapped[str] = mapped_column(Text, nullable=False, doc="Đường dẫn đến file JSON cài đặt hiệu chỉnh góc/độ nghiêng")
    speed_path: Mapped[str] = mapped_column(Text, nullable=False, doc="Đường dẫn đến file JSON cài đặt hiệu chỉnh chuyển động")

    pattern_cols: Mapped[int] = mapped_column(Integer, nullable=False, doc="Số cột mẫu chấm")
    pattern_rows: Mapped[int] = mapped_column(Integer, nullable=False, doc="Số hàng mẫu chấm")

    created_at: Mapped[str] = mapped_column(String, nullable=False, default=lambda: datetime.now().isoformat(), doc="Thời gian tạo bản ghi (ISO 8601)")
    updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Thời gian cập nhật cuối cùng (ISO 8601)")
    deleted_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Thời gian xóa (ISO 8601)")
    deleted: Mapped[bool] = mapped_column(SmallInteger, nullable=False, default=0, doc="Cài đặt đã bị xóa hay chưa")

    pose_file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status_pose: Mapped[bool] = mapped_column(SmallInteger, nullable=False, default=0)

    work_configs: Mapped[List["WorkConfigs"]] = relationship(back_populates="sensor_settings", cascade="all, delete-orphan")

    __table_args__ = (
        Index('sensor_settings_unique_name', 'name', unique=True, sqlite_where=deleted == 0),
    )


    def __repr__(self) -> str:
        return (
            f"SensorSettings(id={self.id!r}, \
            name={self.name!r}, \
            intrinsic_path={self.intrinsic_path!r}, \
            bias_path={self.bias_path!r}, \
            perspective_path={self.perspective_path!r}, \
            speed_path={self.speed_path!r}, \
            pattern_cols={self.pattern_cols!r}, \
            pattern_rows={self.pattern_rows!r})"
        )
