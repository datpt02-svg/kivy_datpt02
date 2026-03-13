from sqlalchemy.orm import Session
from db.models.dataset_images import DatasetImages
from datetime import datetime
from typing import Optional

def create_dataset_image(
    db: Session,
    dataset_id: int,
    image_source_path: str,
    usage_type: str,
) -> DatasetImages:
    new_image = DatasetImages(
        dataset_id=dataset_id,
        image_source_path=image_source_path,
        usage_type=usage_type,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )
    db.add(new_image)
    db.flush()
    
    return new_image




def create_dataset_images(
    db: Session,
    images_data: list[dict]
) -> list[DatasetImages]:
    """
    Bulk insert multiple DatasetImages records.
    Each dict in images_data should have keys: dataset_id, image_source_path, usage_type.
    """
    now = datetime.now().isoformat()
    images = [
        DatasetImages(
            dataset_id=data["dataset_id"],
            image_source_path=data["image_source_path"],
            usage_type=data["usage_type"],
            created_at=now,
            updated_at=now,
        )
        for data in images_data
    ]
    db.add_all(images)
    return images


def read_dataset_image(db: Session, image_id: int) -> Optional[DatasetImages]:
    return db.query(DatasetImages).filter(DatasetImages.id == image_id).first()

def update_dataset_image(
    db: Session,
    image_id: int,
    image_source_path: Optional[str] = None,
    usage_type: Optional[str] = None,
    dataset_id: Optional[int] = None
) -> Optional[DatasetImages]:
    image = db.query(DatasetImages).filter(DatasetImages.id == image_id).first()
    if image:
        if image_source_path is not None:
            image.image_source_path = image_source_path
        if usage_type is not None:
            image.usage_type = usage_type
        if dataset_id is not None:
            image.dataset_id = dataset_id
        image.updated_at = datetime.now().isoformat()
        return image
    return None

def update_dataset_images(
    db: Session,
    updates: list[dict]
) -> int:
    """
    Bulk update DatasetImages records.
    Mỗi dict trong updates cần có key 'id' và các trường cần update.
    Trả về số bản ghi đã update.
    """
    count = 0
    for data in updates:
        image_id = data.pop("id")
        data["updated_at"] = datetime.now().isoformat()
        result = db.query(DatasetImages).filter(DatasetImages.id == image_id).update(data)
        count += result
    return count

def delete_dataset_image(
    db: Session,
    image_id: int,
    soft_delete: bool = True
) -> bool:
    """
    Xóa một ảnh trong DatasetImages.
    Nếu soft_delete=True thì chỉ cập nhật deleted_at, ngược lại sẽ xóa cứng.
    """
    image = db.query(DatasetImages).filter(DatasetImages.id == image_id).first()
    if not image:
        return False
    if soft_delete:
        image.deleted_at = datetime.now().isoformat()
    else:
        db.delete(image)
    return True

def delete_dataset_images(
    db: Session,
    image_ids: list[int],
    soft_delete: bool = True
) -> int:
    """
    Xóa nhiều ảnh trong DatasetImages.
    Nếu soft_delete=True thì chỉ cập nhật deleted_at, ngược lại sẽ xóa cứng.
    Trả về số ảnh đã xóa.
    """
    if not image_ids:
        return 0
    if soft_delete:
        result = db.query(DatasetImages).filter(DatasetImages.id.in_(image_ids)).update(
            {"deleted_at": datetime.now().isoformat()}, synchronize_session=False
        )
        return result
    else:
        images = db.query(DatasetImages).filter(DatasetImages.id.in_(image_ids)).all()
        for img in images:
            db.delete(img)
        return len(images)