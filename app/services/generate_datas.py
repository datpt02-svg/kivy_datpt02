from sqlalchemy.orm import Session
from db.models.generate_datas import GenerateDatas
from datetime import datetime
from typing import Optional

def create_generate_data(
    db: Session,
    work_config_id: int,
    data_dir: str,
) -> GenerateDatas:
    new_data = GenerateDatas(
        work_config_id=work_config_id,
        data_dir=data_dir,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )
    db.add(new_data)
    db.commit()
    db.refresh(new_data)
    return new_data

def read_generate_data(db: Session, data_id: int) -> Optional[GenerateDatas]:
    return db.query(GenerateDatas).filter(GenerateDatas.id == data_id).first()

def update_generate_data(
    db: Session,
    data_id: int,
    work_config_id: Optional[int] = None,
    data_dir: Optional[str] = None,
) -> Optional[GenerateDatas]:
    record = db.query(GenerateDatas).filter(GenerateDatas.id == data_id).first()
    if record:
        if work_config_id is not None:
            record.work_config_id = work_config_id
        if data_dir is not None:
            record.data_dir = data_dir
        record.updated_at = datetime.now().isoformat()
        db.commit()
        db.refresh(record)
        return record
    return None
