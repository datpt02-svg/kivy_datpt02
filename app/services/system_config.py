from sqlalchemy.orm import Session
from db.models.system_config import SystemConfig
from typing import Optional
import traceback

def create_system_config(
    db: Session,
    key: str,
    value: str
) -> SystemConfig:
    config = SystemConfig(key=key, value=value)
    db.add(config)
    db.commit()
    db.refresh(config)
    return config

def read_system_config(
    db: Session,
    key: str
) -> Optional[SystemConfig]:
    return db.query(SystemConfig).filter(SystemConfig.key == key).first()

def update_system_config(
    db: Session,
    key: str,
    value: str
) -> Optional[SystemConfig]:
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if config:
        config.value = value
        db.commit()
        db.refresh(config)
        return config
    return None

def delete_system_config(
    db: Session,
    key: str
) -> bool:
    config = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    if config:
        db.delete(config)
        db.commit()
        return True
    return False

def read_windows_size(db: Session):
    show_his_image_window = ""
    show_image_window = ""
    try:
        show_his_image_window_width = read_system_config(db, 'SHOW_HIS_IMAGE_WINDOW_WIDTH').value
        show_his_image_window_height = read_system_config(db, 'SHOW_HIS_IMAGE_WINDOW_HEIGHT').value
        show_image_window_width = read_system_config(db, 'SHOW_IMAGE_WINDOW_WIDTH').value
        show_image_window_height = read_system_config(db, 'SHOW_IMAGE_WINDOW_HEIGHT').value
        
        if show_his_image_window_width and show_his_image_window_height:
            show_his_image_window = f"{show_his_image_window_width}x{show_his_image_window_height}"
        if show_image_window_width and show_image_window_height:
            show_image_window = f"{show_image_window_width}x{show_image_window_height}"

        return show_his_image_window, show_image_window
    except Exception as e:
        traceback.print_exc()
        return show_his_image_window, show_image_window