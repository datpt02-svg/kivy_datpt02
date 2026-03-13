'''Screen B1: WorkConfigScreen'''

import traceback
import shutil
import os
import cv2
import numpy as np
from sqlalchemy import func

from kivy.clock import Clock
from kivy.app import App
from kivy.logger import Logger

from db.session import get_db
from db.models.work_configs import WorkConfigs
from db.models.sensor_settings import SensorSettings
from db.models.alignment_images import AlignmentImages

from app.services.work_configs import create_work_config, update_work_config_with_alignment_image
from app.services.utils.recursive_delete import recursive_delete
from app.screen.PyModule.utils.ini_editor import IniEditor
from app.screen.PyModule.utils.datatable_manager import DataTableManager
from app.screen.PyModule.utils.dataset_spinner import DatasetSpinner
from app.screen.PyModule.utils.scroll_action import scroll_to_first_error
from app.screen.PyModule.utils.cli_manager import CLIManager
from app.screen.PyModule.subprocess.build_command import BuildCommand
from app.libs.widgets.components import MyPopup
from app.libs.widgets.components import FormScreen

#CONST
from app.libs.constants.default_values import DefaultValuesB1
from app.env import BE_FOLDER, HISTOGRAM_FOLDER_PATH, HISTOGRAM_TEMP_PATH, ALIGN_IMAGE_PATH, ALIGNED_IMAGE_TEMP_PATH, BIAS_PATH, INI_PATH
_SCRIPT_PATH = os.path.join(BE_FOLDER, "flows", "tile", "ir_histogram.py")
_STATUS_HANDLERS = {
    "D010": "on_pipe_start",
    "D005": "on_pipe_running",
    "D012": "on_pipe_end",
    "E001": "on_pipe_error",
    "E002": "on_pipe_ini_error"
}

