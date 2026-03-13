"""
Environment and directory setup for the application.

This module loads environment variables, ensures required directories exist,
copies default data on first startup, and manages Python virtual environment relocation.
"""

import os
import sys
import shutil
import traceback
from pathlib import Path

from dotenv import load_dotenv

from app.services.system_config import (
    create_system_config,
    read_system_config,
    update_system_config,
)
from app.utils.paths import resource_path
from db.session import get_db

load_dotenv(dotenv_path=".env", override=True)

def os_getenv_abs_path(name, *args, default=''):
    '''Get the absolute path. Join args if provided. If the path does not exist, create it.'''
    env_value = os.getenv(name, default)
    path = os.path.abspath(os.path.join(env_value, *args))
    if not os.path.exists(path):
        print(f"Path '{path}' does not exist. Creating directory...")
        os.makedirs(path, exist_ok=True)
    return path

def make_dir(paths):
    '''Checks if a list of directories exists and creates them if they don't.'''
    if not isinstance(paths, list):
        raise TypeError("paths must be a list")
    for path in paths:
        if not os.path.exists(path):
            os.makedirs(path)

def copy_if_empty(folder, ext, default_file, target_name):
    """Copy a default file if folder does not contain files with given extension."""
    ext = ext.lower()
    has_file = any(f.name.lower().endswith(ext) for f in os.scandir(folder) if f.is_file())
    if not has_file:
        shutil.copy(os.path.join(DEFAULT_DATA_FOLDER, default_file), os.path.join(folder, target_name))

def is_first_time_startup():
    '''Check if this is the first time the app is starting up by checking APP_INITIALIZED in database.'''
    try:
        with get_db() as db:
            config = read_system_config(db=db, key="APP_INITIALIZED")
            return config is None or config.value == "0"
    except Exception:
        # If database is not available or any error occurs, assume first time startup
        return True

def mark_app_initialized():
    '''Mark the app as initialized in the database.'''
    try:
        with get_db() as db:
            config = read_system_config(db=db, key="APP_INITIALIZED")
            if config:
                update_system_config(db=db, key="APP_INITIALIZED", value="1")
            else:
                create_system_config(db=db, key="APP_INITIALIZED", value="1")
    except Exception as e:
        print(f"Warning: Could not mark app as initialized: {e}")

def relocate_venv(venv_path="_internal/.venv"):
    """Update pyvenv.cfg 'home' path to correct Python directory in the venv."""
    try:
        venv_path = Path(venv_path).resolve()
        cfg_file = venv_path / "pyvenv.cfg"

        if not cfg_file.exists():
            print(f"Error: {cfg_file} not found.")
            sys.exit(1)

        print(f"Updating {cfg_file} ...")

        # Find the python home directory inside venv containing version '3.9'
        # (e.g., cpython-3.9.23-windows-x86_64-none). Pick the first match alphabetically.
        candidates = [d.resolve() for d in venv_path.iterdir() if d.is_dir() and "3.9" in d.name]
        if not candidates:
            print("Error: Could not find a Python directory containing '3.9' under the venv.")
            sys.exit(1)
        candidates.sort()
        python_dir = candidates[0]
        print(f"Python directory: {python_dir}")

        # Read pyvenv.cfg
        lines = cfg_file.read_text(encoding="utf-8").splitlines()

        new_lines = []
        updated = False
        for line in lines:
            if line.strip().startswith("home"):
                new_line = f"home = {python_dir}"
                print(f"Changing: {line}  ->  {new_line}")
                new_lines.append(new_line)
                updated = True
            else:
                new_lines.append(line)

        if not updated:
            print("Warning: No 'home' line found in pyvenv.cfg.")
            sys.exit(2)

        # Backup the old file
        shutil.copy(cfg_file, cfg_file.with_suffix(".cfg.bak"))

        # Write the updated version
        cfg_file.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

        print("Update complete.")
        print("Check by activating the environment:")
        print(f"    {venv_path}\\Scripts\\activate")
    except Exception:
        traceback.print_exc()

