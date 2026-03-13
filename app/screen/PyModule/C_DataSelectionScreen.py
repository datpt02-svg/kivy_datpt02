"""
Data selection screen module for Kivy-based application.
"""
import os
import shutil
import traceback
from datetime import datetime

from sqlalchemy import desc

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.factory import Factory
from kivy.metrics import dp
from kivy.properties import ListProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import Screen

from app.env import DATASETS_FOLDER, HISTOGRAM_FOLDER
from app.libs.constants.colors import COLORS
from app.libs.constants.default_values import DefaultAnimation
from app.libs.widgets.components import CustomScrollView, KeyLabel, MyPopup
from app.services.dataset_images import create_dataset_images, update_dataset_images
from app.services.datasets import create_dataset, update_dataset
from app.services.utils.recursive_delete import recursive_delete
from db.models.dataset_images import DatasetImages
from db.models.datasets import Datasets
from db.models.generate_datas import GenerateDatas
from db.models.work_configs import WorkConfigs
from db.session import get_db

from .utils.datatable_manager import DataTableManager


DATA_SELECTION_JSON = os.path.join("app", "config", "c1_data_selection.json")


class DataSelectionScreen(Screen):
    """
    Screen for managing dataset selection and configuration.

    This screen allows users to create, edit, and manage datasets for AI model training.
    It provides functionality for selecting work configurations, loading images from folders,
    and organizing images into different usage types (train, check, defect).

    The screen supports:
    - Creating new datasets
    - Editing existing datasets
    - Copying datasets
    - Deleting datasets
    - Loading images from generated data folders
    - Categorizing images by usage type
    - Lazy loading of images for performance optimization

    Attributes:
        c1_folder_select_label_value (StringProperty): Label value for folder selection
        editing_item_name (str): Name of the dataset being edited
        copy_mode (bool): Flag indicating if in copy mode
        popup (MyPopup): Popup instance for displaying messages
        app (App): Reference to the running Kivy application
        data_selection_table (DataTableManager): Manager for the dataset table
        image_album (ImageAlbum): Widget for displaying and managing images
        loaded_image_selections (list): List of loaded image selections from database
    """
    c1_folder_select_label_value = StringProperty("")

    def set_c1_folder_select_label_value_to_placeholder(self):
        """Reset the folder selection label value to an empty placeholder."""
        self.c1_folder_select_label_value = ""

    def set_c1_folder_select_label_value_to_value(self, path_value):
        """Set the folder selection label value to the specified path.

        Args:
            path_value: The path value to set for the folder selection label.
        """
        self.c1_folder_select_label_value = path_value

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.editing_item_name = None
        self.copy_mode = False
        self.popup = MyPopup()
        self.app = App.get_running_app()

        # Initialize table manager
        self.data_selection_table = DataTableManager(
            screen=self,
            table_id="data_table_c1_data_selection",
            pagination_box_id="pagination_box_c1_data_selection",
            headers=['dataset_name_column_C1',
                     'ai_model_trained_column_C1', 'action_column'],
            db_headers=['name', 'is_trained', 'button'],
            db_model=Datasets,
            config_fields=[],
            types=['str', 'str', 'button_copy'],
            settings_file=DATA_SELECTION_JSON,
            custom_message=True,
            markup_columns=[1],
            translation_columns=[1]
        )

        Clock.schedule_once(self.post_init)

    def on_pipe(self, data):
        """Handles incoming data from the pipeline.

        This screen does not process pipeline data.

        Args:
            data: Data received from the pipeline.
        """
        pass # pylint: disable=unnecessary-pass

    def update_radio_options(self):
        """Update radio options for all ImageItem when language changes"""
        # Update cached texts
        ImageItem.update_cached_texts()

        # Update existing ImageItems
        if hasattr(self, 'image_album') and self.image_album:
            for item in self.image_album.items:
                if hasattr(item, 'update_radio_texts_if_needed'):
                    item.update_radio_texts_if_needed()

        # Reset flag after updating all items
        ImageItem.reset_text_update_flag()

    def clear_errors(self):
        """Clear all error messages from input fields."""
        self.ids.c1_dataset_name_input.error_message = ""
        self.ids.c1_work_config_select.error_message = ""
        self.ids.c1_folder_select.error_message = ""
        self.ids.image_album_error.error_message = ""

    def scroll_screen_c1_to_default(self):
        """Scroll the C1 data selection screen to the default (top) position."""
        try:
            scroll_view = self.ids.get('scroll_screen_C1_data_selection', None)
            if not scroll_view:
                print("ScrollView with id 'scroll_screen_C1_data_selection' not found")
                return

            def try_scroll_to_top(*args):
                # Only scroll when content has valid height
                content = scroll_view.children[0] if scroll_view.children else None
                if content and content.height > scroll_view.height:
                    scroll_view.scroll_y = 1.0
                else:
                    # If not ready, try again after 1 frame
                    Clock.schedule_once(try_scroll_to_top, 0.05)

            # Start trying to scroll
            try_scroll_to_top()
        except Exception as e:
            traceback.print_exc()
            print(f"Error when scrolling to default state: {e}")

    def on_pre_enter(self, *args):
        """Event called before the screen is displayed"""
        self.scroll_screen_c1_to_default()
        self.clear_errors()
        self.reset_form()
        self.editing_item_name = None
        self.copy_mode = False

        # SINGLE CONNECTION
        with get_db() as db:
            self.load_data_table(keep_current_page=False, db_session=db)
            self._display_work_config_options(db)

    def on_pre_leave(self, *args):
        self.image_album.stop_monitoring()
        self.image_album.cancel_lazy_loading()

    def on_leave(self, *args):
        self.image_album.stop_monitoring()
        self.image_album.cancel_lazy_loading()

    def reset_form(self):
        """Reset all form fields to their default state.

        Clears the dataset name input, work config selection, folder selection,
        and image album to prepare the form for new input.
        """
        self.ids.c1_dataset_name_input.text = ""

        self.ids.c1_work_config_select.text = ''

        self.ids.c1_work_config_select.hint_text = self.app.lang.get(
            'select_placeholder')

        self.set_c1_folder_select_label_value_to_placeholder()
        self.ids.c1_folder_select.text = ''
        self.ids.c1_folder_select.values = []

        self.image_album.clear()

    def post_init(self, _dt):
        """Initialize the image album widget after screen creation.

        Args:
            _dt: Delta time parameter (unused, required by Kivy Clock callback).
        """
        self.image_album = ImageAlbum()
        self.ids.image_album_container.add_widget(self.image_album)

    def load_spinner_from_list_folders(self, db, work_config_id):
        """Load folder names into the spinner from the database.

        Queries the GenerateDatas table for data directories associated with
        the given work_config_id and populates the folder selection spinner
        with the basename of each directory.

        Args:
            db: Database session object.
            work_config_id: ID of the work configuration to filter by.
        """
        try:
            generate_datas = db.query(GenerateDatas.data_dir) \
                .filter(GenerateDatas.deleted_at.is_(None)) \
                .filter(GenerateDatas.work_config_id == work_config_id) \
                .order_by(GenerateDatas.created_at.desc()) \
                .all()
            self.ids.c1_folder_select.text = ''
            self.ids.c1_folder_select.values = [
                os.path.basename(name) for (name,) in generate_datas
            ]

        except Exception:
            self.ids.c1_folder_select.values = []
            traceback.print_exc()

    def delete_item(self, item):
        """Delete a dataset item from the database and file system.

        Args:
            item: Dictionary containing the dataset information with 'name' key.
        """
        with get_db() as db:
            try:
                work_config_id = self._get_work_config_id_by_dataset_name(
                    db,
                    WorkConfigs,
                    Datasets,
                    item.get('name')
                )

                dataset_id = self._get_id_by_name(
                    db,
                    Datasets,
                    item.get('name')
                )

                if not work_config_id or not dataset_id:
                    return

                recursive_delete(
                    Datasets,
                    dataset_id,
                    db_session=db
                )

                db.commit()
            except Exception:
                db.rollback()
                traceback.print_exc()
                raise

        self.delete_folders(
            [os.path.join(DATASETS_FOLDER, str(
                work_config_id), item.get('name'))]
        )
        self.load_data_table()

        if self.editing_item_name == item.get('name') and not self.copy_mode:
            self.clear_errors()
            self.reset_form()

    def delete_folders(self, folder_list):
        """Delete a list of folders from the filesystem.

        Args:
            folder_list: List of folder paths to delete.

        Note:
            Prints status messages for each folder (deleted, error, or not found).
        """
        for folder in folder_list:
            if os.path.isdir(folder):
                try:
                    shutil.rmtree(folder)
                    print(f"Deleted: {folder}")
                except Exception as e:
                    print(f"Error deleting {folder}: {e}")
            else:
                print(f"Folder not found: {folder}")

    def _get_id_by_name(self, db, table, name):
        query = db.query(table.id).filter(table.name == name)
        if hasattr(table, 'deleted_at'):
            query = query.filter(table.deleted_at.is_(None))
        data = query.first()
        return data.id if data else None

    def _display_work_config_options(self, db):
        names = db.query(WorkConfigs.name) \
            .filter(WorkConfigs.deleted_at.is_(None)) \
            .order_by(WorkConfigs.created_at.desc()) \
            .all()
        self.ids.c1_work_config_select.values = [name for (name,) in names]

    def on_language(self):
        """Event called when the application language changes"""
        self.update_radio_options()

    def on_c1_work_config_selected(self):
        """Event handler called when a work configuration is selected from the dropdown"""
        self.image_album.show_no_data_message()

        with get_db() as db:
            work_config_id = self._get_id_by_name(
                db,
                WorkConfigs,
                self.ids.c1_work_config_select.text
            )

            if work_config_id:
                placeholder_dir = os.path.join(
                    HISTOGRAM_FOLDER, str(work_config_id), "")
                self.set_c1_folder_select_label_value_to_value(placeholder_dir)
                self.load_spinner_from_list_folders(db, work_config_id)
            else:
                self.set_c1_folder_select_label_value_to_placeholder()
                self.ids.c1_folder_select.values = []

    def get_delete_warning_message(self, _item):
        """Get warning message when deleting an item. Called by delete button.

        Args:
            _item: The item to be deleted (unused in this implementation)

        Returns:
            str: The message key for the delete confirmation popup
        """
        return "delete_message_popup"

    def load_data_table(
        self,
        show_button=True,
        keep_current_page=True,
        db_session=None,
        target_page=1
        ):
        """
        Load data table with ability to use existing session or create new

        Args:
            show_button: Whether to show action button
            keep_current_page: Whether to keep current page or reset to page 1
            db_session: Existing database session. If None, will create new connection
            target_page: Specific page number to jump to. Overrides keep_current_page if provided
        """
        def _load_data(db):
            """Helper function to load data in session"""
            datasets = (
                db.query(Datasets)
                .filter(Datasets.deleted_at.is_(None))
                .order_by(desc(Datasets.id))
                .all()
            )

            data = []
            for dataset in datasets:
                name = dataset.name
                is_trained = dataset.is_trained

                # Create the row
                row = {
                    "name": name,
                    "is_trained": (
                        "trained_status_done_C1"
                        if is_trained
                        else {
                            "text_key": "trained_status_not_done_C1",
                            "format_args": {
                                "hex_color": COLORS.get(
                                    "DARK_RED", color_format="hex"
                                )
                            },
                        }
                    ),
                }

                if show_button:
                    row["button"] = "placeholder"

                data.append(row)
            return data

        # Check if there is an existing session
        if db_session is not None:
            # Use existing session - DO NOT create new connection
            data = _load_data(db_session)
        else:
            # Create new connection
            with get_db() as db:
                data = _load_data(db)

        # Update UI
        self.data_selection_table.all_rows = data

        if not keep_current_page:
            self.data_selection_table.current_page = target_page
        self.data_selection_table.display_current_page()
        self.data_selection_table.create_pagination_controls()

    def load_item_to_form(self, item, edit_mode=True):
        """Load item information into form for editing"""
        try:
            self.image_album.clear()
            self.clear_errors()
            self.editing_item_name = item.get('name', '')

            if edit_mode:
                self.copy_mode = False
                self.ids.c1_dataset_name_input.text = self.editing_item_name

            else:
                self.copy_mode = True
                self.ids.c1_dataset_name_input.text = self.editing_item_name + ' - ' + "Copy"

            with get_db() as db:
                # Get dataset_id from name
                dataset_id = self._get_id_by_name(
                    db, Datasets, self.editing_item_name)
                if not dataset_id:
                    return

                work_config_name = self._get_work_config_name_by_id(
                    db,
                    WorkConfigs,
                    Datasets,
                    dataset_id
                )

                self.ids.c1_work_config_select.text = work_config_name

                images = (
                    db.query(DatasetImages).
                    filter_by(dataset_id=dataset_id)
                    .filter(DatasetImages.deleted_at.is_(None))
                    .all()
                )
                images = [img for img in images if os.path.isfile(
                    img.image_source_path)]
                selections = []
                folder_name = ""
                # Get parent folder containing images (if any)
                if images:
                    # Get all parent folders of images
                    folder_names = []
                    for img in images:
                        parent_folder = os.path.basename(
                            os.path.dirname(img.image_source_path))
                        folder_names.append(parent_folder)
                    unique_folders = set(folder_names)
                    if len(unique_folders) == 1:
                        folder_name = list(unique_folders)[0]
                    else:
                        folder_name = ""

                self.ids.c1_folder_select.text = folder_name

                for img in images:
                    selections.append({
                        'id': str(img.id if hasattr(img, 'id') else img.image_id),
                        'source': img.image_source_path,
                        'selected_option': img.usage_type,
                    })

            # Load images and options into image album
            self.loaded_image_selections = selections
            self.load_images(selections)

        except Exception:
            traceback.print_exc()

    def load_images(self, image_data_list):
        """Load image list into album"""
        # Use the new lazy loading method
        self.image_album.load_images_lazy(image_data_list)

        # If no data, clear will automatically show message
        if not image_data_list:
            return

        # If we have valid images, restore selections
        valid_images = 0
        for image_data in image_data_list:
            source_path = image_data['source']
            if os.path.isfile(source_path):
                valid_images += 1

        if valid_images == 0:
            self.image_album.show_no_data_message()

    def load_saved_image_selections(self, folder_path=""):
        """Load saved image selections from a specified folder.

        Loads PNG images from the given folder path and displays them in the image album
        using lazy loading. Images are sorted by creation time and filename.

        Args:
            folder_path (str, optional): Path to the folder containing images. Defaults to "".

        Returns:
            None: Clears the image album if folder doesn't exist or contains no images.
        """
        try:
            if not os.path.exists(folder_path):
                self.image_album.clear()
                return

            # Get all image files in folder
            image_files = [f for f in os.listdir(folder_path)
                           if f.lower().endswith(('.png'))]

            if not image_files:
                self.image_album.clear()
                return

            image_files.sort(key=lambda f: (
                os.path.getctime(os.path.join(folder_path, f)), f))

            # Create image list to load
            image_data_list = []
            for i, filename in enumerate(image_files):
                image_data_list.append({
                    'source': os.path.join(folder_path, filename),
                    'alt_text': filename,
                    'id': f"img_{i}_{filename}"
                })

            # Load images into ImageAlbum using lazy loading
            self.image_album.load_images_lazy(image_data_list)

        except Exception:
            traceback.print_exc()
            self.image_album.clear()

    def on_folder_select_text(self, spinner):
        """Handle folder selection event and load saved image selections.

        Args:
            spinner: The spinner widget containing the selected folder text.
        """
        with get_db() as db:
            work_config_id = db.query(WorkConfigs.id) \
                .filter(WorkConfigs.name == self.ids.c1_work_config_select.text) \
                .filter(WorkConfigs.deleted_at.is_(None)) \
                .scalar()

        base_folder = os.path.join(
            HISTOGRAM_FOLDER, str(work_config_id))
        folder_path = os.path.join(base_folder, spinner.text)
        self.load_saved_image_selections(folder_path)

    def _validate_all_inputs(self):
        """Centralized validation for all form inputs"""
        self.clear_errors()
        has_error = False
        do_scroll_to_error = False

        # Validate dataset name
        validation_error, error_widget_id = self._validate_dataset_name()
        if validation_error:
            self._show_validation_error(
                widget_id='c1_dataset_name_input', error_message=validation_error)
            has_error = True
            do_scroll_to_error = True
        elif error_widget_id:
            has_error = True
            do_scroll_to_error = True

        # Validate work config selection
        self.ids.c1_work_config_select.validate_text(
            self.ids.c1_work_config_select.text)
        if self.ids.c1_work_config_select.error_message:
            has_error = True
        # Validate folder selection
        self.ids.c1_folder_select.validate_text(
            self.ids.c1_folder_select.text)
        if self.ids.c1_folder_select.error_message:
            has_error = True

        return not has_error, do_scroll_to_error

    def _show_error_popup_with_navigation(self, do_scroll_to_error):
        """Show error popup with navigation to first error"""
        def on_popup_dismiss():
            if do_scroll_to_error:
                self.navigate_to_error(
                    target_screen='screen_C1_data_selection',
                    reference_id='c1_dataset_name_input'
                )

        failure_popup = self.popup.create_adaptive_popup(
            title='error_popup',
            message='save_dataset_failed_message'
        )
        failure_popup.bind(on_dismiss=lambda *args: on_popup_dismiss())
        failure_popup.open()

    def _show_success_popup(self):
        """Show success popup and reset screen"""
        success_popup = self.popup.create_adaptive_popup(
            title='notification_popup',
            message='save_dataset_success_message'
        )
        success_popup.open()
        self.scroll_screen_c1_to_default()

    def _show_failure_popup(self):
        """Show failure popup for unexpected errors"""
        failure_popup = self.popup.create_adaptive_popup(
            title='error_popup',
            message='save_dataset_failed_message'
        )
        failure_popup.open()

    def save_image_selections(self):
        """Main entry point for saving image selections"""
        try:
            # Validate all inputs
            is_valid, do_scroll_to_error = self._validate_all_inputs()

            if not is_valid:
                self._show_error_popup_with_navigation(do_scroll_to_error)
                return

            # Perform save operation
            self._save_data()

            # Show success feedback
            self._show_success_popup()

        except Exception:
            traceback.print_exc()
            self._show_failure_popup()

    def _validate_dataset_name(self):
        """Validate dataset name, return error message if any"""
        c1_dataset_name_input = self.ids.c1_dataset_name_input
        dataset_name = c1_dataset_name_input.text.strip()
        first_error = None

        c1_dataset_name_input.validate_text(dataset_name)
        if self.ids.c1_dataset_name_input.error_message:
            first_error = 'c1_dataset_name_input'
            return None, first_error

        c1_dataset_name_input.validate_filename(dataset_name)
        if self.ids.c1_dataset_name_input.error_message:
            first_error = 'c1_dataset_name_input'
            return None, first_error
        # Check for existing name
        if self.editing_item_name is None or dataset_name != self.editing_item_name:
            existing_names = [item["name"].strip().lower()
                              for item in self.data_selection_table.all_rows]
            if dataset_name.strip().lower() in existing_names:
                return 'save_dataset_duplicated_message', 'c1_dataset_name_input'
        return None, first_error

    def _show_validation_error(self, widget_id, error_message):
        self.ids[widget_id].error_message = error_message

    def find_screen_manager(self, widget):
        """
        Recursively search for a ScreenManager widget in the widget tree.

        Args:
            widget: The widget to search from, starting point of the search.

        Returns:
            The ScreenManager widget if found, None otherwise.
        """
        if (
            widget.__class__.__name__ == "ScreenManager"
            or "ScreenManager" in str(widget.__class__)
            or hasattr(widget, "current")
            and hasattr(widget, "screens")
        ):
            return widget

        # Search in children
        for child in widget.children:
            result = self.find_screen_manager(child)
            if result:
                return result
        return None

    def navigate_to_error(self, target_screen, reference_id):
        """Navigate to a specific screen and scroll to an error widget.

        Args:
            target_screen: The name of the screen to navigate to
            reference_id: The ID of the widget to scroll to
        """
        if not target_screen or not reference_id:
            return

        screen_manager = self.find_screen_manager(self.app.root)
        if not screen_manager:
            return

        screen_manager.current = target_screen
        Clock.schedule_once(
            lambda dt: self.scroll_to_error_widget(reference_id), 0.2)

    def scroll_to_error_widget(self, reference_id):
        """Scroll to the target widget"""
        screen_manager = self.find_screen_manager(self.app.root)
        if not screen_manager:
            print("ERROR: ScreenManager not found!")
            return

        current_screen = screen_manager.current_screen
        target_widget = self.find_widget_by_id(current_screen, reference_id)

        if target_widget:
            scroll_view = self.find_scroll_view_parent(target_widget)

            if scroll_view:
                self.scroll_to_position(scroll_view, target_widget)

    def find_widget_by_id(self, parent, widget_id):
        """Find widget by ID"""
        if hasattr(parent, 'ids') and widget_id in parent.ids:
            return parent.ids[widget_id]

        for child in parent.children:
            result = self.find_widget_by_id(child, widget_id)
            if result:
                return result
        return None

    def find_scroll_view_parent(self, widget):
        """Find ScrollView parent"""
        parent = widget.parent
        while parent:
            if parent.__class__.__name__ == 'ScrollView':
                return parent
            parent = parent.parent
        return None

    def scroll_to_position(self, scroll_view, target_widget):
        """Scroll target_widget to the center of ScrollView along OY axis."""

        def _scroll_to_center(*_):
            content = scroll_view.children[0] if scroll_view.children else None
            if not content:
                print("ScrollView has no content")
                return

            center_x, center_y = target_widget.to_window(
                target_widget.center_x,
                target_widget.center_y
            )
            _, y_in_content = content.to_widget(center_x, center_y)

            content_height = content.height
            scroll_view_height = scroll_view.height
            if content_height <= scroll_view_height:
                return

            desired_center = y_in_content - scroll_view_height / 2
            scrollable_height = content_height - scroll_view_height
            scroll_y = desired_center / scrollable_height
            scroll_y = min(max(scroll_y, 0), 1)

            anim = Animation(scroll_y=scroll_y, d=DefaultAnimation.SCROLL_DURATION, t=DefaultAnimation.SCROLL_TRANSITION)
            anim.start(scroll_view)

        Clock.schedule_once(_scroll_to_center, 0)

    def _prepare_image_selections(self):
        """Prepare image selections data by merging DB and UI data"""
        if self.editing_item_name is not None and hasattr(self, 'loaded_image_selections'):
            return self._merge_db_and_ui_selections()
        else:
            return self.image_album.get_all_selected_data()

    def _merge_db_and_ui_selections(self):
        """Merge database and UI selections when editing"""
        ui_selected = self.image_album.get_selected_data()
        ui_all = self.image_album.get_all_selected_data()

        # Map between DB and UI
        ui_map = {item['id']: item['selected_option'] for item in ui_selected}

        merged = []
        db_ids = set()

        # Merge existing DB items with UI updates
        for item in self.loaded_image_selections:
            if item['id'] in ui_map:
                merged.append({
                    'id': item['id'],
                    'source': item['source'],
                    'selected_option': ui_map.get(item['id'], item['selected_option'])
                })
                db_ids.add(item['id'])

        # Add new UI items not in DB
        for item in ui_all:
            if item['id'] not in db_ids:
                merged.append(item)

        # If no images can be mapped, take all from UI
        return ui_all if not merged else merged

    def _create_or_update_dataset(self, db, dataset_name, work_config_id):
        """Create new dataset or update existing one based on current mode"""
        if self.copy_mode:
            return create_dataset(
                db=db,
                name=dataset_name,
                work_config_id=work_config_id,
                is_trained=False
            )
        else:
            if self.editing_item_name is None:
                return create_dataset(
                    db=db,
                    name=dataset_name,
                    work_config_id=work_config_id,
                    is_trained=False
                )
            else:
                return update_dataset(
                    db=db,
                    dataset_id=self._get_id_by_name(
                        db, Datasets, self.editing_item_name),
                    name=dataset_name,
                    work_config_id=work_config_id
                )

    def _handle_dataset_images(self, db, dataset_obj, selections):
        """Handle dataset images based on current mode"""
        if self.copy_mode:
            self._create_dataset_images(db, dataset_obj, selections)
        else:
            if self.editing_item_name is None:
                self._create_dataset_images(db, dataset_obj, selections)
            else:
                self._update_dataset_images(db, dataset_obj, selections)

    def _create_dataset_images(self, db, dataset_obj, selections):
        """Create new dataset images"""
        images_data = [
            {
                "dataset_id": dataset_obj.id,
                "image_source_path": item['source'],
                "usage_type": item['selected_option']
            }
            for item in selections
        ]
        create_dataset_images(db=db, images_data=images_data)

    def _update_dataset_images(self, db, dataset_obj, selections):
        """Update existing dataset images with optimized DELETE, ADD, UPDATE operations"""
        # Get current DB images
        db_images = db.query(DatasetImages).filter_by(
            dataset_id=dataset_obj.id, deleted_at=None
        ).all()

        db_images_map = {img.image_source_path: img for img in db_images}
        selection_paths = {item['source'] for item in selections}

        # SOFT DELETE images in DB but not in selections
        self._soft_delete_removed_images(db, db_images, selection_paths)

        # ADD new images in selections but not in DB
        self._add_new_images(db, dataset_obj, selections, db_images_map)

        # UPDATE usage_type for images present in both if changed
        self._update_changed_images(db, selections, db_images_map)

    def _soft_delete_removed_images(self, db, db_images, selection_paths):
        """Soft delete images that are in DB but not in current selections"""
        for img in db_images:
            if img.image_source_path not in selection_paths:
                img.deleted_at = datetime.now().isoformat()
                img.deleted = 1
                db.add(img)

    def _add_new_images(self, db, dataset_obj, selections, db_images_map):
        """Add new images that are in selections but not in DB"""
        new_images = [
            {
                "dataset_id": dataset_obj.id,
                "image_source_path": item['source'],
                "usage_type": item['selected_option']
            }
            for item in selections if item['source'] not in db_images_map
        ]
        if new_images:
            create_dataset_images(db=db, images_data=new_images)

    def _update_changed_images(self, db, selections, db_images_map):
        """Update usage_type for images that have changed"""
        updates = []
        for item in selections:
            img = db_images_map.get(item['source'])
            if img and img.usage_type != item['selected_option']:
                updates.append({
                    "id": img.id,
                    "usage_type": item['selected_option']
                })
        if updates:
            update_dataset_images(db=db, updates=updates)

    def _reset_editing_state(self):
        """Reset editing state and refresh UI"""
        target_record_name = None
        if self.editing_item_name and not self.copy_mode:
            target_record_name = self.ids.c1_dataset_name_input.text.strip()

        self.editing_item_name = None
        self.copy_mode = False

        try:
            if target_record_name:
                target_page = self.data_selection_table.find_page_for_record(
                    record_name=target_record_name,
                    name_field='name'
                )
                self.load_data_table(
                    keep_current_page=False,
                    target_page=target_page
                )
            else:
                self.load_data_table(keep_current_page=False)
        except ValueError:
            self.load_data_table()

        self.reset_form()

    def _save_data(self):
        """Perform saving data to DB"""
        dataset_name = self.ids.c1_dataset_name_input.text.strip()

        # If editing but no original data or cannot map, treat as new
        selections = self._prepare_image_selections()

        # SINGLE TRANSACTION
        with get_db() as db:
            try:
                work_config_id = self._get_id_by_name(
                    db,
                    WorkConfigs,
                    self.ids.c1_work_config_select.text
                )

                dataset_obj = self._create_or_update_dataset(
                    db, dataset_name, work_config_id
                )

                if dataset_obj:
                    self._handle_dataset_images(db, dataset_obj, selections)
                db.commit()

                self.create_txt_training(
                    dataset_name, selections, work_config_id)

            except Exception:
                db.rollback()
                traceback.print_exc()
                raise

        self._reset_editing_state()

    def _get_work_config_name_by_id(self, db, work_config_table, dataset_table, dataset_id):
        """
        Return work_config name based on dataset_id.
        """
        result = (
            db.query(work_config_table.name)
            .join(dataset_table, work_config_table.id == dataset_table.work_config_id)
            .filter(dataset_table.id == dataset_id)
            .filter(work_config_table.deleted_at.is_(None))
            .first()
        )
        return result[0] if result else ''

    def _get_work_config_id_by_dataset_name(
        self,
        db,
        work_config_table,
        dataset_table,
        dataset_name
    ):
        """
        Return work_config id based on dataset_name.
        """
        result = (
            db.query(work_config_table.id)
            .join(dataset_table, work_config_table.id == dataset_table.work_config_id)
            .filter(dataset_table.name == dataset_name)
            .filter(work_config_table.deleted_at.is_(None))
            .first()
        )
        return result[0] if result else ''

    def create_txt_training(self, dataset_name, selections, work_config_id):
        """
        Create txt file containing image list and usage type, save to DATASETS_FOLDER/{dataset_name}/data.txt
        Each line format: {source} | {selected_option}
        """
        if not dataset_name or not selections:
            return

        # Dataset folder path
        dataset_folder = os.path.join(
            DATASETS_FOLDER, str(work_config_id), dataset_name)
        # Txt file path
        txt_path = os.path.join(dataset_folder, "data.txt")

        # Ensure folder exists
        os.makedirs(dataset_folder, exist_ok=True)

        # Delete old txt file if exists
        if os.path.exists(txt_path):
            try:
                os.remove(txt_path)
            except Exception:
                traceback.print_exc()
        # Write file
        try:
            with open(txt_path, "w", encoding="utf-8") as f:
                for item in selections:
                    # Write correct format: {source} | {selected_option}
                    f.write(f"{item['source']} | {item['selected_option']}\n")
        except Exception:
            traceback.print_exc()

    def upload_images(self):
        """Upload images from the selected folder.

        Validates that a work configuration and folder are selected,
        clears any previous errors, and initiates the folder selection process.
        """
        self.image_album.clear()
        self.ids.c1_dataset_name_input.error_message = ''
        self.ids.c1_work_config_select.error_message = ''
        self.ids.c1_folder_select.error_message = ''
        errors = []

        c1_work_config_select = self.ids.c1_work_config_select.text
        if not c1_work_config_select:
            errors.append(
                ('c1_work_config_select', 'no_select_error_message')
            )

        c1_folder_select = self.ids.c1_folder_select
        c1_folder_select_text = c1_folder_select.text
        if not c1_folder_select_text:
            errors.append(('c1_folder_select', 'no_select_error_message'))

        # Show all errors (if any)
        for error_id, error_message in errors:
            self._show_validation_error(
                widget_id=error_id, error_message=error_message)

        if errors:
            return

        self.on_folder_select_text(c1_folder_select)


