'''Screen D1: AIDetectionExecutionScreen'''

import os
import traceback

from kivy.clock import Clock
from kivy.logger import Logger

from db.session import get_db
from db.models.trained_models import TrainedModels
from app.services.detection_results import create_detection_result
from app.libs.widgets.components import FormScreen, MyPopup
from app.screen.PyModule.utils.cli_manager import CLIManager
from app.screen.PyModule.utils.scroll_action import scroll_to_first_error, scroll_to_widget
from app.screen.PyModule.subprocess.build_command import BuildCommand

#CONST
from app.libs.constants.colors import COLORS
from app.libs.constants.default_values import DefaultValuesD1
from app.env import BE_FOLDER, BIAS_PATH, DETECTION_RESULTS_FOLDER
_SCRIPT_PATH = os.path.join(BE_FOLDER, "flows", "tile", "ir_detection.py")
_STATUS_HANDLERS = {
    "D019": "on_pipe_start",
    "D020": "on_pipe_running",
    "D021": "on_pipe_end",
    "E001": "on_pipe_error",
    "E002": "on_pipe_ini_error"
}

class AIDetectionExecutionScreen(FormScreen, CLIManager):
    '''D1 main class.'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.popup = MyPopup()

    def on_kv_post(self, base_widget):
        '''Event handler for post-Kivy setup.'''
        self.form_mapping = {
            "select_models":                self.ids.select_models.ids.form_spinner,
            "select_models_value_to_name":  self.ids.select_models.value_to_name,
            "heat_kernel_size":             self.ids.heat_kernel_size.ids.form_input,
            "heat_min_area":                self.ids.heat_min_area.ids.form_input,
            "heat_threshold":               self.ids.heat_threshold.ids.form_slider.ids.input_box,
            "heat_min_intensity":           self.ids.heat_min_intensity.ids.form_input,
            "learn_method":                 self.ids.learn_method,
            "input_size":                   self.ids.input_size,
            "patch_size":                   self.ids.patch_size,
            "sensor_setting_name":          self.ids.sensor_setting_name,
            "work_config_name":             self.ids.work_config_name,
            "display_log":                  self.ids.display_log
        }
        self.val_on_reload_preset = [
            self.form_mapping['select_models']
        ]
        self.val_list = [
            self.form_mapping['select_models'],
            self.form_mapping['heat_kernel_size'],
            self.form_mapping['heat_min_area'],
            self.form_mapping['heat_threshold'],
            self.form_mapping['heat_min_intensity']
        ]
        self.ids.open_folder_button.path = rf"{DETECTION_RESULTS_FOLDER}"
        self.dropdown_work_config_id = None #change in on_selected_model()
        return super().on_kv_post(base_widget)

    def on_pre_enter(self, *args):
        '''Event handler for when the screen is entered.'''
        self.ids.main_scroll_view.scroll_y = 1
        self.loading_popup = self.popup.create_loading_popup(title="loading_popup")
        self.reset_form()
        self._display_model_selection_options()
        return super().on_pre_enter(*args)

    def on_selected_model(self):
        '''Call after a model is selected in the dropdown.'''
        try:
            if self.form_mapping["select_models"].text:
                selected_model_name = self.extract_model_name(self.form_mapping["select_models"].text)
                with get_db() as db:
                    data = db.query(TrainedModels).filter(TrainedModels.name == selected_model_name, TrainedModels.deleted_at.is_(None)).first()
                    self.dropdown_work_config_id = data.datasets.work_config_id
                    self.form_mapping["learn_method"].db_data = str(data.learn_method) #change learn_method text
                    if int(data.learn_method)==0: #"1 patch only"
                        self.form_mapping["patch_size"].text = str(data.patch_size_1)
                        self.form_mapping["input_size"].text = str(data.input_size_1)
                    else: #"parallel"
                        self.form_mapping["patch_size"].text = str(data.patch_size_1) + " / " + str(data.patch_size_2)
                        self.form_mapping["input_size"].text = str(data.input_size_1) + " / " + str(data.input_size_2)
                    self.form_mapping["sensor_setting_name"].text = str(data.datasets.work_configs.sensor_settings.name)
                    self.form_mapping["work_config_name"].text = str(data.datasets.work_configs.name)

                self.update_open_folder_path()
                self.form_mapping["display_log"].clear_logs_key(default_key="detection_status_placeholder_D1") #clear old logs
        except Exception:
            return

    def on_start_detection(self):
        '''Call when "Bắt đầu phát hiện" button is pressed'''
        #Validate
        try:
            self.reset_val_status(self.val_list)
            self.validate(self.val_list)
            self.validate_paths()
            self.check_val_status(self.val_list)
        except Exception:
            self.form_mapping["display_log"].clear_logs_key(default_key="detection_status_placeholder_D1")
            popup = self.popup.create_adaptive_popup(
                title="error_popup",
                message="detection_failed"
            )
            popup.bind(on_dismiss=lambda *args: scroll_to_first_error(scroll_view=self.ids.main_scroll_view))
            popup.open()
            return
        #End validate
        self.form_mapping["display_log"].clear_logs_key()
        self.form_mapping["display_log"].add_log_line_key(text_key='processing_detection', color=COLORS['BLUE'])
        self.run_detect_errors()

    def on_pipe(self, data: dict):
        '''Handles incoming data from the pipeline.'''
        if not isinstance(data, dict):
            Logger.error("Expected dict, got %s", type(data).__name__)
            return
        else:
            status = data.get('status_code')
            if not status:
                raise KeyError("Missing required key: 'status_code'")
        pipeline_status = data.get("status_code")
        handler = _STATUS_HANDLERS.get(pipeline_status)
        if handler:
            getattr(self, handler)(data)
        else:
            Logger.error("No handler defined for status %s", pipeline_status)
            return

    def on_pipe_start(self, data: dict):
        '''Handles the start of the pipeline.'''
        if self.loading_popup:
            self.loading_popup.dismiss()
            try:
                scroll_to_widget(scroll_view=self.ids.main_scroll_view, widget=self.form_mapping["display_log"], padding=-self.form_mapping["display_log"].height)
            except Exception:
                Logger.error("ScrollError: Failed to scroll to widget")

    def on_pipe_running(self, data: dict):
        '''Handles the pipeline running state.'''
        if self.loading_popup:
            self.loading_popup.dismiss()
        info = data['data']
        histogram_path = info['histogram_path']
        heatmap_path = info['detect_histogram_path']
        thumbnail_path = self.get_thumbnail_path(heatmap_path)
        detect_time = info['detect_time']
        self.form_mapping["display_log"].add_log_line(text="")
        self.form_mapping["display_log"].add_log_line(text=f"type_detect: {info['type_detect']}")
        self.form_mapping["display_log"].add_log_line(text=f"histogram_path: {info['histogram_path']}")
        self.form_mapping["display_log"].add_log_line(text=f"detect_histogram_path: {info['detect_histogram_path']}")
        self.form_mapping["display_log"].add_log_line(text=f"detect_time: {info['detect_time']}")
        self.write_detection_result_to_db(his_img_path=histogram_path, heatmap_img_path=heatmap_path, thumb_img_path=thumbnail_path, detected_at=detect_time)

    def on_pipe_end(self, data: dict):
        '''Handles the end of the pipeline.'''
        self.loading_popup.open()
        self.form_mapping["display_log"].add_log_line(text="")

    def on_pipe_error(self, data: dict):
        '''Handles pipeline errors.'''
        self.form_mapping["display_log"].add_log_line(text="")
        self.loading_popup.dismiss()
        self.__show_popup()

    def on_pipe_ini_error(self, data: dict):
        '''Handles pipeline errors.'''
        self.form_mapping["display_log"].add_log_line(text="")
        self.loading_popup.dismiss()
        self.__show_popup(title="error_popup", message="ini_error_message_E2")

    def on_reload_preset(self):
        try:
            #Validate
            try:
                self.reset_val_status(self.val_list)
                self.validate(self.val_on_reload_preset)
                self.check_val_status(self.val_on_reload_preset)
            except Exception:
                return
            #End Validate
            if self.form_mapping["select_models"].text:
                with get_db() as db:
                    trained_model = db.query(TrainedModels).filter(
                        TrainedModels.name == self.extract_model_name(self.form_mapping["select_models"].text),
                        TrainedModels.deleted_at.is_(None)
                    ).first()
                    if not trained_model:
                        Logger.warning("on_reload_preset: Model not found in database")
                        return
                    # Extract
                    if not trained_model.has_preset:
                        Logger.warning("on_reload_preset: No preset found (trained_model.has_preset is 0)")
                        self.popup.create_adaptive_popup(
                            title="notification_popup",
                            message="no_preset_popup_D1"
                        ).open()
                        return
                    # Update
                    self.form_mapping["heat_kernel_size"].text = self._convert_str(trained_model.heat_kernel_size)
                    self.form_mapping["heat_threshold"].text = self._convert_str(trained_model.heat_threshold)
                    self.form_mapping["heat_min_area"].text = self._convert_str(trained_model.heat_min_area)
                    self.form_mapping["heat_min_intensity"].text = self._convert_str(trained_model.heat_min_intensity)
            else:
                Logger.warning("on_reload_preset: No model selected")
        except Exception:
            Logger.warning("on_reload_preset: Failed to load preset.", exc_info=1)
            return

    def _convert_str(self, value):
        '''Safely convert value to string.'''
        return "" if value is None else str(value)

    def update_open_folder_path(self):
        '''Update the open folder button path from  DETECTION_RESULTS_FOLDER -> DETECTION_RESULTS_FOLDER/id.'''
        if self.dropdown_work_config_id:
            self.ids.open_folder_button.path = os.path.join(DETECTION_RESULTS_FOLDER, str(self.dropdown_work_config_id))
        else:
            self.ids.open_folder_button.path = rf"{DETECTION_RESULTS_FOLDER}" #default

    def validate_paths(self):
        '''Custom validation for paths. Paths: intrinsics_path, perspective_path, speed_path, bias_path, weight_path_1, weight_path_2'''
        try:
            with get_db() as db:
                trained_model = db.query(TrainedModels).filter(
                    TrainedModels.name == self.extract_model_name(self.form_mapping["select_models"].text),
                    TrainedModels.deleted_at.is_(None)
                ).first()
                if trained_model:
                    intrinsics_path = trained_model.datasets.work_configs.sensor_settings.intrinsic_path
                    perspective_path = trained_model.datasets.work_configs.sensor_settings.perspective_path
                    speed_path = trained_model.datasets.work_configs.sensor_settings.speed_path
                    bias_path = os.path.join(BIAS_PATH, trained_model.datasets.work_configs.bias_path)
                    weight_path_1 = trained_model.weight_path_1
                    learn_method = trained_model.learn_method #condition to check optional val
                    weight_path_2 = trained_model.weight_path_2 #optional
                else:
                    intrinsics_path = perspective_path = speed_path = bias_path = weight_path_1 = weight_path_2 = learn_method = None
            val_pairs = [
                (intrinsics_path, self.form_mapping["select_models"]),
                (perspective_path, self.form_mapping["select_models"]),
                (speed_path, self.form_mapping["select_models"]),
                (bias_path, self.form_mapping["select_models"]),
                (weight_path_1, self.form_mapping["select_models"]),
            ]
            val_pairs_optional = [
                (weight_path_2, self.form_mapping["select_models"])
            ]
            if learn_method == 1:
                val_pairs.extend(val_pairs_optional)

            for path, widget in val_pairs:
                if path is not None: #Only check if there are paths. Paths empty cases are already covered
                    if not os.path.exists(os.path.normpath(path)):
                        Logger.warning("Path: Not found %s", path)
                        if not widget.error_message:
                            widget.error_message = 'file_not_found_error_message'
                else:
                    Logger.debug("Path: path is None")
        except Exception:
            Logger.error("Failed to validate paths")

    def _display_model_selection_options(self):
        self.form_mapping["select_models_value_to_name"] = {}
        self.form_mapping["select_models"].values = []
        values = [] #placeholder
        with get_db() as db:
            datas = db.query(TrainedModels).filter(TrainedModels.deleted_at.is_(None)).order_by(TrainedModels.id.desc()).all()
            for data in datas:
                display_value = f"{data.name} ({data.datasets.name})"
                values.append(display_value)
                self.form_mapping["select_models_value_to_name"][display_value] = data.name #NOTE: will overwrite if duplicate
            self.form_mapping["select_models"].values = values

    def extract_model_name(self, option):
        '''Extract model name from "{data.name} ({data.datasets.name})" format.'''
        try:
            return self.form_mapping["select_models_value_to_name"][option]
        except KeyError:
            Logger.error("Failed to extract model name for %s", option)
            return

    def reset_form(self):
        '''Resets the form to its initial state.'''
        self.ids.open_folder_button.path = rf"{DETECTION_RESULTS_FOLDER}"
        self.dropdown_work_config_id = None
        self.form_mapping["heat_kernel_size"].text = str(DefaultValuesD1.HEAT_KERNEL_SIZE)
        self.form_mapping["heat_threshold"].text = str(DefaultValuesD1.HEAT_THRESHOLD)
        self.form_mapping["heat_min_area"].text = str(DefaultValuesD1.HEAT_MIN_AREA)
        self.form_mapping["heat_min_intensity"].text = str(DefaultValuesD1.HEAT_MIN_INTENSITY)
        self.form_mapping["select_models"].text = ''
        self.form_mapping["learn_method"].db_data = '-'
        self.form_mapping["patch_size"].text = '-'
        self.form_mapping["input_size"].text = '-'
        self.form_mapping["sensor_setting_name"].text = '-'
        self.form_mapping["work_config_name"].text = '-'
        self.form_mapping["display_log"].clear_logs_key(default_key="detection_status_placeholder_D1")
        self.reset_val_status(self.val_list)

    def run_detect_errors(self):
        '''Call optimizer_auto_detect_errors.py from logic code using subprocess. The subprocess runs on a different thread. Wrapped by on_start_detection()'''
        def run_subprocess():
            command = BuildCommand.get_d1(self.form_mapping)
            result = self._run_cli(
                script_path=str(_SCRIPT_PATH),
                use_module=False,
                arg_list=command,
                title_window_focus=["Detect", "Sensor", "Histogram"],
                cwd=BE_FOLDER,
                use_pipe_server=True
            )

            if result is not True:
                traceback.print_exc()
                raise Exception("Command failed")

        self._run_task_in_thread(run_subprocess)

    def extract_status(self, filepath):
        '''Status mapping. OK -> 0, NG -> 1'''
        # Look for NG/OK in the path parts (should use rel paths to avoid user folders naming)
        parts = os.path.normpath(filepath).split(os.sep)
        if "NG" in parts:
            return 1
        elif "OK" in parts:
            return 0
        else:
            raise Exception("Fail to extract status 'NG' or 'OK'")

    def get_thumbnail_path(self, path: str) -> str:
        '''Replace the last occurrence of the 'heatmap' folder in the given path with 'thumbnail', keeping the rest unchanged.'''
        norm_path = os.path.normpath(path)
        parts = norm_path.split(os.sep)

        for i in range(len(parts) - 1, -1, -1):
            if parts[i] == "heatmap":
                parts[i] = "thumbnail"
                break  # stop after last one

        return os.sep.join(parts)

    def rollback_images(self, his_img_path=None, thumb_img_path=None, heatmap_img_path=None):
        '''Delete generated images (his_img_path, thumb_img_path, heatmap_img_path) if an error occurs.'''
        for path in [his_img_path, thumb_img_path, heatmap_img_path]:
            if path and os.path.exists(path):
                try:
                    os.remove(path)
                    Logger.info("Rollback: %s", path)
                except Exception as remove_err:
                    Logger.error("Failed to delete image %s: %s", path, remove_err)

    def write_detection_result_to_db(self, his_img_path, thumb_img_path, heatmap_img_path, detected_at):
        '''Write new detection results into the database.'''
        def write(*args):
            with get_db() as db:
                # Get the selected model
                trained_model = db.query(TrainedModels).filter(
                    TrainedModels.name == self.extract_model_name(self.form_mapping["select_models"].text),
                    TrainedModels.deleted_at.is_(None)
                ).first()
                if not trained_model:
                    Logger.error("Write Data Error: Trained model not found.")
                    self.rollback_images(his_img_path, thumb_img_path, heatmap_img_path)
                    return
                if not his_img_path or not thumb_img_path or not heatmap_img_path:
                    Logger.error("Write Data Error: Missing paths")
                    self.rollback_images(his_img_path, thumb_img_path, heatmap_img_path)
                    return
                try:
                    rel_his_img_path = os.path.relpath(his_img_path, DETECTION_RESULTS_FOLDER) #get relative path
                    rel_thumb_img_path = os.path.relpath(thumb_img_path, DETECTION_RESULTS_FOLDER)
                    rel_heatmap_img_path = os.path.relpath(heatmap_img_path, DETECTION_RESULTS_FOLDER)
                    create_detection_result(
                        db=db,
                        work_config_id=trained_model.datasets.work_config_id,
                        trained_model_id=trained_model.id,
                        judgment=self.extract_status(rel_his_img_path),
                        his_img_path=rel_his_img_path,
                        thumbnail_path=rel_thumb_img_path,
                        heatmap_path=rel_heatmap_img_path,
                        detected_at=detected_at,
                    )
                except Exception:
                    db.rollback() #db rollback
                    Logger.error("Write Data Error: Failed to create detection result for %s", rel_his_img_path)
                    # Check and delete images if they exist
                    self.rollback_images(his_img_path, thumb_img_path, heatmap_img_path)

                db.commit()
                Logger.info("Inserted new detection results into the database.")
        Clock.schedule_once(write, 0)

    def _check_thread(self, dt, thread):
        '''Check if the subprocess thread return/raise errors'''
        if thread.is_finished():
            try:
                thread.result()    # re‑raises if exception occurred
                self.loading_popup.dismiss()
                self.update_open_folder_path()
                self.form_mapping["display_log"].add_log_line_key(text_key='detection_completed', color=COLORS['LIGHT_GREEN'])
            except Exception as e:
                Logger.error(str(e))
                self.loading_popup.dismiss()
                #self.__show_popup()
                self.form_mapping["display_log"].add_log_line_key(text_key='detection_failed', color=COLORS['LIGHT_RED'])
            finally:
                self.enable_click()
            return False
        else:
            self.disable_click(all_widget=True, allow_widget=[self.ids.open_folder_button])
        return True

    def __show_popup(self, title="error_popup", message="detection_failed"):
        '''Display popup in sync with multi-threading'''
        def _show(dt):
            popup = self.popup.create_adaptive_popup(
                title=title,
                message=message
            )
            popup.bind(on_dismiss=lambda *args: scroll_to_first_error(scroll_view=self.ids.main_scroll_view))
            popup.open()
        Clock.schedule_once(_show, 0)