#------------- Paths -------------
FE_FOLDER= resource_path('')
BE_FOLDER= os_getenv_abs_path('BE_FOLDER', default='../../logic/2.source')
CONFIG_FOLDER = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else FE_FOLDER
SETUP_BAT_PATH = os.path.join(FE_FOLDER, 'setup.bat')

DEFAULT_DATA_FOLDER = os.path.join(FE_FOLDER, 'default_data')
DATA_FOLDER = os.path.join(os_getenv_abs_path('DATA_FOLDER', default=FE_FOLDER), 'data')
DATASETS_FOLDER = os.path.join(os_getenv_abs_path('DATA_FOLDER', default=FE_FOLDER), 'datasets')
HISTOGRAM_FOLDER = os.path.join(os_getenv_abs_path('DATA_FOLDER', default=FE_FOLDER), 'histogram')
DETECTION_RESULTS_FOLDER = os.path.join(os_getenv_abs_path('DATA_FOLDER', default=FE_FOLDER), 'detection_results')
RAW_PATH = os_getenv_abs_path('RAW_PATH')
RAW_PATH_COORDINATE = os.getenv('RAW_PATH_COORDINATE')
INI_PATH = os.path.join(os_getenv_abs_path('CONFIG_INI_FOLDER', default=CONFIG_FOLDER), 'config.ini')
DELETE_SETTING_INI_PATH = os.path.join(CONFIG_FOLDER, 'delete_setting.ini')

# Helper function to convert string to int, return None if value is None or empty
def _getenv_int(name):
    value = os.getenv(name)
    try:
        return int(value)
    except (ValueError, TypeError):
        return value

# Helper function to convert string to float, return None if value is None or empty
def _getenv_float(name):
    value = os.getenv(name)
    try:
        return float(value)
    except (ValueError, TypeError):
        return value


TOLERANCE_PCT_COORDINATE = _getenv_float('TOLERANCE_PCT_COORDINATE')
MIN_FREQ_COORDINATE = _getenv_int('MIN_FREQ_COORDINATE')
MAX_FREQ_COORDINATE = _getenv_int('MAX_FREQ_COORDINATE')
START_TH_COORDINATE = _getenv_int('START_TH_COORDINATE')
STOP_TH_COORDINATE = _getenv_int('STOP_TH_COORDINATE')
PERCENT_ACTIVITY_COORDINATE = _getenv_float('PERCENT_ACTIVITY_COORDINATE')
FPS_COORDINATE = _getenv_int('FPS_COORDINATE')
KERNEL_COORDINATE = _getenv_int('KERNEL_COORDINATE')
DELTA_T_COORDINATE = _getenv_int('DELTA_T_COORDINATE')


INTRINSIC_PATH = os.path.join(DATA_FOLDER, 'intrinsics')
PERSPECTIVE_PATH = os.path.join(DATA_FOLDER, 'perspectives')
SPEED_PATH = os.path.join(DATA_FOLDER, 'speed')
BIAS_PATH = os.path.join(DATA_FOLDER, 'bias')
DOT_PATTERN_PATH = os.path.join(DATA_FOLDER, 'dot_templates')
ALIGN_IMAGE_PATH = os.path.join(DATA_FOLDER, "align_images")
POSE_PATH = os.path.join(DATA_FOLDER, "poses")

# Temporary folders
TEMP_FOLDER = os.path.join(DATA_FOLDER, 'tmp')
DOT_BOX_PATH = os.path.join(TEMP_FOLDER, 'dot')
DOT_BOX_PATH_PREVIEW = os.path.join(TEMP_FOLDER, 'dot_preview')
OUTPUT_INTRINSIC_PATH = os.path.join(TEMP_FOLDER, 'pattern')
HISTOGRAM_FOLDER_PATH = os.path.join(DATA_FOLDER, 'histogram')
HISTOGRAM_TEMP_PATH = os.path.join(TEMP_FOLDER, 'histogram')

HISTOGRAM_TEST_PATH = os.path.join(TEMP_FOLDER, "histogram_test")
ALIGNED_IMAGE_TEMP_PATH = os.path.join(TEMP_FOLDER, "align_images_tmp")
HEATMAP_PATH = os.path.join(TEMP_FOLDER, 'heatmap')

