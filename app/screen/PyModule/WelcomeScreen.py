"""Welcome screen module for Kivy-based application.

This module defines the WelcomeScreen class, which initializes default
system settings, loads localized text for the welcome interface, and
automatically removes outdated detection result images from disk.
"""

import traceback

from kivy.app import App
from kivy.properties import StringProperty
from kivy.uix.screenmanager import Screen
from kivy.logger import Logger

from db.session import get_db
from app.env import (
    DEBUG,
    DOT_POINT,
    SHOW_IMAGE_WINDOW_HEIGHT,
    SHOW_IMAGE_WINDOW_WIDTH,
    SHOW_HIS_IMAGE_WINDOW_HEIGHT,
    SHOW_HIS_IMAGE_WINDOW_WIDTH,
    PATCH_SIZE_LIST,
    INPUT_SIZE_LIST,
    DELETE_SETTING_INI_PATH,
    DETECTION_RESULTS_FOLDER
)
from app.screen.PyModule.utils.debug_status import apply_debug_setting
from app.services.system_config import read_system_config, create_system_config
from app.screen.PyModule.utils.ini_editor import IniEditor

class WelcomeScreen(Screen):
    """Screen that displays a welcome message and initializes system settings."""
    welcome_title_text = StringProperty('')
    welcome_instruction_text = StringProperty('')
    welcome_description_text = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.settings_default_value = {
            "DEBUG":                            str(DEBUG),
            "DOT_POINT":                        str(DOT_POINT),
            "DETECT_AREA_SPLIT":                "0",
            "SHOW_IMAGE_WINDOW_WIDTH":          str(SHOW_IMAGE_WINDOW_WIDTH),
            "SHOW_IMAGE_WINDOW_HEIGHT":         str(SHOW_IMAGE_WINDOW_HEIGHT),
            "SHOW_HIS_IMAGE_WINDOW_WIDTH":      str(SHOW_HIS_IMAGE_WINDOW_WIDTH),
            "SHOW_HIS_IMAGE_WINDOW_HEIGHT":     str(SHOW_HIS_IMAGE_WINDOW_HEIGHT),
            "PATCH_SIZE_LIST":                  str(PATCH_SIZE_LIST),
            "INPUT_SIZE_LIST":                  str(INPUT_SIZE_LIST),
            "BACKUP_PATH":                      "",
            "APP_INITIALIZED":                  "0",
        }
        self.ini_editor = IniEditor(ini_file_path=DELETE_SETTING_INI_PATH)

    def on_language(self, *args):
        """Update UI text when application language changes."""
        app = App.get_running_app()
        self.welcome_title_text = app.lang.get("welcome_title")
        self.welcome_instruction_text = app.lang.get("welcome_instruction")
        self.welcome_description_text = app.lang.get("welcome_description")

    def on_kv_post(self, base_widget):
        self.create_default_system_settings()
        self.update_target_dir_delete_setting_ini()
        return super().on_kv_post(base_widget)

    def create_default_system_settings(self):
        '''Create default system settings in DB.'''
        try:
            with get_db() as db:
                settings_name_list = list(self.settings_default_value.keys())
                for i in range(len(self.settings_default_value)):
                    key = settings_name_list[i]
                    config = read_system_config(db=db, key=key)
                    if not config:
                        #if config does not exist create default
                        create_system_config(db=db, key=key, value=self.settings_default_value[key])
                    if key == "DEBUG":
                        value = config.value if config else self.settings_default_value[key]
                        apply_debug_setting(value)
        except Exception:
            traceback.print_exc()

    def update_target_dir_delete_setting_ini(self):
        '''Update target_dir to the ini file.'''
        try:
            self.ini_editor.set_ini("detection_results", "target_dir", str(DETECTION_RESULTS_FOLDER))
            Logger.info("update_target_dir_delete_setting_ini: Ini settings updated.")
        except FileNotFoundError:
            Logger.error("update_target_dir_delete_setting_ini: File not found.")
        except Exception:
            Logger.error("update_target_dir_delete_setting_ini: Error while updating ini file.", exc_info=1)