class WorkConfigScreen(FormScreen, CLIManager):
    '''B1 main class'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.alignment_count = 3
        self.form_mapping = None
        self.temp_histogram = None
        self.editing_item_name = None
        self.blocker = None
        self.clock_update_temp_histogram = None
        self.app = App.get_running_app()
        self.popup = MyPopup()
        self.work_configs_table = DataTableManager(
            screen=self,
            table_id="data_table_b_work_config",
            pagination_box_id="pagination_box_b_work_config",
            headers=["table_b1_header_1", "table_b1_header_2", "table_b1_header_3", "table_b1_header_4", "table_b1_header_5"],
            db_model=WorkConfigs,
            types=['str', 'image', 'float', 'str', 'button'],
            custom_message=True
        )
        self.colormap_map = {
            'JET': cv2.COLORMAP_JET,
            'AUTUMN': cv2.COLORMAP_AUTUMN,
            'BONE': cv2.COLORMAP_BONE,
            'HOT': cv2.COLORMAP_HOT,
            'RAINBOW': cv2.COLORMAP_RAINBOW,
        }
        self.ini_editor = IniEditor(ini_file_path=INI_PATH)

    def on_kv_post(self, base_widget):
        self.form_mapping = {
            # --- Basic configs ---
            "b_setting_name": self.ids.b_setting_name.ids.form_input,
            "prophesee_setting": self.ids.prophesee_setting.ids.form_spinner,
            "delta_t": self.ids.delta_t.ids.form_input,
            "i_roi_checkbox": self.ids.i_roi_checkbox,
            "i_roi_input": self.ids.i_roi_input,
            "b_bias_path_select": self.ids.b_bias_path_select.ids.form_spinner,
            "sensor_filter": self.ids.sensor_filter,
            "sensor_filter_threshold": self.ids.sensor_filter_threshold.ids.form_input,
            "seg_kernel_size": self.ids.seg_kernel_size.ids.form_slider.ids.input_box,
            "seg_threshold": self.ids.seg_threshold.ids.form_slider.ids.input_box,
            "seg_padding": self.ids.seg_padding.ids.form_slider.ids.input_box,
            "on_event_his_value": self.ids.on_event_his_value.ids.form_input,
            "off_event_his_value": self.ids.off_event_his_value.ids.form_input,
            "histogram_add_pixel_params": self.ids.histogram_add_pixel_params.ids.form_slider.ids.input_box,
            "color_map": self.ids.color_map.ids.form_spinner,

            # --- ROI coords ---
            "roi.top_left_x": self.ids.top_left_x.ids.margin_input,
            "roi.top_left_y": self.ids.top_left_y.ids.margin_input,
            "roi.bottom_right_x": self.ids.bottom_right_x.ids.margin_input,
            "roi.bottom_right_y": self.ids.bottom_right_y.ids.margin_input,

            # --- Alignment ---
            "alignment_1": self.ids.alignment_1,
            "alignment_1.error_image": self.ids.alignment_1.error_image,
            "alignment_1.error_alignment": self.ids.alignment_1.error_alignment,
            "alignment_1.top_left_x": self.ids.alignment_1.ids.image_top_left_x.ids.margin_input,
            "alignment_1.top_left_y": self.ids.alignment_1.ids.image_top_left_y.ids.margin_input,
            "alignment_1.bottom_right_x": self.ids.alignment_1.ids.image_bottom_right_x.ids.margin_input,
            "alignment_1.bottom_right_y": self.ids.alignment_1.ids.image_bottom_right_y.ids.margin_input,

            "alignment_2": self.ids.alignment_2,
            "alignment_2.error_image": self.ids.alignment_2.error_image,
            "alignment_2.error_alignment": self.ids.alignment_2.error_alignment,
            "alignment_2.top_left_x": self.ids.alignment_2.ids.image_top_left_x.ids.margin_input,
            "alignment_2.top_left_y": self.ids.alignment_2.ids.image_top_left_y.ids.margin_input,
            "alignment_2.bottom_right_x": self.ids.alignment_2.ids.image_bottom_right_x.ids.margin_input,
            "alignment_2.bottom_right_y": self.ids.alignment_2.ids.image_bottom_right_y.ids.margin_input,

            "alignment_3": self.ids.alignment_3,
            "alignment_3.error_image": self.ids.alignment_3.error_image,
            "alignment_3.error_alignment": self.ids.alignment_3.error_alignment,
            "alignment_3.top_left_x": self.ids.alignment_3.ids.image_top_left_x.ids.margin_input,
            "alignment_3.top_left_y": self.ids.alignment_3.ids.image_top_left_y.ids.margin_input,
            "alignment_3.bottom_right_x": self.ids.alignment_3.ids.image_bottom_right_x.ids.margin_input,
            "alignment_3.bottom_right_y": self.ids.alignment_3.ids.image_bottom_right_y.ids.margin_input,
        }

        self.val_list_configs = [
            self.form_mapping["b_setting_name"],
            self.form_mapping["prophesee_setting"],
            self.form_mapping["delta_t"],
            self.form_mapping["b_bias_path_select"],
            self.form_mapping["sensor_filter_threshold"],
            self.form_mapping["on_event_his_value"],
            self.form_mapping["off_event_his_value"],
            self.form_mapping["seg_kernel_size"],
            self.form_mapping["seg_threshold"],
            self.form_mapping["seg_padding"],
            self.form_mapping["histogram_add_pixel_params"],
        ]

        self.val_list_coords = [
            self.form_mapping["roi.top_left_x"],
            self.form_mapping["roi.top_left_y"],
            self.form_mapping["roi.bottom_right_x"],
            self.form_mapping["roi.bottom_right_y"],
        ]

        self.val_list_alignments = []
        for i in range(1, self.alignment_count+1):  # alignment_1 -> alignment_3
            alignment_n = f"alignment_{i}"
            alignment_widget = self.form_mapping[alignment_n]
            alignment_widget.hist_dir = HISTOGRAM_TEMP_PATH #setup paths
            alignment_widget.alignment_dir = ALIGNED_IMAGE_TEMP_PATH
            self.val_list_alignments.extend([
                alignment_widget,
                self.form_mapping[f"{alignment_n}.error_image"],
                self.form_mapping[f"{alignment_n}.error_alignment"],
                self.form_mapping[f"{alignment_n}.top_left_x"],
                self.form_mapping[f"{alignment_n}.top_left_y"],
                self.form_mapping[f"{alignment_n}.bottom_right_x"],
                self.form_mapping[f"{alignment_n}.bottom_right_y"],
            ])
        return super().on_kv_post(base_widget)

    def on_pre_enter(self, *args):
        self.loading_popup = self.popup.create_loading_popup(title="loading_popup")
        self._display_prophesee_setting_options()

        b_bias = DatasetSpinner(screen=self, spinner_id='b_bias_path_select', folder_path=BIAS_PATH, extension='.bias')
        b_bias.load_spinner_from_folder()

        self.ids.main_scroll_view.scroll_y = 1
        self.reset_form()
        self.load_data_table()

        # Setup hide_alignment_window
        is_alignment_window_visible = not self.get_hide_alignment_window_b1_ini()
        self.form_mapping['alignment_2'].is_visible = is_alignment_window_visible
        self.form_mapping['alignment_3'].is_visible = is_alignment_window_visible

        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        self.reset_form(reload_data_table=False)
        return super().on_pre_leave(*args)

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
        '''Handle pipe start event.'''
        if self.loading_popup:
            self.loading_popup.dismiss()

    def on_pipe_running(self, data: dict):
        '''Handle pipe running event.'''
        if self.loading_popup:
            self.loading_popup.dismiss()
        self.temp_histogram = data['data']
        self.async_update_temp_histogram()

    def on_pipe_end(self, data: dict):
        '''Handle pipe end event.'''
        self.loading_popup.open()

    def on_pipe_error(self, data: dict):
        '''Handle pipe error event.'''
        self.loading_popup.dismiss()
        self.__show_popup()

    def on_pipe_ini_error(self, data: dict):
        '''Handles pipeline errors.'''
        self.loading_popup.dismiss()
        self.__show_popup(title="error_popup", message="ini_error_message_E2")

    def validate_coords(self):
        '''Custom validation for coords. Binded on on_error_message in kv script.'''
        errors = [self.form_mapping["roi.top_left_x"].error_message,
                  self.form_mapping["roi.top_left_y"].error_message,
                  self.form_mapping["roi.bottom_right_x"].error_message,
                  self.form_mapping["roi.bottom_right_y"].error_message]
        if len("".join(errors)) != 0: #errors exist
            self.form_mapping["i_roi_input"].error_message = 'range_int_coordinates_message'
        else:
            self.form_mapping["i_roi_input"].error_message = ''

    def validate_paths(self):
        '''Custom validation for paths. Paths: intrinsics_path, perspective_path, speed_path and bias_path (bias_path is from spinner instead of db)'''
        try:
            with get_db() as db:
                bias_path = os.path.join(BIAS_PATH, self.form_mapping["b_bias_path_select"].text)
                sensor_settings = db.query(SensorSettings).filter(SensorSettings.name == self.form_mapping["prophesee_setting"].text, SensorSettings.deleted_at.is_(None)).first()
                if sensor_settings:
                    intrinsics_path = sensor_settings.intrinsic_path
                    perspective_path = sensor_settings.perspective_path
                    speed_path = sensor_settings.speed_path
                else:
                    intrinsics_path = perspective_path = speed_path = None

            val_pairs = [
                (bias_path, self.form_mapping["b_bias_path_select"]),
                (intrinsics_path, self.form_mapping["prophesee_setting"]),
                (perspective_path, self.form_mapping["prophesee_setting"]),
                (speed_path, self.form_mapping["prophesee_setting"]),
            ]

            for path, widget in val_pairs:
                if path is not None: #Only check if there are paths. Paths empty cases are already covered
                    if not os.path.exists(os.path.normpath(path)):
                        Logger.warning("Path: Not found %s", path)
                        if not widget.error_message:
                            widget.error_message = 'file_not_found_error_message'
                else:
                    Logger.debug("Path: path is None")
        except Exception:
            Logger.error("Error in validate_paths:", exc_info=True)

    def reset_form(self, reload_data_table=True):
        '''Resets the form to its initial state.'''
        self.editing_item_name = None
        self.form_mapping["b_setting_name"].text = str(DefaultValuesB1.B_SETTING_NAME)
        self.form_mapping["prophesee_setting"].text = str(DefaultValuesB1.PROPHESEE_SETTING)
        self.form_mapping["delta_t"].text = str(DefaultValuesB1.DELTA_T)
        self.form_mapping["b_bias_path_select"].text = str(DefaultValuesB1.B_BIAS_PATH_SELECT)

        self.form_mapping["i_roi_checkbox"].active = bool(DefaultValuesB1.I_ROI_CHECKBOX)
        self.form_mapping["roi.top_left_x"].text = str(DefaultValuesB1.ROI_TOP_LEFT_X)
        self.form_mapping["roi.top_left_y"].text = str(DefaultValuesB1.ROI_TOP_LEFT_Y)
        self.form_mapping["roi.bottom_right_x"].text = str(DefaultValuesB1.ROI_BOTTOM_RIGHT_X)
        self.form_mapping["roi.bottom_right_y"].text = str(DefaultValuesB1.ROI_BOTTOM_RIGHT_Y)

        self.form_mapping["sensor_filter"].text = str(DefaultValuesB1.SENSOR_FILTER)
        self.form_mapping["sensor_filter_threshold"].text = str(DefaultValuesB1.SENSOR_FILTER_THRESHOLD)
        self.form_mapping["seg_kernel_size"].text = str(DefaultValuesB1.SEG_KERNEL_SIZE)
        self.form_mapping["seg_threshold"].text = str(DefaultValuesB1.SEG_THRESHOLD)
        self.form_mapping["seg_padding"].text = str(DefaultValuesB1.SEG_PADDING)
        self.form_mapping["on_event_his_value"].text = str(DefaultValuesB1.ON_EVENT_HIS_VALUE)
        self.form_mapping["off_event_his_value"].text = str(DefaultValuesB1.OFF_EVENT_HIS_VALUE)
        self.form_mapping["histogram_add_pixel_params"].text = str(DefaultValuesB1.HISTOGRAM_ADD_PIXEL_PARAMS)
        self.form_mapping["color_map"].text = str(DefaultValuesB1.COLOR_MAP)
        self.ids.show_confirm_hist.source = ""

        for i in range(1, self.alignment_count+1):
            self.form_mapping[f"alignment_{i}"].reset_input()
            self.form_mapping[f"alignment_{i}"].reset_val_status() #reset val status
            self.form_mapping[f"alignment_{i}"].hist_dir = HISTOGRAM_TEMP_PATH #reset hist_dir

        #reset val status
        self.reset_val_status(self.val_list_configs)
        self.reset_val_status(self.val_list_coords)
        self.reset_val_status(self.val_list_alignments)

        #delete temp files
        shutil.rmtree(ALIGNED_IMAGE_TEMP_PATH, ignore_errors=True) #clear temp align images
        os.makedirs(ALIGNED_IMAGE_TEMP_PATH, exist_ok=True)
        shutil.rmtree(HISTOGRAM_TEMP_PATH, ignore_errors=True) #clear temp hist
        os.makedirs(HISTOGRAM_TEMP_PATH, exist_ok=True)

        self.temp_histogram = None

        if reload_data_table:
            self.load_data_table()

    def on_i_roi_check_box(self, active):
        '''Event handler for i_roi_check_box'''
        not_active = not active
        self.form_mapping["roi.top_left_x"].text = ''
        self.form_mapping["roi.top_left_y"].text = ''
        self.form_mapping["roi.bottom_right_x"].text = ''
        self.form_mapping["roi.bottom_right_y"].text = ''
        self.reset_val_status(self.val_list_coords)

        self.form_mapping["roi.top_left_x"].allow_none = not_active
        self.form_mapping["roi.top_left_y"].allow_none = not_active
        self.form_mapping["roi.bottom_right_x"].allow_none = not_active
        self.form_mapping["roi.bottom_right_y"].allow_none = not_active

    def load_data_table(
        self,
        show_button=True,
        reset_page=True,
        target_page=1
        ):
        '''Load data into the DataTable widget. '''
        data = []
        with get_db() as db:
            work_configs = db.query(WorkConfigs).filter(WorkConfigs.deleted_at.is_(None)).order_by(WorkConfigs.id.desc()).all()
            for work_config in work_configs:
                alignment_images = work_config.alignment_images
                # Find the corresponding alignment image
                alignment_image = next((img for img in alignment_images if img.work_config_id == work_config.id), None)
                # Extract data
                name = work_config.name
                speed_correction_param = work_config.speed_correction_param
                roi = work_config.roi
                image_path = alignment_image.image_path if alignment_image else "No Image"
                # Create the row
                row = {
                    "name": name,
                    "image_path": image_path,
                    "speed_correction_param": speed_correction_param,
                    "roi": roi,
                }
                if show_button:
                    row["button"] = "placeholder"
                data.append(row)
        if reset_page:
            self.work_configs_table.current_page = target_page
        self.work_configs_table.all_rows = data
        self.work_configs_table.display_current_page()
        self.work_configs_table.create_pagination_controls()

    def delete_item(self, item):
        '''on_detele_button: Delete an item from the database and reload the data table.'''
        try:
            work_config_id = self._get_id_by_name(WorkConfigs, item.get('name'))
            recursive_delete(WorkConfigs, work_config_id)
            if self.editing_item_name == item.get('name'):
                self.reset_form(reload_data_table=False)
            self.load_data_table(reset_page=False)
        except Exception:
            Logger.error("Error in delete_item:", exc_info=True)

    def get_delete_warning_message(self, item):
        '''Get warning message when deleting an item. Called by delete button'''
        return "delete_message_popup"

    def get_hide_alignment_window_b1_ini(self):
        '''Get the value of _hide_alignment_window_b1 from the config.ini file.'''
        try:
            ini_data = self.ini_editor.parse_ini()
            if ini_data:
                settings_section = ini_data.get("settings", {})
                hide_alignment_window_b1_str = settings_section.get("_hide_alignment_window_b1")
                if hide_alignment_window_b1_str is not None:
                    return hide_alignment_window_b1_str.strip() == '1'
                else:
                    return bool(DefaultValuesB1.HIDE_ALIGNMENT_WINDOW)
            else:
                Logger.warning("get_hide_alignment_window_b1_ini: No data found in config.ini.")
                return bool(DefaultValuesB1.HIDE_ALIGNMENT_WINDOW)
        except Exception:
            Logger.warning("Error in get_hide_alignment_window_b1_ini, fallback to default value...", exc_info=True)
            return bool(DefaultValuesB1.HIDE_ALIGNMENT_WINDOW)

    def load_item_to_form(self, item):
        '''on_edit_button: Load from database into kivy front-end. Called by edit button.'''
        self.reset_form(reload_data_table=False)
        try:
            self.editing_item_name = item.get('name') #name get direcly from datatable

            if self.editing_item_name:
                with get_db() as db:
                    work_config = db.query(WorkConfigs).filter(WorkConfigs.name == self.editing_item_name,
                                                               WorkConfigs.deleted_at.is_(None)).first()

                    if work_config:
                        self.form_mapping["b_setting_name"].text = str(work_config.name)
                        self.form_mapping["prophesee_setting"].text = str(work_config.sensor_settings.name)
                        self.form_mapping["delta_t"].text = str(work_config.delta_t)
                        self.form_mapping["i_roi_checkbox"].active = bool(work_config.use_roi)
                        self.form_mapping["b_bias_path_select"].text = str(work_config.bias_path)
                        self.form_mapping["sensor_filter"].selected_index = int(work_config.sensor_filter)
                        self.form_mapping["sensor_filter_threshold"].text = str(work_config.sensor_filter_threshold) if work_config.sensor_filter_threshold is not None else ""
                        self.form_mapping["seg_kernel_size"].text = str(work_config.seg_kernel_size)
                        self.form_mapping["seg_threshold"].text = str(work_config.seg_threshold)
                        self.form_mapping["seg_padding"].text = str(work_config.seg_padding)
                        self.form_mapping["on_event_his_value"].text = str(work_config.on_event_his_value)
                        self.form_mapping["off_event_his_value"].text = str(work_config.off_event_his_value)
                        self.form_mapping["histogram_add_pixel_params"].text = str(work_config.speed_correction_param)
                        self.form_mapping["color_map"].text = str(work_config.colormap)
                        # ROI parsing
                        if work_config.roi:
                            roi_str = work_config.roi
                            top_left, bottom_right = roi_str.split('-')
                            top_left_x, top_left_y = top_left.split('x')
                            bottom_right_x, bottom_right_y = bottom_right.split('x')
                            self.form_mapping["roi.top_left_x"].text = top_left_x
                            self.form_mapping["roi.top_left_y"].text = top_left_y
                            self.form_mapping["roi.bottom_right_x"].text = bottom_right_x
                            self.form_mapping["roi.bottom_right_y"].text = bottom_right_y

                        # Load alignment images and coordinates
                        alignment_images = work_config.alignment_images or []
                        for i in range(1, self.alignment_count+1):
                            alignment_n = f"alignment_{i}"
                            alignment_widget = self.form_mapping[alignment_n]
                            image = next((img for img in alignment_images if img.image_index == i - 1), None)
                            if image:
                                alignment_widget.image_source = image.image_path
                                coords = image.alignment_coord.split(",")
                                if len(coords) == 4:
                                    self.form_mapping[f"{alignment_n}.top_left_x"].text = coords[0]
                                    self.form_mapping[f"{alignment_n}.top_left_y"].text = coords[1]
                                    self.form_mapping[f"{alignment_n}.bottom_right_x"].text = coords[2]
                                    self.form_mapping[f"{alignment_n}.bottom_right_y"].text = coords[3]

                        # Load histogram image
                        if work_config.histogram_path and os.path.exists(work_config.histogram_path):
                            self.temp_histogram = work_config.histogram_path
                            self.async_update_temp_histogram()
                            # Set alignment images to use saved histogram folder
                            saved_hist_dir = os.path.dirname(work_config.histogram_path)
                            for i in range(1, self.alignment_count+1):
                                self.form_mapping[f"alignment_{i}"].hist_dir = saved_hist_dir
                    else:
                        raise Exception(f"Cannot find work config {self.editing_item_name}.")

        except Exception:
            Logger.error("Error in load_item_to_form:", exc_info=True)
            popup = self.popup.create_adaptive_popup(
                title="error_popup",
                message="overall_error_popup"
            )
            popup.open()
            self.editing_item_name = None

    def is_name_duplicate(self, name):
        '''Check if a name already exists in the database when saving'''
        with get_db() as db:
            existing_config = db.query(WorkConfigs).filter(
                func.lower(WorkConfigs.name) == name.lower(),
                WorkConfigs.deleted_at.is_(None)
            ).first()
            if existing_config:
                return True
            return False

    def save_align_images(self, work_config_id):
        '''Save aligned images to internal path. Format:"{align_image_path_unique}/alignment_{i+1}.png"'''
        # copy image from alignment_n.image_source (path) to ALIGN_IMAGE_PATH/WorkConfigs_id
        try:
            image_sources = [self.form_mapping["alignment_1"].image_source, self.form_mapping["alignment_2"].image_source, self.form_mapping["alignment_3"].image_source]
            align_image_path_unique = os.path.join(ALIGN_IMAGE_PATH, str(work_config_id)) #join with WorkConfigs_id
            if not os.path.exists(align_image_path_unique):
                os.makedirs(align_image_path_unique)
            align_image_path_list = []
            for src, dest in zip(image_sources, [f"{align_image_path_unique}/alignment_{i+1}.png" for i in range(3)]):
                if src:
                    norm_src = os.path.normpath(os.path.abspath(src))
                    norm_dest = os.path.normpath(os.path.abspath(dest))
                    if norm_src == norm_dest: #no new upload
                        align_image_path_list.append(dest) #skip shutil
                        continue
                    shutil.copyfile(norm_src, norm_dest)
                    align_image_path_list.append(norm_dest)
                else:
                    align_image_path_list.append("")
            return align_image_path_list
        except Exception:
            Logger.error("Error in save_align_images:", exc_info=True)
            return [] #this will raise exception in save_work_configs

    def _cleanup_alignment_images(self, old_paths, new_paths):
        '''Deletes alignment image files that are no longer referenced after an update.'''
        old_paths_set = set(os.path.normpath(os.path.abspath(p)) for p in old_paths if p)
        new_paths_set = set(os.path.normpath(os.path.abspath(p)) for p in new_paths if p)
        paths_to_delete = old_paths_set - new_paths_set

        for path in paths_to_delete:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
                    Logger.info(f"_cleanup_alignment_images: Deleted orphaned alignment image {path}")
            except Exception as e:
                Logger.error(f"_cleanup_alignment_images: Failed to delete orphaned image {path}: {e}", exc_info=True)

    def _reset_editing_state(self):
        '''Reset the editing state after saving or canceling an edit.'''
        target_record_name = None
        if self.editing_item_name:
            target_record_name = self.form_mapping["b_setting_name"].text.strip()

        try:
            if target_record_name:
                target_page = self.work_configs_table.find_page_for_record(
                    record_name=target_record_name,
                    name_field='name'
                )
                self.load_data_table(
                    target_page=target_page
                )
            else:
                self.load_data_table()
        except ValueError:
            self.load_data_table(reset_page=False)

    def save_histogram_image(self, work_config_id):
        '''
        Save temp histogram image to internal path.
        Return:
            - Path: Saved path.
            - None: Update to None.
            - -1: Do not update.
        '''
        target_dir = os.path.join(HISTOGRAM_FOLDER_PATH, str(work_config_id))

        # Check source
        source_file = None
        if self.temp_histogram and os.path.exists(self.temp_histogram):
            source_file = self.temp_histogram

        result_path = None
        if source_file:
            # Normalize paths for comparison
            abs_source = os.path.abspath(source_file)
            abs_hist_folder = os.path.abspath(HISTOGRAM_FOLDER_PATH)

            # Check if source is already in HISTOGRAM_FOLDER_PATH
            if os.path.commonpath([abs_source, abs_hist_folder]) == abs_hist_folder:
                # Self destruction case, exit -1
                result_path = -1
            else:
                # Delete existing target dir if exists
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                os.makedirs(target_dir, exist_ok=True)

                filename = os.path.basename(source_file)
                dest_path = os.path.join(target_dir, filename)
                shutil.copy2(source_file, dest_path)
                result_path = dest_path
        else:
            # Delete existing target dir if exists
            if os.path.exists(target_dir):
                shutil.rmtree(target_dir)

        # Clean temp is handled in reset_form
        return result_path

    def save_work_configs(self):
        '''on_save_work_configs: Save configs to database'''
        try:
            # Check alignment image visibility
            for i in range(1, self.alignment_count + 1):
                alignment_widget = self.form_mapping[f"alignment_{i}"]
                if not alignment_widget.is_visible and alignment_widget.image_source:
                    alignment_widget.reset_input() # Wipe hidden data
                    Logger.info("save_work_configs: Hidden alignment %s data detected, wiping...", i)

            #Remove old val status
            self.reset_val_status(self.val_list_configs)
            self.reset_val_status(self.val_list_coords)
            self.reset_val_status(self.val_list_alignments)
            #Validate
            self.validate(self.val_list_configs)
            self.validate(self.val_list_coords)
            self.validate(self.val_list_alignments)
            self.validate_paths()
            #Custom validate for name
            if self.is_name_duplicate(self.form_mapping["b_setting_name"].text) and self.editing_item_name != self.form_mapping["b_setting_name"].text:
                self.form_mapping["b_setting_name"].error_message = "save_work_config_duplicated_message"
                raise Exception("save_work_config_duplicated_message")

            self.check_val_status(self.val_list_configs, error_message="save_work_config_fail")
            self.check_val_status(self.val_list_coords, error_message="save_work_config_fail")
            self.check_val_status(self.val_list_alignments, error_message="save_work_config_fail")

            #End Validate
            with get_db() as db:
                common_params = {
                    "db": db,
                    "name":                     str(self.form_mapping["b_setting_name"].text),
                    "sensor_setting_id":        int(self._get_id_by_name(SensorSettings, self.form_mapping["prophesee_setting"].text)),
                    "delta_t":                  int(self.form_mapping["delta_t"].text),
                    "use_roi":                  bool(self.form_mapping["i_roi_checkbox"].active),
                    "bias_path":                str(self.form_mapping["b_bias_path_select"].text),
                    "sensor_filter":            int(self.form_mapping["sensor_filter"].selected_index),
                    "sensor_filter_threshold":  int(self.form_mapping["sensor_filter_threshold"].text) if self.form_mapping["sensor_filter_threshold"].text else None,
                    "seg_kernel_size":          int(self.form_mapping["seg_kernel_size"].text),
                    "seg_threshold":             int(self.form_mapping["seg_threshold"].text),
                    "seg_padding":              int(self.form_mapping["seg_padding"].text),
                    "on_event_his_value":       int(self.form_mapping["on_event_his_value"].text),
                    "off_event_his_value":      int(self.form_mapping["off_event_his_value"].text),
                    "speed_correction_param":   float(self.form_mapping["histogram_add_pixel_params"].text),
                    "colormap":                 str(self.form_mapping["color_map"].text),
                    "roi":                      (f"{self.form_mapping['roi.top_left_x'].text or '0'}x"
                                                f"{self.form_mapping['roi.top_left_y'].text or '0'}-"
                                                f"{self.form_mapping['roi.bottom_right_x'].text or '0'}x"
                                                f"{self.form_mapping['roi.bottom_right_y'].text or '0'}")
                }
                if self.editing_item_name: #editing mode
                    work_config_id = self._get_id_by_name(WorkConfigs, self.editing_item_name)
                    # Get old paths before update
                    old_alignment_images = db.query(AlignmentImages.image_path).filter(AlignmentImages.work_config_id == work_config_id).all()
                    old_image_paths = [img.image_path for img in old_alignment_images]

                    align_image_path_list = self.save_align_images(work_config_id)
                    update_work_config_with_alignment_image(
                        work_config_id = int(work_config_id),
                        alignment_images_data = [
                            {
                                'image_path': align_image_path_list[i],
                                'alignment_coord': f"{alignment.ids.image_top_left_x.ids.margin_input.text},{alignment.ids.image_top_left_y.ids.margin_input.text},{alignment.ids.image_bottom_right_x.ids.margin_input.text},{alignment.ids.image_bottom_right_y.ids.margin_input.text}",
                                'image_index': i
                            }
                            for i, alignment in enumerate([self.form_mapping["alignment_1"], self.form_mapping["alignment_2"], self.form_mapping["alignment_3"]])
                            if align_image_path_list[i] != "" # only include if there's an image source
                        ],
                        **common_params
                    )
                    # Cleanup orphaned files after DB update
                    self._cleanup_alignment_images(old_image_paths, align_image_path_list)

                    # Handle histogram
                    new_hist_path = self.save_histogram_image(work_config_id)
                    if new_hist_path != -1:
                        db.query(WorkConfigs).filter(WorkConfigs.id == work_config_id).update({"histogram_path": new_hist_path})
                        db.commit()
                else:
                    new_work_config = create_work_config(**common_params)
                    align_image_path_list = self.save_align_images(new_work_config.id)
                    new_work_config.alignment_images = [
                        AlignmentImages(
                            image_path=align_image_path_list[i],
                            alignment_coord=f"{alignment.ids.image_top_left_x.ids.margin_input.text},{alignment.ids.image_top_left_y.ids.margin_input.text},{alignment.ids.image_bottom_right_x.ids.margin_input.text},{alignment.ids.image_bottom_right_y.ids.margin_input.text}",
                            image_index=i,
                        )
                        for i, alignment in enumerate([self.form_mapping["alignment_1"], self.form_mapping["alignment_2"], self.form_mapping["alignment_3"]])
                        if align_image_path_list[i] != "" # only include if there's an image source
                    ]
                    db.commit()
                    # Handle histogram
                    new_hist_path = self.save_histogram_image(new_work_config.id)
                    if new_hist_path != -1:
                        new_work_config.histogram_path = new_hist_path
                        db.commit()
                        db.refresh(new_work_config)

            success_popup = self.popup.create_adaptive_popup(
                title="notification_popup",
                message="save_work_config_success"
            )
            success_popup.open()
            self.ids.main_scroll_view.scroll_y = 1 # reset scroll position to top
            self._reset_editing_state()
            self.reset_form(reload_data_table=False)

            return True

        except Exception:
            Logger.error("Error in save_work_configs:", exc_info=True)
            popup = self.popup.create_adaptive_popup(
                title="error_popup",
                message="save_work_config_fail"
            )
            popup.bind(on_dismiss=lambda *args: scroll_to_first_error(scroll_view=self.ids.main_scroll_view))
            popup.open()

    def run_confirmation(self):
        '''on_run_confirmation: Calling custom_window_histogram.py from logic code using subprocess. The subprocess runs on a different thread.'''
        #Remove old val status
        self.reset_val_status(self.val_list_configs)
        self.reset_val_status(self.val_list_coords)
        self.reset_val_status(self.val_list_alignments)
        #Validate
        try:
            self.validate(self.val_list_configs[1:]) # skip self.ids.b_setting_name.ids.form_input,
            self.validate(self.val_list_coords)
            self.validate_paths()
            self.check_val_status(self.val_list_configs[1:])
            self.check_val_status(self.val_list_coords)
        except Exception:
            Logger.error("Error in run_confirmation:", exc_info=True)
            self.__show_popup()
            self.temp_histogram = None # Reset histogram if fails
            self.async_update_temp_histogram()
            return
        #End Validate
        def run_subprocess():
            command = BuildCommand.get_b1(self.form_mapping)
            shutil.rmtree(HISTOGRAM_TEMP_PATH, ignore_errors=True)
            os.makedirs(HISTOGRAM_TEMP_PATH, exist_ok=True)
            self.temp_histogram = None

            result = self._run_cli(
                arg_list=command,
                script_path=str(_SCRIPT_PATH),
                use_module=False,
                title_window_focus=["Sensor", "Histogram"],
                cwd=BE_FOLDER,
                use_pipe_server=True
            )
            if result is not True:
                traceback.print_exc()
                raise Exception("Command failed")

        self.temp_histogram = None #reset on run
        self.async_update_temp_histogram()

        # Reset alignment images to use temp folder
        for i in range(1, self.alignment_count+1):
            self.form_mapping[f"alignment_{i}"].hist_dir = HISTOGRAM_TEMP_PATH

        self._run_task_in_thread(run_subprocess)

    def _check_thread(self, dt, thread):
        '''Check if the subprocess thread return/raise errors'''
        if thread.is_finished():
            try:
                thread.result()   # re‑raises if exception occurred
                self.loading_popup.dismiss()
            except Exception:
                Logger.error("Error in _check_thread:", exc_info=True)
                self.loading_popup.dismiss()
                self.temp_histogram = None # Reset histogram if fails
                self.async_update_temp_histogram()
            finally:
                self.enable_click()
            return False
        else:
            self.disable_click(all_widget=True)
        return True

    def __show_popup(self, title="error_popup", message="confirm_settings_fail"):
        '''Display popup in sync with multi-threading'''
        def _show(dt):
            popup = self.popup.create_adaptive_popup(
                title=title,
                message=message
            )
            popup.bind(on_dismiss=lambda *args: scroll_to_first_error(scroll_view=self.ids.main_scroll_view))
            popup.open()
        Clock.schedule_once(_show, 0)

    def apply_color_map(self, input_path):
        '''Apply color map for histogram image'''
        try:
            color_map_type = str(self.form_mapping["color_map"].text)
            colormap = self.colormap_map.get(color_map_type, cv2.COLORMAP_JET)
            image = cv2.imdecode(np.fromfile(input_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
            image_map = cv2.applyColorMap(image, colormap)
            path = os.path.join(HISTOGRAM_TEMP_PATH, "color_map.png")
            success, buf = cv2.imencode(".png", image_map)
            if success:
                buf.tofile(path)
            return path
        except Exception:
            Logger.error("Error apply_color_map:", exc_info=True)

    def update_temp_histogram(self, *args):
        '''Update the blue window containing temp histogram for config testing purpose'''
        try:
            if self.temp_histogram:
                self.ids.show_confirm_hist.source = ""
                self.ids.show_confirm_hist.source = self.apply_color_map(self.temp_histogram)
            else:
                self.ids.show_confirm_hist.source = ""
        except Exception:
            Logger.error("Error in update_temp_histogram:", exc_info=True)

    def async_update_temp_histogram(self, *args):
        '''Async wrapper for update_temp_histogram'''
        if self.clock_update_temp_histogram:
            self.clock_update_temp_histogram.cancel()
        self.clock_update_temp_histogram = Clock.schedule_once(lambda dt: self.update_temp_histogram(), 0)

    def on_sensor_filter(self):
        '''Change required status of sensor_filter_threshold based on sensor_filter option.'''
        if self.form_mapping:
            if self.form_mapping["sensor_filter"].text in ['STC', 'Trail']:
                self.form_mapping["sensor_filter_threshold"].allow_none = False
            else:
                self.form_mapping["sensor_filter_threshold"].allow_none = True

    def _display_prophesee_setting_options(self):
        '''Display list of available Prophesee setting options.'''
        with get_db() as db:
            names = db.query(SensorSettings.name).filter(SensorSettings.deleted_at.is_(None)).order_by(SensorSettings.id.desc()).all()
            self.form_mapping["prophesee_setting"].values = [name for (name,) in names] #convert to list

    def _get_id_by_name(self, table, name):
        with get_db() as db:
            query = db.query(table.id).filter(table.name == name)
            if hasattr(table, 'deleted_at'):
                query = query.filter(table.deleted_at.is_(None))
            data = query.first()
            if data:
                return data.id
            return None
