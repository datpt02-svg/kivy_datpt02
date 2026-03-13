"""Module for building command-line argument lists for backend processes.

This module provides the `BuildCommand` class, which constructs argument lists
for different processing modes (`b1`, `b2`, `d1`) based on user form input and
database configuration. It also includes helper functions and mappings used
in command construction.
"""
import os
from datetime import datetime
from kivy.logger import Logger

from db.session import get_db
from db.models.work_configs import WorkConfigs
from db.models.sensor_settings import SensorSettings
from db.models.trained_models import TrainedModels
from db.models.system_config import SystemConfig

from app.screen.PyModule.utils.debug_status import get_debug_status
from app.services.system_config import read_windows_size
from app.env import RAW_PATH, BIAS_PATH, USE_SENSOR, HISTOGRAM_TEMP_PATH, DETECTION_RESULTS_FOLDER, FAST_FLOW_BACKBONE, MASK_HIS_CUT_FLAG, INI_PATH


_SENSOR_FILTER_MAPPING = {'STC': 1, 'Trail': 2}
_LEARN_METHOD_MAPPING = {"1 patch only": 0, "parallel": 1}


def _add_arg(cmd, key, value):
    if value not in [None, ""]:
        cmd.extend([f"--{key}", str(value)])
    else:
        Logger.warning("_add_arg: Argument '--%s' skipped, no value provided.", key)

