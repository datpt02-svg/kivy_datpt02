"""
This module provides a utility function to delete `.png` image files
from one or more specified folders. It is typically used for cleaning
up temporary or generated image data in the application workflow.
"""

import os
import traceback
from glob import glob

def delete_images_in_folders(folder_paths=None, delete_npy=False):
    """
    Delete all `.png` image files in the given list of folders.

    Args:
        folder_paths (list[str] | None): A list of folder paths to clean.
            If None, the function will return without performing any action.
    """
    if folder_paths is None:
        return

    for folder in folder_paths:
        if os.path.exists(folder):
            image_files = glob(os.path.join(folder, "*.png"))
            npy_files = glob(os.path.join(folder, '*.npy'))

            if delete_npy:
                for npy_file in npy_files:
                    try:
                        os.remove(npy_file)
                    except Exception:
                        traceback.print_exc()

            for img_file in image_files:
                try:
                    os.remove(img_file)
                except Exception:
                    traceback.print_exc()
