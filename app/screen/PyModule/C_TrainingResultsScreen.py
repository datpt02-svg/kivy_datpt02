"""C3 Screen"""
import os
import re
import hashlib
import traceback
import weakref
import gc
from contextlib import contextmanager
import subprocess

from kivy.app import App
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.logger import Logger
from kivy.metrics import dp
from kivy.properties import ListProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.scrollview import ScrollView
from kivy.uix.image import AsyncImage

from app.env import BE_FOLDER, DATASETS_FOLDER, FAST_FLOW_BACKBONE, HEATMAP_PATH, INI_PATH

from app.libs.constants.default_values import DefaultAnimation, DefaultValuesC3
from app.libs.widgets.components import FormScreen, KeyLabel, MyPopup, cursor_manager
from app.libs.widgets.hover_behavior import HoverBehavior

from app.screen.PyModule.C_ModelTrainingScreen import LearnMethod
from app.screen.PyModule.utils.cli_manager import CLIManager
from app.screen.PyModule.utils.delete_images_in_folders import delete_images_in_folders
from app.screen.PyModule.utils.propagating_thread import PropagatingThread

from app.services.trained_models import update_trained_model

from db.models.datasets import Datasets
from db.models.trained_models import TrainedModels

from db.session import get_db


def _clean_input_value(t):
    """
    Clean the input string
    """
    return t.lstrip('0') or '0' if t and t.isdigit() else t

