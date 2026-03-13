'''Screen B2: DataGenerationScreen'''

import traceback
import re
import os

from kivy.uix.label import Label
from kivy.core.window import Window
from kivy.uix.gridlayout import GridLayout
from kivy.properties import ObjectProperty
from kivy.metrics import dp
from kivy.clock import Clock
from kivy.logger import Logger

from db.session import get_db
from db.models.work_configs import WorkConfigs
from db.models.generate_datas import GenerateDatas
from app.services.generate_datas import create_generate_data, update_generate_data
from app.libs.widgets.components import ImageFrame, FormScreen, MyPopup, MyModal
from app.screen.PyModule.utils.cli_manager import CLIManager
from app.screen.PyModule.subprocess.build_command import BuildCommand

#CONST
from app.libs.constants.colors import COLORS
from app.env import BE_FOLDER, BIAS_PATH, HISTOGRAM_FOLDER
_SCRIPT_PATH = os.path.join(BE_FOLDER, "flows", "tile", "ir_histogram.py")
_STATUS_HANDLERS = {
    "D010": "on_pipe_start",
    "D005": "on_pipe_running",
    "D012": "on_pipe_end",
    "E001": "on_pipe_error",
    "E002": "on_pipe_ini_error"
}

class DataGenerationScreen(FormScreen, CLIManager):
    '''B2 main class.'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.image_output_dir = ''
        self.image_list = []
        self.popup = MyPopup()
        self.create_folder_modal = CreateFolderModal(parent_screen=self)

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
            Logger.error("No handler defined for status '%s'", pipeline_status)
            return

    def on_pipe_start(self, data: dict):
        '''Handles the start of the pipeline.'''
        if self.loading_popup:
            self.loading_popup.dismiss()

    def on_pipe_running(self, data: dict):
        '''Handles the pipeline running state.'''
        if self.loading_popup:
            self.loading_popup.dismiss()
        self.stream_image(data['data'])

    def on_pipe_end(self, data: dict):
        '''Handles the end of the pipeline.'''
        self.loading_popup.open()

    def on_pipe_error(self, data: dict):
        '''Handles pipeline errors.'''
        self.loading_popup.dismiss()
        self.__show_popup()

    def on_pipe_ini_error(self, data: dict):
        '''Handles pipeline errors.'''
        self.loading_popup.dismiss()
        self.__show_popup(title="error_popup", message="ini_error_message_E2")

    def validate_paths(self):
        '''Custom validation for paths. Paths: intrinsics_path, perspective_path, speed_path and bias_path'''
        try:
            with get_db() as db:
                work_config = db.query(WorkConfigs).filter(WorkConfigs.name == self.form_mapping["select_settings"].text, WorkConfigs.deleted_at.is_(None)).first()
                if work_config:
                    sensor_settings = work_config.sensor_settings
                    intrinsics_path = sensor_settings.intrinsic_path
                    perspective_path = sensor_settings.perspective_path
                    speed_path = sensor_settings.speed_path
                    bias_path = os.path.join(BIAS_PATH, work_config.bias_path)
                else:
                    sensor_settings = intrinsics_path = perspective_path = speed_path = bias_path = None
            val_pairs = [
                (intrinsics_path, self.form_mapping["select_settings"]),
                (perspective_path, self.form_mapping["select_settings"]),
                (speed_path, self.form_mapping["select_settings"]),
                (bias_path, self.form_mapping["select_settings"]),
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
            Logger.error("Failed to validate paths")

    def validate_id_label(self):
        '''Custom validation for id_label.'''
        try:
            id_label_text = (self.form_mapping["id_label"].text or "").strip()
            if id_label_text:
                if not re.fullmatch(r'^[A-Za-z0-9]*$', id_label_text) or len(id_label_text) > 8:
                    self.form_mapping["id_label"].error_message = 'id_label_error_message_B2'
            else:
                self.form_mapping["id_label"].text = ""
                self.form_mapping["id_label"].error_message = ""
        except Exception:
            Logger.error("Failed to validate id_label")

    def on_kv_post(self, base_widget):
        '''Event handler for post-Kivy setup.'''
        self.form_mapping = {
            "select_settings": self.ids.select_settings,
            "new_folder_name": self.create_folder_modal.ids.new_folder_name,
            "create_folder_button": self.create_folder_modal.ids.create_folder_button,
            "output_dir_label": self.create_folder_modal.ids.output_dir_label,
            "folder_select": self.ids.folder_select,
            "open_folder_button": self.ids.open_folder_button,
            "collected_image": self.ids.collected_image,
            "id_label": self.ids.id_label.ids.form_input,
            "image_output_dir": self.image_output_dir,
        }
        #define validation list
        self.dropdown_work_config_id = None #changed in on_work_config_selected()
        self.form_mapping["open_folder_button"].path = rf"{HISTOGRAM_FOLDER}"
        self.val_on_add_folder = [
            self.form_mapping["select_settings"],
            self.form_mapping["new_folder_name"]
        ]
        self.val_on_data_gen = [
            self.form_mapping["select_settings"],
            self.form_mapping["folder_select"],
            self.form_mapping["id_label"]
        ]
        return super().on_kv_post(base_widget)

    def on_pre_enter(self, *args):
        '''Event handler for when the screen is entered.'''
        self.loading_popup = self.popup.create_loading_popup(title="loading_popup")
        self.ids.main_scroll_view.scroll_y = 1
        self.reset_form()
        self._display_work_config_options()
        return super().on_pre_enter(*args)

    def update_open_folder_path(self):
        '''Update the open folder button path from DETECTION_RESULTS_FOLDER -> DETECTION_RESULTS_FOLDER/id.'''
        #called by on_work_config_selected() and in kv folder_select on_text()
        if self.dropdown_work_config_id:
            self.form_mapping["open_folder_button"].path = os.path.join(HISTOGRAM_FOLDER, str(self.dropdown_work_config_id))
            if self.form_mapping["folder_select"].text:
                self.form_mapping["open_folder_button"].path = os.path.join(self.form_mapping["open_folder_button"].path,
                                                                            str(self.form_mapping["folder_select"].text))
        else: #default
            self.form_mapping["open_folder_button"].path = rf"{HISTOGRAM_FOLDER}"

    def reset_form(self):
        '''Resets the form to its initial state.'''
        self.dropdown_work_config_id = None
        self.reset_val_status(self.val_on_data_gen)
        self.form_mapping["open_folder_button"].path = rf"{HISTOGRAM_FOLDER}"
        self.form_mapping["new_folder_name"].text = ""
        self.form_mapping["create_folder_button"].path = ""
        self.form_mapping["create_folder_button"].folder_name = ""
        self.form_mapping["output_dir_label"].id_text = ""
        self.form_mapping["select_settings"].text = ""
        self.form_mapping["select_settings"].values = []
        self.form_mapping["folder_select"].text = ""
        self.form_mapping["folder_select"].folder_list = []
        self.form_mapping["id_label"].text = ""
        self.form_mapping["image_output_dir"] = ""
        self.image_list = []
        self.form_mapping["collected_image"].clear_widgets()

    def load_spinner_from_list_folders(self, path):
        '''Load all folder names in the specified folder into the spinner'''
        try:
            spinner = self.form_mapping["folder_select"]
            if not path or not os.path.exists(path):
                spinner.folder_list = []
                spinner.text = ""
                return
            self.dataset_names = sorted([f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))],
                                        key=lambda f: os.path.getmtime(os.path.join(path, f)),
                                        reverse=True)
            if not self.dataset_names:
                spinner.folder_list = []
                spinner.text = ""  # Reset text to show hint
                return
            spinner.folder_list = self.dataset_names
            spinner.text = ""
        except Exception as e:
            Logger.error("Load Spinner Error: %s", str(e))

    def _get_id_by_name(self, table, name):
        '''Retrieves the ID of a record by its name from the specified table.'''
        with get_db() as db:
            query = db.query(table.id).filter(table.name == name)
            if hasattr(table, 'deleted_at'):
                query = query.filter(table.deleted_at.is_(None))
            data = query.first()
            if data:
                return data.id
            return None

    def _display_work_config_options(self):
        '''Populates the select_settings dropdown with available work configurations.'''
        with get_db() as db:
            names = db.query(WorkConfigs.name).filter(WorkConfigs.deleted_at.is_(None)).order_by(WorkConfigs.id.desc()).all()
            self.form_mapping["select_settings"].values = [name for (name,) in names]

    def on_work_config_selected(self):
        '''Callback when a work config is selected from select_settings dropdown.'''
        #reset related
        self.form_mapping["collected_image"].clear_widgets()
        self.form_mapping["id_label"].text = ""
        #update output_dir_label
        if self.form_mapping["select_settings"].text:
            self.dropdown_work_config_id = self._get_id_by_name(WorkConfigs, self.form_mapping["select_settings"].text)
            if self.dropdown_work_config_id:
                self.form_mapping["output_dir_label"].id_text = str(self.dropdown_work_config_id)
                self.form_mapping["create_folder_button"].path = self.form_mapping["output_dir_label"].path_text #needed for update_image_dir
                self.load_spinner_from_list_folders(self.form_mapping["output_dir_label"].path_text)
                self.update_open_folder_path() #update open folder
            else:
                self.form_mapping["output_dir_label"].id_text = ''
                self.form_mapping["image_output_dir"] = ''
                self.form_mapping["create_folder_button"].path = ''
                self.form_mapping["create_folder_button"].folder_name = ''
                self.load_spinner_from_list_folders('')

    def on_folder_create_button(self):
        '''Run when the create folder button is pressed'''
        try:
            self.reset_val_status(self.val_on_add_folder)
            #Validate
            self.validate(self.val_on_add_folder)#validate text and required above
            if not self.form_mapping["new_folder_name"].error_message: #if folder name is good, continue checking
                #validate window rules
                self.form_mapping["new_folder_name"].validate_filename(self.form_mapping["new_folder_name"].text)
                #validate duplicate name
                base_output_dir = os.path.join(HISTOGRAM_FOLDER,
                                               str(self._get_id_by_name(WorkConfigs, self.form_mapping["select_settings"].text)))
                if os.path.exists(base_output_dir):
                    if self.is_folder_name_duplicate(self.form_mapping["new_folder_name"].text, base_output_dir):
                        self.form_mapping["new_folder_name"].error_message = "folder_name_already_exists"
                        raise Exception(self.form_mapping["new_folder_name"].error_message)
            self.check_val_status(self.val_on_add_folder)
            #End Validate
            if self.form_mapping["new_folder_name"].text:
                self.form_mapping["create_folder_button"].folder_name = self.form_mapping["new_folder_name"].text
            if self.form_mapping["select_settings"].text:
                self.form_mapping["create_folder_button"].path = base_output_dir
            self.create_folder_modal.dismiss()
        except Exception:
            self.form_mapping["create_folder_button"].folder_name = "" #ensure no folder is created
            traceback.print_exc()
            return

    def on_folder_created(self):
        '''Run after the folder is created: Reload the spinner with the new folders added and reset folder name.'''
        if self.form_mapping["select_settings"].text and self.form_mapping["new_folder_name"].text:
            self.load_spinner_from_list_folders(os.path.join(
                HISTOGRAM_FOLDER,
                str(self._get_id_by_name(WorkConfigs, self.form_mapping["select_settings"].text))
            ))
            self.form_mapping["folder_select"].text = self.form_mapping["new_folder_name"].text #change spinner text accordingly
            self.form_mapping["new_folder_name"].text = "" #reset folder name

    def on_folder_select(self):
        if self.form_mapping["folder_select"].text == self.form_mapping["folder_select"].make_folder_text and self.form_mapping["folder_select"].selected_index == 0:
            self.open_create_folder_modal()
        else:
            self.update_image_dir()
            self.update_open_folder_path()

    def update_image_dir(self):
        '''Call on folder_select'''
        if self.form_mapping["create_folder_button"].path and self.form_mapping["folder_select"].text:
            self.form_mapping["image_output_dir"] = os.path.join(self.form_mapping["create_folder_button"].path,
                                                 self.form_mapping["folder_select"].text)
            self.form_mapping["collected_image"].clear_widgets()
            #self.display_image() #test function TODO: check if removed

    # def display_image(self): #test function
    #     display_image_box = self.form_mapping["collected_image"]
    #     image_list = self.load_saved_image()
    #     if not image_list:
    #         self.reset_image()
    #         return

    #     display_image_box.clear_widgets() #clear empty_label

    #     for image_path in image_list: #rows
    #         image_source = os.path.join(self.form_mapping["image_output_dir"], image_path)
    #         image_frame = ImageFrame(height=dp(150), border_color=COLORS['LIGHT_GRAY'], source=image_source)
    #         display_image_box.add_widget(image_frame)

    def stream_image(self, image_path):
        '''Add new images to the widget.'''
        image_source = os.path.join(self.form_mapping["image_output_dir"], image_path)
        if os.path.exists(image_source):
            image_frame = ImageFrame(height=dp(150), border_color=COLORS['LIGHT_GRAY'], source=image_source)
            self.form_mapping["collected_image"].add_widget(image_frame)

    def load_saved_image(self):
        '''Load images from the specified directory and return a list of image filenames.'''
        try:
            if not self.form_mapping["image_output_dir"] or not os.path.exists(self.form_mapping["image_output_dir"]):
                return
            self.image_list = [f for f in os.listdir(self.form_mapping["image_output_dir"]) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            if not self.image_list:
                Logger.error('%s is empty', self.form_mapping["image_output_dir"])
                return
            return self.image_list

        except Exception:
            popup = self.popup.create_adaptive_popup(
                title='error_popup',
                message='error_loading_images_from_folder_popup_B2'
            )
            popup.open()

    def is_folder_name_duplicate(self, name, directory):
        '''Check if a name already exists in the folder directory when creating'''
        for folder_name in os.listdir(directory):
            if name.lower() == str(folder_name).lower():
                return True
        return False

    def run_generate(self):
        '''Initiates the data generation process.'''
        try:
            self.reset_val_status(self.val_on_data_gen)
            #Validate
            self.validate(self.val_on_data_gen)
            self.validate_paths()
            self.validate_id_label()
            self.check_val_status(self.val_on_data_gen)
            #End Validate
        except Exception:
            Logger.error("An error occurred during data generation")
            popup = self.popup.create_adaptive_popup(
                title='error_popup',
                message='generation_failed_popup_B2'
            )
            popup.open()
            return
        def run_subprocess():
            '''Runs the data generation subprocess.'''
            command = BuildCommand.get_b2(self.form_mapping)
            result = self._run_cli(
                script_path=str(_SCRIPT_PATH),
                use_module=False,
                arg_list=command,
                title_window_focus=["Sensor", "Histogram"],
                cwd=BE_FOLDER,
                use_pipe_server=True
            )
            if result is not True:
                traceback.print_exc()
                raise Exception("Command failed")

        if not self.form_mapping["select_settings"].text:
            Logger.error("Run Subprocess: missing datas")
            self.__show_popup()
            return

        Clock.schedule_once(lambda dt: self.form_mapping["collected_image"].clear_widgets(), 0)

        self._run_task_in_thread(run_subprocess)

    def _check_thread(self, dt, thread):
        '''Checks the status of the data generation thread.'''
        if thread.is_finished():
            try:
                thread.result()    # re‑raises if exception occurred
                self.loading_popup.dismiss()
                self.__show_popup(title='notification_popup', message='done_popup_message')
                with get_db() as db: #if no issue, save info to database
                    work_config_name = self.form_mapping["select_settings"].text
                    self.dropdown_work_config_id = self._get_id_by_name(WorkConfigs, self.form_mapping["select_settings"].text) #ensure. TODO: check if this line can be removed
                    if self.dropdown_work_config_id:
                        existing_data = db.query(GenerateDatas).filter(GenerateDatas.data_dir == self.form_mapping["image_output_dir"],
                                                                       GenerateDatas.deleted_at.is_(None)).first()
                        if existing_data:
                            update_generate_data(db, existing_data.id, self.dropdown_work_config_id, self.form_mapping["image_output_dir"])
                        else:
                            create_generate_data(db, self.dropdown_work_config_id, self.form_mapping["image_output_dir"])
                    else:
                        message = f"Work config '{work_config_name}' not found in database."
                        Logger.error(message)
                        raise Exception(message)
            except Exception:
                traceback.print_exc()
                self.loading_popup.dismiss()
            finally:
                self.enable_click()
            return False
        else:
            self.disable_click(all_widget=True, allow_widget=[self.form_mapping["open_folder_button"]])
        return True

    def __show_popup(self, title='error_popup', message="generation_failed_popup_B2"):
        '''Display popup in sync with multi-threading'''
        def _show(dt):
            if self.popup:
                self.popup.create_adaptive_popup(
                    title=title,
                    message=message
                ).open()
        Clock.schedule_once(_show, 0)

    def open_create_folder_modal(self):
        """Open the folder creation modal."""
        if self.form_mapping["new_folder_name"].text:
            self.form_mapping["new_folder_name"].text = ""
        self.create_folder_modal.open()

    def close_create_folder_modal(self):
        """Close the folder creation modal."""
        if self.form_mapping["folder_select"].text == self.form_mapping["folder_select"].make_folder_text:
            self.form_mapping["folder_select"].text = ""
        if self.form_mapping["new_folder_name"].error_message:
            self.form_mapping["new_folder_name"].error_message = ""

class CollectedImageLayout(GridLayout):
    '''Layout for displaying collected images.'''
    def __init__(self, **kwargs):
        '''Initializes the CollectedImageLayout.'''
        super().__init__(**kwargs)
        self._placeholder = None
        self._user_scroll = False

    def on_kv_post(self, base_widget):
        '''Event handler for post-Kivy setup.'''
        Clock.schedule_once(lambda dt: self.update_layout(), 0)
        self.scrollview = self._get_scrollview()
        if self.scrollview:
            self.scrollview.bind(on_scroll_start=self.scroll_binding)
        return super().on_kv_post(base_widget)

    def add_widget(self, widget, *args, **kwargs):
        '''Persistent scrollview (keep same pixel distance from top)'''
        distance_from_top = 0
        if self.scrollview and self._user_scroll:
            content = self.scrollview.children[0]
            scrollable_height = max(1, content.height - self.scrollview.height)
            # current pixel offset from top
            distance_from_top = (1 - self.scrollview.scroll_y) * scrollable_height
        super().add_widget(widget, *args, **kwargs)
        def restore_scroll(dt):
            content = self.scrollview.children[0]
            new_scrollable_height = max(1, content.height - self.scrollview.height)
            # restore same pixel offset from top
            new_scroll_y = 1 - (distance_from_top / new_scrollable_height)
            self.scrollview.scroll_y = new_scroll_y
        if self.scrollview and self._user_scroll:
            Clock.schedule_once(restore_scroll, -1)
        return

    def _get_scrollview(self):
        '''Returns the parent scrollview if it exists.'''
        parent = self.parent
        if parent.__class__.__name__ == "CustomScrollView":
            return parent
        return None

    def scroll_binding(self, *args):
        '''Binds scroll events to user interaction.'''
        if self.collide_point(*self.to_widget(*Window.mouse_pos)) and not self._user_scroll:
            self._user_scroll = True

    def scroll_to_latest(self, widget=None):
        '''Scrolls the view to the latest added widget.'''
        if self.scrollview and self.minimum_height > self.scrollview.height:
            Clock.schedule_once(lambda dt: setattr(self.scrollview, "scroll_y", 0), 0) #to bottom

    def reset_scroll(self):
        '''Resets the scroll position.'''
        self._user_scroll = False
        if self.scrollview:
            Clock.schedule_once(lambda dt: setattr(self.scrollview, "scroll_y", 1), 0)

    def update_layout(self, *args):
        '''Updates the layout.'''
        if len(self.children) == 0 or (len(self.children) == 1 and self._placeholder): # no data -> add placeholder
            if not self._placeholder and self.scrollview:
                self.col_force_default = False
                self._placeholder = NoDataLabel(custom_parent=self.scrollview)
                self.add_widget(self._placeholder)
                self.reset_scroll()
        else: #contains data
            if self._placeholder: #remove placeholder
                self.col_force_default = True
                if self._placeholder in self.children:
                    self.remove_widget(self._placeholder)
                self._placeholder = None
            if self.children:
                if self._user_scroll:
                    return
                self.scroll_to_latest(self.children[0])

    def on_children(self, instance, value):
        '''Event handler for when the children change.'''
        Clock.schedule_once(self.update_layout, 0)

    def clear_widgets(self, children=None):
        '''Clears the widgets.'''
        self._placeholder = None
        self._user_scroll = False
        self.height = self.minimum_height
        super().clear_widgets(children)

class NoDataLabel(Label):
    '''Label for no data.'''
    custom_parent = ObjectProperty(None) #to set height and width

class CreateFolderModal(MyModal):
    parent_screen = ObjectProperty(None)
    def on_folder_create_button(self):
        """Delegate to parent screen's logic"""
        if self.parent_screen:
            self.parent_screen.on_folder_create_button()

    def on_folder_created(self):
        """Delegate to parent screen's logic"""
        # Can be left empty triggered by KV event binding.
        if self.parent_screen:
            self.parent_screen.on_folder_created()

    def dismiss(self, *args, **kwargs):
        """Delegate to parent screen's logic"""
        super().dismiss(*args, **kwargs)
        if self.parent_screen:
            self.parent_screen.close_create_folder_modal()
