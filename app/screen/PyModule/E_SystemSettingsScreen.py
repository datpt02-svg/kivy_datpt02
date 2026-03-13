'''Screen E1: SystemSettingScreen'''

import os
import traceback
from kivy.app import App
from kivy.logger import Logger

from db.session import get_db
from app.services.system_config import read_system_config, create_system_config, update_system_config
from app.libs.widgets.components import MyPopup, FormLabel, TextWrapper, FormScreen
from app.screen.PyModule.utils.debug_status import apply_debug_setting
from app.screen.PyModule.utils.ini_editor import IniEditor
from app.libs.constants.default_values import DefaultValuesE
from app.env import (
    DEBUG, DOT_POINT, DETECT_AREA_SPLIT,
    SHOW_IMAGE_WINDOW_HEIGHT, SHOW_IMAGE_WINDOW_WIDTH,
    SHOW_HIS_IMAGE_WINDOW_HEIGHT, SHOW_HIS_IMAGE_WINDOW_WIDTH,
    PATCH_SIZE_LIST, INPUT_SIZE_LIST,
    DETECTION_RESULTS_FOLDER, DELETE_SETTING_INI_PATH
)

class SystemSettingsScreen(FormScreen):
    '''E1 main class.'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.popup = MyPopup()
        self.app = App.get_running_app()
        self.ini_editor = IniEditor(ini_file_path=DELETE_SETTING_INI_PATH)

    def on_kv_post(self, base_widget):
        self.form_mapping = {
            "debug":                        self.ids.debug,
            "dot_point":                    self.ids.dot_point.ids.form_input,
            "detect_area_split":            self.ids.detect_area_split.ids.form_spinner,
            "show_image_window_width":      self.ids.show_image_window_width.ids.form_input,
            "show_image_window_height":     self.ids.show_image_window_height.ids.form_input,
            "show_his_image_window_width":  self.ids.show_his_image_window_width.ids.form_input,
            "show_his_image_window_height": self.ids.show_his_image_window_height.ids.form_input,
            "patch_size_list":              self.ids.patch_size_list.ids.form_input,
            "input_size_list":              self.ids.input_size_list.ids.form_input,
            "backup_path":                  self.ids.backup_path,
            "auto_cleaner_checkbox":        self.ids.auto_cleaner_checkbox,
            "auto_cleaner_days_to_keep":    self.ids.auto_cleaner_days_to_keep,
        }
        self.settings_default_value = {
            "DEBUG":                            str(DEBUG),
            "DOT_POINT":                        str(DOT_POINT),
            "DETECT_AREA_SPLIT":                str(DETECT_AREA_SPLIT),
            "SHOW_IMAGE_WINDOW_WIDTH":          str(SHOW_IMAGE_WINDOW_WIDTH),
            "SHOW_IMAGE_WINDOW_HEIGHT":         str(SHOW_IMAGE_WINDOW_HEIGHT),
            "SHOW_HIS_IMAGE_WINDOW_WIDTH":      str(SHOW_HIS_IMAGE_WINDOW_WIDTH),
            "SHOW_HIS_IMAGE_WINDOW_HEIGHT":     str(SHOW_HIS_IMAGE_WINDOW_HEIGHT),
            "PATCH_SIZE_LIST":                  str(PATCH_SIZE_LIST),
            "INPUT_SIZE_LIST":                  str(INPUT_SIZE_LIST),
            "BACKUP_PATH":                      "",
        }
        self.settings_list = [
            self.form_mapping["debug"],
            self.form_mapping["dot_point"],
            self.form_mapping["detect_area_split"],
            self.form_mapping["show_image_window_width"],
            self.form_mapping["show_image_window_height"],
            self.form_mapping["show_his_image_window_width"],
            self.form_mapping["show_his_image_window_height"],
            self.form_mapping["patch_size_list"],
            self.form_mapping["input_size_list"],
            self.form_mapping["backup_path"].path_text,
        ]
        self.val_list_settings = [
            self.form_mapping["dot_point"],
            self.form_mapping["backup_path"], #Note: does not have 'validate_text'
            self.form_mapping["show_image_window_width"],
            self.form_mapping["show_image_window_height"],
            self.form_mapping["show_his_image_window_width"],
            self.form_mapping["show_his_image_window_height"],
        ]
        self.val_list_optional = [
            self.form_mapping["auto_cleaner_days_to_keep"],
        ]
        self.val_list_str = [ #require custom validation logic
            self.form_mapping["patch_size_list"],
            self.form_mapping["input_size_list"],
        ]
        return super().on_kv_post(base_widget)

    def on_pre_enter(self, *args):
        self.ids.main_scroll_view.scroll_y = 1
        self.load_system_settings()
        self.load_delete_setting_ini()
        self.reset_val_status(self.val_list_settings)
        self.reset_val_status(self.val_list_optional)
        self.reset_val_status(self.val_list_str)

    def on_auto_cleaner_checkbox(self, *args):
        '''Event handler for auto_cleaner_checkbox.'''
        try:
            self.form_mapping["auto_cleaner_days_to_keep"].text = str(DefaultValuesE.AUTO_CLEANER_DAYS_TO_KEEP)
            self.reset_val_status([self.form_mapping["auto_cleaner_days_to_keep"]])
        except Exception:
            Logger.error("on_auto_cleaner_checkbox: Error while updating auto_cleaner_days_to_keep.", exc_info=1)

    def validate_paths(self):
        '''Custom validation for paths. Paths: backup_path.path_text.text'''
        try:
            if self.form_mapping["backup_path"].path_text.text:
                val_pairs = [
                    (self.form_mapping["backup_path"].path_text.text, self.form_mapping["backup_path"]),
                ]
                for path, widget in val_pairs:
                    if path is not None: #Only check if there are paths. Paths empty cases are already covered
                        if not os.path.exists(os.path.normpath(path)):
                            Logger.warning("Path: Not found %s", path)
                            if not widget.error_message:
                                widget.error_message = "backup_popup_failed_D2"
                    else:
                        Logger.debug("Path: path is None")
        except Exception:
            traceback.print_exc()

    def validate_list(self):
        '''Custom validation for input_size_list and patch_size_list.'''
        val_list_map = {
            self.form_mapping["input_size_list"]: (32, "input_size_validate_message_E1"), #component: (multiples_of, val_message)
            self.form_mapping["patch_size_list"]: (32, "patch_size_validate_message_E1"),
        }
        for component in self.val_list_str:
            if not component.error_message and component in val_list_map:
                n, error_msg = val_list_map[component]
                if not self._are_multiples_of_n(component.text, n=n):
                    component.error_message = error_msg

    def load_delete_setting_ini(self):
        '''Read the current settings from the ini file.'''
        try:
            ini_data = self.ini_editor.parse_ini()
            if ini_data:
                # General section
                general_settings = ini_data.get("general", {})
                enabled = general_settings.get("enabled", str(DefaultValuesE.AUTO_CLEANER_CHECKBOX_DEFAULT)).lower() == "true"
                self.form_mapping["auto_cleaner_checkbox"].active = enabled
                if enabled:
                    # Detection results section
                    detection_results_settings = ini_data.get("detection_results", {})
                    days_to_keep = detection_results_settings.get(
                        "days_to_keep",
                        str(DefaultValuesE.AUTO_CLEANER_DAYS_TO_KEEP)
                    )
                    self.form_mapping["auto_cleaner_days_to_keep"].text = days_to_keep
            else:
                Logger.warning("load_delete_setting_ini: No data found in delete_setting.ini.")
        except FileNotFoundError:
            Logger.warning("load_delete_setting_ini: delete_setting.ini not found.")
            self.form_mapping["auto_cleaner_checkbox"].active = DefaultValuesE.AUTO_CLEANER_CHECKBOX_DEFAULT
            self.form_mapping["auto_cleaner_days_to_keep"].text = str(DefaultValuesE.AUTO_CLEANER_DAYS_TO_KEEP)
        except Exception:
            Logger.error("load_delete_setting_ini: Error while reading ini file.", exc_info=1)
            self.form_mapping["auto_cleaner_checkbox"].active = DefaultValuesE.AUTO_CLEANER_CHECKBOX_DEFAULT
            self.form_mapping["auto_cleaner_days_to_keep"].text = str(DefaultValuesE.AUTO_CLEANER_DAYS_TO_KEEP)

    def update_delete_setting_ini(self):
        '''Update the current settings on the UI to the ini file.'''
        def _set_main_settings():
            self.ini_editor.set_ini("detection_results", "target_dir", str(DETECTION_RESULTS_FOLDER))
            self.ini_editor.set_ini("general", "enabled", str(self.form_mapping["auto_cleaner_checkbox"].active))
            self.ini_editor.set_ini('detection_results', 'days_to_keep', str(self.form_mapping["auto_cleaner_days_to_keep"].text))
        try:
            _set_main_settings()
            Logger.info("update_delete_setting_ini: Ini settings updated.")
        except FileNotFoundError:
            try:
                self.ini_editor.create_ini()
                self.ini_editor.set_ini("general", "enable_logging", str(True))
                self.ini_editor.set_ini("general", "log_file", str("auto_cleaner.log"))
                _set_main_settings()
                Logger.info("update_delete_setting_ini: Created and updated Ini settings.")
            except Exception as e:
                Logger.error("update_delete_setting_ini: Error while creating and updating ini file.", exc_info=1)
                raise Exception("Error while creating and updating ini file.") from e
        except Exception as e:
            Logger.error("update_delete_setting_ini: Error while updating ini file.", exc_info=1)
            raise Exception("Error while updating ini file.") from e

    def normalize_string_list(self, input_string):
        '''Strip all spaces. For example: " 224, 448,  672 " -> "224,448,672"'''
        return "".join(input_string.split())

    def _are_multiples_of_n(self, input_string, n, exclude_zero=True):
        numbers = self.normalize_string_list(input_string).split(',')
        for number in numbers:
            try:
                num = int(number.strip())
                if exclude_zero and num == 0:
                    return False
                if num % n != 0:
                    return False
            except ValueError:
                return False
        return True

    def load_system_settings(self):
        '''Load existing settings.'''
        try:
            with get_db() as db:
                for i, key in enumerate(self.settings_default_value.keys()):
                    config = read_system_config(db=db, key=key)
                    if config:
                        # load setting
                        if key == "DEBUG":
                            self.settings_list[i].selected_index = apply_debug_setting(config.value)
                        elif key == "DETECT_AREA_SPLIT":
                            self.settings_list[i].text = self.app.lang.get("no_detect_area_split") if config.value == "0" else config.value
                        else:
                            self.settings_list[i].text = config.value
                    else:
                        #if config does not exist create default
                        self.settings_list[i].text = self.settings_default_value[key]
                        create_system_config(db=db, key=key, value=self.settings_default_value[key])
        except Exception:
            traceback.print_exc()
            popup = self.popup.create_adaptive_popup(
                title="error_popup",
                message="overall_error_popup"
            )
            popup.open()

    def save_system_settings(self):
        '''Save save_system_settings to database'''
        try:
            self.reset_val_status(self.val_list_settings)
            self.reset_val_status(self.val_list_optional)
            self.reset_val_status(self.val_list_str)
            #Validate
            if self.form_mapping["auto_cleaner_checkbox"].active:
                self.validate(self.val_list_optional)
            self.validate(self.val_list_settings)
            self.validate(self.val_list_str)
            self.validate_paths()
            self.validate_list()
            if self.form_mapping["auto_cleaner_checkbox"].active:
                self.check_val_status(self.val_list_optional, error_message="save_settings_failed_popup_E1")
            self.check_val_status(self.val_list_settings, error_message="save_settings_failed_popup_E1")
            self.check_val_status(self.val_list_str, error_message="save_settings_failed_popup_E1")
            #End validate
            with get_db() as db:
                for i, key in enumerate(self.settings_default_value.keys()):
                    value = self.settings_list[i].text
                    if key == "DEBUG":
                        value = "0" if value == self.app.lang.get("debug_mode_off_E1") else "1"
                        apply_debug_setting(value) # Apply debug setting when saving
                    elif key == "DETECT_AREA_SPLIT":
                        value = "0" if value == self.app.lang.get("no_detect_area_split") else value
                    existing_config = read_system_config(db=db, key=key)
                    if existing_config:
                        #Update
                        update_system_config(db=db, key=key, value=value)
                    else:
                        #Create
                        create_system_config(db=db, key=key, value=value)
            self.update_delete_setting_ini()
            success_popup = self.popup.create_adaptive_popup(
                title="notification_popup",
                message="save_settings_success_popup_E1"
            )
            success_popup.open()
            #self.ids.main_scroll_view.scroll_y = 1
        except Exception:
            traceback.print_exc()
            popup = self.popup.create_adaptive_popup(
                title="error_popup",
                message="save_settings_failed_popup_E1"
            )
            popup.open()

class PathWrapperLabel(FormLabel):
    '''Wrapper class for path label'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.path_text = TextWrapper()
