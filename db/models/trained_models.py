"""
Module: trained_models
This module defines the TrainedModels model, which stores information about
trained machine learning models, including their configuration, dataset,
training parameters, and weight file paths.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import Integer, Text, ForeignKey, String, SmallInteger, Index

from db.base import Base

if TYPE_CHECKING:
    from .datasets import Datasets
    from .detection_results import DetectionResults

class TrainedModels(Base):
    """
    ORM model representing a trained machine learning model and its metadata.

    Attributes:
        id (int): Primary key of the trained model.
        name (str): Name of the trained model.
        dataset_id (int): Foreign key referencing the dataset used for training.
        epochs (int): Number of epochs the model was trained for.
        learn_method (int): Learning method used — 0: patch, 1: parallel.
        patch_size_1 (int): Patch size of model 1.
        input_size_1 (int): Input size of model 1.
        weight_path_1 (str): File path to the weight file for model 1.
        patch_size_2 (int | None): Patch size of model 2 (if applicable).
        input_size_2 (int | None): Input size of model 2 (if applicable).
        weight_path_2 (str | None): File path to the weight file for model 2.
        created_at (str): Record creation timestamp (ISO 8601).
        updated_at (str | None): Last updated timestamp.
        deleted_at (str | None): Deletion timestamp.
        deleted (bool): Soft delete flag (0 = active, 1 = deleted).
        datasets (Datasets): Dataset associated with this trained model.
        detection_results (list[DetectionResults]): Detection results linked to this model.
    """
    __tablename__ = "trained_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(Text, nullable=False, doc="Tên mô hình")

    dataset_id: Mapped[int] = mapped_column(Integer, ForeignKey("datasets.id"), nullable=False, doc="ID bộ dữ liệu đã sử dụng để học")

    epochs: Mapped[int] = mapped_column(Integer, nullable=False, doc="Số epoch đã huấn luyện")

    learn_method: Mapped[int] = mapped_column(SmallInteger, nullable=False, doc="0: patch, 1: parallel")
    patch_size_1: Mapped[int] = mapped_column(Integer, nullable=False, doc="Giá trị patch của model 1")
    input_size_1: Mapped[int] = mapped_column(Integer, nullable=False, doc="Giá trị input size của model 1")
    weight_path_1: Mapped[str] = mapped_column(Text, nullable=False, doc="Đường dẫn file weights của model 1")
    engine_path_1: Mapped[str] = mapped_column(Text, nullable=False, doc="Đường dẫn file weights tensorrt của model 1")
    patch_size_2: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, doc="Giá trị patch của model 2")
    input_size_2: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, doc="Giá trị input size của model 2")
    weight_path_2: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Đường dẫn file weights của model 2")
    engine_path_2: Mapped[Optional[str]] = mapped_column(Text, nullable=True, doc="Đường dẫn file weights tensorrt của model 2")
    heat_kernel_size: Mapped[int] = mapped_column(Integer, nullable=True, doc="Độ mờ của vùng phát hiện")
    heat_min_area: Mapped[int] = mapped_column(Integer, nullable=True, doc="Diện tích tối thiểu của vùng phát hiện")
    heat_threshold: Mapped[int] = mapped_column(Integer, nullable=True, doc="Mức độ để phán đoán là bất thường (0-255)")
    heat_min_intensity: Mapped[int] = mapped_column(Integer, nullable=True, doc="Cường độ phát hiện")
    has_preset: Mapped[bool] = mapped_column(SmallInteger, nullable=False, default=0, doc="Mô hình có preset đã lưu hay không")

    created_at: Mapped[str] = mapped_column(String, nullable=False, default=lambda: datetime.now().isoformat(), doc="Thời gian tạo bản ghi (ISO 8601)")
    updated_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Thời gian cập nhật cuối cùng")
    deleted_at: Mapped[Optional[str]] = mapped_column(String, nullable=True, doc="Thời gian xóa")
    deleted: Mapped[bool] = mapped_column(SmallInteger, nullable=False, default=0, doc="Cài đặt đã bị xóa hay chưa")

    datasets: Mapped["Datasets"] = relationship(back_populates="trained_models")
    detection_results: Mapped[list["DetectionResults"]] = relationship(back_populates="trained_models", doc="Danh sách kết quả phát hiện thuộc về mô hình này")


    __table_args__ = (
        Index('trained_models_unique_name', 'name', unique=True, sqlite_where=deleted == 0),
    )

    def __repr__(self) -> str:
        return f"<TrainedModels(id={self.id}, name={self.name!r})>"
