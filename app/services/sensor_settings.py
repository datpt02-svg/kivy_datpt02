from sqlalchemy.orm import Session
from db.models.sensor_settings import SensorSettings
from datetime import datetime
from typing import Optional

def create_sensor_settings(
    db: Session,
    name: str,
    intrinsic_path: str,
    perspective_path: str,
    speed_path: str,
    pattern_cols: int,
    pattern_rows: int,
    bias_path: Optional[str] = None,
    pose_file_path: Optional[str] = None,
    status_pose: bool = False
) -> SensorSettings:
    now = datetime.now().isoformat()
    new_setting = SensorSettings(
        name=name,
        intrinsic_path=intrinsic_path,
        perspective_path=perspective_path,
        speed_path=speed_path,
        pattern_cols=pattern_cols,
        pattern_rows=pattern_rows,
        bias_path=bias_path,
        pose_file_path=pose_file_path,
        status_pose=status_pose,
        created_at=now,
        updated_at=now,
        deleted_at=None,
        deleted=0
    )

    db.add(new_setting)
    db.commit()
    db.refresh(new_setting)
    return new_setting

def read_sensor_settings(db: Session, setting_id: int) -> Optional[SensorSettings]:
    return (
        db.query(SensorSettings)
        .filter(
            SensorSettings.id == setting_id,
            SensorSettings.deleted == 0
        )
        .first()
    )

def update_sensor_settings(
    db: Session,
    setting_id: int,
    name: Optional[str] = None,
    intrinsic_path: Optional[str] = None,
    perspective_path: Optional[str] = None,
    speed_path: Optional[str] = None,
    pattern_cols: Optional[int] = None,
    pattern_rows: Optional[int] = None,
    bias_path: Optional[str] = None,
    pose_file_path: Optional[str] = None,
    status_pose: Optional[bool] = None
) -> Optional[SensorSettings]:
    setting = (
        db.query(SensorSettings)
        .filter(
            SensorSettings.id == setting_id,
            SensorSettings.deleted == 0
        )
        .first()
    )
    if setting:
        if name is not None:
            setting.name = name
        if intrinsic_path is not None:
            setting.intrinsic_path = intrinsic_path
        if perspective_path is not None:
            setting.perspective_path = perspective_path
        if speed_path is not None:
            setting.speed_path = speed_path
        if pattern_cols is not None:
            setting.pattern_cols = pattern_cols
        if pattern_rows is not None:
            setting.pattern_rows = pattern_rows
        if bias_path is not None:
            setting.bias_path = bias_path
        if pose_file_path is not None:
            setting.pose_file_path = pose_file_path
        if status_pose is not None:
            setting.status_pose = status_pose
        setting.updated_at = datetime.now().isoformat()
        db.commit()
        db.refresh(setting)
        return setting
    return None

def delete_permanent_sensor_settings(db: Session, setting_id: int) -> bool:
    setting = db.query(SensorSettings).filter(SensorSettings.id == setting_id).first()
    if setting:
        db.delete(setting)
        db.commit()
        return True
    return False

def delete_sensor_settings(db: Session, setting_id: int) -> bool:
    setting = (
        db.query(SensorSettings)
        .filter(
            SensorSettings.id == setting_id,
            SensorSettings.deleted == 0
        )
        .first()
    )
    if setting:
        now = datetime.now().isoformat()
        setting.deleted_at = now
        setting.deleted = 1
        setting.updated_at = now
        db.commit()
        return True
    return False

def check_duplicate_name(db: Session, name: str) -> bool:
    """
    Kiểm tra tên cài đặt đã tồn tại trong DB chưa (chỉ tính bản ghi chưa bị xóa).
    Trả về True nếu đã tồn tại, False nếu chưa.
    """
    return (
        db.query(SensorSettings)
        .filter(
            SensorSettings.name == name,
            SensorSettings.deleted == 0
        )
        .first()
        is not None
    )