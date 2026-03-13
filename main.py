"""Main entry point for the EVS UI application.

Handles migration, environment setup, and app startup.
"""
import logging.config
import logging
import sys
import os
from pathlib import Path

def setup_license_key():
    """Configure PyArmor license key from environment or project root."""

    # 1. Check existing environment variable
    env_key = os.environ.get('PYARMOR_RKEY')
    if env_key:
        if os.path.exists(env_key):
            print(f"[License] Found valid key in environment: {env_key}")
            return True
        print(f"[License] Warning: PYARMOR_RKEY='{env_key}' not found. Fallback to search...")

    # 2. Search in project root
    # __file__ is main.py, so its parent is the root (dist or 2.source)
    root_dir = Path(__file__).resolve().parent

    # Find the first .rkey file
    key_files = list(root_dir.glob("*.rkey"))
    if key_files:
        key_folder = str(key_files[0].parent)
        os.environ['PYARMOR_RKEY'] = key_folder
        print(f"[License] Found key in folder: {key_folder}")
        return True

    print(f"[License] No .rkey file found in {root_dir}")
    return False

setup_license_key()

from app.utils.paths import resource_path
os.environ['KIVY_HOME'] = resource_path('app/libs/kivy')
from kivy.config import Config as KivyConfig
KivyConfig.set('graphics', 'width', '1080')
KivyConfig.set('graphics', 'height', '720')
KivyConfig.set('kivy', 'default_font', ['NotoSansJP',
    resource_path('app/libs/assets/fonts/NotoSansJP-Regular.ttf'),
    resource_path('app/libs/assets/fonts/NotoSansJP-Regular.ttf'),
    resource_path('app/libs/assets/fonts/NotoSansJP-Bold.ttf'),
])
KivyConfig.set('input', 'mouse', 'mouse,disable_multitouch')
KivyConfig.set('kivy', 'window_icon', 'app/libs/assets/icons/icon.png')
KivyConfig.set('kivy', 'log_level', 'info')
KivyConfig.write()

from alembic import command
from alembic.config import Config
from kivy.logger import Logger

from app.env import (
    is_first_time_startup,
    mark_app_initialized,
    relocate_venv,
)
from app.ui import MainApp
from app.utils.single_instance import ensure_single_instance
from db.engine import SQLALCHEMY_DATABASE_URL


def run_migrations():
    """Run Alembic database migrations."""
    original_file_config = None
    try:
        cfg = Config(resource_path("alembic.ini"))
        cfg.set_main_option("script_location", resource_path("db/alembic"))
        cfg.set_main_option("sqlalchemy.url", SQLALCHEMY_DATABASE_URL)

        # Temporarily disable Alembic's default logging config
        if hasattr(logging.config, "fileConfig"):
            original_file_config = logging.config.fileConfig
            logging.config.fileConfig = lambda *a, **kw: None  # type: ignore

        command.upgrade(cfg, "head")

    except Exception:
        Logger.exception("Alembic upgrade failed")

    finally:
        # Restore original fileConfig
        if original_file_config is not None:
            logging.config.fileConfig = original_file_config


def pre_run():
    """Perform pre-launch setup on first startup."""
    if is_first_time_startup():
        mark_app_initialized()
        if getattr(sys, "frozen", False):
            relocate_venv()


if __name__ == "__main__":
    # Disable PIL debug logging
    logging.getLogger('PIL').setLevel(logging.WARNING)

    if not ensure_single_instance("EVS-UI"):
        Logger.info("Another instance is already running. Exiting...")
        sys.exit(0)

    run_migrations()
    pre_run()
    MainApp().run()
