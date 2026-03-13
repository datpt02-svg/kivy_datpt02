from sqlalchemy.orm import Session
from db.models.work_configs import WorkConfigs
from db.models.alignment_images import AlignmentImages
from datetime import datetime
from typing import Optional, List

def create_work_config(
    db: Session,
    name: str,
    sensor_setting_id: int,
    delta_t: int,
    use_roi: bool,
    bias_path: str,
    sensor_filter: int,
    seg_kernel_size: int,
    seg_threshold: int,
    seg_padding: int,
    on_event_his_value: int,
    off_event_his_value: int,
    speed_correction_param: float,
    colormap: str,
    roi: Optional[str] = None,
    sensor_filter_threshold: Optional[int] = None
) -> WorkConfigs:
    new_config = WorkConfigs(
        name=name,
        sensor_setting_id=sensor_setting_id,
        delta_t=delta_t,
        use_roi=use_roi,
        roi=roi,
        bias_path=bias_path,
        sensor_filter=sensor_filter,
        sensor_filter_threshold=sensor_filter_threshold,
        seg_kernel_size=seg_kernel_size,
        seg_threshold=seg_threshold,
        seg_padding=seg_padding,
        on_event_his_value=on_event_his_value,
        off_event_his_value=off_event_his_value,
        speed_correction_param=speed_correction_param,
        colormap=colormap,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )
    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    return new_config

def create_work_config_with_alignment_image(
    db: Session,
    name: str,
    sensor_setting_id: int,
    delta_t: int,
    use_roi: bool,
    bias_path: str,
    sensor_filter: int,
    seg_kernel_size: int,
    seg_threshold: int,
    seg_padding: int,
    on_event_his_value: int,
    off_event_his_value: int,
    speed_correction_param: float,
    colormap: str,
    roi: Optional[str] = None,
    sensor_filter_threshold: Optional[int] = None,
    alignment_images_data: Optional[List[dict]] = None
) -> WorkConfigs:
    new_config = WorkConfigs(
        name=name,
        sensor_setting_id=sensor_setting_id,
        delta_t=delta_t,
        use_roi=use_roi,
        roi=roi,
        bias_path=bias_path,
        sensor_filter=sensor_filter,
        sensor_filter_threshold=sensor_filter_threshold,
        seg_kernel_size=seg_kernel_size,
        seg_threshold=seg_threshold,
        seg_padding=seg_padding,
        on_event_his_value=on_event_his_value,
        off_event_his_value=off_event_his_value,
        speed_correction_param=speed_correction_param,
        colormap=colormap,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
    )

    if alignment_images_data:
        for img_data in alignment_images_data:
            new_image = AlignmentImages(
                image_path=img_data['image_path'],
                alignment_coord=img_data['alignment_coord'],
                image_index=img_data['image_index'],
            )
            new_config.alignment_images.append(new_image)

    db.add(new_config)
    db.commit()
    db.refresh(new_config)
    return new_config

def read_work_config(db: Session, config_id: int) -> Optional[WorkConfigs]:
    return db.query(WorkConfigs).filter(WorkConfigs.id == config_id).first()

