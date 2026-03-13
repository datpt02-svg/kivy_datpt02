"""
Module: work_configs
This module defines the WorkConfigs model, which stores configuration settings
for inspection work, including sensor parameters, ROI, filtering, mask thresholds,
event values, speed correction, and relationships to datasets, images, and detection results.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Text, Boolean, ForeignKey, Float, SmallInteger, Index

from db.base import Base

if TYPE_CHECKING:
    from .sensor_settings import SensorSettings
    from .alignment_images import AlignmentImages
    from .datasets import Datasets
    from .detection_results import DetectionResults
    from .generate_datas import GenerateDatas

class WorkConfigs(Base):
    """
    ORM model representing a configuration for inspection work.

    Attributes:
        id (int): Primary key of the work configuration.
        name (str): Name of the work configuration.
        sensor_setting_id (int): Foreign key referencing the Prophesee sensor setting.
        delta_t (int): Event data time interval.
        use_roi (bool): Whether to use ROI.
        roi (str | None): ROI coordinates (x1,y1: top-left; x2,y2: bottom-right).
        bias_path (str): Path to bias file applied.
        sensor_filter (int): Sensor filter type.
        sensor_filter_threshold (int | None): Threshold for sensor filter.
        mask_img_thresh_1 (int): Noise removal threshold.
        mask_img_thresh_2 (int): Edge extraction threshold.
        mask_minimal_area (int): Minimum pixels for detection threshold.
        skip_frame (int | None): Number of frames to skip for display.
        on_event_his_value (int): On event value adjustment.
        off_event_his_value (int): Off event value adjustment.
        speed_correction_param (float): Speed correction parameter.
        colormap (str): OpenCV colormap name.
        created_at (str): Record creation timestamp (ISO 8601).
        updated_at (str | None): Last updated timestamp.
        deleted_at (str | None): Deletion timestamp.
        deleted (bool): Soft delete flag (0 = active, 1 = deleted).
        sensor_settings (SensorSettings): Associated sensor settings.
        alignment_images (list[AlignmentImages]): Alignment images linked to this config.
        datasets (list[Datasets]): Datasets linked to this config.
        detection_results (list[DetectionResults]): Detection results linked to this config.
        generate_datas (list[GenerateDatas]): Generated data linked to this config.
    """
    __tablename__ = "work_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, doc="Tên cấu hình vật kiểm")

    sensor_setting_id: Mapped[int] = mapped_column(Integer, ForeignKey("sensor_settings.id"), nullable=False, doc="ID cài đặt Prophesee được tham chiếu")

    delta_t: Mapped[int] = mapped_column(Integer, nullable=False, doc="Khoảng thời gian dữ liệu sự kiện")
    use_roi: Mapped[bool] = mapped_column(Boolean, nullable=False, doc="Có sử dụng ROI hay không")

    roi: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Tọa độ ROI (x1, y1: trên trái; x2, y2: dưới phải)")

    bias_path: Mapped[str] = mapped_column(Text, nullable=False, doc="Đường dẫn bias áp dụng")
    sensor_filter: Mapped[int] = mapped_column(Integer, nullable=False, doc="Kiểu bộ lọc cảm biến")
    sensor_filter_threshold: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, doc="Ngưỡng cho bộ lọc cảm biến")

    seg_kernel_size: Mapped[int] = mapped_column(Integer, nullable=False, doc="Ngưỡng loại bỏ nhiễu")
    seg_threshold: Mapped[int] = mapped_column(Integer, nullable=False, doc="Ngưỡng trích xuất đường viền")
    seg_padding: Mapped[int] = mapped_column(Integer, nullable=False, doc="Padding")

    on_event_his_value: Mapped[int] = mapped_column(Integer, nullable=False, doc="Số cộng/trừ sự kiện On")
    off_event_his_value: Mapped[int] = mapped_column(Integer, nullable=False, doc="Số cộng/trừ sự kiện Off")

    speed_correction_param: Mapped[float] = mapped_column(Float, nullable=False, doc="Giá trị hiệu chỉnh tốc độ")
    colormap: Mapped[str] = mapped_column(String, nullable=False, doc="Tên bản đồ màu OpenCV")
    histogram_path: Mapped[str] = mapped_column(String, nullable=True, doc="Đường dẫn ảnh histogram")

    created_at: Mapped[str] = mapped_column(String, nullable=False, default=lambda: datetime.now().isoformat(), doc="Thời gian tạo bản ghi (ISO 8601)")
    updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Thời gian cập nhật cuối")
    deleted_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Thời gian xóa")
    deleted: Mapped[bool] = mapped_column(SmallInteger, nullable=False, default=0, doc="Cài đặt đã bị xóa hay chưa")

    sensor_settings: Mapped["SensorSettings"] = relationship(back_populates="work_configs")
    alignment_images: Mapped[list["AlignmentImages"]] = relationship(back_populates="work_configs", cascade="all, delete-orphan", doc="Danh sách ảnh căn chỉnh thuộc về cấu hình này")
    datasets: Mapped[list["Datasets"]] = relationship(doc="Danh sách bộ dữ liệu thuộc về cấu hình này")
    detection_results: Mapped[list["DetectionResults"]] = relationship(doc="Danh sách kết quả phát hiện thuộc về cấu hình này")
    generate_datas: Mapped[list["GenerateDatas"]] = relationship(doc="Danh sách dữ liệu đã tạo thuộc về cấu hình này")

    __table_args__ = (
        Index('work_configs_unique_name', 'name', unique=True, sqlite_where=deleted == 0),
    )

    def __repr__(self) -> str:
        return (
            f"WorkConfigs(id={self.id!r}, \
            name={self.name!r}, \
            sensor_setting_id={self.sensor_setting_id!r}, \
            delta_t={self.delta_t!r}, \
            use_roi={self.use_roi!r}, \
            bias_path={self.bias_path!r}, \
            sensor_filter={self.sensor_filter!r})"
        )