class BuildCommand:
    """Utility class to generate backend process command arguments.

    This class retrieves configuration data from the database and form mappings,
    then constructs command argument lists for different modes:
    - `get_b1()`: Build command for mode B1 (histogram generation)
    - `get_b2()`: Build command for mode B2 (configuration-based histogram)
    - `get_d1()`: Build command for mode D1 (detection using trained model)
    """
    @staticmethod
    def get_b1(form_mapping: dict) -> list:
        """Generate command arguments for histogram building mode (B1).

        Args:
            form_mapping (dict): Mapping of form UI elements to their values.

        Returns:
            list: Command arguments for the histogram builder.

        Raises:
            FileNotFoundError: If required sensor calibration paths are missing.
            Exception: If no matching sensor configuration is found in the database.
        """
        with get_db() as db:
            debug = str(int(get_debug_status(db)))
            show_his_image_window, show_image_window = read_windows_size(db)
            #_get_screen_a_json_paths
            sensor_setting = db.query(SensorSettings).filter(SensorSettings.name == form_mapping["prophesee_setting"].text,
                                                             SensorSettings.deleted_at.is_(None)).first()
            if sensor_setting:
                intrinsics_path = sensor_setting.intrinsic_path
                perspective_path = sensor_setting.perspective_path
                speed_path = sensor_setting.speed_path
                if not intrinsics_path:
                    raise FileNotFoundError("Intrinsic path not found.")
                if not perspective_path:
                    raise FileNotFoundError("Perspective path not found.")
                if not speed_path:
                    raise FileNotFoundError("Speed path not found.")
            else: raise Exception("No matching sensor_setting in the database.")
        command = []
        _add_arg(command, "raw_path", RAW_PATH)
        _add_arg(command, "use_sensor", USE_SENSOR)
        _add_arg(command, "bias_path", os.path.join(BIAS_PATH, form_mapping["b_bias_path_select"].text))
        _add_arg(command, "delta_t", form_mapping["delta_t"].text)
        _add_arg(command, "intrinsics_path", intrinsics_path)
        _add_arg(command, "perspective_path", perspective_path)
        _add_arg(command, "speed_path", speed_path)
        _add_arg(command, "histogram_add_pixel_params", form_mapping["histogram_add_pixel_params"].text)
        _add_arg(command, "export_dir", HISTOGRAM_TEMP_PATH)
        _add_arg(command, "sensor_filter", form_mapping["sensor_filter"].selected_index)
        _add_arg(command, "on_event_his_value", form_mapping["on_event_his_value"].text)
        _add_arg(command, "off_event_his_value", form_mapping["off_event_his_value"].text)
        _add_arg(command, "seg_kernel_size", form_mapping["seg_kernel_size"].text)
        _add_arg(command, "seg_threshold", form_mapping["seg_threshold"].text)
        _add_arg(command, "seg_padding", form_mapping["seg_padding"].text)
        _add_arg(command, "show_his_image_window", show_his_image_window)
        _add_arg(command, "show_image_window", show_image_window)
        _add_arg(command, "mask_his_cut_flag", MASK_HIS_CUT_FLAG)
        _add_arg(command, "ini_path", INI_PATH)
        _add_arg(command, "debug", debug)
        #Optional
        sensor_filter_threshold = form_mapping["sensor_filter_threshold"].text
        use_roi = form_mapping["i_roi_checkbox"].active
        roi = "{x1}x{y1}-{x2}x{y2}".format(
            x1=form_mapping.get("roi.top_left_x", "0").text or "0",
            y1=form_mapping.get("roi.top_left_y", "0").text or "0",
            x2=form_mapping.get("roi.bottom_right_x", "0").text or "0",
            y2=form_mapping.get("roi.bottom_right_y", "0").text or "0",
        )
        if sensor_filter_threshold not in [None, ""]:
            _add_arg(command, "sensor_filter_threshold", sensor_filter_threshold)
        if bool(use_roi):
            _add_arg(command, "roi_setting", roi)

        return command

    @staticmethod
    def get_b2(form_mapping: dict) -> list:
        """Generate command arguments for configuration-based histogram mode (B2).

        Args:
            form_mapping (dict): Mapping of form UI elements to their values.

        Returns:
            list: Command arguments for B2 mode.

        Raises:
            Exception: If no corresponding work configuration is found in the database.
        """
        work_config_name = form_mapping["select_settings"].text
        with get_db() as db:
            debug = str(int(get_debug_status(db)))
            work_config = db.query(WorkConfigs).filter(WorkConfigs.name == work_config_name,
                                                        WorkConfigs.deleted_at.is_(None)).first()
            if work_config:
                sensor_filter = work_config.sensor_filter
                show_his_image_window, show_image_window = read_windows_size(db)
                command = []
                _add_arg(command, "raw_path", RAW_PATH)
                _add_arg(command, "use_sensor", USE_SENSOR)
                _add_arg(command, "bias_path", os.path.join(BIAS_PATH, work_config.bias_path))
                _add_arg(command, "delta_t", work_config.delta_t)
                _add_arg(command, "intrinsics_path", work_config.sensor_settings.intrinsic_path)
                _add_arg(command, "perspective_path", work_config.sensor_settings.perspective_path)
                _add_arg(command, "speed_path", work_config.sensor_settings.speed_path)
                _add_arg(command, "histogram_add_pixel_params", work_config.speed_correction_param)
                _add_arg(command, "export_dir", form_mapping["image_output_dir"])
                _add_arg(command, "sensor_filter", sensor_filter)
                _add_arg(command, "on_event_his_value", work_config.on_event_his_value)
                _add_arg(command, "off_event_his_value", work_config.off_event_his_value)
                _add_arg(command, "seg_kernel_size", work_config.seg_kernel_size)
                _add_arg(command, "seg_threshold", work_config.seg_threshold)
                _add_arg(command, "seg_padding", work_config.seg_padding)
                _add_arg(command, "show_his_image_window", show_his_image_window)
                _add_arg(command, "show_image_window", show_image_window)
                _add_arg(command, "mask_his_cut_flag", MASK_HIS_CUT_FLAG)
                _add_arg(command, "ini_path", INI_PATH)
                _add_arg(command, "debug", debug)
                #Optional
                sensor_filter_threshold = work_config.sensor_filter_threshold
                use_roi = work_config.use_roi
                label = form_mapping["id_label"].text
                if label not in [None, ""]:
                    _add_arg(command, "label", label)
                if sensor_filter_threshold not in [None, ""]:
                    _add_arg(command, "sensor_filter_threshold", sensor_filter_threshold)
                if bool(use_roi):
                    _add_arg(command, "roi_setting", work_config.roi)
            else:
                raise Exception("WorkConfig not found in the database.")

        return command

    @staticmethod
    def get_d1(form_mapping: dict) -> list:
        """Generate command arguments for model-based detection mode (D1).

        Args:
            form_mapping (dict): Mapping of form UI elements to their values.

        Returns:
            list: Command arguments for D1 detection mode.

        Raises:
            Exception: If model data or related configuration is missing.
        """
        with get_db() as db:
            try:
                model_name = form_mapping["select_models_value_to_name"][form_mapping["select_models"].text]
            except KeyError as exc:
                raise Exception("Failed to extract model name.") from exc
            debug = str(int(get_debug_status(db)))
            trained_model = db.query(TrainedModels).filter(
                TrainedModels.name == model_name,
                TrainedModels.deleted_at.is_(None)
            ).first()
            if trained_model:
                time = datetime.now().strftime("%Y%m%d")# get current time
                export_dir = os.path.join(DETECTION_RESULTS_FOLDER, str(trained_model.datasets.work_config_id), time)
                if not os.path.exists(export_dir):
                    os.makedirs(export_dir)
                show_his_image_window, show_image_window = read_windows_size(db)

                detect_area_split_data = db.query(SystemConfig).filter(SystemConfig.key == 'DETECT_AREA_SPLIT').first().value
                ratio_grid = None if detect_area_split_data in ['0', None] else detect_area_split_data
                image_master_path = None
                roi_master = None
                alignment_images_data = trained_model.datasets.work_configs.alignment_images
                first_img_obj = next((img for img in alignment_images_data if img.image_index == 0), None)
                if first_img_obj:
                    image_master_path = first_img_obj.image_path
                    roi_master = first_img_obj.alignment_coord

                command = []
                _add_arg(command, "export_dir", export_dir)
                _add_arg(command, "learn_method", trained_model.learn_method)
                _add_arg(command, "m1_input_size", trained_model.input_size_1)
                _add_arg(command, "m1_patch_size", trained_model.patch_size_1)
                _add_arg(command, "m1_weight_path", trained_model.weight_path_1)
                _add_arg(command, "m1_engine_path", trained_model.engine_path_1)
                _add_arg(command, "speed_path", trained_model.datasets.work_configs.sensor_settings.speed_path)
                _add_arg(command, "perspective_path", trained_model.datasets.work_configs.sensor_settings.perspective_path)
                _add_arg(command, "intrinsics_path", trained_model.datasets.work_configs.sensor_settings.intrinsic_path)
                _add_arg(command, "delta_t", trained_model.datasets.work_configs.delta_t)
                _add_arg(command, "sensor_filter", trained_model.datasets.work_configs.sensor_filter)
                _add_arg(command, "use_sensor", USE_SENSOR)
                _add_arg(command, "raw_path", RAW_PATH)
                _add_arg(command, "bias_path", os.path.join(BIAS_PATH, trained_model.datasets.work_configs.bias_path))
                _add_arg(command, "on_event_his_value", trained_model.datasets.work_configs.on_event_his_value)
                _add_arg(command, "off_event_his_value", trained_model.datasets.work_configs.off_event_his_value)
                _add_arg(command, "histogram_add_pixel_params", trained_model.datasets.work_configs.speed_correction_param)
                _add_arg(command, "seg_threshold", trained_model.datasets.work_configs.seg_threshold)
                _add_arg(command, "seg_padding", trained_model.datasets.work_configs.seg_padding)
                _add_arg(command, "seg_kernel_size", trained_model.datasets.work_configs.seg_kernel_size)
                _add_arg(command, "backbone", FAST_FLOW_BACKBONE)
                _add_arg(command, "combine_method", 'mean')
                _add_arg(command, "overlap", 0.25)
                _add_arg(command, "show_his_image_window", show_his_image_window)
                _add_arg(command, "show_image_window", show_image_window)
                _add_arg(command, "heat_kernel_size", form_mapping["heat_kernel_size"].text)
                _add_arg(command, "heat_min_area", form_mapping["heat_min_area"].text)
                _add_arg(command, "heat_threshold", form_mapping["heat_threshold"].text)
                _add_arg(command, "heat_min_intensity", form_mapping["heat_min_intensity"].text)
                _add_arg(command, "image_master_path", image_master_path)
                _add_arg(command, "roi_master", roi_master)
                _add_arg(command, "mask_his_cut_flag", MASK_HIS_CUT_FLAG)
                _add_arg(command, "ini_path", INI_PATH)
                _add_arg(command, "debug", debug)

                #Optional
                use_roi = trained_model.datasets.work_configs.use_roi
                sensor_filter_threshold = trained_model.datasets.work_configs.sensor_filter_threshold
                if bool(use_roi):
                    _add_arg(command, "roi_setting", trained_model.datasets.work_configs.roi)
                if sensor_filter_threshold not in [None, ""]:
                    _add_arg(command, "sensor_filter_threshold", sensor_filter_threshold)
                if trained_model.learn_method == _LEARN_METHOD_MAPPING["parallel"]:
                    _add_arg(command, "m2_input_size", trained_model.input_size_2)
                    _add_arg(command, "m2_patch_size", trained_model.patch_size_2)
                    _add_arg(command, "m2_weight_path", trained_model.weight_path_2)
                    _add_arg(command, "m2_engine_path", trained_model.engine_path_2)
                if ratio_grid:
                    _add_arg(command, "ratio_grid", ratio_grid)

            else:
                raise Exception("TrainedModel not found in the database.")

        return command