def update_work_config(
    db: Session,
    config_id: int,
    name: Optional[str] = None,
    sensor_setting_id: Optional[int] = None,
    delta_t: Optional[int] = None,
    use_roi: Optional[bool] = None,
    roi: Optional[str] = None,
    bias_path: Optional[str] = None,
    sensor_filter: Optional[int] = None,
    sensor_filter_threshold: Optional[int] = None,
    seg_kernel_size: Optional[int] = None,
    seg_threshold: Optional[int] = None,
    seg_padding: Optional[int] = None,
    on_event_his_value: Optional[int] = None,
    off_event_his_value: Optional[int] = None,
    speed_correction_param: Optional[float] = None,
    colormap: Optional[str] = None
) -> Optional[WorkConfigs]:
    config = db.query(WorkConfigs).filter(WorkConfigs.id == config_id).first()
    if config:
        if name is not None:
            config.name = name
        if sensor_setting_id is not None:
            config.sensor_setting_id = sensor_setting_id
        if delta_t is not None:
            config.delta_t = delta_t
        if use_roi is not None:
            config.use_roi = use_roi
        if roi is not None:
            config.roi = roi
        if bias_path is not None:
            config.bias_path = bias_path
        if sensor_filter is not None:
            config.sensor_filter = sensor_filter
        if sensor_filter_threshold is not None:
            config.sensor_filter_threshold = sensor_filter_threshold
        if seg_kernel_size is not None:
            config.seg_kernel_size = seg_kernel_size
        if seg_threshold is not None:
            config.seg_threshold = seg_threshold
        if seg_padding is not None:
            config.seg_padding = seg_padding
        if on_event_his_value is not None:
            config.on_event_his_value = on_event_his_value
        if off_event_his_value is not None:
            config.off_event_his_value = off_event_his_value
        if speed_correction_param is not None:
            config.speed_correction_param = speed_correction_param
        if colormap is not None:
            config.colormap = colormap

        config.updated_at = datetime.now().isoformat()
        db.commit()
        db.refresh(config)
        return config
    return None

def update_work_config_with_alignment_image(
    db: Session,
    work_config_id: int,
    name: Optional[str] = None,
    sensor_setting_id: Optional[int] = None,
    delta_t: Optional[int] = None,
    use_roi: Optional[bool] = None,
    roi: Optional[str] = None,
    bias_path: Optional[str] = None,
    sensor_filter: Optional[int] = None,
    sensor_filter_threshold: Optional[int] = None,
    seg_kernel_size: Optional[int] = None,
    seg_threshold: Optional[int] = None,
    seg_padding: Optional[int] = None,
    on_event_his_value: Optional[int] = None,
    off_event_his_value: Optional[int] = None,
    speed_correction_param: Optional[float] = None,
    colormap: Optional[str] = None,
    alignment_images_data: Optional[List[dict]] = None
) -> WorkConfigs:
    work_config = db.query(WorkConfigs).filter(WorkConfigs.id == work_config_id).first()

    if not work_config:
        raise ValueError(f"WorkConfig with id {work_config_id} not found")

    if name is not None:
        work_config.name = name
    if sensor_setting_id is not None:
        work_config.sensor_setting_id = sensor_setting_id
    if delta_t is not None:
        work_config.delta_t = delta_t
    if use_roi is not None:
        work_config.use_roi = use_roi
    if roi is not None:
        work_config.roi = roi
    if bias_path is not None:
        work_config.bias_path = bias_path
    if sensor_filter is not None:
        work_config.sensor_filter = sensor_filter
    work_config.sensor_filter_threshold = sensor_filter_threshold #allow none
    if seg_kernel_size is not None:
        work_config.seg_kernel_size = seg_kernel_size
    if seg_threshold is not None:
        work_config.seg_threshold = seg_threshold
    if seg_padding is not None:
        work_config.seg_padding = seg_padding
    if on_event_his_value is not None:
        work_config.on_event_his_value = on_event_his_value
    if off_event_his_value is not None:
        work_config.off_event_his_value = off_event_his_value
    if speed_correction_param is not None:
        work_config.speed_correction_param = speed_correction_param
    if colormap is not None:
        work_config.colormap = colormap

    work_config.updated_at = datetime.now().isoformat()

    if alignment_images_data is not None:
        # Clear existing alignment images
        for image in work_config.alignment_images[:]:
            db.delete(image)
        work_config.alignment_images = [] # clear the list, and remove them

        # Add new alignment images
        for img_data in alignment_images_data:
            new_image = AlignmentImages(
                image_path=img_data['image_path'],
                alignment_coord=img_data['alignment_coord'],
                image_index=img_data['image_index'],
            )
            work_config.alignment_images.append(new_image)

    db.commit()
    db.refresh(work_config)
    return work_config