class ImageItem(BoxLayout):
    """Widget representing an individual image item with selection options.

    Displays an image with radio button options for categorizing it as
    training data, check data, or defect data. Includes delete functionality
    and supports data binding for dynamic updates.
    """
    # Properties for data binding
    source = StringProperty('')
    alt_text = StringProperty('')
    item_id = StringProperty('')
    selected_option = StringProperty('0')

    # Callbacks
    on_delete = ObjectProperty(None)
    on_option_change = ObjectProperty(None)

    # Class-level cached texts - created only once
    _cached_texts = None
    _text_update_needed = True

    @classmethod
    def update_cached_texts(cls):
        """Update cached radio button texts - only called when language changes"""
        app = App.get_running_app()
        cls._cached_texts = [
            {'value': '0', 'text': app.lang.get('usage_train_C1')},
            {'value': '1', 'text': app.lang.get('usage_check_C1')},
            {'value': '2', 'text': app.lang.get('usage_defect_C1')}
        ]
        cls._text_update_needed = True

    @classmethod
    def reset_text_update_flag(cls):
        """Reset the text update flag after all items have been updated"""
        cls._text_update_needed = False

    @classmethod
    def get_cached_texts(cls):
        """Get cached texts, update if needed"""
        if cls._cached_texts is None:
            cls.update_cached_texts()
        return cls._cached_texts

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.popup = MyPopup()
        self.app = App.get_running_app()
        self.radio_widgets = {}

        # Set default selection if not set
        if not self.selected_option:
            self.selected_option = '0'

        Clock.schedule_once(self._post_init)

    def _post_init(self, dt):
        """Create radio buttons only once"""
        # Get cached texts
        cached_texts = ImageItem.get_cached_texts()

        # Create radio buttons once
        for option in cached_texts or []:
            radio = Factory.FormCheckBox(
                text=option['text'],
                font_size_checkbox=dp(13.6),
                group=f'group_{self.item_id}',
                active=self.selected_option == option['value'],
                size_hint_y=None,
                height=dp(20),
                spacing=dp(10)
            )

            # Store reference
            self.radio_widgets[option['value']] = radio

            # Bind active property change
            radio.bind(active=lambda widget, active, value=option['value']:
                       self.on_radio_select(value) if active else None)

            self.ids.radio_container.add_widget(radio)

    def update_radio_texts_if_needed(self):
        """Only update text when necessary (when language changes)"""
        if not ImageItem._text_update_needed:
            return

        cached_texts = ImageItem.get_cached_texts()

        # Update existing radio button texts
        for option in cached_texts or []:
            if option["value"] in self.radio_widgets:
                self.radio_widgets[option["value"]].text = option["text"]

    def on_radio_select(self, value):
        """Handle when a radio button is selected"""
        if self.selected_option != value:
            self.selected_option = value
            if self.on_option_change is not None:
                self.on_option_change(value)

    def get_label_from_source(self):
        """Extract label from filename using the specified pattern"""
        if not self.source:
            return None

        try:
            # Get filename from path
            filename = os.path.basename(self.source)

            name = filename.rsplit('.', 1)[0]
            parts = name.split('_')
            if len(parts) == 4:
                return parts[-1]
            return None
        except (IndexError, AttributeError):
            return None

    def on_delete_press(self):
        """Handle when delete button is pressed"""
        def on_confirm():
            """Callback when user confirms deletion"""
            if self.on_delete is not None:
                self.on_delete()
            return True
        # Show confirmation popup
        confirmation_popup = self.popup.create_confirmation_popup(
            title='confirm_popup',
            message='delete_image_popup',
            on_confirm=on_confirm
        )
        confirmation_popup.open()