class TrainingResultsScreen(FormScreen, CLIManager):  # pylint: disable=too-many-instance-attributes
    """Screen for displaying and managing training results and validation.

    This screen allows users to:
    - View trained models and their associated datasets
    - Configure validation parameters (blur, min area, threshold, event intensity)
    - Run validation on trained models
    - Display validation results as image albums
    - Export and explore validation results
    """

    def set_left_mouse_disabled(self, disabled: bool):
        """Enable/disable left mouse functionality"""
        if disabled:
            self.disable_click(
                all_widget=True,
                allow_widget=[self.ids.window_explore_button]
            )
        else:
            self.enable_click()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.popup = MyPopup()
        self.preview_popup = None
        self.app = App.get_running_app()
        self.display_to_model_dataset = {}
        self._received_generate_data = False
        self._heatmap_generated = False
        self._heatmap_file_hashes = {}
        self.validated_parameters = None
        self.current_export_dir = None
        self._preview_params_cache = {}
        self._last_validation_params = {}
        Clock.schedule_once(self._post_init)

    def handle_pipe_error(self, error_message):
        """Handle pipe communication errors by dismissing loading popup and showing error message.

        Args:
            error_message: The error message to display to the user.
        """
        if self.loading_popup:
            self.loading_popup.opacity = 0
            self.loading_popup.dismiss()
            self.loading_popup = None
        self.__show_popup(
            title='error_popup',
            message=error_message
        )

    def on_pipe(self, obj):
        """Handle pipe messages for streaming training result images.

        Args:
            obj: Dictionary containing status_code, data, and message from the pipe.
                 - 'D017': Image data received, load and display the image
                 - 'D018' or 'End Generate Data': Generation complete
        """
        if obj.get('status_code') == 'D017' and obj.get('data'):
            if not self._received_generate_data:
                self.image_album.clear(show_no_data_message=False)

            if self.loading_popup and getattr(self.loading_popup, 'process', None) == 'validation':
                self.loading_popup.opacity = 0
                self.loading_popup.dismiss()
                self.loading_popup = None
                self.set_left_mouse_disabled(True)

            self.image_album.load_stream_images(
                image_path=obj.get('data').get('thumbnail_path'),
            )

            self._received_generate_data = True

        if obj.get('status_code') == 'D018':
            if self.loading_popup and getattr(self.loading_popup, 'process', None) == 'validation':
                self.loading_popup.opacity = 0
                self.loading_popup.dismiss()
                self.loading_popup = None

            # When receiving stop signal, check if any images have been received
            if not self._received_generate_data:
                self.image_album.clear()

            self.__show_popup(
                title='notification_popup',
                message='done_popup_message'
            )

            # Reset image receiving state for next time
            self._received_generate_data = False
            self.set_left_mouse_disabled(False)

        if obj.get('status_code') == 'E001':
            self.handle_pipe_error(error_message='validate_failed_C3')
            self._received_generate_data = False
            self.set_left_mouse_disabled(False)

        if obj.get('status_code') == 'E002':
            self.handle_pipe_error(error_message='ini_error_message_E2')
            self._received_generate_data = False
            self.set_left_mouse_disabled(False)

        if obj.get('status_code') == 'D026' and obj.get('data'):
            if self.loading_popup and getattr(self.loading_popup, 'process', None) == 'preview':
                self.loading_popup.opacity = 0
                self.loading_popup.dismiss()
                self.loading_popup = None
            if self.preview_popup:
                self.preview_popup._load_image_to_preview_popup(image_path=obj.get('data')) # pylint: disable=protected-access
                # Update label with current parameters after successful preview
                try:
                    if hasattr(self.preview_popup, 'c3_section') and hasattr(self.preview_popup, '_old_result_label'):
                        params = {
                            'blur': self.preview_popup.c3_section.ids.c3_blur_input.ids.input_box.text,
                            'min_area': self.preview_popup.c3_section.ids.c3_min_area_input.ids.input_box.text,
                            'threshold': self.preview_popup.c3_section.ids.c3_threshold_slider.ids.input_box.text,
                            'event_intensity': self.preview_popup.c3_section.ids.c3_event_intensity.ids.input_box.text
                        }
                        # Update format_args to trigger text update
                        self.preview_popup._old_result_label.format_args = params # pylint: disable=protected-access
                        self.preview_popup._validated_parameters = params # pylint: disable=protected-access
                except Exception:
                    traceback.print_exc()

        if obj.get('status_code') == 'D027':
            if self.loading_popup and getattr(self.loading_popup, 'process', None) == 'preview':
                self.loading_popup.opacity = 0
                self.loading_popup.dismiss()
                self.loading_popup = None

        if obj.get('status_code') == 'D032' and obj.get('data'):
            npy_path = obj.get('data')
            if isinstance(npy_path, str) and os.path.isfile(npy_path):
                self._heatmap_file_hashes[npy_path] = self._hash_file(npy_path)
            self._heatmap_generated = True

        if obj.get('status_code') == 'D033':
            if self.loading_popup and getattr(self.loading_popup, 'process', None) == 'heatmap':
                self.loading_popup.opacity = 0
                self.loading_popup.dismiss()
                self.loading_popup = None

    def _post_init(self, dt):
        """Initialize the validation image album widget after screen setup.

        Args:
            _dt: Delta time from Clock.schedule_once (unused but required by Kivy)
        """
        self.image_album = ValidationAlbum()
        self.ids.image_album_container.add_widget(self.image_album)

    def __show_popup(self, title, message):
        def _show(dt):
            if self.popup:
                self.popup.create_adaptive_popup(
                    title=title,
                    message=message
                ).open()
        Clock.schedule_once(_show, 0)

    def _check_thread(self, dt, thread, expected_popup=None):
        '''Check if the subprocess thread return/raise errors'''
        if thread.is_finished():
            try:
                _ = thread.result()
                self.set_left_mouse_disabled(False)
                if self.loading_popup and (expected_popup is None or self.loading_popup == expected_popup):
                    self.loading_popup.opacity = 0
                    self.loading_popup.dismiss()
                    self.loading_popup = None
            except Exception as e:
                traceback.print_exc()
                self.set_left_mouse_disabled(False)
                if self.loading_popup and (expected_popup is None or self.loading_popup == expected_popup):
                    self.loading_popup.opacity = 0
                    self.loading_popup.dismiss()
                    self.loading_popup = None
                self.__show_popup(title="error_popup", message=f"Error: {e}")
            return False
        return True

    def _load_validation_results(self, evaluation_dir, include_subfolders=False):
        """Load validation result images from saved export_dir
        Args:
            include_subfolders (bool): If True, traverse subfolders too, default is False (only traverse root folder)
        """
        try:
            image_extensions = ['.png']
            image_data_list = []

            if os.path.exists(evaluation_dir):
                if include_subfolders:
                    for root, _, files in os.walk(evaluation_dir):
                        current_root = root
                        files.sort(key=lambda f, r=current_root: (
                            os.path.getmtime(os.path.join(r, f)), f))
                        for file in files:
                            if any(file.lower().endswith(ext) for ext in image_extensions):
                                image_path = os.path.join(root, file)
                                relative_path = os.path.relpath(
                                    image_path, evaluation_dir)
                                image_data_list.append({
                                    'source': image_path,
                                    'alt_text': file,
                                    'id': relative_path.replace(os.sep, '_')
                                })

                else:
                    files = [file for file in os.listdir(evaluation_dir)
                             if os.path.isfile(os.path.join(evaluation_dir, file)) and
                             any(file.lower().endswith(ext) for ext in image_extensions)]
                    files.sort(key=lambda f: (os.path.getmtime(
                        os.path.join(evaluation_dir, f)), f))
                    for file in files:
                        file_path = os.path.join(evaluation_dir, file)
                        image_data_list.append({
                            'source': file_path,
                            'alt_text': file,
                            'id': file.replace(os.sep, '_')
                        })

            # Load images into album with lazy loading
            if image_data_list:
                self.image_album.load_images_lazy(image_data_list)
                Logger.debug("Loaded %s images from validation results", len(image_data_list))
            else:
                self.image_album.show_no_data_message()

        except Exception:
            traceback.print_exc()

    def reload_validation_album(self):
        """Clear the validation album UI and reload images from the export folder sorted by date modified ascending."""
        try:
            # Check if album has any images (works for both streamed and lazy-loaded)
            # Check for any ValidationItem in content_layout - works for stream, lazy-load, and cleared states
            has_images = any(isinstance(c, ValidationItem) for c in self.image_album.content_layout.children)

            if not has_images:
                return

            validation_folder = self.form_mapping['folder_displaying'].directory_path

            if not validation_folder or not validation_folder.strip():
                return

            thumbnail_folder = os.path.join(validation_folder, 'thumbnail')

            # Reload the album
            self.image_album.clear()
            self._load_validation_results(evaluation_dir=thumbnail_folder)
        except Exception:
            traceback.print_exc()

    def scroll_screen_c3_to_default(self):
        """Scroll the training results screen (C3) to the default top position."""
        try:
            # Assume ScrollView of screen C3 has id 'scroll_screen_C3_training_results'
            scroll_view = self.ids.get(
                'scroll_screen_C3_training_results', None)
            if not scroll_view:
                print("ScrollView with id 'scroll_screen_C3_training_results' not found")
                return

            def apply_scroll(*args):
                scroll_view.scroll_y = 1.0

            Clock.schedule_once(apply_scroll, 0.1)
        except Exception:
            traceback.print_exc()

    def on_kv_post(self, base_widget):
        # Bind validation for threshold slider
        self.form_mapping = {
            "c3_dataset_select": self.ids.c3_dataset_select,
            "c3_settings_section": self.ids.c3_settings_section,
            "c3_blur_input": self.ids.c3_settings_section.ids.c3_blur_input.ids.input_box,
            "c3_min_area_input": self.ids.c3_settings_section.ids.c3_min_area_input.ids.input_box,
            "c3_threshold_slider": self.ids.c3_settings_section.ids.c3_threshold_slider.ids.input_box,
            "c3_event_intensity": self.ids.c3_settings_section.ids.c3_event_intensity.ids.input_box,
            "folder_displaying": self.ids.folder_displaying,
            "create_heatmap_error": self.ids.create_heatmap_error
        }

        return super().on_kv_post(base_widget)

    def on_pre_enter(self, *args):
        """Called when entering the screen"""
        self.scroll_screen_c3_to_default()
        self.clear_error_messages()
        self.reset_screen_c3()
        delete_images_in_folders(folder_paths=[HEATMAP_PATH], delete_npy=True)
        self._display_results()

    def _display_results(self):
        try:
            with get_db() as db:
                results = db.query(TrainedModels, Datasets) \
                    .join(Datasets, TrainedModels.dataset_id == Datasets.id) \
                    .filter(TrainedModels.deleted_at.is_(None)) \
                    .filter(Datasets.deleted_at.is_(None)) \
                    .filter(Datasets.is_trained.is_(True)) \
                    .order_by(TrainedModels.created_at.desc()) \
                    .all()

                display_values = []
                self.display_to_model_dataset.clear()
                for trained_model, dataset in results:
                    display_str = f'{trained_model.name} ({dataset.name})'
                    display_values.append(display_str)
                    self.display_to_model_dataset[display_str] = (
                        trained_model.name, dataset.name)

                self.form_mapping['c3_dataset_select'].values = display_values
        except Exception:
            self.form_mapping['c3_dataset_select'].values = []
            traceback.print_exc()

    def clear_error_messages(self):
        """Clear all validation error messages"""
        self.form_mapping['c3_dataset_select'].error_message = ""

        self.form_mapping['c3_blur_input'].error_message = ""

        self.form_mapping['c3_min_area_input'].error_message = ""

        self.form_mapping['c3_threshold_slider'].error_message = ""

        self.form_mapping['c3_event_intensity'].error_message = ""

        self.form_mapping['create_heatmap_error'].error_message = ""

    def reset_screen_c3(self):
        """Reset all C3 screen input fields to their default values."""
        self.form_mapping['c3_dataset_select'].text = DefaultValuesC3.C3_DATASET_SELECT

        self.form_mapping['c3_blur_input'].text = DefaultValuesC3.C3_BLUR_INPUT

        self.form_mapping['c3_min_area_input'].text = DefaultValuesC3.C3_MIN_AREA_INPUT

        self.form_mapping['c3_threshold_slider'].text = DefaultValuesC3.C3_THRESHOLD_INPUT

        self.form_mapping['c3_event_intensity'].text = DefaultValuesC3.C3_EVENT_INTENSITY_INPUT

        self.form_mapping['folder_displaying'].directory_path = os.path.join(
            r"\datasets", "{work_config_id}", "{dataset_name}", "{model_name}", "evaluation", "")
        self.image_album.clear()

    def _show_validation_error(self, widget_id, error_message):
        self.ids[widget_id].error_message = error_message

    def find_screen_manager(self, widget, visited=None):
        """
        Recursively search for a ScreenManager widget in the widget tree.

        Args:
            widget: The widget to start searching from.
            visited: Set of already visited widget IDs to prevent infinite loops.

        Returns:
            ScreenManager instance if found, None otherwise.
        """
        if visited is None:
            visited = set()

        if id(widget) in visited:
            return None
        visited.add(id(widget))

        if isinstance(widget, ScreenManager) or (
            hasattr(widget, 'current') and hasattr(widget, 'screens')
        ):
            return widget

        # Search in children
        for child in widget.children:
            result = self.find_screen_manager(child, visited)
            if result:
                return result
        return None

    def navigate_to_error(self, target_screen, reference_id):
        """Navigate to a specific screen and scroll to an error widget.

        Args:
            target_screen: The name of the target screen to navigate to
            reference_id: The reference ID of the error widget to scroll to
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
        """Scroll target_widget to center of ScrollView along Y axis."""

        def _scroll_to_center(*_):
            content = scroll_view.children[0] if scroll_view.children else None
            if not content:
                print("⚠️ ScrollView has no content")
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

    def _validate_inputs(self, mode=None):
        """1. Validate all inputs

        Args:
            mode: 'npy' - validate dataset/model selection + weight paths only
                  'validation' - validate dataset selection + heatmap params only
                  None - validate all (backward compatible)
        """
        errors = {}
        first_error_widget_id = None

        # Validate dataset selection (always needed)
        c3_dataset_select = self.form_mapping['c3_dataset_select'].text
        self.form_mapping['c3_dataset_select'].validate_text(c3_dataset_select)

        if self.form_mapping['c3_dataset_select'].error_message:
            if not first_error_widget_id:
                first_error_widget_id = 'c3_dataset_select'

        model_name = None
        dataset_name = None
        if c3_dataset_select:
            try:
                model_name, dataset_name = self.display_to_model_dataset[c3_dataset_select]
            except Exception:
                errors['c3_dataset_select'] = 'no_select_error_message'
                if not first_error_widget_id:
                    first_error_widget_id = 'c3_dataset_select'

        # Validate weight paths (for 'npy' mode or all)
        if mode in (None, 'npy'):
            weight_path_1 = None
            weight_path_2 = None
            if model_name:
                try:
                    with get_db() as db:
                        trained_model = db.query(TrainedModels) \
                            .filter(TrainedModels.name == model_name) \
                            .filter(TrainedModels.deleted_at.is_(None)) \
                            .first()
                        if trained_model:
                            weight_path_1 = trained_model.weight_path_1
                            weight_path_2 = trained_model.weight_path_2
                except Exception:
                    traceback.print_exc()
                    pass # pylint: disable=unnecessary-pass

                if not weight_path_1 or not os.path.isfile(weight_path_1):
                    errors['c3_dataset_select'] = 'file_not_found_error_message'
                    if not first_error_widget_id:
                        first_error_widget_id = 'c3_dataset_select'
                if weight_path_2 and not os.path.isfile(weight_path_2):
                    errors['c3_dataset_select'] = 'file_not_found_error_message'
                    if not first_error_widget_id:
                        first_error_widget_id = 'c3_dataset_select'

        # Validate heatmap params (for 'validation' mode or all)
        c3_blur_input = self.form_mapping['c3_blur_input'].text
        c3_min_area_input = self.form_mapping['c3_min_area_input'].text
        c3_threshold_slider = self.form_mapping['c3_threshold_slider'].text
        c3_event_intensity = self.form_mapping['c3_event_intensity'].text

        if mode in (None, 'validation'):
            self.form_mapping['c3_blur_input'].validate_text(c3_blur_input)
            self.form_mapping['c3_min_area_input'].validate_text(c3_min_area_input)
            self.form_mapping['c3_threshold_slider'].validate_text(c3_threshold_slider)
            self.form_mapping['c3_event_intensity'].validate_text(c3_event_intensity)

        valid = True
        if mode in (None, 'validation'):
            valid = not any(
                widget.error_message for widget in [
                    self.form_mapping['c3_blur_input'],
                    self.form_mapping['c3_min_area_input'],
                    self.form_mapping['c3_threshold_slider'],
                    self.form_mapping['c3_event_intensity'],
                ]
            )

        return errors, {
            'dataset_select': c3_dataset_select,
            'model_name': model_name,
            'dataset_name': dataset_name,
            'blur_input': c3_blur_input,
            'min_area_input': c3_min_area_input,
            'threshold_slider': c3_threshold_slider,
            'event_intensity': c3_event_intensity
        }, first_error_widget_id, valid

    def _validate_parameters(self, params, c3_section=None):
        """1. Validate all parameters

        Args:
            params: Dictionary of parameters to validate
            c3_section: Optional C3SettingsSection widget (for popup validation).
                       If None, uses self.ids.c3_settings_section (main screen)
        """
        errors = {}
        first_error_widget_id = None

        # Use provided c3_section or default to main screen's section
        settings_section = c3_section if c3_section is not None else self.form_mapping['c3_settings_section']

        # Validate blur input
        c3_blur_input = params['blur']
        settings_section.ids.c3_blur_input.ids.input_box.validate_text(c3_blur_input)

        # Validate min area input
        c3_min_area_input = params['min_area']
        settings_section.ids.c3_min_area_input.ids.input_box.validate_text(c3_min_area_input)

        # Validate threshold slider
        c3_threshold_slider = params['threshold']
        settings_section.ids.c3_threshold_slider.ids.input_box.validate_text(c3_threshold_slider)

        # Validate event intensity
        c3_event_intensity = params['event_intensity']
        settings_section.ids.c3_event_intensity.ids.input_box.validate_text(c3_event_intensity)

        valid = not any(
            widget.error_message for widget in [
                settings_section.ids.c3_blur_input.ids.input_box,
                settings_section.ids.c3_min_area_input.ids.input_box,
                settings_section.ids.c3_threshold_slider.ids.input_box,
                settings_section.ids.c3_event_intensity.ids.input_box
            ]
        )
        return errors, {
            'blur_input': c3_blur_input,
            'min_area_input': c3_min_area_input,
            'threshold_slider': c3_threshold_slider,
            'event_intensity': c3_event_intensity
        }, first_error_widget_id, valid

    def _handle_validation_errors(self, errors, first_error_widget_id, mode='validation'):
        """2. Handle validation errors"""
        if errors:
            for error_id, error_message in errors.items():
                self._show_validation_error(error_id, error_message)
            # Show popup and navigate to first error if there are validation errors

            def show_popup_and_navigate(dt):
                def on_popup_dismiss():
                    if first_error_widget_id:
                        self.navigate_to_error(
                            target_screen='screen_C3_training_results',
                            reference_id=first_error_widget_id
                        )
                    self.image_album.clear()

                failure_popup = self.popup.create_adaptive_popup(
                    title='error_popup',
                    message='validate_failed_C3'
                )
                failure_popup.bind(on_dismiss=lambda *args: on_popup_dismiss())
                failure_popup.open()
            if mode == 'validation':
                Clock.schedule_once(show_popup_and_navigate, 0.1)
            return True
        return False

    def _get_validation_data(self, model_name, dataset_name):
        """3. Work with data and database using both model name and dataset name"""
        try:
            with get_db() as db:
                # Get dataset first
                dataset = db.query(Datasets) \
                    .filter(Datasets.name == dataset_name) \
                    .filter(Datasets.is_trained.is_(True)) \
                    .filter(Datasets.deleted_at.is_(None)) \
                    .first()

                if not dataset:
                    raise ValueError(
                        f"Dataset '{dataset_name}' does not exist or has not been trained.")

                # Get trained model by name and dataset_id
                trained_model = db.query(TrainedModels) \
                    .filter(TrainedModels.name == model_name) \
                    .filter(TrainedModels.dataset_id == dataset.id) \
                    .filter(TrainedModels.deleted_at.is_(None)) \
                    .first()

                if not trained_model:
                    raise ValueError(
                        f"Could not find trained model '{model_name}' for dataset '{dataset_name}'.")

                return {
                    'dataset_id': dataset.id,
                    'work_config_id': dataset.work_config_id,
                    'model_name': trained_model.name,
                    'learn_method': trained_model.learn_method,
                    'm1_input_size': trained_model.input_size_1,
                    'm1_patch_size': trained_model.patch_size_1,
                    'm1_weight_path': trained_model.weight_path_1,
                    'm1_engine_path': trained_model.engine_path_1,
                    'm2_input_size': trained_model.input_size_2,
                    'm2_patch_size': trained_model.patch_size_2,
                    'm2_weight_path': trained_model.weight_path_2,
                    'm2_engine_path': trained_model.engine_path_2,
                    'heat_kernel_size': self.form_mapping['c3_blur_input'].text.strip(),
                    'heat_min_area': self.form_mapping['c3_min_area_input'].text.strip(),
                    'heat_threshold': self.form_mapping['c3_threshold_slider'].text.strip(),
                    'heat_min_intensity': self.form_mapping['c3_event_intensity'].text.strip()
                }
        except Exception as e:
            traceback.print_exc()
            raise e

    def _build_npy_command(self, validation_data, test_dir, npy_save_dir):
        """Build command for gen_npy_cli.py"""
        command = [
            '--learn_method', str(validation_data['learn_method']),
            '--data_root', fr'{test_dir}',
            '--save_dir', fr'{npy_save_dir}',
            '--backbone', str(FAST_FLOW_BACKBONE),

            '--m1_input_size', str(validation_data['m1_input_size']),
            '--m1_patch_size', str(validation_data['m1_patch_size']),
            '--m1_weight_path', fr'{validation_data["m1_weight_path"]}',
            '--m1_engine_path', fr'{validation_data["m1_engine_path"]}',

            '--ini_path', INI_PATH,
        ]

        if str(validation_data['learn_method']) == LearnMethod.PARALLEL:
            command += [
                '--m2_input_size', str(validation_data['m2_input_size']),
                '--m2_patch_size', str(validation_data['m2_patch_size']),
                '--m2_weight_path', fr'{validation_data["m2_weight_path"]}',
                '--m2_engine_path', fr'{validation_data["m2_engine_path"]}',
            ]

        return command

    def _build_gen_validation_command(self, validation_data, data_histogram_dir, npy_dir, save_dir, save_dir_preview_image=None):
        """Build command for gen_validation_cli.py"""
        command = [
            '--data_histogram_dir', fr'{data_histogram_dir}',
            '--npy_dir', fr'{npy_dir}',
            '--save_dir', fr'{save_dir}',

            '--heat_kernel_size', str(validation_data['heat_kernel_size']),
            '--heat_min_area', str(validation_data['heat_min_area']),
            '--heat_threshold', str(validation_data['heat_threshold']),
            '--heat_min_intensity', str(validation_data['heat_min_intensity']),

            '--thumbnail_flag', '1',
        ]

        if save_dir_preview_image:
            command += ['--save_dir_preview_image', fr'{save_dir_preview_image}']

        return command

    def _execute_npy_command(self, command):
        """Execute gen_npy_cli.py command"""
        script_path = os.path.join(BE_FOLDER, 'flows', 'fastflow', 'gen_npy_cli.py')
        success = self._run_cli(
            arg_list=command,
            script_path=script_path,
            use_module=False,
            cwd=BE_FOLDER,
            use_pipe_server=True,
        )
        return success, None

    def _execute_gen_validation_command(self, command):
        """Execute gen_validation_cli.py command"""
        script_path = os.path.join(BE_FOLDER, 'flows', 'fastflow', 'gen_heatmap_cli.py')
        success = self._run_cli(
            arg_list=command,
            script_path=script_path,
            use_module=False,
            cwd=BE_FOLDER,
            use_pipe_server=True,
        )
        return success, None

    @contextmanager
    def validation_context(self):
        """Context manager to ensure cleanup of mouse disabled state"""
        self.set_left_mouse_disabled(True)
        self._validation_thread_running = False

        try:
            yield
        except Exception:
            traceback.print_exc()
            self.image_album.clear()
            self.__show_popup(
                title='error_popup',
                message='validate_failed_C3'
            )
            raise
        finally:
            # Only unlock if thread has not been started
            if not getattr(self, '_validation_thread_running', False):
                self.set_left_mouse_disabled(False)

    def create_heatmap(self):
        """Create heatmap (.npy files) using gen_npy_cli.py"""
        self.clear_error_messages()

        # 1. Validate inputs (npy mode - dataset/model + weight paths only)
        validation_errors, input_values, first_error_widget_id, valid = self._validate_inputs(mode='npy')
        if not valid:
            return

        # 2. Handle validation errors
        if self._handle_validation_errors(validation_errors, first_error_widget_id, mode='npy'):
            return

        model_name = input_values.get('model_name')
        dataset_name = input_values.get('dataset_name')
        if not model_name or not dataset_name:
            return

        try:
            # 3. Get data from database
            validation_data = self._get_validation_data(
                model_name, dataset_name)

            # Prepare directories
            test_dir = os.path.join(DATASETS_FOLDER, str(validation_data['work_config_id']),
                                    dataset_name, 'data.txt')

            # 4. Check data.txt content before proceeding
            if not self._validate_data_file(test_dir):
                return

            npy_save_dir = HEATMAP_PATH
            delete_images_in_folders(
                folder_paths=[npy_save_dir],
                delete_npy=True
                )

            # 5. Build and execute npy command
            command = self._build_npy_command(
                validation_data, test_dir, npy_save_dir)

            def run_process():
                Logger.debug("Starting gen_npy CLI execution...")
                success, _ = self._execute_npy_command(command)
                Logger.debug("gen_npy CLI completed with result: %s", success)
                if not success:
                    Logger.error("gen_npy CLI execution failed")

            self.loading_popup = self.popup.create_loading_popup(
                title='loading_popup')
            self.loading_popup.process = 'heatmap'
            self.loading_popup.open()
            current_popup = self.loading_popup
            thread_collect = PropagatingThread(target=run_process)
            thread_collect.start()
            Clock.schedule_interval(
                lambda dt: self._check_thread(dt, thread_collect, current_popup), 0.5)

        except Exception:
            traceback.print_exc()
            self.__show_popup(
                title='error_popup',
                message='create_heatmap_failed_C3'
            )
            return

    def start_validation(self):
        """Main validation function - runs gen_validation_cli.py from .npy files"""
        with self.validation_context():
            self.clear_error_messages()
            self.image_album.clear(show_no_data_message=True)
            self.image_album.do_scroll_x = False
            self.image_album.do_scroll_y = False
            self.image_album.scroll_x = 0
            self.image_album.scroll_y = 1

            # 0. Check heatmap integrity
            if not self._heatmap_generated or not self._verify_heatmap_integrity():
                self.form_mapping['create_heatmap_error'].error_message = 'heatmap_not_created'

            # 1. Validate inputs (validation mode - dataset + heatmap params only)
            validation_errors, input_values, first_error_widget_id, valid = self._validate_inputs(mode='validation')

            if not valid or not self._heatmap_generated or not self._verify_heatmap_integrity():
                return

            self.validated_parameters = {
                'blur': self.form_mapping['c3_blur_input'].text,
                'min_area': self.form_mapping['c3_min_area_input'].text,
                'threshold': self.form_mapping['c3_threshold_slider'].text,
                'event_intensity': self.form_mapping['c3_event_intensity'].text
            }
            # 2. Handle validation errors
            if self._handle_validation_errors(validation_errors, first_error_widget_id):
                return

            model_name = input_values.get('model_name')
            dataset_name = input_values.get('dataset_name')
            if not model_name or not dataset_name:
                return

            try:
                # 3. Get data from database
                validation_data = self._get_validation_data(
                    model_name, dataset_name)

                # Prepare directories
                test_dir = os.path.join(DATASETS_FOLDER, str(validation_data['work_config_id']),
                                        dataset_name, 'data.txt')

                # 4. Check data.txt content before proceeding
                if not self._validate_data_file(test_dir):
                    return

                data_histogram_dir = self._get_histogram_dir_from_data_txt(test_dir)
                if not data_histogram_dir:
                    self.__show_popup(
                        title='error_popup',
                        message='validate_failed_C3'
                    )
                    return
                npy_dir = HEATMAP_PATH
                export_dir = os.path.join(DATASETS_FOLDER, str(validation_data['work_config_id']),
                                          dataset_name, validation_data['model_name'], 'evaluation')
                preview_modal_dir = os.path.join(export_dir, 'preview_modal')
                self.current_export_dir = export_dir

                delete_images_in_folders(
                    folder_paths=[
                        export_dir,
                        os.path.join(export_dir, 'thumbnail'),
                        preview_modal_dir
                        ],
                    )

                # 5. Build and execute gen_validation command
                command = self._build_gen_validation_command(
                    validation_data, data_histogram_dir, npy_dir, export_dir,
                    save_dir_preview_image=preview_modal_dir)

                # Capture baseline parameters for individual previews
                screen_params = self.get_parameterts() or {}
                self._last_validation_params = {
                    **screen_params,
                    'show_bbox': '1',
                    'show_info': '1',
                    'overlay': '0.50'
                }
                self._preview_params_cache = {}  # Clear cache on new validation run
                self._validation_thread_running = True

                def run_process():
                    try:
                        print("Starting gen_validation CLI execution...")
                        success, _ = self._execute_gen_validation_command(command)
                        print(f"gen_validation CLI completed with result: {success}")
                        if not success:
                            print("gen_validation CLI execution failed")
                    finally:
                        print("Finally block executing - thread cleanup")
                        self._validation_thread_running = False

                self.loading_popup = self.popup.create_loading_popup(
                    title='loading_popup')
                self.loading_popup.process = 'validation'
                self.loading_popup.open()
                current_popup = self.loading_popup
                thread_collect = PropagatingThread(target=run_process)
                thread_collect.start()
                Clock.schedule_interval(
                    lambda dt: self._check_thread(dt, thread_collect, current_popup), 0.5)

            except Exception:
                traceback.print_exc()
                self.image_album.clear()
                self.__show_popup(
                    title='error_popup',
                    message='validate_failed_C3'
                )
                return
        # self.current_export_dir = r'D:\project\New folder\2.source\datasets\1\ádasdasd\model_21_01_2026 new\evaluation\thumbnail'
        # self._load_validation_results()
        #TODO: function _load_validation_results ---> load image from folder # pylint: disable=protected-access

    @staticmethod
    def _hash_file(file_path, chunk_size=8192):
        """Compute MD5 hash of a file."""
        h = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    h.update(chunk)
            return h.hexdigest()
        except Exception:
            traceback.print_exc()
            return None

    def _verify_heatmap_integrity(self):
        """Verify that all generated .npy files still exist and are unchanged.

        Returns:
            bool: True if all files exist and hashes match, False otherwise.
        """
        if not self._heatmap_file_hashes:
            return False

        for file_path, original_hash in self._heatmap_file_hashes.items():
            if not os.path.isfile(file_path):
                return False
            if self._hash_file(file_path) != original_hash:
                return False
        return True

    def _get_histogram_dir_from_data_txt(self, data_txt_path):
        """Extract the histogram directory from data.txt.

        Reads the first valid entry in data.txt and returns the parent directory
        of the image path found there.

        Args:
            data_txt_path (str): Path to data.txt file

        Returns:
            str or None: Directory containing histogram images, or None if not found
        """
        try:
            if not os.path.exists(data_txt_path):
                return None

            with open(data_txt_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and '|' in line:
                        parts = line.split('|')
                        if len(parts) >= 2:
                            image_path = parts[0].strip()
                            if image_path and os.path.exists(image_path):
                                return os.path.dirname(image_path)
            return None
        except Exception:
            traceback.print_exc()
            return None

    def _validate_data_file(self, data_file_path):
        """Validate data.txt file content and show appropriate popup"""
        try:
            if not os.path.exists(data_file_path):
                self.__show_popup(
                    title='error_popup',
                    message='validate_failed_C3'
                )
                return False

            has_type_0 = False
            has_other_types = False

            with open(data_file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    if has_type_0 and has_other_types:
                        break
                    line = line.strip()
                    if line and '|' in line:
                        parts = line.split('|')
                        if len(parts) >= 2:
                            try:
                                type_value = int(parts[1].strip())
                                if type_value == 0:
                                    has_type_0 = True
                                else:
                                    has_other_types = True
                            except ValueError:
                                continue

            # Check validation conditions
            if not has_type_0 and not has_other_types:
                # Empty or invalid file
                self.__show_popup(
                    title='error_popup',
                    message='validate_failed_C3'
                )
                return False

            if has_type_0 and not has_other_types:
                self.__show_popup(
                    title='notification_popup',
                    message='validate_only_type_0_C3'
                )
                return False

            return True

        except Exception:
            traceback.print_exc()
            self.__show_popup(
                title='error_popup',
                message='validate_failed_C3'
            )
            return False

    def open_folder(self):
        """Open the current folder in the system file explorer."""
        folder_to_open = self.form_mapping['folder_displaying'].directory_path
        self.open_path_in_explorer(folder_to_open, select_file=False)

    def open_path_in_explorer(self, target_path, select_file=False):
        """Open a path in Windows Explorer, falling back to parent directories if it doesn't exist.
        
        Args:
            target_path: The path to open or select
            select_file: If True, attempts to select the exact file in Explorer. 
                         If the file is missing, falls back to opening the nearest folder.
        """
        try:
            current_path = target_path

            # Fast path for file selection
            if select_file and os.path.exists(os.path.normpath(current_path)):
                subprocess.Popen(f'explorer /select,"{os.path.normpath(current_path)}"')
                return

            # If selecting a file failed or not requested, find the nearest directory
            if select_file and current_path:
                current_path = os.path.dirname(current_path)

            while current_path and not os.path.exists(os.path.normpath(current_path)):
                parent_folder = os.path.dirname(current_path)
                if parent_folder == current_path:
                    break
                current_path = parent_folder

            if not current_path or os.path.normpath(current_path) in ('\\', '/'):
                current_path = DATASETS_FOLDER

            os.startfile(current_path)
        except Exception:
            os.startfile(DATASETS_FOLDER)
            traceback.print_exc()

    def on_dataset_selection_changed(self):
        """Called when dataset selection changes"""
        self._heatmap_generated = False
        self._heatmap_file_hashes = {}
        try:
            selected_text = self.form_mapping['c3_dataset_select'].text
            if not selected_text or selected_text not in self.display_to_model_dataset:
                self.current_export_dir = None
                return

            model_name, dataset_name = self.display_to_model_dataset[selected_text]

            with get_db() as db:
                dataset = db.query(Datasets) \
                    .filter(Datasets.name == dataset_name) \
                    .filter(Datasets.is_trained.is_(True)) \
                    .filter(Datasets.deleted_at.is_(None)) \
                    .first()

                trained_model = db.query(TrainedModels) \
                    .filter(TrainedModels.name == model_name) \
                    .filter(TrainedModels.deleted_at.is_(None)) \
                    .first()

            if not dataset:
                self.current_export_dir = None
                self.form_mapping['folder_displaying'].directory_path = ""
                self.image_album.show_no_data_message()
                return

            if not trained_model:
                self.current_model_id = None

            # Set current_export_dir
            self.current_export_dir = os.path.join(
                DATASETS_FOLDER,
                str(dataset.work_config_id),
                dataset_name,
                model_name,
            )

            self.current_model_id = trained_model.id

            # Update folder display path
            self.form_mapping['folder_displaying'].directory_path = os.path.join(
                f"{self.current_export_dir}", "evaluation", "")

            self.image_album.show_no_data_message()
        except Exception:
            traceback.print_exc()
            self.current_export_dir = None

    def get_parameterts(self):
        """
        Get parameters from screen
        """
        try:
            blur_value = _clean_input_value(self.form_mapping['c3_blur_input'].text)
            min_area_value = _clean_input_value(self.form_mapping['c3_min_area_input'].text)
            threshold_value = _clean_input_value(self.form_mapping['c3_threshold_slider'].text)
            event_intensity_value = _clean_input_value(self.form_mapping['c3_event_intensity'].text)
            return {
                'blur': blur_value,
                'min_area': min_area_value,
                'threshold': threshold_value,
                'event_intensity': event_intensity_value
            }
        except Exception:
            traceback.print_exc()
            return None

    def save_parameters(self):
        """
        Save parameters to database
        """
        c3_dataset_select = self.form_mapping['c3_dataset_select'].text
        self.form_mapping['c3_dataset_select'].validate_text(c3_dataset_select)
        if self.form_mapping['c3_dataset_select'].error_message:
            return
        try:
            parameters = self.get_parameterts()
            if parameters is None:
                return

            with get_db() as db:
                updated_model = update_trained_model(
                    db=db,
                    model_id=self.current_model_id,
                    heat_kernel_size=parameters['blur'] if parameters['blur'] else None,
                    heat_min_area=parameters['min_area'] if parameters['min_area'] else None,
                    heat_threshold=parameters['threshold'] if parameters['threshold'] else None,
                    heat_min_intensity=parameters['event_intensity'] if parameters['event_intensity'] else None,
                    has_preset=True,
                )
                if updated_model:
                    db.commit()
                    self.__show_popup(
                        title='notification_popup',
                        message='save_success_C3'
                    )

        except Exception:
            db.rollback()
            traceback.print_exc()

    def reload_preset(self):
        """
        Reload preset from database
        """
        c3_dataset_select = self.form_mapping['c3_dataset_select'].text
        self.form_mapping['c3_dataset_select'].validate_text(c3_dataset_select)
        if self.form_mapping['c3_dataset_select'].error_message:
            return

        try:
            with get_db() as db:
                trained_model = db.query(TrainedModels).filter(
                    TrainedModels.id == self.current_model_id,
                    TrainedModels.deleted_at.is_(None)
                ).first()
                if not trained_model:
                    Logger.warning("reload_preset: Model not found in database")
                    return
                if not trained_model.has_preset:
                    Logger.warning("reload_preset: No preset found (trained_model.has_preset is 0)")
                    self.popup.create_adaptive_popup(
                        title="notification_popup",
                        message="no_preset_popup_D1"
                    ).open()
                    return
                self.form_mapping['c3_blur_input'].text = self._convert_str(trained_model.heat_kernel_size)
                self.form_mapping['c3_min_area_input'].text = self._convert_str(trained_model.heat_min_area)
                self.form_mapping['c3_threshold_slider'].text = self._convert_str(trained_model.heat_threshold)
                self.form_mapping['c3_event_intensity'].text = self._convert_str(trained_model.heat_min_intensity)
        except Exception:
            traceback.print_exc()
            return

    def _convert_str(self, value):
        '''Safely convert value to string.'''
        return "" if value is None else str(value)

    def on_pre_leave(self, *args):
        """Called when leaving the screen. Clear album and force GC to release VRAM."""
        if hasattr(self, 'image_album'):
            self.image_album.clear()
        gc.collect() # Force immediate destruction of widgets in WeakSet

class ValidationItem(BoxLayout, HoverBehavior):
    """A widget representing a single validation item in the album.

    This class displays an image with associated metadata and provides
    popup functionality for viewing details.
    """
    # Properties for data binding
    source = StringProperty('')
    alt_text = StringProperty('')
    item_id = StringProperty('')
    _all_instances = weakref.WeakSet()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.screen = None  # Reference to TrainingResultsScreen
        self.img_widget = None # Store reference for cleanup
        ValidationItem._all_instances.add(self)
        Clock.schedule_once(self._post_init)

    def _post_init(self, dt):
        self.canvas.ask_update()
        # Get reference to TrainingResultsScreen
        app = App.get_running_app()
        if app and hasattr(app, 'root') and hasattr(app.root, 'ids') and hasattr(app.root.ids, 'screen_manager'):
            screen_manager = app.root.ids.screen_manager
            self.screen = screen_manager.get_screen('screen_C3_training_results')

    def on_parent(self, widget, parent):
        """Release texture from GPU when widget is removed from layout."""
        if parent is None:
            # Check if img_widget exists (via KV id or Python ref)
            img = getattr(self, 'img_widget', None) or self.ids.get('img_widget')

            if img:
                if hasattr(img, 'texture') and img.texture:
                    img.texture = None

                if hasattr(img, 'source'):
                    img.source = ''

                # Clear references
                if hasattr(self, 'img_widget'):
                    self.img_widget = None

    def on_enter(self):
        '''Handle mouse enter - show hand cursor'''
        cursor_manager.set_cursor('hand')

    def on_leave(self):
        '''Handle mouse leave - restore cursor only if no other ValidationItems are hovering'''
        # Check if any other ValidationItem is hovering
        has_other_hovering = any(
            item != self and hasattr(item, 'hover_visible') and item.hover_visible
            for item in ValidationItem._all_instances
            if hasattr(item, 'parent') and item.parent is not None  # WeakSet logic
        )

        if not has_other_hovering:
            cursor_manager.reset()

    def on_touch_down(self, touch):
        '''Handle touch/click events on the ValidationItem'''
        if self.collide_point(*touch.pos):
            if touch.button in ('scrollup', 'scrolldown', 'scrollleft', 'scrollright'):
                return False
            self._open_preview_popup()
            return True
        return super().on_touch_down(touch)

    def _build_command_preview_heatmap(
        self,
        histogram_path,
        heatmap_path,
        heat_kernel_size,
        heat_min_area,
        heat_threshold,
        heat_min_intensity,
        export_heatmap_dir,
        show_bounding_box_flag,
        show_area_volume_flag,
        overlay
        ):
        command = [
            '--histogram_path', histogram_path,
            '--heatmap_path', heatmap_path,
            '--heat_kernel_size', heat_kernel_size,
            '--heat_min_area', heat_min_area,
            '--heat_threshold', heat_threshold,
            '--heat_min_intensity', heat_min_intensity,
            '--export_heatmap_dir', export_heatmap_dir,
            '--show_bounding_box_flag', show_bounding_box_flag,
            '--show_area_volume_flag', show_area_volume_flag,
            '--overlay', overlay
        ]
        return command

    def _validate_file_paths(self, histogram_name):
        """Validate and get required file paths for preview.

        Args:
            histogram_name (str): Base name of the histogram file

        Returns:
            dict: Dictionary containing:
                - valid (bool): True if all validations pass
                - histogram_path (str): Path to histogram file if valid, None otherwise
                - heatmap_path (str): Path to heatmap file if valid, None otherwise
        """
        # Initialize default response
        response = {
            "valid": False,
            "histogram_path": None,
            "heatmap_path": None
        }

        try:
            # Get dataset folder path (two levels up from directory_path)
            dataset_folder_path = os.path.dirname(
                os.path.dirname(
                    self.screen.ids.folder_displaying.directory_path.rstrip('\\')
                )
            )

            # Check data.txt exists
            data_txt_path = os.path.join(dataset_folder_path, 'data.txt')
            if not os.path.exists(data_txt_path):
                return response

            # Find histogram path in data.txt
            histogram_path = self._find_histogram_path(data_txt_path, histogram_name)
            if not histogram_path or not os.path.exists(histogram_path):
                return response

            # Check heatmap file exists
            heatmap_path = os.path.join(HEATMAP_PATH, f"{histogram_name}.npy")
            if not os.path.exists(heatmap_path):
                return response

            response.update({
                "valid": True,
                "histogram_path": histogram_path,
                "heatmap_path": heatmap_path
            })
            return response

        except Exception as e:
            print(f"[_validate_file_paths] Error: {e}")
            traceback.print_exc()
            return response

    def _find_histogram_path(self, data_txt_path, histogram_name):
        '''Find histogram path in data.txt file'''
        if not os.path.exists(data_txt_path):
            print(f"[ValidationItem] data.txt not found: {data_txt_path}")
            return None
        try:
            pattern = re.compile(rf"^(.*(?:[\\/]|^){re.escape(histogram_name)}\.png)\s*\|", re.IGNORECASE)

            with open(data_txt_path, 'r', encoding='utf-8') as f:
                for line in f:
                    match = pattern.search(line)
                    if match:
                        return match.group(1).strip()
        except Exception as e:
            print(f"[ValidationItem] Error reading data.txt: {e}")
        return None

    def _open_preview_popup(self):
        '''Open preview popup with current parameters'''
        if not self.screen:
            print("[ValidationItem] Screen reference not found")
            return

        # Convert thumbnail path to preview image path in sibling folder preview_modal
        preview_image_path = None
        directory = os.path.dirname(self.source)
        if os.path.basename(directory).lower() == 'thumbnail':
            # Sibling of thumbnail within evaluation folder
            evaluation_dir = os.path.dirname(directory)
            preview_image_path = os.path.join(evaluation_dir, 'preview_modal', os.path.basename(self.source))

        if not preview_image_path or not os.path.exists(preview_image_path):
            self.screen.popup.create_adaptive_popup(
                title="error_popup",
                message="file_not_found_error_message"
            ).open()
            return

        blur_value = self.screen.ids.c3_settings_section.ids.c3_blur_input.ids.input_box.text
        min_area_value = self.screen.ids.c3_settings_section.ids.c3_min_area_input.ids.input_box.text
        threshold_value = self.screen.ids.c3_settings_section.ids.c3_threshold_slider.ids.input_box.text
        event_intensity_value = self.screen.ids.c3_settings_section.ids.c3_event_intensity.ids.input_box.text

        # Initialize cache for this image if it's the first time opening preview since validation
        histogram_name = os.path.splitext(os.path.basename(self.source))[0]
        if histogram_name not in self.screen._preview_params_cache: # pylint: disable=protected-access
            self.screen._preview_params_cache[histogram_name] = self.screen._last_validation_params.copy() # pylint: disable=protected-access

        def on_preview(params):
            '''Handle preview button click'''
            if self.screen.preview_popup:
                self.screen.preview_popup._remove_image_from_preview_popup() # pylint: disable=protected-access
            # 1. Validate inputs using popup's c3_section
            popup_c3_section = self.screen.preview_popup.c3_section if self.screen.preview_popup else None
            # pylint: disable=protected-access
            validation_errors, _, first_error_widget_id, valid = self.screen._validate_parameters(
                params,
                c3_section=popup_c3_section
            )
            if not valid:
                return
            # 2. Handle validation errors
            if self.screen._handle_validation_errors(validation_errors, first_error_widget_id): # pylint: disable=protected-access
                return

            histogram_name = os.path.splitext(os.path.basename(self.source))[0]

            # Cache check
            cached_params = self.screen._preview_params_cache.get(histogram_name)
            if cached_params == params:
                Logger.debug("[ValidationItem] Cache hit for %s. Reloading existing preview.", histogram_name)
                if self.screen.preview_popup:
                    # Resolve preview_modal path again
                    directory = os.path.dirname(self.source)
                    evaluation_dir = os.path.dirname(directory)
                    preview_image_path = os.path.join(evaluation_dir, 'preview_modal', os.path.basename(self.source))
                    Clock.schedule_once(lambda dt: self.screen.preview_popup._load_image_to_preview_popup(image_path=preview_image_path), 0.1)
                return

            # Validate file paths and get required paths
            result = self._validate_file_paths(histogram_name)
            if not result["valid"]:
                self.screen.popup.create_adaptive_popup(
                    title="error_popup",
                    message="preview_failed_C3"
                ).open()
                return

            histogram_path = result["histogram_path"]
            heatmap_path = result["heatmap_path"]

            # Output directory for CLI
            directory = os.path.dirname(self.source)
            evaluation_dir = os.path.dirname(directory)
            preview_modal_dir = os.path.join(evaluation_dir, 'preview_modal')

            command = self._build_command_preview_heatmap(
                histogram_path=histogram_path,
                heatmap_path=heatmap_path,
                heat_kernel_size=params['blur'],
                heat_min_area=params['min_area'],
                heat_threshold=params['threshold'],
                heat_min_intensity=params['event_intensity'],
                export_heatmap_dir=preview_modal_dir,
                show_bounding_box_flag=params['show_bbox'],
                show_area_volume_flag=params['show_info'],
                overlay=params['overlay']
            )

            # Update cache after launching CLI
            self.screen._preview_params_cache[histogram_name] = params.copy()
            Logger.debug("[ValidationItem] Cache updated for %s with params: %s", histogram_name, params)

            def run_process():
                # pylint: disable=protected-access
                return self.screen._run_cli(
                    arg_list=command,
                    script_path=os.path.join(BE_FOLDER, 'flows', 'settings', 'preview_heatmap_image.py'),
                    use_module=False,
                    cwd=BE_FOLDER,
                    use_pipe_server=True,
                )
            self.screen._run_task_in_thread(run_process)

        def on_apply(params):
            '''Handle confirm button click'''
            # Update screen parameters
            try:
                self.screen.ids.c3_settings_section.ids.c3_blur_input.ids.input_box.text = params['blur']
                self.screen.ids.c3_settings_section.ids.c3_min_area_input.ids.input_box.text = params['min_area']
                self.screen.ids.c3_settings_section.ids.c3_threshold_slider.ids.input_box.text = params['threshold']
                self.screen.ids.c3_settings_section.ids.c3_event_intensity.ids.input_box.text = params['event_intensity']
                return True  # Return True to dismiss popup
            except Exception as e:
                print(f"[ValidationItem] Error updating parameters: {e}")
                return False

        def on_close():
            '''Handle cancel button click'''
            if self.screen and self.screen.preview_popup:
                # Manually release the texture in the popup's image container
                popup = self.screen.preview_popup
                if hasattr(popup, '_image_container'):
                    for widget in popup._image_container.children: # pylint: disable=protected-access
                        if hasattr(widget, 'texture') and widget.texture:
                            widget.texture = None
                            if hasattr(widget, 'source'):
                                widget.source = ''

                self.screen.preview_popup = None
            print("[ValidationItem] Closed")

        # Clean up any lingering preview popup from a previous session
        if self.screen.preview_popup:
            try:
                self.screen.preview_popup.dismiss()
            except Exception:
                pass
            self.screen.preview_popup = None

        # Use the specific cache for this image as the 'validated_parameters' for the popup
        # This ensures _old_result_label and the right column options match the cache
        image_cached_params = self.screen._preview_params_cache.get(histogram_name) # pylint: disable=protected-access
        Logger.debug("[ValidationItem] Modal load image: %s with params: %s", histogram_name, image_cached_params)

        def on_open_folder():
            '''Handle open folder button click'''
            has_image = False
            if self.screen.preview_popup and hasattr(self.screen.preview_popup, '_image_container'):
                for widget in self.screen.preview_popup._image_container.children: # pylint: disable=protected-access
                    if isinstance(widget, (AsyncImage, ScrollView)):
                        has_image = True
                        break

            if has_image:
                self.screen.open_path_in_explorer(preview_image_path, select_file=True)
            else:
                # If no image is currently displayed, just open the folder
                self.screen.open_path_in_explorer(os.path.dirname(preview_image_path), select_file=False)

        # Set up kwargs for popup
        preview_kwargs = {
            'image_path': preview_image_path,
            'blur_value': _clean_input_value(blur_value),
            'min_area_value': _clean_input_value(min_area_value),
            'threshold_value': _clean_input_value(threshold_value),
            'event_intensity_value': _clean_input_value(event_intensity_value),
            'validated_parameters': image_cached_params,
            'on_preview': on_preview,
            'on_apply': on_apply,
            'on_close': on_close,
            'on_open_folder': on_open_folder
        }

        self.screen.preview_popup = self.screen.popup.create_preview_popup(**preview_kwargs)
        self.screen.preview_popup.open()

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

class ValidationAlbum(ScrollView):
    """
    A scrollable gallery widget for displaying validation images with lazy loading.

    This widget extends ScrollView to display validation images in a grid layout,
    implementing lazy loading to efficiently handle large numbers of images by
    loading them in batches as the user scrolls.

    Attributes:
        items (ListProperty): List of image items to display in the gallery.
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
        self.is_showing_no_data = False

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
            scroll_y <= 0.3 and  # Increased threshold for earlier loading
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

    def _continuous_scroll_check(self, dt):
        """Continuously check scroll position - independent of image loading logic"""
        # Only check when not in no-data state and there is data to load
        if self.is_showing_no_data or not self.all_image_data:
            return True  # Continue the timer

        # There is unloaded data
        has_unloaded_data = self.loaded_count < len(self.all_image_data)

        if has_unloaded_data:
            # Check two cases that need adjustment:
            # 1. Scroll is at the top (>= 0.99)
            # 2. Scroll is at the bottom or negative (<= 0.0)
            if self.scroll_y >= 0.99:
                # At the top but still has unloaded data
                pass
            elif self.scroll_y <= 0.0:
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
        # First batch loads immediately without streaming
        if self.is_first_batch:
            chunk_size = len(valid_images)  # Load all at once for first batch
            self.is_first_batch = False
        else:
            chunk_size = 1  # Streaming: Load 1 image at a time for subsequent batches

        chunks = [valid_images[i:i + chunk_size]
                  for i in range(0, len(valid_images), chunk_size)]

        self._load_chunk_index = 0
        self._load_chunks = chunks
        self._load_next_chunk()

    def _load_next_chunk(self):
        """Load the next chunk of images"""
        if self._load_chunk_index >= len(self._load_chunks):
            self.is_loading = False
            Clock.schedule_once(lambda dt: self._force_layout_update(), 0.05)
            return

        chunk = self._load_chunks[self._load_chunk_index]

        # Load this chunk
        for image_data in chunk:
            self._add_image_item(
                source=image_data['source'],
                alt_text=image_data.get('alt_text', ''),
                item_id=image_data.get('id'),
            )

        self._load_chunk_index += 1

        # Schedule next chunk with different delays
        if len(self._load_chunks) == 1:
            # First batch: no delay
            Clock.schedule_once(lambda dt: self._load_next_chunk(), 0.01)
        else:
            # Streaming batches: slower delay for visual effect
            Clock.schedule_once(lambda dt: self._load_next_chunk(), 0.1)

    def _add_image_item(self, source, alt_text='', item_id=None):
        """Add a single image item to the album (internal method)"""
        item = ValidationItem(
            source=source,
            alt_text=alt_text,
            item_id=item_id or str(len(self.items)),
            size_hint_x=None,
            width=dp(294)
        )
        self.items.append(item)
        self.content_layout.add_widget(item)

    def show_no_data_message(self):
        """Display no data message"""
        self.content_layout.clear_widgets()
        self.is_showing_no_data = True

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

    def load_stream_images(self, image_path):
        """Load single stream image"""
        self.content_layout.cols = 5
        self.content_layout.size_hint_y = None
        self.content_layout.padding = dp(10)
        self.content_layout.spacing = dp(15)

        item = ValidationItem(
            source=image_path,
            size_hint_x=None,
            width=dp(296)
        )
        self.content_layout.add_widget(item)

        total_images = len(self.content_layout.children)
        if total_images >= 11:
            self.do_scroll_x = True
            self.do_scroll_y = True
            self.scroll_x = 0
            self.scroll_y = 0
        else:
            self.do_scroll_x = False
            self.do_scroll_y = False

    def load_images_lazy(self, image_data_list):
        """Load image list into album with lazy loading"""
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
        self.last_scroll_y = 1.0  # Reset scroll position tracker
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

    def clear(self, show_no_data_message=True):
        """Clear all images in the album"""
        # Stop scroll monitoring
        self._stop_scroll_position_monitoring()

        self.content_layout.clear_widgets()
        self.items.clear()
        self.all_image_data.clear()
        self.loaded_count = 0
        self.is_loading = False
        self.last_scroll_y = 1.0
        if show_no_data_message:
            self.show_no_data_message()
