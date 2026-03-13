from sqlalchemy.orm import Session
from db.models.datasets import Datasets
from datetime import datetime
from typing import Optional

def create_dataset(
    db: Session,
    name: str,
    work_config_id: int,
    is_trained: bool = False,
) -> Datasets:
    new_dataset = Datasets(
        name=name,
        work_config_id=work_config_id,
        is_trained=is_trained,
        created_at=datetime.now().isoformat(),
    )
    db.add(new_dataset)
    db.flush()
    return new_dataset

def read_dataset(db: Session, dataset_id: int) -> Optional[Datasets]:
    return db.query(Datasets).filter(Datasets.id == dataset_id).first()

def update_dataset(
    db: Session,
    dataset_id: int,
    name: Optional[str] = None,
    work_config_id: Optional[int] = None,
    is_trained: Optional[bool] = None
) -> Optional[Datasets]:
    dataset = db.query(Datasets).filter(Datasets.id == dataset_id).first()
    if dataset:
        if name is not None:
            dataset.name = name
        if work_config_id is not None:
            dataset.work_config_id = work_config_id
        if is_trained is not None:
            dataset.is_trained = is_trained
        dataset.updated_at = datetime.now().isoformat()
        return dataset
    return None
