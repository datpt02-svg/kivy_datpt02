from sqlalchemy.orm import Session
from db.models.trained_models import TrainedModels
from datetime import datetime
from typing import Optional

def create_trained_model(
    db: Session,
    name: str,
    dataset_id: int,
    epochs: int,
    learn_method: int,
    patch_size_1: int,
    input_size_1: int,
    weight_path_1: str,
    engine_path_1: str,
    patch_size_2: Optional[int] = None,
    input_size_2: Optional[int] = None,
    weight_path_2: Optional[str] = None,
    engine_path_2: Optional[str] = None,
    heat_min_intensity: Optional[int] = None,
    heat_threshold: Optional[int] = None,
    heat_min_area: Optional[int] = None,
    heat_kernel_size: Optional[int] = None,
    has_preset: Optional[bool] = None
) -> TrainedModels:
    new_model = TrainedModels(
        name=name,
        dataset_id=dataset_id,
        epochs=epochs,
        learn_method=learn_method,
        patch_size_1=patch_size_1,
        input_size_1=input_size_1,
        weight_path_1=weight_path_1,
        engine_path_1=engine_path_1,
        patch_size_2=patch_size_2,
        input_size_2=input_size_2,
        weight_path_2=weight_path_2,
        engine_path_2=engine_path_2,
        heat_min_intensity=heat_min_intensity,
        heat_threshold=heat_threshold,
        heat_min_area=heat_min_area,
        heat_kernel_size=heat_kernel_size,
        has_preset=has_preset,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        deleted=0
    )
    db.add(new_model)
    db.commit()
    db.refresh(new_model)
    return new_model

def read_trained_model(db: Session, model_id: int) -> Optional[TrainedModels]:
    return db.query(TrainedModels).filter(TrainedModels.id == model_id, TrainedModels.deleted == 0).first()

def update_trained_model(
    db: Session,
    model_id: int,
    name: Optional[str] = None,
    dataset_id: Optional[int] = None,
    epochs: Optional[int] = None,
    learn_method: Optional[int] = None,
    patch_size_1: Optional[int] = None,
    input_size_1: Optional[int] = None,
    weight_path_1: Optional[str] = None,
    engine_path_1: Optional[str] = None,
    patch_size_2: Optional[int] = None,
    input_size_2: Optional[int] = None,
    weight_path_2: Optional[str] = None,
    engine_path_2: Optional[str] = None,
    heat_min_intensity: Optional[int] = None,
    heat_threshold: Optional[int] = None,
    heat_min_area: Optional[int] = None,
    heat_kernel_size: Optional[int] = None,
    has_preset: Optional[bool] = None
) -> Optional[TrainedModels]:
    model = db.query(TrainedModels).filter(TrainedModels.id == model_id, TrainedModels.deleted == 0).first()
    if model:
        if name is not None:
            model.name = name
        if dataset_id is not None:
            model.dataset_id = dataset_id
        if epochs is not None:
            model.epochs = epochs
        if learn_method is not None:
            model.learn_method = learn_method
        if patch_size_1 is not None:
            model.patch_size_1 = patch_size_1
        if input_size_1 is not None:
            model.input_size_1 = input_size_1
        if weight_path_1 is not None:
            model.weight_path_1 = weight_path_1
        if engine_path_1 is not None:
            model.engine_path_1 = engine_path_1
        if patch_size_2 is not None:
            model.patch_size_2 = patch_size_2
        if input_size_2 is not None:
            model.input_size_2 = input_size_2
        if weight_path_2 is not None:
            model.weight_path_2 = weight_path_2
        if engine_path_2 is not None:
            model.engine_path_2 = engine_path_2
        if has_preset is not None:
            model.has_preset = has_preset
        #allow update to None
        model.heat_min_intensity = heat_min_intensity
        model.heat_threshold = heat_threshold
        model.heat_min_area = heat_min_area
        model.heat_kernel_size = heat_kernel_size
        model.updated_at = datetime.now().isoformat()
        db.commit()
        db.refresh(model)
        return model
    return None