from sqlalchemy.orm import Session
from db.models.app_logs import AppLogs
from datetime import datetime
from typing import Optional

def create_app_log(
    db: Session,
    level: str,
    message: str,
    logger_name: Optional[str] = None,
    exception_info: Optional[str] = None
) -> AppLogs:
    new_log = AppLogs(
        timestamp=datetime.now().isoformat(),
        level=level,
        message=message,
        logger_name=logger_name,
        exception_info=exception_info
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return new_log

def read_app_log(db: Session, log_id: int) -> Optional[AppLogs]:
    return db.query(AppLogs).filter(AppLogs.id == log_id).first()

def delete_app_log(db: Session, log_id: int) -> bool:
    log = db.query(AppLogs).filter(AppLogs.id == log_id).first()
    if log:
        db.delete(log)
        db.commit()
        return True
    return False