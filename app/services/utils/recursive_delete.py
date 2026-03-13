"""
This module provides utility functions for recursively deleting SQLAlchemy objects and their associated files.
It also includes a function for hard-deleting files and directories.
"""
import os
import shutil
from datetime import datetime

from kivy.logger import Logger
from sqlalchemy.orm import class_mapper, RelationshipProperty

from db.session import get_db
from app.env import ALIGN_IMAGE_PATH, HISTOGRAM_FOLDER, DATASETS_FOLDER, HISTOGRAM_FOLDER_PATH

def _hard_delete(path, base_path):
    '''
    Recursively deletes directories (including all contents)
    from the given path upwards, stopping at the specified base path.
    '''
    try:
        path = os.path.abspath(path)
        base_path = os.path.abspath(base_path)

        #Safe exit
        if path == base_path:
            return
        if path == os.path.dirname(path):
            return
        if len(path) < len(base_path):
            return
        if os.path.commonpath([path, base_path]) != base_path:
            return

        if not os.path.exists(path):
            parent = os.path.dirname(path) # move up
            _hard_delete(parent, base_path)
        if os.path.isfile(path):
            os.remove(path)
            Logger.info("Deleted file: %s", path)
        elif os.path.isdir(path):
            shutil.rmtree(path)
            Logger.info("Deleted directory: %s", path)
        parent = os.path.dirname(path) # move up
        _hard_delete(parent, base_path)
    except Exception:
        Logger.error("Failed to delete: %s", path, exc_info=True)


def _delete(obj, now=None, visited=None, depth=0):
    """
    Recursively soft-delete SQLAlchemy objects by setting their `deleted_at` field.
    Also deletes files (e.g. image_path) if applicable.

    Args:
        obj: SQLAlchemy model instance.
        now: The timestamp to use for deletion. Defaults to current UTC time.
        depth: Current depth (used internally for recursion).
        visited: Set of visited object ids to avoid cycles.
    """
    visited = visited or set()

    if obj is None:
        return

    if obj is None or id(obj) in visited:
        return
    visited.add(id(obj))

    # Soft delete
    if hasattr(obj, 'deleted_at'):
        obj.deleted_at = now
    if hasattr(obj, 'deleted'):
        obj.deleted = 1

    # Hard delete files/folders
    if hasattr(obj, 'image_path') and getattr(obj, '__tablename__', '') == 'alignment_images':
        if obj.image_path:
            _hard_delete(obj.image_path, ALIGN_IMAGE_PATH)
    if hasattr(obj, 'histogram_path') and getattr(obj, '__tablename__', '') == 'work_configs':
        if obj.histogram_path:
            target_dir = os.path.join(HISTOGRAM_FOLDER_PATH, str(obj.id))
            _hard_delete(target_dir, HISTOGRAM_FOLDER_PATH)
    if hasattr(obj, 'image_source_path') and getattr(obj, '__tablename__', '') == 'dataset_images' and depth > 1: #only delete if the action is from higher screen (A, B)
        if obj.image_source_path:
            _hard_delete(obj.image_source_path, HISTOGRAM_FOLDER)
    if hasattr(obj, 'data_dir') and getattr(obj, '__tablename__', '') == 'generate_datas':
        if obj.data_dir:
            _hard_delete(obj.data_dir, HISTOGRAM_FOLDER)
    if hasattr(obj, 'weight_path_1') and hasattr(obj, 'weight_path_2') and getattr(obj, '__tablename__', '') == 'trained_models':
        if depth > 1:
            delete_dir = DATASETS_FOLDER #delete work_config_id folder if the action is from higher screen
        else:
            delete_dir = os.path.join(DATASETS_FOLDER, str(obj.datasets.work_config_id))
        if obj.weight_path_1:
            _hard_delete(obj.weight_path_1, delete_dir)
        if obj.weight_path_2:
            _hard_delete(obj.weight_path_2, delete_dir)

    # Recurse into relationships
    for prop in class_mapper(obj.__class__).iterate_properties:
        if isinstance(prop, RelationshipProperty):
            rel_name = prop.key
            try:
                rel_value = getattr(obj, rel_name)
            except Exception as e:
                Logger.error("Failed to access relationship %s on %s: %s", rel_name, obj, e)
                continue

            # Skip
            if rel_value is None: # no relationship value
                continue
            if not prop.uselist and prop.direction.name == 'MANYTOONE': # skip many-to-one relationships
                continue

            if isinstance(rel_value, list):
                for child in rel_value:
                    _delete(child, now, visited, depth + 1)
            else:
                _delete(rel_value, now, visited, depth + 1)

def recursive_delete(obj, obj_id, db_session=None):
    """Entry point to inspect deletion flags starting from a obj record."""
    if db_session:
        obj_list = db_session.query(obj).filter(obj.id == obj_id).all()

        if not obj_list:
            Logger.warning("No %s found for ID %s", obj, obj_id)
            return

        for obj in obj_list:
            now = datetime.now().isoformat()
            _delete(obj, now)

    else:
        with get_db() as db:
            obj_list = db.query(obj).filter(obj.id == obj_id).all()

            if not obj_list:
                Logger.warning("No %s found for ID %s", obj, obj_id)
                return

            for obj in obj_list:
                now = datetime.now().isoformat()
                _delete(obj, now)

            db.commit()