class ImageAlbum(CustomScrollView):  # pylint: disable=too-many-instance-attributes
    """
    A scrollable image album widget with lazy loading support.

    This widget displays images in a grid layout and implements lazy loading
    to efficiently handle large numbers of images. It loads images in batches
    as the user scrolls, improving performance and memory usage.

    Attributes:
        items: List of currently loaded image items
        all_image_data: Complete list of all image data to be displayed
        loaded_count: Number of images currently loaded
        items_per_batch: Number of images to load per batch (default: 15)
        is_loading: Flag to prevent multiple simultaneous loads
        content_layout: GridLayout containing the image widgets
    """
    items = ListProperty([])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.scroll_type = ['bars']  # Only scroll using bars
        self.bar_width = dp(9)      # Scroll bar width
        self.effect_cls = "ScrollEffect"  # Basic scroll effect
        # Lazy loading properties
        self.all_image_data = []  # Store all image data
        self.loaded_count = 0     # Number of images currently loaded
        self.items_per_batch = 15  # Load 15 images at a time
        self.is_loading = False   # Prevent multiple simultaneous loads
        self.last_scroll_y = 1.0  # Track last scroll position
        self.is_showing_no_data = False  # Track no-data message display state

        # Scroll position check timer
        self.scroll_check_event = None

        # Streaming properties
        self.is_first_batch = True  # Track first batch to avoid streaming

        self.content_layout = GridLayout(
            cols=5,
            spacing=dp(15),
            padding=dp(10),
            size_hint_y=None,
        )
        self.content_layout.bind(
            minimum_height=self.content_layout.setter('height'))
        self.add_widget(self.content_layout)

        self.content_layout.bind(
            height=lambda *a: Clock.schedule_once(
                lambda dt: (self._update_bar(), self._show_scrollbar(),
                            self._schedule_hide_scrollbar()), 0
            )
        )

        # Bind scroll event for lazy loading
        self.bind(scroll_y=self._on_scroll)

        # Start continuous scroll position checking
        self._start_scroll_position_monitoring()

        self.show_no_data_message()

    def _on_scroll(self, instance, scroll_y):
        """Handle scroll event for lazy loading with debouncing"""
        if self.is_loading or not self.all_image_data:
            return

        # Add debouncing to prevent too frequent triggers
        if hasattr(self, '_scroll_trigger'):
            self._scroll_trigger.cancel()

        self._scroll_trigger = Clock.schedule_once(
            lambda dt: self._check_load_more(scroll_y), 0.01
        )

    def _check_load_more(self, scroll_y):
        """Check if we need to load more images"""
        # Only trigger when scrolling down and reaching near bottom
        if (scroll_y < self.last_scroll_y and  # Scrolling down
            scroll_y <= 0.03 and  # Increased threshold for earlier loading
                self.loaded_count < len(self.all_image_data)):  # More items to load

            # Simplified trigger condition
            remaining_items = len(self.all_image_data) - self.loaded_count
            if remaining_items > 0:
                self._load_next_batch()

        self.last_scroll_y = scroll_y

    def _start_scroll_position_monitoring(self):
        """Start continuous scroll position monitoring"""
        self._stop_scroll_position_monitoring()  # Stop any existing monitoring
        # Check every 0.5 seconds
        self.scroll_check_event = Clock.schedule_interval(
            self._continuous_scroll_check, 0.5
        )

    def _stop_scroll_position_monitoring(self):
        """Stop scroll position monitoring"""
        if self.scroll_check_event:
            self.scroll_check_event.cancel()
            self.scroll_check_event = None

    def stop_monitoring(self):
        """Stop scroll position monitoring - public interface"""
        self._stop_scroll_position_monitoring()

    def cancel_lazy_loading(self):
        """Immediately cancel any ongoing lazy loading"""
        self.is_loading = False

        self._cancel_load = True

        if hasattr(self, '_load_chunks') and isinstance(self._load_chunks, list):
            self._load_chunks.clear()
        if hasattr(self, '_load_chunk_index'):
            self._load_chunk_index = 0

        if hasattr(self, '_next_chunk_ev') and self._next_chunk_ev:
            try:
                self._next_chunk_ev.cancel()
            except Exception:
                pass
            self._next_chunk_ev = None
        if hasattr(self, '_force_layout_ev') and self._force_layout_ev:
            try:
                self._force_layout_ev.cancel()
            except Exception:
                pass
            self._force_layout_ev = None

    def _continuous_scroll_check(self, dt):
        """Continuously check scroll position - independent from image loading logic"""
        # Only check when not in no-data state and there is data to load
        if self.is_showing_no_data or not self.all_image_data:
            return True  # Continue the timer

        # There is still unloaded data
        has_unloaded_data = self.loaded_count < len(self.all_image_data)

        if has_unloaded_data:
            # Check two cases that need adjustment:
            # 1. Scroll is at the top (>= 0.99)
            # 2. Scroll is at the bottom or negative (<= 0.0)
            if self.scroll_y >= 0.99:
                # At the top but still has unloaded data
                pass
            elif self.scroll_y <= 0.03:
                # At the bottom or negative but still has unloaded data
                self.scroll_y = 0.05

        return True  # Continue the timer

    def _on_size_change(self, instance, size):
        """Handle size changes and check if scroll position needs adjustment"""
        if self.is_showing_no_data or not self.all_image_data:
            return

        # Schedule a check after layout is updated
        Clock.schedule_once(self._check_scroll_position, 0.1)

    def _check_scroll_position(self, dt):
        """Check if scroll position needs adjustment due to unloaded data"""
        if (self.loaded_count < len(self.all_image_data) and
                self.scroll_y >= 0.99):  # At top but still has unloaded data

            # Calculate how much content we should have
            total_items = len(self.all_image_data)
            loaded_items = len(self.items)

            if loaded_items < total_items:
                # Adjust scroll position to allow scrolling down
                # Move slightly away from top to enable scroll detection
                self.scroll_y = 0.95

                # Also trigger a load check
                Clock.schedule_once(lambda dt: self._load_next_batch(), 0.1)

    def _load_next_batch(self):
        """Load the next batch of images with optimization"""
        if self.is_loading or self.loaded_count >= len(self.all_image_data):
            return

        self.is_loading = True

        # Calculate the range for next batch
        start_idx = self.loaded_count
        end_idx = min(start_idx + self.items_per_batch,
                      len(self.all_image_data))

        # Pre-filter valid images to reduce UI blocking
        valid_images = []
        for i in range(start_idx, end_idx):
            image_data = self.all_image_data[i]
            # Quick check without blocking UI
            if self._is_valid_image_path(image_data['source']):
                valid_images.append(image_data)

        # Update loaded count immediately
        self.loaded_count = end_idx

        # Load images in smaller chunks to prevent UI blocking
        if valid_images:
            self._load_images_chunked(valid_images)
        else:
            self.is_loading = False

    def _is_valid_image_path(self, path):
        """Quick path validation without heavy file operations"""
        try:
            # Quick checks first
            if not path or not isinstance(path, str):
                return False

            # Check if path format is reasonable
            if not path.lower().endswith('.png'):
                return False

            # Only do file existence check if path seems valid
            return os.path.isfile(path)
        except Exception:
            return False

    def _load_images_chunked(self, valid_images):
        """Load images in small chunks to prevent UI blocking"""
        if not valid_images or len(valid_images) <= 0:
            self.is_loading = False
            return

        if self.is_first_batch:
            chunk_size = len(valid_images)  # Load all at once for first batch
            self.is_first_batch = False
        else:
            chunk_size = 1  # Streaming: Load 1 image at a time for subsequent batches

        chunks = [valid_images[i:i + chunk_size]
                  for i in range(0, len(valid_images), chunk_size)]

        self._load_chunk_index = 0
        self._load_chunks = chunks

        self._cancel_load = False

        if hasattr(self, '_next_chunk_ev') and self._next_chunk_ev:
            try:
                self._next_chunk_ev.cancel()
            except Exception:
                pass
            self._next_chunk_ev = None
        if hasattr(self, '_force_layout_ev') and self._force_layout_ev:
            try:
                self._force_layout_ev.cancel()
            except Exception:
                pass
            self._force_layout_ev = None

        self._load_next_chunk()

    def _load_next_chunk(self):
        """Load the next chunk of images"""
        if getattr(self, '_cancel_load', False) or not self.is_loading:
            return

        if (not hasattr(self, '_load_chunks') or not self._load_chunks or
                self._load_chunk_index >= len(self._load_chunks)):
            self.is_loading = False

            if not getattr(self, '_cancel_load', False):
                try:
                    self._force_layout_ev = Clock.schedule_once(
                        lambda dt: self._force_layout_update(), 0.05)
                except Exception:
                    pass
            return

        chunk = self._load_chunks[self._load_chunk_index]

        # Load this chunk
        for image_data in chunk:
            if getattr(self, '_cancel_load', False):
                return
            self._add_image_item(
                source=image_data['source'],
                alt_text=image_data.get('alt_text', ''),
                item_id=image_data.get('id'),
                selected_option=image_data.get('selected_option')
            )

        self._load_chunk_index += 1

        if getattr(self, '_cancel_load', False):
            return

        # Schedule next chunk with different delays
        try:
            if len(self._load_chunks) == 1:
                # First batch: no delay
                self._next_chunk_ev = Clock.schedule_once(
                    lambda dt: self._load_next_chunk(), 0.01)
            else:
                # Streaming batches: slower delay for visual effect
                self._next_chunk_ev = Clock.schedule_once(
                    lambda dt: self._load_next_chunk(), 0.1)
        except Exception:
            pass

    def _add_image_item(self, source, alt_text='', item_id=None, selected_option=None):
        """Add a single image item to the album (optimized)"""
        item = ImageItem(
            source=source,
            alt_text=alt_text,
            item_id=item_id or str(len(self.items)),
            size_hint_x=None,
            width=dp(294)
        )

        # Set selected_option if provided
        if selected_option is not None:
            item.selected_option = selected_option

        item.on_delete = lambda: self.remove_image(item)
        item.on_option_change = lambda value: self.on_image_option_change(
            item, value)

        self.items.append(item)
        self.content_layout.add_widget(item)

    def show_no_data_message(self):
        """Display no data message"""
        self.content_layout.clear_widgets()
        self.is_showing_no_data = True
        self.all_image_data.clear()
        self.items.clear()
        self.loaded_count = 0

        # Stop scroll monitoring when no data
        self._stop_scroll_position_monitoring()

        # Disable scroll when there's no data
        self.do_scroll_x = False
        self.do_scroll_y = False

        # Reset layout for content_layout to center the label
        self.content_layout.cols = 1
        self.content_layout.size_hint_y = 1
        self.content_layout.height = self.height
        self.content_layout.padding = 0
        self.content_layout.spacing = 0

        # Create notification label
        label = KeyLabel(
            text_key='no_data_placeholder',
            halign='center',
            valign='middle',
            color=[0.6, 0.6, 0.6, 1],
            font_size=dp(20),
            size_hint=(1, 1),
            height=self.height,
            text_size=(None, None)
        )
        label.bind(size=lambda instance, value: setattr(
            instance, 'text_size', value))
        self.content_layout.add_widget(label)

    def add_image(self, source, alt_text='', item_id=None):
        """Add a new image to the album (kept for backward compatibility)"""
        # Store the image data for lazy loading
        image_data = {
            'source': source,
            'alt_text': alt_text,
            'id': item_id or str(len(self.all_image_data))
        }
        self.all_image_data.append(image_data)

        # If this is the first image, setup for lazy loading
        if len(self.all_image_data) == 1:
            self.content_layout.clear_widgets()
            # Enable scroll when there are images
            self.do_scroll_x = False
            self.do_scroll_y = True

            # Reset layout properties
            self.content_layout.cols = getattr(self, 'cols_number', 5)
            self.content_layout.size_hint_y = None
            self.content_layout.padding = dp(10)
            self.content_layout.spacing = dp(15)

        # Load first batch if we haven't loaded anything yet
        if self.loaded_count == 0:
            self._load_next_batch()

    def load_images_lazy(self, image_data_list):
        """Load image list into album with lazy loading (optimized)"""
        # Clear data but don't show no-data message yet
        self.content_layout.clear_widgets()
        self.items.clear()
        self.all_image_data.clear()
        self.loaded_count = 0
        self.is_loading = False
        self.last_scroll_y = 1.0
        self.is_showing_no_data = False

        # Cancel any pending scroll triggers
        if hasattr(self, '_scroll_trigger'):
            self._scroll_trigger.cancel()

        if not image_data_list:
            self.show_no_data_message()
            return

        # Store all image data
        self.all_image_data = image_data_list.copy()
        self.loaded_count = 0
        self.last_scroll_y = 1.0
        self.is_first_batch = True  # Reset first batch flag

        # Setup layout for images (not no-data message)
        self.content_layout.cols = 5
        self.content_layout.size_hint_y = None
        self.content_layout.padding = dp(10)
        self.content_layout.spacing = dp(15)

        self.do_scroll_x = False
        self.do_scroll_y = True

        # Load first batch with delay to allow UI to settle
        Clock.schedule_once(lambda dt: self._load_next_batch(), 0.1)

        # Scroll to top
        self.scroll_x = 0
        self.scroll_y = 1.0

        # Start scroll monitoring for this new data
        self._start_scroll_position_monitoring()

    def _force_layout_update(self):
        """Force update layout for all image items (optimized)"""
        # Batch layout updates
        self.content_layout.do_layout()

        # Update only visible items to reduce lag
        # Only update recently added items
        for item in self.items[-self.items_per_batch:]:
            if hasattr(item, 'ids') and 'radio_container' in item.ids:
                item.ids.radio_container.do_layout()
            item.canvas.ask_update()

    def _load_replacement_image(self):
        """Load next unloaded image to replace a deleted one"""
        # Check if there are unloaded images remaining
        if self.loaded_count >= len(self.all_image_data):
            return

        # Find next unloaded image starting from loaded_count index
        # Since we maintain loaded_count = len(items), and items can be deleted,
        # we need to find the first image in all_image_data that's not in items
        loaded_ids = {item.item_id for item in self.items}
        
        # Start searching from the position after currently loaded items
        # This is more efficient than always starting from index 0
        for image_data in self.all_image_data:
            image_id = image_data.get('id')
            if image_id not in loaded_ids:
                # Found an unloaded image, validate and load it
                if self._is_valid_image_path(image_data['source']):
                    self._add_image_item(
                        source=image_data['source'],
                        alt_text=image_data.get('alt_text', ''),
                        item_id=image_id,
                        selected_option=image_data.get('selected_option')
                    )
                    # Update loaded count
                    self.loaded_count = len(self.items)
                    
                    # Force layout update to ensure scrollbar visibility
                    Clock.schedule_once(lambda dt: self._force_layout_update(), 0.05)
                    return  # Exit after loading one replacement
                # If invalid, continue to next image


    def remove_image(self, item):
        """Remove an image from the album"""
        if item in self.items:
            file_path = item.source
            item_id = item.item_id
            
            # Remove from display
            self.items.remove(item)
            self.content_layout.remove_widget(item)

            # Remove from all_image_data - optimized in-place removal
            # Instead of creating a new list, find and remove the specific item
            for i, img_data in enumerate(self.all_image_data):
                if img_data.get('id') == item_id:
                    del self.all_image_data[i]
                    break

            if os.path.exists(file_path):
                os.remove(file_path)
                print(f"Deleted file: {file_path}")

            # Update loaded count to reflect current loaded items
            self.loaded_count = len(self.items)

            # If no images remain, show notification
            if not self.items:
                self.show_no_data_message()
            else:
                # Load next unloaded image to replace the deleted one
                self._load_replacement_image()

    def on_image_option_change(self, item, value):
        """Handle when radio option of an image changes"""
        print(f"Image {item.item_id} changed to {value}")

    def get_selected_data(self):
        """Get data of all images and their selections"""
        return [{
            'id': item.item_id,
            'source': item.source,
            'selected_option': item.selected_option
        } for item in self.items]

    def get_all_selected_data(self):
        """
        Get data of all images (including those not yet loaded as widgets).
        If image has loaded widget, get actual usage_type, otherwise default to '0'.
        """
        selected_map = {
            item.item_id: item.selected_option for item in self.items}
        result = []
        for img in self.all_image_data:
            selected_option = selected_map.get(
                img.get('id'), img.get('selected_option', '0') or '0')
            result.append({
                'id': img.get('id'),
                'source': img.get('source'),
                'selected_option': selected_option
            })
        return result

    def clear(self):
        """Clear all images in the album"""
        # Stop scroll monitoring
        self._stop_scroll_position_monitoring()

        self.content_layout.clear_widgets()
        self.items.clear()
        self.all_image_data.clear()
        self.loaded_count = 0
        self.is_loading = False
        self.last_scroll_y = 1.0
        self.is_first_batch = True  # Reset first batch flag
        self.show_no_data_message()
