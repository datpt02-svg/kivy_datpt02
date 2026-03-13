from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from db.models.detection_results import DetectionResults
from datetime import datetime
from typing import Optional

_JUDGMENT_MAPPING = {
    "OK": 0,
    "NG": 1
}

def create_detection_result(
    db: Session,
    work_config_id: int,
    trained_model_id: int,
    judgment: int,
    thumbnail_path: str,
    his_img_path: str,
    heatmap_path: str,
    detected_at: Optional[str] = None
) -> DetectionResults:
    new_result = DetectionResults(
        work_config_id=work_config_id,
        trained_model_id=trained_model_id,
        judgment=judgment,
        thumbnail_path=thumbnail_path,
        his_img_path=his_img_path,
        heatmap_path=heatmap_path,
        detected_at=detected_at or datetime.now().isoformat(),
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )
    db.add(new_result)
    #db.commit() #manually commit instead
    #db.refresh(new_result)
    return new_result

def read_detection_result(db: Session, result_id: int) -> Optional[DetectionResults]:
    return db.query(DetectionResults).filter(DetectionResults.id == result_id).first()

def update_detection_result(
    db: Session,
    result_id: int,
    work_config_id: Optional[int] = None,
    trained_model_id: Optional[int] = None,
    judgment: Optional[int] = None,
    thumbnail_path: Optional[str] = None,
    his_img_path: Optional[str] = None,
    heatmap_path: Optional[str] = None,
    detected_at: Optional[str] = None
) -> Optional[DetectionResults]:
    result = db.query(DetectionResults).filter(DetectionResults.id == result_id).first()
    if result:
        if work_config_id is not None:
            result.work_config_id = work_config_id
        if trained_model_id is not None:
            result.trained_model_id = trained_model_id
        if judgment is not None:
            result.judgment = judgment
        if thumbnail_path is not None:
            result.thumbnail_path = thumbnail_path
        if his_img_path is not None:
            result.his_img_path = his_img_path
        if heatmap_path is not None:
            result.heatmap_path = heatmap_path
        if detected_at is not None:
            result.detected_at = detected_at
        result.updated_at = datetime.now().isoformat()
        db.commit()
        db.refresh(result)
        return result
    return None

def filter_detection_results(db: Session, work_config_name: str = None, date_filter: str = None, detection_result_filter: str = None) -> list:
        '''Query detection results from database with filters applied'''
        query = db.query(DetectionResults).filter(DetectionResults.deleted_at.is_(None))
        query = query.options(joinedload(DetectionResults.work_configs))
        
        if work_config_name:
            query = query.filter(DetectionResults.work_configs.has(name=work_config_name))
        if date_filter:
            query = query.where(
                func.substr(DetectionResults.detected_at, 1, 10) == date_filter.replace('/', '-') #substr trim the datetime str to get format similar to user input
            )
        if detection_result_filter:
            if detection_result_filter in _JUDGMENT_MAPPING:
                query = query.filter(DetectionResults.judgment == _JUDGMENT_MAPPING[detection_result_filter])

        detection_results = query.order_by(DetectionResults.id.desc()).all() #sort by newest desc
        return detection_results