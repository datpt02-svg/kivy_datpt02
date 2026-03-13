from sqlalchemy.orm import Session
from db.models.alignment_images import AlignmentImages
from typing import Optional

def create_alignment_image(
    db: Session,
    work_config_id: int,
    image_path: str,
    alignment_coord: str,
    image_index: int
) -> AlignmentImages:
    new_image = AlignmentImages(
        work_config_id=work_config_id,
        image_path=image_path,
        alignment_coord=alignment_coord,
        image_index=image_index
    )
    db.add(new_image)
    db.commit()
    db.refresh(new_image)
    return new_image

def read_alignment_image(db: Session, image_id: int) -> Optional[AlignmentImages]:
    return db.query(AlignmentImages).filter(AlignmentImages.id == image_id).first()

def update_alignment_image(
    db: Session,
    image_id: int,
    image_path: Optional[str] = None,
    alignment_coord: Optional[str] = None,
    image_index: Optional[int] = None
) -> Optional[AlignmentImages]:
    image = db.query(AlignmentImages).filter(AlignmentImages.id == image_id).first()
    if image:
        if image_path is not None:
            image.image_path = image_path
        if alignment_coord is not None:
            image.alignment_coord = alignment_coord
        if image_index is not None:
            image.image_index = image_index
        db.commit()
        db.refresh(image)
        return image
    return None