# Ensure all dirs exist
make_dir([
    BE_FOLDER, DATA_FOLDER, DATASETS_FOLDER,
    DETECTION_RESULTS_FOLDER, HISTOGRAM_FOLDER,
    INTRINSIC_PATH, PERSPECTIVE_PATH,
    SPEED_PATH, BIAS_PATH, DOT_PATTERN_PATH,
    ALIGN_IMAGE_PATH, TEMP_FOLDER, DOT_BOX_PATH,
    DOT_BOX_PATH_PREVIEW,
    OUTPUT_INTRINSIC_PATH, HISTOGRAM_FOLDER_PATH, HISTOGRAM_TEMP_PATH,
    HISTOGRAM_TEST_PATH, ALIGNED_IMAGE_TEMP_PATH,
    HEATMAP_PATH, POSE_PATH
    ])

# Only copy default files on first startup
if is_first_time_startup():
    copy_if_empty(DOT_PATTERN_PATH, ".png", "default_dot_template.png", "default_dot_template.png")
    copy_if_empty(BIAS_PATH, ".bias", "default.bias", "default.bias")
    copy_if_empty(INTRINSIC_PATH, ".json", "intrinsics.json", "intrinsics.json")

#------------- Environment Variables -------------
DEBUG = os.getenv('DEBUG', '0')
DOT_POINT = os.getenv('DOT_POINT', '0.5')
DETECT_AREA_SPLIT = os.getenv('DETECT_AREA_SPLIT', '0')
SHOW_IMAGE_WINDOW_WIDTH = os.getenv('SHOW_IMAGE_WINDOW_WIDTH', '1280')
SHOW_IMAGE_WINDOW_HEIGHT = os.getenv('SHOW_IMAGE_WINDOW_HEIGHT', '720')
SHOW_HIS_IMAGE_WINDOW_WIDTH = os.getenv('SHOW_HIS_IMAGE_WINDOW_WIDTH', '1280')
SHOW_HIS_IMAGE_WINDOW_HEIGHT = os.getenv('SHOW_HIS_IMAGE_WINDOW_HEIGHT', '720')
PATCH_SIZE_LIST = os.getenv('PATCH_SIZE_LIST', '448,896,1792')
INPUT_SIZE_LIST = os.getenv('INPUT_SIZE_LIST', '224,448,672')
USE_SENSOR = os.getenv('USE_SENSOR', '1')
FAST_FLOW_BACKBONE = os.getenv('FAST_FLOW_BACKBONE', 'wide_resnet50_2')
PIPE_TO_UI_NAME = os.getenv('PIPE_TO_UI_NAME', r"\\.\pipe\mypipe_to_ui")
PIPE_TO_LOGIC_NAME = os.getenv('PIPE_TO_LOGIC_NAME', r"\\.\pipe\mypipe_from_logic")
MASK_HIS_CUT_FLAG = os.getenv('MASK_HIS_CUT_FLAG', '1')

# Python runner used for spawning backend CLI and pipe server processes.
# When packaged (frozen), sys.executable points to the UI executable, which we must NOT spawn.
# Priority:
# 1) .env PYTHON_RUNNER if provided
# 2) Project-local venv at FE_FOLDER/.venv/Scripts/pythonw.exe (Windows, no console)
# 3) shutil.which('python') fallback
# 4) sys.executable (dev mode)
_env_runner = os.getenv('PYTHON_RUNNER', '').strip()
# Use pythonw.exe on Windows to avoid console window popup
_local_venv_runner = os.path.join(resource_path(''), '.venv', 'Scripts', 'pythonw.exe') if os.name == 'nt' else os.path.join(resource_path(''), '.venv', 'bin', 'python')
_which_python = shutil.which('python')

if _env_runner:
    PYTHON_RUNNER = _env_runner
elif os.path.exists(_local_venv_runner):
    PYTHON_RUNNER = _local_venv_runner
elif _which_python:
    PYTHON_RUNNER = _which_python
else:
    PYTHON_RUNNER = sys.executable

# IME
ENGLISH_IME_CODE = 0x04090409
# CONSTANTS
DOT_SCORE_DEFAULT = 0.1
