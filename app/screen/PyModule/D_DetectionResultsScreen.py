'''Screen D2: DetectionResultsScreen'''

import os
import shutil
import traceback
from datetime import datetime, timedelta

from db.models.detection_results import DetectionResults
from db.models.work_configs import WorkConfigs
from db.session import get_db

from app.screen.PyModule.utils.datatable_manager import DataTableManager
from app.libs.widgets.components import MyPopup, FormScreen
from app.services.detection_results import filter_detection_results
from app.services.system_config import read_system_config

#CONST
from app.libs.constants.colors import COLORS
from app.env import DETECTION_RESULTS_FOLDER
JUDGMENT_MAPPING = {
    0: lambda: f"[color={COLORS.get('GREEN', color_format='hex')}]OK[/color]",
    1: lambda: f"[color={COLORS.get('DARK_RED', color_format='hex')}]NG[/color]",
}

class DetectionResultsScreen(FormScreen):
    '''D2 main class.'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.popup = MyPopup()
        self.editing_item_name = None
        self.detection_results_table = DataTableManager(
            screen=self,
            table_id="data_table_d_detection_list",
            pagination_box_id="pagination_box_d_detection_list",
            headers=["id_column_D2", "detection_datetime_column_D2", "work_config_name_column_D2", "id_work_config_column_D2", "thumbnail_column_D2", "judgment_result_column_D2", "action_column"],
            db_model=DetectionResults,
            types=['str', 'str', 'str', 'str', 'image', 'str', 'button_backup'],
            markup_columns=[5]
        )

    def on_language(self, *args):
        '''Event handler for language change.'''
        self.on_pre_enter() #reset if language is changed

    def on_kv_post(self, base_widget):
        '''Event handler for post-Kivy setup.'''
        self.form_mapping = {
            "open_folder_button":       self.ids.open_folder_button,
            "select_settings":          self.ids.select_settings,
            "detection_result_filter":  self.ids.detection_result_filter,
            "date_filter":              self.ids.date_filter,
        }
        self.form_mapping["open_folder_button"].path = rf"{DETECTION_RESULTS_FOLDER}"
        self.dropdown_work_config_id = None #change in on_work_config_selected()
        return super().on_kv_post(base_widget)

    def update_open_folder_path(self):
        '''Change open folder button path from DETECTION_RESULTS_FOLDER -> DETECTION_RESULTS_FOLDER/id.'''
        if self.dropdown_work_config_id:
            self.form_mapping["open_folder_button"].path = os.path.join(DETECTION_RESULTS_FOLDER, str(self.dropdown_work_config_id))
        else: #default
            self.form_mapping["open_folder_button"].path = rf"{DETECTION_RESULTS_FOLDER}"

    def on_work_config_selected(self):
        '''Call after a work config is selected in the dropdown.'''
        self.dropdown_work_config_id = self._get_id_by_name(WorkConfigs, self.form_mapping["select_settings"].text) #None if not exist in case user selected "All"
        self.update_open_folder_path()

    def reset_form(self):
        '''Reset the form to its initial state.'''
        self.dropdown_work_config_id = None
        self.form_mapping["open_folder_button"].path = rf"{DETECTION_RESULTS_FOLDER}"
        self.form_mapping["select_settings"].text = self.form_mapping["select_settings"].values[0]
        self.form_mapping["detection_result_filter"].text = self.form_mapping["detection_result_filter"].label[0]
        self.form_mapping["date_filter"].reset_to_today()

    def on_pre_enter(self, *args):
        '''Event handler for when the screen is entered.'''
        self.ids.main_scroll_view.scroll_y = 1
        self._display_work_config_options()
        self.reset_form() #reset after init all options
        #Init table with default datas
        work_config_name = self.form_mapping["select_settings"].text
        date_filter = self.form_mapping["date_filter"].text
        detection_result_filter = self.form_mapping["detection_result_filter"].text
        self.load_filter_data_table(work_config_name, date_filter, detection_result_filter)

        return super().on_pre_enter(*args)

    def _display_work_config_options(self):
        '''Populate work config dropdown options.'''
        with get_db() as db:
            names = db.query(WorkConfigs.name).filter(WorkConfigs.deleted_at.is_(None)).order_by(WorkConfigs.id.desc()).all()
            self.form_mapping["select_settings"].db_data = [name for (name,) in names]

    def on_filter_button(self):
        ''' Handle the filter button click event.'''
        work_config_name = self.form_mapping["select_settings"].text
        date_filter = self.form_mapping["date_filter"].text
        detection_result_filter = self.form_mapping["detection_result_filter"].text
        # Load data with filter
        filter_state = self.load_filter_data_table(work_config_name, date_filter, detection_result_filter)
        if not filter_state:
            #display popup
            popup = self.popup.create_adaptive_popup(
                title="notification_popup",
                message="no_data_filter_popup_D2"
            )
            popup.open()

    def load_filter_data_table(self, work_config_name, date_filter, detection_result_filter, show_button=True):
        ''' Load data with FILTER into detection results table. Return False if no data.'''
        data = []
        # Handle default values for filters
        if work_config_name == self.form_mapping["select_settings"].values[0]:
            work_config_name = None
        if detection_result_filter == self.form_mapping["detection_result_filter"].label[0]:
            detection_result_filter = None
        with get_db() as db:
            detection_results = filter_detection_results(db, work_config_name, date_filter, detection_result_filter)

        for detection_result in detection_results:
            # Extract data
            thumbnail_path = os.path.join(DETECTION_RESULTS_FOLDER, detection_result.thumbnail_path) #display
            heatmap_path = os.path.join(DETECTION_RESULTS_FOLDER, detection_result.heatmap_path)
            his_img_path = os.path.join(DETECTION_RESULTS_FOLDER, detection_result.his_img_path)
            # Check if the image files exist before displaying
            if not os.path.exists(thumbnail_path) or not os.path.exists(heatmap_path) or not os.path.exists(his_img_path):
                continue
            judgment = self._get_judgment_display(detection_result.judgment)
            # Create the row
            row = {
                "index":            detection_result.id,
                "detected_at":      datetime.fromisoformat(detection_result.detected_at).strftime("%Y/%m/%d %H:%M:%S"),
                "work_config_name": detection_result.work_configs.name,
                "work_config_id":   detection_result.work_config_id,
                "thumbnail_path":   thumbnail_path,
                "judgment":         judgment,
            }
            if show_button:
                row["button"] = "enable"
            else:
                row["button"] = "disable"
            data.append(row)
        self.detection_results_table.all_rows = data
        self.detection_results_table.current_page = 1
        self.detection_results_table.display_current_page()
        self.detection_results_table.create_pagination_controls()
        if len(detection_results) == 0:
            return False #no data
        return True

    def backup_item(self, item):
        '''Call by backup button'''
        try:
            with get_db() as db:
                backup_path = read_system_config(db, 'BACKUP_PATH').value
                if not os.path.exists(backup_path):
                    raise FileNotFoundError(f"Directory does not exist: {backup_path}")
                backup_path = os.path.join(backup_path, "detection_results")

            img_paths = self._get_image_paths_by_id(item.get('index')) #(his_img_path, thumbnail_path, heatmap_path)
            for path in img_paths:
                if path:
                    image_path = os.path.join(DETECTION_RESULTS_FOLDER, path)
                    dest_path = os.path.join(backup_path, path)
                    if not os.path.exists(os.path.dirname(dest_path)):
                        os.makedirs(os.path.dirname(dest_path))
                    shutil.copy2(image_path, dest_path)  # Copy with metadata
                    print(f"Image copied from {image_path} to {dest_path}")
                else:
                    raise Exception(f"No image found for item id: {item.get('index')}")

            popup = self.popup.create_adaptive_popup(
                title="notification_popup",
                message="backup_popup_success_D2"
            )
            popup.open()

        except Exception as e:
            traceback.print_exc()
            if isinstance(e, FileNotFoundError):
                message = "backup_popup_failed_D2"
            else:
                message = "overall_error_popup"
            popup = self.popup.create_adaptive_popup(
                title="error_popup",
                message=message
            )
            popup.open()

    def _get_image_paths_by_id(self, detection_result_id):
        with get_db() as db:
            query = db.query(DetectionResults).filter(DetectionResults.id == detection_result_id)
            if hasattr(DetectionResults, 'deleted_at'):
                query = query.filter(DetectionResults.deleted_at.is_(None))
            data = query.first()
            if data:
                #print(data.__dict__)
                return (data.his_img_path, data.thumbnail_path, data.heatmap_path)
            return (None, None, None)

    def _get_id_by_name(self, table, name):
        with get_db() as db:
            query = db.query(table.id).filter(table.name == name)
            if hasattr(table, 'deleted_at'):
                query = query.filter(table.deleted_at.is_(None))
            data = query.first()
            if data:
                return data.id
            return None

    def _get_judgment_display(self, judgment_value):
        '''Convert judgment value to display string with color.'''
        if judgment_value in JUDGMENT_MAPPING:
            return JUDGMENT_MAPPING[judgment_value]()
        return "Unknown"
