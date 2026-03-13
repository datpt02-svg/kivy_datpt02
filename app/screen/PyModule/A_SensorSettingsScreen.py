"""
Sensor Settings Screen Module.

This module provides the UI and functionality for managing sensor settings,
including calibration, angle detection, speed measurement, and testing.
"""
# Standard library imports
import json
import os
import re
import shutil
import subprocess
import time
import traceback
from contextlib import contextmanager
from typing import List, Optional

# Third-party imports
from kivy.app import App
from kivy.clock import Clock
from kivy.factory import Factory
from kivy.metrics import dp
from kivy.properties import (
    BooleanProperty,
    NumericProperty,
    ObjectProperty,
    StringProperty,
)
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.image import Image
from kivy.uix.scrollview import ScrollView
from kivy.uix.boxlayout import BoxLayout


# Local application imports
from app.env import (
    BE_FOLDER,
    BIAS_PATH,
    DOT_BOX_PATH,
    DOT_BOX_PATH_PREVIEW,
    DOT_PATTERN_PATH,
    DOT_SCORE_DEFAULT,
    HISTOGRAM_TEST_PATH,
    INTRINSIC_PATH,
    OUTPUT_INTRINSIC_PATH,
    PERSPECTIVE_PATH,
    RAW_PATH,
    SPEED_PATH,
    USE_SENSOR,
    POSE_PATH,
    TOLERANCE_PCT_COORDINATE,
    MIN_FREQ_COORDINATE,
    MAX_FREQ_COORDINATE,
    START_TH_COORDINATE,
    STOP_TH_COORDINATE,
    PERCENT_ACTIVITY_COORDINATE,
    FPS_COORDINATE,
    KERNEL_COORDINATE,
    DELTA_T_COORDINATE,
    INI_PATH
)
from app.libs.constants.colors import COLORS
from app.libs.widgets.components import FormScreen, KeyLabel, MyPopup
from app.screen.PyModule.utils.scroll_action import scroll_to_widget
from app.services.sensor_settings import create_sensor_settings, update_sensor_settings
from app.services.system_config import read_system_config
from app.services.utils.recursive_delete import recursive_delete
from app.screen.PyModule.utils.debug_status import get_debug_status
from db.models.sensor_settings import SensorSettings
from db.models.system_config import SystemConfig
from db.session import get_db

from .utils.cli_manager import CLIManager
from .utils.datatable_manager import DataTableManager
from .utils.dataset_spinner import DatasetSpinner
from .utils.delete_images_in_folders import delete_images_in_folders


SENSOR_SETTINGS_JSON = os.path.join("app", "config", "a_sensor_settings.json")

class ImageThumbnail(ButtonBehavior, Image):
    """
    Image thumbnail widget with selection capability.

    Combines button behavior with image display to create clickable thumbnails.
    Only one thumbnail can be selected at a time.
    """
    selected = BooleanProperty(False)
    loading = BooleanProperty(True)
    enable_select = BooleanProperty(True)

    def on_load(self, *args):
        """Handle image load completion event."""
        self.loading = False

    def on_press(self):
        """Handle thumbnail press event to toggle selection."""
        # Change logic to only allow selecting 1 image
        if not self.enable_select:
            return
        if not self.selected:
            # Deselect all other images in parent
            parent = self.parent
            if parent:
                for child in parent.children:
                    if isinstance(child, ImageThumbnail):
                        child.selected = False
            # Select current image
            self.selected = True
        else:
            # Allow deselecting currently selected image
            self.selected = False


class AcquiredImageGalleryWidget(ScrollView):
    """
    Gallery widget for displaying and managing image thumbnails.

    Provides functionality for loading, displaying, and selecting images
    with support for streaming updates and custom thumbnail sizing.
    """
    thumbnail_width = NumericProperty(dp(135))
    thumbnail_height = NumericProperty(dp(83))
    maximum_image = ObjectProperty(None, allownone=True)
    enable_select = BooleanProperty(True)

    def __init__(self, **kwargs):
        """Initialize the gallery widget."""
        super().__init__(**kwargs)
        self.selected_images = []
        self.bind(thumbnail_width=self.update_existing_thumbnails)
        self.bind(thumbnail_height=self.update_existing_thumbnails)
        self.bind(enable_select=self.update_existing_thumbnails_enable_select)

    def set_thumbnail_size(self, width, height):
        """Set thumbnail size"""
        self.thumbnail_width = dp(width)
        self.thumbnail_height = dp(height)

    def update_existing_thumbnails(self, *args):
        """Update size for all existing thumbnails"""
        try:
            if hasattr(self, 'ids') and 'content_layout' in self.ids:
                for child in self.ids.content_layout.children:
                    if isinstance(child, ImageThumbnail):
                        child.size = (self.thumbnail_width,
                                      self.thumbnail_height)
        except Exception as e:
            print(f"Error updating existing thumbnails: {str(e)}")

    def update_existing_thumbnails_enable_select(self, *args):
        """Update enable_select for all existing thumbnails"""
        try:
            if hasattr(self, 'ids') and 'content_layout' in self.ids:
                for child in self.ids.content_layout.children:
                    if isinstance(child, ImageThumbnail):
                        child.enable_select = self.enable_select
        except Exception as e:
            print(f"Error updating existing thumbnails enable_select: {str(e)}")

    def load_stream_images(self, image_path, dot_streaming=True):
        """Load single stream image with binary insertion sort or just add at end if dot_streaming=False"""
        content_layout = self.ids.content_layout
        # Setup layout
        content_layout.cols = getattr(self, 'cols_number', 10)
        content_layout.size_hint_y = None
        content_layout.padding = [dp(10), dp(10)]
        content_layout.spacing = dp(20)

        # Create new thumbnail
        thumbnail = ImageThumbnail(source=image_path, nocache=True)
        thumbnail.size = (self.thumbnail_width, self.thumbnail_height)
        thumbnail.size_hint = (None, None)
        thumbnail.enable_select = self.enable_select

        if dot_streaming:
            # Extract number from filename for comparison
            new_number = self.extract_number_from_filename(image_path)
            # Find insert position using binary search
            insert_position = self.find_insert_position_for_thumbnail(
                content_layout.children, new_number
            )
            # Insert thumbnail at correct position
            content_layout.add_widget(thumbnail, insert_position)
        else:
            # Just add to end of list
            content_layout.add_widget(thumbnail)

        total_images = len(content_layout.children)
        print(f"Total current images: {total_images}")

        # Update scroll settings
        if total_images >= 16:
            self.do_scroll_x = True
            self.do_scroll_y = True
            self.scroll_x = 0
            if not dot_streaming:
                self.scroll_y = 0
        else:
            self.do_scroll_x = False
            self.do_scroll_y = False

    def find_insert_position_for_thumbnail(self, children_list, new_number):
        """Binary search to find insert position for new thumbnail"""
        left, right = 0, len(children_list)

        while left < right:
            mid = (left + right) // 2
            mid_child = children_list[-(mid + 1)]  # Kivy children list is reversed

            if hasattr(mid_child, 'source'):
                mid_number = self.extract_number_from_filename(mid_child.source)

                if mid_number is None:
                    left = mid + 1
                    continue

                # Compare to maintain descending order
                if new_number > mid_number:
                    right = mid
                else:
                    left = mid + 1
            else:
                left = mid + 1

        # Convert position for Kivy (children list is reversed)
        return len(children_list) - left

    @staticmethod
    def extract_number_from_filename(file_path):
        """Extract number from filename for sorting"""
        filename = os.path.basename(file_path)
        numbers = re.findall(r'\d+', filename)
        if numbers:
            return int(numbers[-1])
        return 0

    def load_images(self, folder_path, reverse=False):
        """
        Load images from a folder into the gallery.

        Args:
            folder_path: Path to the folder containing images
            reverse: Whether to reverse the sort order
        """
        content_layout = self.ids.content_layout
        content_layout.clear_widgets()

        # Reset layout to default when there are images
        content_layout.cols = getattr(self, 'cols_number', 10)
        content_layout.size_hint_y = None
        content_layout.padding = [dp(10), dp(10)]
        content_layout.spacing = dp(20)

        # Check if directory exists
        if not os.path.exists(folder_path):
            self.show_no_data_message()
            return

        # Get list of image files from folder, only get files that actually exist
        image_files = []
        for f in os.listdir(folder_path):
            if f.lower().endswith(('.png')):
                file_path = os.path.join(folder_path, f)
                if os.path.isfile(file_path):  # Only get files that haven't been deleted
                    image_files.append(f)

        # Sort by number in filename instead of alphabetical

        def natural_sort_key(filename):
            """Extract number from filename for natural sorting"""
            numbers = re.findall(r'\d+', filename)
            if numbers:
                return int(numbers[-1])  # Get last number in filename
            return 0

        image_files.sort(key=natural_sort_key, reverse=reverse)

        if self.maximum_image is not None:
            try:
                max_img = int(self.maximum_image)
                image_files = image_files[:max_img]
            except Exception:
                pass

        if not image_files:
            self.show_no_data_message()
            return

        # Enable scroll when there are images
        self.do_scroll_x = True
        self.do_scroll_y = True

        for idx, image_file in enumerate(image_files):
            image_path = os.path.join(folder_path, image_file)
            if not os.path.isfile(image_path):
                continue
            thumbnail = ImageThumbnail(source=image_path, nocache=True)

            thumbnail.size = (self.thumbnail_width, self.thumbnail_height)

            # Select first image as default
            if idx == 0:
                thumbnail.selected = True
            content_layout.add_widget(thumbnail)
        # After adding images, reset scroll to top
        self.scroll_x = 0
        self.scroll_y = 1

    def show_no_data_message(self):
        """Display no data message"""
        content_layout = self.ids.content_layout
        content_layout.clear_widgets()
        # Disable scroll when there's no data
        self.do_scroll_x = False
        self.do_scroll_y = False

        # Reset layout for content_layout to center the label
        content_layout.cols = 1
        content_layout.size_hint_y = 1
        content_layout.height = self.height
        content_layout.padding = [0, 0, 0, 0]
        content_layout.spacing = 0

        label = KeyLabel(
            text_key='no_data_placeholder',
            halign='center',
            valign='middle',
            color=[0.6, 0.6, 0.6, 1],
            font_size=dp(20),
            size_hint=(1, 1),
            height=self.height,
            text_size=(None, None),
        )
        label.bind(size=lambda instance, value: setattr(
            instance, 'text_size', value))
        content_layout.add_widget(label)

    def get_selected_images(self):
        """Get selected image, return string path or None"""
        try:
            for child in self.ids.content_layout.children:
                if isinstance(child, ImageThumbnail) and hasattr(child, 'selected') and child.selected:
                    return child.source
            return None  # No image selected
        except Exception:
            traceback.print_exc()
            return None


class SensorSettingsScreen(FormScreen, CLIManager):
    """
    Main screen for managing sensor settings and calibration.

    Provides UI and functionality for sensor calibration, angle detection,
    speed measurement, and testing. Manages multi-step workflow with
    validation and data persistence.
    """
    dot_score = StringProperty('')
    dot_box_path_value = StringProperty('')
    dot_box_path_preview_value = StringProperty('')
    current_subsection = NumericProperty(0)

    def schedule_update_ui(self):
        """Schedule UI updates for navigation buttons and step indicator."""
        Clock.schedule_once(lambda dt: self.update_navigation_buttons(), -1)
        Clock.schedule_once(lambda dt: self.update_step_indicator(), -1)

    def update_navigation_buttons(self, *args):
        """Update navigation buttons visibility based on current subsection"""
        try:
            # Check if screen still exists
            if not self.get_root_window():
                return

            if not all(hasattr(self.ids, name) for name in (
                'previous_button',
                'next_button',
                'widget_button',
                'coordinate_info',
                'register_coordinate_button',
                'verify_coordinate_button',
                'save_button'
            )):
                return

            prev_btn = self.form_mapping['prev_btn']
            next_btn = self.form_mapping['next_btn']
            widget_btn = self.form_mapping['widget_btn']
            coordinate_info = self.form_mapping['coordinate_info']
            register_coordinate_btn = self.form_mapping['register_coordinate_btn']
            verify_coordinate_btn = self.form_mapping['verify_coordinate_btn']
            save_btn = self.form_mapping['save_btn']

            for widget in (
                coordinate_info,
                register_coordinate_btn,
                verify_coordinate_btn,
            ):
                parent = getattr(widget, 'parent', None)
                if parent is not None:
                    parent.remove_widget(widget)

            button_container = self.form_mapping['button_navigation_container']
            if not button_container:
                return
            else:
                button_container.clear_widgets()

            if self.current_subsection == 4:
                # Create vertical layout for coordinate section
                coordinate_section = BoxLayout(
                    orientation='vertical',
                    size_hint_y=None,
                    height=self.minimum_height if hasattr(self, 'minimum_height') else dp(200),
                    spacing=dp(10)
                )

                # Add coordinate info
                coordinate_section.add_widget(coordinate_info)

                # Create horizontal layout for coordinate buttons
                coordinate_buttons_layout = BoxLayout(
                    orientation='horizontal',
                    size_hint_y=None,
                    height=dp(40),
                    spacing=dp(10)
                )
                coordinate_buttons_layout.add_widget(register_coordinate_btn)
                # Only show verify button when coordinates are registered
                try:
                    if self.get_modify_coordinate_info() == "coordinate_registered":
                        coordinate_buttons_layout.add_widget(verify_coordinate_btn)
                except Exception:
                    # In case of any error while checking, default to hiding verify
                    traceback.print_exc()

                coordinate_section.add_widget(coordinate_buttons_layout)

                # Add coordinate section to button container
                button_container.add_widget(coordinate_section)

                button_container.add_widget(widget_btn)
                button_container.add_widget(save_btn)
            else:
                if self.current_subsection == 0:
                    # First subsection: only next button
                    button_container.add_widget(next_btn)
                elif self.current_subsection == 3:
                    # Last subsection: previous and save button
                    button_container.add_widget(prev_btn)
                    button_container.add_widget(widget_btn)
                    button_container.add_widget(save_btn)
                else:
                    # Middle subsections: previous and next buttons
                    button_container.add_widget(prev_btn)
                    button_container.add_widget(next_btn)

        except Exception:
            traceback.print_exc()

    def update_step_indicator(self):
        """Update step indicator visibility based on current subsection"""
        try:
            # Check if screen still exists
            if not self.get_root_window():
                return

            if not hasattr(self.ids, 'step_indicator'):
                return

            step_indicator = self.form_mapping['step_indicator']
            step_indicator_container = self.form_mapping['step_indicator_container']
            main_container = self.form_mapping['main_container']

            if not step_indicator_container or not main_container:
                return

            try:
                if self.current_subsection == 4:
                    # Remove container from parent to free up space
                    if step_indicator_container in main_container.children:
                        main_container.remove_widget(step_indicator_container)
                else:
                    # Add container back if not present
                    if step_indicator_container not in main_container.children:
                        main_container.add_widget(step_indicator_container)

                    # Update current step
                    step_indicator.current_step = self.current_subsection
            except ReferenceError:
                traceback.print_exc()
                pass # pylint: disable=unnecessary-pass

        except Exception:
            traceback.print_exc()

    def go_to_next_subsection(self):
        """Navigate to next subsection"""
        if self.current_subsection < 3:
            # Validate current subsection before moving to next
            errors, json_errors = self.validate_fields(key_validation=self.current_subsection)

            has_any_error =self._handle_validation_errors(
                errors=errors,
                json_errors=json_errors,
            )
            if has_any_error:
                return

            self.current_subsection += 1
            self.schedule_update_ui()
            # Scroll to top when changing subsection
            scroll_view = self.form_mapping['scroll_screen_A_sensor_settings']
            if scroll_view:
                scroll_view.scroll_y = 1

    def validate_fields(self, key_validation):
        """
        Validate all fields with ErrorMessage in current subsection
        Returns True if all valid, False otherwise
        """
        # Clear previous errors
        if isinstance(key_validation, int):
            self.reset_error_screen_a(key_validation)
        else:
            self.reset_error_screen_a()

        if key_validation not in self.error_mapping:
            return True

        config = self.error_mapping[key_validation]
        margin_values = None
        errors = []
        json_errors = []

        # Special handling for test validation: a_bias_path_select_speed takes priority
        # Only validate a_bias_path_select if a_bias_path_select_speed is not set or file doesn't exist
        skip_bias_path_select = False
        if key_validation == 'test':
            bias_path_speed_id = 'a_bias_path_select_speed'
            if bias_path_speed_id in config['fields'] and bias_path_speed_id in self.ids:
                bias_path_speed_widget = self.ids[bias_path_speed_id]
                bias_path_speed_value = bias_path_speed_widget.text.strip() if hasattr(bias_path_speed_widget, 'text') else ''
                if bias_path_speed_value:
                    # a_bias_path_select_speed has value, so skip validating a_bias_path_select
                    skip_bias_path_select = True

        for field_id, rules in config['fields'].items():
            # Skip a_bias_path_select if a_bias_path_select_speed has value
            if skip_bias_path_select and field_id == 'a_bias_path_select':
                continue

            field_type = rules.get('type')
            scroll = rules.get('scroll', False)
            path_template = rules.get('path_template', None)

            # Handle margin validation (special case)
            if field_type == 'margin':
                is_valid, error_msg_key, margin_values = self.validate_margins()
                if not is_valid:
                    json_errors.append((field_id, error_msg_key, scroll))
                continue

            # Handle custom validators
            if field_type == 'custom':
                validator = rules.get('validator')
                if validator:
                    result = validator()
                    if not result:
                        json_errors.append((field_id, 'no_select_error_message', scroll))
                    else:
                        if not os.path.exists(os.path.normpath(result)):
                            json_errors.append((field_id, 'file_not_found_error_message', scroll))
                continue

            if field_type == 'text':
                # Get widget
                if field_id not in self.ids:
                    continue

                widget = self.ids[field_id]
                value = widget.text.strip() if hasattr(widget, 'text') else ''
                duplicate_check = rules.get('duplicate_check', False)

                if value:
                    if path_template:
                        path = path_template(value)
                        if not os.path.exists(os.path.normpath(path)):
                            json_errors.append((field_id, 'file_not_found_error_message', scroll))
                    if duplicate_check:
                        if self.check_duplicate_name(value):
                            json_errors.append((field_id, 'save_sensor_settings_popup_A_duplicated', scroll))

                errors.append((field_id, value, scroll))
        if margin_values:
            return errors, json_errors, margin_values
        return errors, json_errors

    def go_to_previous_subsection(self):
        """Navigate to previous subsection"""
        if self.current_subsection > 0:

            self.current_subsection -= 1
            self.schedule_update_ui()
            # Scroll to top when changing subsection
            scroll_view = self.form_mapping['scroll_screen_A_sensor_settings']
            if scroll_view:
                scroll_view.scroll_y = 1

    def on_folder_selected(self, instance, folder_path, preview=False):
        """Handle folder selection event."""
        self.set_dot_box_path_to_value(folder_path, preview=preview)

    def set_dot_box_path_to_placeholder(self, preview=False):
        """Reset dot box path to empty placeholder."""
        if preview is None:
            self.dot_box_path_preview_value = ''
            self.dot_box_path_value = ''
        elif preview:
            self.dot_box_path_preview_value = ''
        else:
            self.dot_box_path_value = ''

    def set_dot_box_path_to_value(self, path_value, preview=False):
        """Set dot box path value."""
        if preview:
            self.dot_box_path_preview_value = path_value
        else:
            self.dot_box_path_value = path_value

    def set_left_mouse_disabled(self, disabled: bool):
        """
        Enable or disable mouse clicks on widgets.

        Args:
            disabled: If True, disable clicks except for allowed widgets
        """
        if disabled:
            self.disable_click(
                all_widget=True,
                allow_widget=[
                    self.form_mapping['open_folder_perspective_button'],
                    self.form_mapping['open_folder_speed_button']
                ]
                )
        else:
            self.enable_click()

    def _get_coordinate_info_by_name(self, db, table, name):
        """
        Get coordinate info by name from database table.

        Args:
            db: Database session
            table: Database table model
            name: Name of the item to find

        Returns:
            int or None: Item coordinate info if found, None otherwise
        """
        query = db.query(table.status_pose).filter(table.name == name)
        if hasattr(table, 'deleted_at'):
            query = query.filter(table.deleted_at.is_(None))
        data = query.first()
        return str(data.status_pose) if data else ""

    def get_modify_coordinate_info(self):
        """Get modify coordinate info text key"""
        with get_db() as db:
            try:
                coordinate_info = self._get_coordinate_info_by_name(
                    db,
                    SensorSettings,
                    self.editing_item_name
                    )
                if coordinate_info == "0":
                    return "coordinate_not_registered"
                return "coordinate_registered"
            except Exception:
                traceback.print_exc()
                return "coordinate_not_registered"

    def __init__(self, **kwargs):
        """Initialize the sensor settings screen."""
        super().__init__(**kwargs)
        self.pipe_mode = None
        self._received_gallery_image = False
        self._received_dot_box_image = False
        self._received_dot_box_preview_image = False
        self._received_perspective_json = False
        self._received_speed_json = False
        self._received_test_histogram = False
        self._received_coordinate = False

        self.editing_item_name = None
        self.max_len_item_name = 100
        self.popup = MyPopup()
        self.app = App.get_running_app()
        self.sensor_settings_table = DataTableManager(
            screen=self,
            table_id="data_table_a_sensor_settings",
            pagination_box_id="pagination_box_a_sensor_settings",
            headers=['setting_name_column_A', 'last_updated_column_A', 'action_column'],
            db_headers=["name", "updated_at", "button"],
            db_model=SensorSettings,
            config_fields=[
                "id",
                "intrinsic_path", "pattern_cols",
                "pattern_rows", "bias_path",
                "perspective_path", "speed_path"
            ],
            types=['str', 'str', 'button'],
            settings_file=SENSOR_SETTINGS_JSON,
            custom_message=True
        )

        self.spinners = {
            'a_bias_path_select': DatasetSpinner(screen=self, spinner_id='a_bias_path_select', folder_path=BIAS_PATH, extension='.bias'),
            'a_intrinsic_json_select': DatasetSpinner(screen=self, spinner_id='a_intrinsic_json_select', folder_path=INTRINSIC_PATH),
            'a_perspective_json_select': DatasetSpinner(screen=self, spinner_id='a_perspective_json_select', folder_path=PERSPECTIVE_PATH),
            'a_speed_json_select': DatasetSpinner(screen=self, spinner_id='a_speed_json_select', folder_path=SPEED_PATH),
            'a_bias_path_select_speed': DatasetSpinner(screen=self, spinner_id='a_bias_path_select_speed', folder_path=BIAS_PATH, extension='.bias'),
        }
        for spinner in self.spinners.values():
            Clock.schedule_once(lambda dt, s=spinner: s.load_spinner_from_folder())
        Clock.schedule_once(self.load_dot_pattern_images)

    def create_navigation_buttons(self):
        """Initialize navigation buttons after KV file is loaded."""
        # Create navigation buttons dynamically
        button_container = self.form_mapping['button_navigation_container']
        if button_container:
            # Create previous button
            prev_btn = Factory.FormButton(
                text_key='previous_button',
            )
            prev_btn.bind(on_release=lambda x: self.go_to_previous_subsection())

            # Create next button
            next_btn = Factory.FormButton(
                text_key='next_button',
            )
            next_btn.bind(on_release=lambda x: self.go_to_next_subsection())

            widget_btn = Factory.Widget(
                size_hint_x=1
            )

            # Create coordinate info using ReadOnlyInfoGroup
            coordinate_info = Factory.ReadOnlyInfoGroup()
            coordinate_info.text_key = "modify_coordinate_info"

            register_coordinate_btn = Factory.FormButton(
                text_key='coordinate_register_button',
                bg_color=COLORS['BLUE'],
            )
            register_coordinate_btn.bind(on_release=lambda x: self.register_coordinate())

            verify_coordinate_btn = Factory.FormButton(
                text_key='coordinate_verify_button',
                bg_color=COLORS['BLUE'],
            )
            verify_coordinate_btn.bind(on_release=lambda x: self.verify_coordinate())

            # Create save button with green background
            save_btn = Factory.FormButton(
                text_key='save_sensor_settings_button_A',
                bold=True,
                bg_color=COLORS['GREEN'],
            )
            save_btn.bind(on_release=lambda x: self.save_prophesee_settings())

            # Store references
            self.ids['previous_button'] = prev_btn
            self.ids['next_button'] = next_btn
            self.ids['widget_button'] = widget_btn
            self.ids['coordinate_info'] = coordinate_info
            self.ids['register_coordinate_button'] = register_coordinate_btn
            self.ids['verify_coordinate_button'] = verify_coordinate_btn
            self.ids['save_button'] = save_btn

            # Add initial button (only next for subsection 0)
            button_container.add_widget(next_btn)

    def create_step_indicator(self):
        """Initialize step indicator after KV file is loaded."""
        step_indicator_container = self.form_mapping['step_indicator_container']
        if step_indicator_container:
            step_indicator = Factory.StepIndicator(
                current_step=self.current_subsection,
                size_hint_x=None,
                size_hint_y=None,
                height=dp(60),
                padding=[0, dp(15), 0, dp(15)],
            )

            # Bind width to screen width
            def update_width(instance, value):
                step_indicator.width = value * 0.5

            self.bind(width=update_width)

            # Store reference
            self.ids['step_indicator'] = step_indicator

            # Add initial step indicator
            step_indicator_container.add_widget(step_indicator)

    def update_register_coordinate_db(self, pose_file_path):
        """Update register coordinate in database"""
        with get_db() as db:
            try:
                setting = db.query(SensorSettings).filter(
                    SensorSettings.name == self.editing_item_name,
                    SensorSettings.deleted_at.is_(None)
                    ).first()
                if not setting:
                    return

                setting.pose_file_path = pose_file_path
                setting.status_pose = True
                db.commit()
                db.refresh(setting)
            except Exception:
                db.rollback()
                traceback.print_exc()
                raise

    def validate_default_params(self):
        """Validate default params"""
        if TOLERANCE_PCT_COORDINATE and (not isinstance(TOLERANCE_PCT_COORDINATE, float) or TOLERANCE_PCT_COORDINATE < 0 or TOLERANCE_PCT_COORDINATE > 100):
            return False

        if MIN_FREQ_COORDINATE and (not isinstance(MIN_FREQ_COORDINATE, int) or MIN_FREQ_COORDINATE < 50 or MIN_FREQ_COORDINATE > 520):
            return False

        if MAX_FREQ_COORDINATE and (not isinstance(MAX_FREQ_COORDINATE, int) or MAX_FREQ_COORDINATE < 50 or MAX_FREQ_COORDINATE > 520):
            return False

        if START_TH_COORDINATE and (not isinstance(START_TH_COORDINATE, int) or START_TH_COORDINATE < 0 or START_TH_COORDINATE > 7):
            return False

        if STOP_TH_COORDINATE and (not isinstance(STOP_TH_COORDINATE, int) or STOP_TH_COORDINATE < 0 or STOP_TH_COORDINATE > 7):
            return False

        if PERCENT_ACTIVITY_COORDINATE and (not isinstance(PERCENT_ACTIVITY_COORDINATE, float) or PERCENT_ACTIVITY_COORDINATE < 0.1 or PERCENT_ACTIVITY_COORDINATE > 1):
            return False

        if FPS_COORDINATE and (not isinstance(FPS_COORDINATE, int) or FPS_COORDINATE < 0):
            return False

        if KERNEL_COORDINATE and (not isinstance(KERNEL_COORDINATE, int) or KERNEL_COORDINATE < 1 or KERNEL_COORDINATE > 35 or KERNEL_COORDINATE % 2 == 0):
            return False

        if DELTA_T_COORDINATE and (not isinstance(DELTA_T_COORDINATE, int) or DELTA_T_COORDINATE < 0):
            return False

        return True

    def register_coordinate(self):
        """Register coordinate"""
        self.pipe_mode = 'coordinate'

        command = [
            "--mode", "save",
            "--pose_file", POSE_PATH,
            "--use_sensor", "1",
        ]

        if not self.validate_default_params():
            self.__show_popup(
                title="error_popup",
                message="register_coordinate_A_failed",
            )
            return

        if TOLERANCE_PCT_COORDINATE is not None:
            command.extend(["--tolerance_pct", str(TOLERANCE_PCT_COORDINATE)])

        if MIN_FREQ_COORDINATE is not None:
            command.extend(["--min_freq", str(MIN_FREQ_COORDINATE)])

        if MAX_FREQ_COORDINATE is not None:
            command.extend(["--max_freq", str(MAX_FREQ_COORDINATE)])

        if START_TH_COORDINATE is not None:
            command.extend(["--start_th", str(START_TH_COORDINATE)])

        if STOP_TH_COORDINATE is not None:
            command.extend(["--stop_th", str(STOP_TH_COORDINATE)])

        if PERCENT_ACTIVITY_COORDINATE is not None:
            command.extend(["--percent_activity", str(PERCENT_ACTIVITY_COORDINATE)])

        if FPS_COORDINATE is not None:
            command.extend(["--fps", str(FPS_COORDINATE)])

        if KERNEL_COORDINATE is not None:
            command.extend(["--kernel", str(KERNEL_COORDINATE)])

        if DELTA_T_COORDINATE is not None:
            command.extend(["--delta_t", str(DELTA_T_COORDINATE)])

        def run_process():
            result = self._run_cli(
                script_path=os.path.join(BE_FOLDER, 'flows', 'settings', 'prophesee_calibration.py'),
                use_module=False,
                arg_list=command,
                title_window_focus=["Metavision Sensor Pose Alignment Tool"],
                cwd=BE_FOLDER,
                use_pipe_server=True,
                log_callback=True
            )
            return result
        self._run_task_in_thread(run_process)

    def _get_pose_file_path_by_name(self, db, table, name):
        """
        Get pose file path by name
        """
        query = db.query(table.pose_file_path).filter(table.name == name)
        if hasattr(table, 'deleted_at'):
            query = query.filter(table.deleted_at.is_(None))
        data = query.first()
        return data.pose_file_path if data else ""

    def verify_coordinate(self):
        """Verify coordinate"""
        self.pipe_mode = 'verify_coordinate'

        with get_db() as db:
            try:
                pose_file_path = self._get_pose_file_path_by_name(
                    db,
                    SensorSettings,
                    self.editing_item_name
                )
            except Exception:
                traceback.print_exc()
                return

        if not self.validate_default_params():
            self.__show_popup(
                title="error_popup",
                message="register_coordinate_A_failed",
            )
            return

        if not pose_file_path or not os.path.exists(pose_file_path):
            self.__show_popup(
                title="error_popup",
                message="register_coordinate_A_deleted",
            )
            return

        command = [
            "--mode", "align",
            "--pose_file", pose_file_path,
            "--use_sensor", "1",
        ]

        if TOLERANCE_PCT_COORDINATE is not None:
            command.extend(["--tolerance_pct", str(TOLERANCE_PCT_COORDINATE)])

        if MIN_FREQ_COORDINATE is not None:
            command.extend(["--min_freq", str(MIN_FREQ_COORDINATE)])

        if MAX_FREQ_COORDINATE is not None:
            command.extend(["--max_freq", str(MAX_FREQ_COORDINATE)])

        if START_TH_COORDINATE is not None:
            command.extend(["--start_th", str(START_TH_COORDINATE)])

        if STOP_TH_COORDINATE is not None:
            command.extend(["--stop_th", str(STOP_TH_COORDINATE)])

        if PERCENT_ACTIVITY_COORDINATE is not None:
            command.extend(["--percent_activity", str(PERCENT_ACTIVITY_COORDINATE)])

        if FPS_COORDINATE is not None:
            command.extend(["--fps", str(FPS_COORDINATE)])

        if KERNEL_COORDINATE is not None:
            command.extend(["--kernel", str(KERNEL_COORDINATE)])

        if DELTA_T_COORDINATE is not None:
            command.extend(["--delta_t", str(DELTA_T_COORDINATE)])

        def run_process():
            result = self._run_cli(
                script_path=os.path.join(BE_FOLDER, 'flows', 'settings', 'prophesee_calibration.py'),
                use_module=False,
                arg_list=command,
                title_window_focus=["Metavision Sensor Pose Alignment Tool"],
                cwd=BE_FOLDER,
                use_pipe_server=True,
                log_callback=True
            )
            return result
        self._run_task_in_thread(run_process)

    def on_kv_post(self, base_widget):
        self.form_mapping = {
            'a_setting_name': self.ids.a_setting_name,
            'a_intrinsic_json_select': self.ids.a_intrinsic_json_select,
            'a_pattern_cols': self.ids.a_pattern_cols,
            'a_pattern_rows': self.ids.a_pattern_rows,
            'a_delta_t': self.ids.a_delta_t,
            'a_bias_path_select': self.ids.a_bias_path_select,
            'a_bias_path_select_speed': self.ids.a_bias_path_select_speed,
            'a_dot_pattern_list': self.ids.a_dot_pattern_list,
            'a_resize_dot_pattern': self.ids.a_resize_dot_pattern,
            'a_dot_box_dir_image_list': self.ids.a_dot_box_dir_image_list,
            'a_dot_box_dir_image_list_preview': self.ids.a_dot_box_dir_image_list_preview,
            'a_acquired_image_gallery': self.ids.a_acquired_image_gallery,
            'a_perspective_json_select': self.ids.a_perspective_json_select,
            'a_resize_speed_pattern': self.ids.a_resize_speed_pattern,
            'a_speed_json_select': self.ids.a_speed_json_select,
            'a_delta_t_speed': self.ids.a_delta_t_speed,
            'button_navigation_container': self.ids.button_navigation_container,
            'main_container': self.ids.main_container,
            'step_indicator_container': self.ids.step_indicator_container,
            'open_folder_perspective_button': self.ids.open_folder_perspective_button,
            'open_folder_speed_button': self.ids.open_folder_speed_button,
            'scroll_screen_A_sensor_settings': self.ids.scroll_screen_A_sensor_settings,
            'save_to_dot_box': self.ids.save_to_dot_box,
            'save_to_dot_box_preview': self.ids.save_to_dot_box_preview,
            'margin_left': self.ids.margin_left,
            'margin_top': self.ids.margin_top,
            'margin_right': self.ids.margin_right,
            'margin_bottom': self.ids.margin_bottom,
            'a_intrinsic_json_select_label': self.ids.intrinsic_info.ids.value_label,
            'a_pattern_cols_label': self.ids.pattern_cols_info.ids.value_label,
            'a_pattern_rows_label': self.ids.pattern_rows_info.ids.value_label,
            'a_bias_path_select_label': self.ids.bias_info.ids.value_label,
            'a_perspective_json_select_label': self.ids.perspective_info.ids.value_label,
            'a_speed_json_select_label': self.ids.speed_info.ids.value_label,
            'a_setting_name_edit': self.ids.a_setting_name_edit,
        }
        self.create_navigation_buttons()
        self.create_step_indicator()

        mapping_updates = {
            'prev_btn': self.ids.previous_button,
            'next_btn': self.ids.next_button,
            'widget_btn': self.ids.widget_button,
            'save_btn': self.ids.save_button,
            'step_indicator': self.ids.step_indicator,
        }

        if 'coordinate_info' in self.ids:
            coordinate_info_widget = self.ids['coordinate_info']
            mapping_updates['coordinate_info'] = coordinate_info_widget
            self.form_mapping['a_coordinate_label'] = coordinate_info_widget.ids.value_label

        if 'register_coordinate_button' in self.ids:
            mapping_updates['register_coordinate_btn'] = self.ids['register_coordinate_button']

        if 'verify_coordinate_button' in self.ids:
            mapping_updates['verify_coordinate_btn'] = self.ids['verify_coordinate_button']

        self.form_mapping.update(mapping_updates)

        self.error_mapping = {
            0: {  # SubsectionContainer 1
                'fields': {
                    'a_setting_name': {
                        'type': 'text',
                        'duplicate_check': True,
                    },
                    'a_intrinsic_json_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(INTRINSIC_PATH, text),
                    },
                    'a_pattern_cols': {
                        'type': 'text',
                    },
                    'a_pattern_rows': {
                        'type': 'text',
                    },
                    'a_delta_t': {
                        'type': 'text',
                    },
                    'a_bias_path_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(BIAS_PATH, text),
                    },
                }
            },
            1: {  # SubsectionContainer 2
                'fields': {
                    'a_dot_pattern_list_error': {
                        'type': 'custom',
                        'validator': lambda: self.get_selected_dot_pattern(),
                        'scroll': True
                    },
                    'a_perspective_json_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(PERSPECTIVE_PATH, text),
                    },
                }
            },
            2: {  # SubsectionContainer 3
                'fields': {
                    'a_speed_json_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(SPEED_PATH, text),
                    },
                }
            },
            'calibration': {
                'fields': {
                    'a_bias_path_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(BIAS_PATH, text),
                        'scroll': True
                    },
                    'a_intrinsic_json_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(INTRINSIC_PATH, text),
                        'scroll': True
                    },
                    'a_resize_dot_pattern': {
                        'type': 'text',
                        'scroll': True
                    },
                    'a_dot_pattern_list_error': {
                        'type': 'custom',
                        'validator': lambda: self.get_selected_dot_pattern(),
                        'scroll': True
                    },
                }
            },
            'angle': {
                'fields': {
                    'a_resize_dot_pattern': {
                        'type': 'text',
                        'scroll': True
                    },
                    'a_dot_pattern_list_error': {
                        'type': 'custom',
                        'validator': lambda: self.get_selected_dot_pattern(),
                        'scroll': True
                    },
                    'a_acquired_image_gallery_error': {
                        'type': 'custom',
                        'validator': lambda: self.get_selected_gallery_images(),
                    },
                    'a_margin_group_error': {
                        'type': 'margin',
                    },
                }
            },
            'speed': {
                'fields': {
                    'a_bias_path_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(BIAS_PATH, text),
                        'scroll': True
                    },
                    'a_intrinsic_json_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(INTRINSIC_PATH, text),
                        'scroll': True
                    },
                    'a_perspective_json_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(PERSPECTIVE_PATH, text),
                        'scroll': True
                    },
                    'a_resize_speed_pattern': {
                        'type': 'text',
                    },
                    'a_dot_pattern_list_error': {
                        'type': 'custom',
                        'validator': lambda: self.get_selected_dot_pattern(),
                        'scroll': True
                    },
                }
            },
            'test': {
                'fields': {
                    'a_bias_path_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(BIAS_PATH, text),
                        'scroll': True
                    },
                    'a_intrinsic_json_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(INTRINSIC_PATH, text),
                        'scroll': True
                    },
                    'a_perspective_json_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(PERSPECTIVE_PATH, text),
                        'scroll': True
                    },
                    'a_speed_json_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(SPEED_PATH, text),
                        'scroll': True
                    },
                    'a_delta_t_speed': {
                        'type': 'text',
                    },
                    'a_bias_path_select_speed': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(BIAS_PATH, text),
                    }
                }
            },
            'save': {
                'fields': {
                    'a_bias_path_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(BIAS_PATH, text),
                        'scroll': True
                    },
                    'a_intrinsic_json_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(INTRINSIC_PATH, text),
                        'scroll': True
                    },
                    'a_perspective_json_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(PERSPECTIVE_PATH, text),
                        'scroll': True
                    },
                    'a_speed_json_select': {
                        'type': 'text',
                        'path_template': lambda text: os.path.join(SPEED_PATH, text),
                        'scroll': True
                    },
                }
            },
            'save_edit': {
                'fields': {
                    'a_setting_name_edit': {
                        'type': 'text',
                        'duplicate_check': True,
                    }
                }
            }
        }
        super().on_kv_post(base_widget)

    @property
    def args_mapping(self):
        """
        Map of arguments for different operations.

        Returns:
            dict: Mapping of operation names to their required arguments
        """
        return {
            'calibration': {
                'bias_path': os.path.join(BIAS_PATH, self.form_mapping['a_bias_path_select'].text),
                'delta_t': self.form_mapping['a_delta_t'].text,
                'intrinsics_path': os.path.join(INTRINSIC_PATH, self.form_mapping['a_intrinsic_json_select'].text),
                'pattern_cols': self.form_mapping['a_pattern_cols'].text,
                'pattern_rows': self.form_mapping['a_pattern_rows'].text,
                'resize_dot_pattern': self.form_mapping['a_resize_dot_pattern'].text,
                'dot_pattern_path': self.get_selected_dot_pattern(),
            },
            'angle': {
                'pattern_cols': self.form_mapping['a_pattern_cols'].text,
                'pattern_rows': self.form_mapping['a_pattern_rows'].text,
                'dot_pattern_path': self.get_selected_dot_pattern(),
                'resize_dot_pattern': self.form_mapping['a_resize_dot_pattern'].text,
                'pattern_path': self.get_selected_gallery_images(),
            },
            'speed': {
                'delta_t': self.form_mapping['a_delta_t'].text,
                'intrinsics_path': os.path.join(INTRINSIC_PATH, self.form_mapping['a_intrinsic_json_select'].text),
                'perspective_path': os.path.join(PERSPECTIVE_PATH, self.form_mapping['a_perspective_json_select'].text),
                'pattern_cols': self.form_mapping['a_pattern_cols'].text,
                'pattern_rows': self.form_mapping['a_pattern_rows'].text,
                'dot_pattern_path': self.get_selected_dot_pattern(),
                'resize_dot_pattern': self.form_mapping['a_resize_speed_pattern'].text,
                'bias_path': os.path.join(BIAS_PATH, self.form_mapping['a_bias_path_select'].text),
            },
            'test': {
                'bias_path': self.get_test_bias_path(),
                'delta_t': self.form_mapping['a_delta_t_speed'].text,
                'intrinsics_path': os.path.join(INTRINSIC_PATH, self.form_mapping['a_intrinsic_json_select'].text),
                'perspective_path': os.path.join(PERSPECTIVE_PATH, self.form_mapping['a_perspective_json_select'].text),
                'speed_path': os.path.join(SPEED_PATH, self.form_mapping['a_speed_json_select'].text),
            },
            'save': {
                'name': self.form_mapping['a_setting_name'].text,
                'intrinsic_path': os.path.join(INTRINSIC_PATH, self.form_mapping['a_intrinsic_json_select'].text),
                'bias_path': os.path.join(BIAS_PATH, self.form_mapping['a_bias_path_select'].text),
                'perspective_path': os.path.join(PERSPECTIVE_PATH, self.form_mapping['a_perspective_json_select'].text),
                'speed_path': os.path.join(SPEED_PATH, self.form_mapping['a_speed_json_select'].text),
                'pattern_cols': self.form_mapping['a_pattern_cols'].text,
                'pattern_rows': self.form_mapping['a_pattern_rows'].text,
            },
            'save_edit': {
                'name': self.form_mapping['a_setting_name_edit'].text,
            }
        }

    def scroll_screen_a_to_default(self):
        """Scroll the screen to default position (top) and reset subsection."""
        try:
            scroll_view = self.form_mapping['scroll_screen_A_sensor_settings']
            if not scroll_view:
                print(
                    "Could not find ScrollView with id 'scroll_screen_A_sensor_settings'")
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
            self.reset_subsection()
        except Exception:
            traceback.print_exc()

    def reset_subsection(self, subsection=0):
        """
        Reset to a specific subsection.

        Args:
            subsection: The subsection index to reset to (default: 0)
        """
        self.current_subsection = subsection
        self.schedule_update_ui()

    def on_pre_enter(self, *args):
        """Event called before screen is displayed"""
        self.form_mapping['a_dot_pattern_list'].scroll_y = 1.0
        self.reset_screen_a()
        delete_images_in_folders(
            folder_paths=[DOT_BOX_PATH, DOT_BOX_PATH_PREVIEW, OUTPUT_INTRINSIC_PATH, HISTOGRAM_TEST_PATH]
            )

        # Reload table data
        self.sensor_settings_table.load_settings_from_db(
            keep_current_page=False
        )

        self.load_dot_pattern_images()
        # Reload json
        screens = self.app.root.ids.screen_manager.screens
        for screen in screens:
            if hasattr(screen, 'spinners'):
                for spinner in screen.spinners.values():
                    spinner.load_spinner_from_folder(
                    )
        self.update_dot_score()
    def update_dot_score(self):
        """Update dot score value from database."""
        value = self.get_dot_score_from_db()
        self.dot_score = str(value) if value is not None else ''

    def get_selected_dot_box_dir_images(self):
        """Get selected image list from dot_box_dir_image_list."""
        try:
            gallery = self.form_mapping['a_dot_box_dir_image_list']
            return gallery.get_selected_images()  # Return string path or None
        except Exception:
            traceback.print_exc()
            return None

    def json_reload(self, spinner_id=None, keep_selected_text=False):
        """
        Only reload spinner according to passed spinner_id.
        If spinner_id=None then do nothing.
        """
        try:
            if spinner_id and spinner_id in self.spinners:
                spinner = self.spinners[spinner_id]
                spinner.load_spinner_from_folder(keep_selected_text=keep_selected_text)
        except Exception:
            traceback.print_exc()


    def open_folder(self, folder_path):
        """
        Open folder in Windows Explorer.

        Args:
            folder_path: Path to the folder to open
        """
        folder_path = os.path.normpath(folder_path)
        # Find nearest existing directory by going up parent directories
        while folder_path and not os.path.exists(folder_path):
            parent_folder = os.path.dirname(folder_path)
            if parent_folder == folder_path:
                break
            folder_path = parent_folder
        try:
            subprocess.Popen(f'explorer "{folder_path}"')
        except Exception:
            traceback.print_exc()

    def load_gallery_images(self, folder_path=OUTPUT_INTRINSIC_PATH):
        """
        Load images into gallery widget.

        Args:
            folder_path: Path to the folder containing images
        """
        if not os.path.exists(folder_path):
            os.makedirs(folder_path, exist_ok=True)
        gallery = self.form_mapping['a_acquired_image_gallery']
        gallery.load_images(folder_path)

    def get_selected_gallery_images(self):
        """Get selected image list from gallery."""
        gallery = self.form_mapping['a_acquired_image_gallery']
        return gallery.get_selected_images()

    def get_delete_warning_message(self, item):
        """Get the warning message key for delete confirmation."""
        return 'delete_message_popup'

    def delete_item(self, item):
        """
        Delete a sensor settings item from database.

        Args:
            item: Dictionary containing item data with 'name' key
        """
        with get_db() as db:
            try:
                item_id = self._get_id_by_name(
                    db,
                    SensorSettings,
                    item.get('name')
                    )

                if not item_id:
                    return

                recursive_delete(SensorSettings, item_id, db_session=db)

                db.commit()

            except Exception as e:
                db.rollback()
                traceback.print_exc()
                raise e

        self.sensor_settings_table.load_settings_from_db()

        if self.editing_item_name == item.get('name'):
            # Reset form if editing deleted item
            self.reset_screen_a()

    def _get_id_by_name(self, db, table, name):
        """
        Get item ID by name from database table.

        Args:
            db: Database session
            table: Database table model
            name: Name of the item to find

        Returns:
            int or None: Item ID if found, None otherwise
        """
        query = db.query(table.id).filter(table.name == name)
        if hasattr(table, 'deleted_at'):
            query = query.filter(table.deleted_at.is_(None))
        data = query.first()
        return data.id if data else None

    def load_item_to_form(self, item):
        """Load item information into form for editing"""
        try:
            self.current_subsection = 4
            self.schedule_update_ui()
            self.reset_error_screen_a()
            self.editing_item_name = item.get('name', '')

            # Load values into form
            self.form_mapping['a_setting_name_edit']._suppress_suggestion_popup = True # pylint: disable=protected-access
            self.form_mapping['a_setting_name_edit'].text = self.editing_item_name
            self.form_mapping['a_setting_name_edit'].focus = True

            try:
                self.form_mapping['a_setting_name_edit'].cursor = (len(self.editing_item_name), 0)
                if hasattr(self.form_mapping['a_setting_name_edit'], 'scroll_x'):
                    self.form_mapping['a_setting_name_edit'].scroll_x = 0
                if hasattr(self.form_mapping['a_setting_name_edit'], '_trigger_refresh_text'):
                    self.form_mapping['a_setting_name_edit']._trigger_refresh_text() # pylint: disable=protected-access
                if hasattr(self.form_mapping['a_setting_name_edit'], 'selection_text'):
                    self.form_mapping['a_setting_name_edit'].selection_text = ''
            except Exception:
                traceback.print_exc()

            self.form_mapping['a_setting_name_edit']._suppress_suggestion_popup = False # pylint: disable=protected-access

            config = item.get('config', {})
            self.form_mapping['a_bias_path_select_label'].text = config.get('bias_path') if config.get('bias_path') else ''
            self.form_mapping['a_intrinsic_json_select_label'].text = config.get('intrinsic_path') if config.get('intrinsic_path') else ''
            self.form_mapping['a_pattern_cols_label'].text = str(config.get('pattern_cols'))
            self.form_mapping['a_pattern_rows_label'].text = str(config.get('pattern_rows'))
            self.form_mapping['a_perspective_json_select_label'].text = config.get('perspective_path') if config.get('perspective_path') else ''
            self.form_mapping['a_speed_json_select_label'].text = config.get('speed_path') if config.get('speed_path') else ''
            self.form_mapping['a_coordinate_label'].text_key = self.get_modify_coordinate_info()

        except Exception:
            traceback.print_exc()

    def _reset_editing_state(self):
        """Reset editing state and reload data after save."""
        target_record_name = None
        if self.editing_item_name:
            target_record_name = self.editing_item_name

        self.editing_item_name = None

        try:
            if target_record_name:
                target_page = self.sensor_settings_table.find_page_for_record(
                    record_name=target_record_name,
                )
                self.sensor_settings_table.load_settings_from_db(
                    keep_current_page=False,
                    target_page=target_page
                )
            else:
                self.sensor_settings_table.load_settings_from_db(keep_current_page=False)
        except ValueError:
            self.sensor_settings_table.load_settings_from_db()

        for spinner in self.spinners.values():
            spinner.load_spinner_from_folder()

        self.__show_popup(
            title='notification_popup',
            message='save_sensor_settings_popup_A_done'
        )
        self.reset_screen_a()

    def check_duplicate_name(self, name):
        """
        Check if a name already exists in the database.

        Args:
            name: Name to check for duplicates

        Returns:
            bool: True if duplicate exists, False otherwise
        """
        if self.editing_item_name is None or name != self.editing_item_name:
            existing_names = [item["name"].strip().lower()
                                for item in self.sensor_settings_table.all_rows]
            if name.strip().lower() in existing_names:
                return True
        return False

    def save_prophesee_settings(self):
        """
        Save or update sensor settings to database.

        Returns:
            bool: True if save successful, False otherwise
        """
        try:
            self.reset_error_screen_a()
            if self.editing_item_name:
                errors, json_errors = self.validate_fields(key_validation='save_edit')
            else:
                errors, json_errors = self.validate_fields(key_validation='save')

            if self._handle_validation_errors(
                errors=errors,
                json_errors=json_errors,
                error_message='save_sensor_settings_popup_A_failed'
            ):
                return

            with get_db() as db:
                # Save to DB
                if self.editing_item_name:
                    # Edit mode
                    setting = db.query(SensorSettings).filter(SensorSettings.name == self.editing_item_name,
                                                              SensorSettings.deleted_at.is_(None)).first()
                    if setting:
                        update_sensor_settings(
                            db=db,
                            setting_id=setting.id,
                            **self.args_mapping['save_edit']
                        )
                else:
                    # Add new mode
                    create_sensor_settings(
                        db=db,
                        **self.args_mapping['save']
                    )
            self._reset_editing_state()
            return True

        except Exception:
            self.__show_popup(
                title='error_popup',
                message='save_sensor_settings_popup_A_failed'
            )
            traceback.print_exc()
            return False

    def validate_use_sensor(self, use_sensor_value):
        """
        Validate and normalize USE_SENSOR value.

        Args:
            use_sensor_value: The USE_SENSOR value from environment

        Returns:
            str: '0' or '1' (valid sensor values)

        Raises:
            ValueError: If the value cannot be converted to a valid sensor value
        """
        if use_sensor_value is None:
            return "1"  # Default value

        try:
            # Convert to string first
            str_value = str(use_sensor_value).strip()

            # Check if it's already a valid string value
            if str_value in ['0', '1']:
                return str_value

            # Try to convert to int first, then validate
            int_value = int(float(str_value))  # Handle cases like '1.0'
            if int_value in [0, 1]:
                return str(int_value)
            else:
                raise ValueError(f"Sensor value must be 0 or 1, got: {int_value}")

        except Exception as e:
            raise ValueError(
                f"Cannot process USE_SENSOR value '{use_sensor_value}': {str(e)}"
            ) from e

    def get_dot_score_from_db(self):
        """
        Get dot_score value from DB.

        Returns:
            float: Dot score value from database or default value if error
        """
        try:
            with get_db() as db:
                result = float(read_system_config(db, "DOT_POINT").value)
                print("Dot score from DB:", result)
                return result
        except Exception:
            traceback.print_exc()
            return DOT_SCORE_DEFAULT


    def handle_pipe_error(self, error_message):
        """
        Handle pipe error by dismissing loading popup and showing error message.

        Args:
            error_message: Error message key to display
        """
        if self.loading_popup:
            self.loading_popup.opacity = 0
            self.loading_popup.dismiss()
            self.loading_popup = None
        self.__show_popup(
            title='error_popup',
            message=error_message
        )

    def on_pipe(self, data):
        """
        Handle pipe data based on current pipe mode.

        Args:
            data: Data received from pipe
        """
        if self.pipe_mode == 'calibration':
            self.on_pipe_calibration(data)
        elif self.pipe_mode == 'angle':
            self.on_pipe_angle(data)
        elif self.pipe_mode == 'speed':
            self.on_pipe_speed(data)
        elif self.pipe_mode == 'test':
            self.on_pipe_test(data)
        elif self.pipe_mode == 'coordinate':
            self.on_pipe_coordinate(data)
        elif self.pipe_mode == 'verify_coordinate':
            self.on_pipe_verify_coordinate(data)

    def on_pipe_calibration(self, obj):
        """
        Handle calibration pipe data.

        Args:
            obj: Data object from calibration pipe
        """
        if obj.get('status_code') == 'D023' and obj.get('data'):
            a_dot_box_dir_image_list = self.form_mapping['a_dot_box_dir_image_list']
            if not self._received_dot_box_image:
                a_dot_box_dir_image_list.ids.content_layout.clear_widgets()
            a_dot_box_dir_image_list.load_stream_images(
                image_path=obj.get('data'),
                dot_streaming=True
            )
            if self.loading_popup:
                self.loading_popup.opacity = 0
                self.loading_popup.dismiss()
                self.loading_popup = None
                self.set_left_mouse_disabled(True)

            self._received_dot_box_image = True

        if obj.get('status_code') == 'D002' and obj.get('data'):
            a_acquired_image_gallery = self.form_mapping['a_acquired_image_gallery']
            if not self._received_gallery_image:
                a_acquired_image_gallery.ids.content_layout.clear_widgets()
            a_acquired_image_gallery.load_stream_images(
                image_path=obj.get('data'),
                dot_streaming=False
            )
            if self.loading_popup:
                self.loading_popup.opacity = 0
                self.loading_popup.dismiss()
                self.loading_popup = None
                self.set_left_mouse_disabled(True)

            self._received_gallery_image = True

        if obj.get('status_code') == 'D003':
            if self.loading_popup:
                self.loading_popup.opacity = 0
                self.loading_popup.dismiss()
                self.loading_popup = None
            # When receiving stop signal, check if any images have been received
            if not self._received_dot_box_image:
                self.init_empty_dot_box_dir_list()

            if not self._received_gallery_image:
                self.init_empty_gallery()
                self.__show_popup(
                    title='error_popup',
                    message='get_correction_data_A_failed_no_dot_score'
                )

            # Reset image receiving state for next time
            self._received_gallery_image = False
            self._received_dot_box_image = False
            self.set_left_mouse_disabled(False)

        if obj.get('status_code') == 'E001':
            self.handle_pipe_error(error_message='get_correction_data_A_failed')
            self._received_gallery_image = False
            self._received_dot_box_image = False
            self.set_left_mouse_disabled(False)


    def on_pipe_angle(self, obj):
        """
        Handle angle pipe data.

        Args:
            obj: Data object from angle pipe
        """
        if obj.get('status_code') == 'D005' and obj.get('data'):
            self.form_mapping['a_perspective_json_select'].text = os.path.basename(obj.get('data').get('export_path'))
            if obj.get('data').get('auto_margin'):
                self.form_mapping['margin_top'].ids.margin_input.text = str(obj.get('data').get('auto_margin')[0])
                self.form_mapping['margin_bottom'].ids.margin_input.text = str(obj.get('data').get('auto_margin')[1])
                self.form_mapping['margin_left'].ids.margin_input.text = str(obj.get('data').get('auto_margin')[2])
                self.form_mapping['margin_right'].ids.margin_input.text = str(obj.get('data').get('auto_margin')[3])
            self._received_perspective_json = True

        if obj.get('status_code') == 'D006' or obj.get('message') == 'End Export Perspective':
            if self.loading_popup:
                self.loading_popup.opacity = 0
                self.loading_popup.dismiss()
                self.loading_popup = None
            self.json_reload(spinner_id='a_perspective_json_select', keep_selected_text=True)

            if not self._received_perspective_json:
                self.__show_popup(
                    title='error_popup',
                    message='get_perspective_correction_A_failed'
                )
            self._received_perspective_json = False

        if obj.get('status_code') == 'E001':
            self.handle_pipe_error(error_message='get_perspective_correction_A_failed')
            self._received_perspective_json = False


    def on_pipe_speed(self, obj):
        """
        Handle speed pipe data.

        Args:
            obj: Data object from speed pipe
        """
        if obj.get('status_code') == 'D023' and obj.get('data'):
            a_dot_box_dir_image_list_preview = self.form_mapping['a_dot_box_dir_image_list_preview']
            if not self._received_dot_box_preview_image:
                a_dot_box_dir_image_list_preview.ids.content_layout.clear_widgets()
            a_dot_box_dir_image_list_preview.load_stream_images(
                image_path=obj.get('data'),
                dot_streaming=True
            )
            if self.loading_popup:
                self.loading_popup.opacity = 0
                self.loading_popup.dismiss()
                self.loading_popup = None
                self.set_left_mouse_disabled(True)

            self._received_dot_box_preview_image = True

        if obj.get('status_code') == 'D008' and obj.get('data'):
            self.form_mapping['a_speed_json_select'].text = os.path.basename(obj.get('data'))
            self._received_speed_json = True

        if obj.get('status_code') == 'D009':
            if self.loading_popup:
                self.loading_popup.opacity = 0
                self.loading_popup.dismiss()
                self.loading_popup = None
            self.json_reload(spinner_id='a_speed_json_select', keep_selected_text=True)

            if not self._received_dot_box_preview_image:
                self.init_empty_dot_box_dir_list_preview()

            if not self._received_speed_json:
                self.__show_popup(
                    title='error_popup',
                    message='get_motion_correction_A_failed'
                )
            self._received_speed_json = False
            self._received_dot_box_preview_image = False
            self.set_left_mouse_disabled(False)

        if obj.get('status_code') == 'E001':
            self.handle_pipe_error(error_message='get_motion_correction_A_failed')
            self._received_speed_json = False
            self._received_dot_box_preview_image = False
            self.set_left_mouse_disabled(False)


    def on_pipe_test(self, obj):
        """
        Handle test pipe data.

        Args:
            obj: Data object from test pipe
        """
        if obj.get('status_code') == 'D005' and obj.get('data'):
            self._received_test_histogram = True
        if obj.get('status_code') == 'D012' or obj.get('message') == 'End Export Histogram':
            if self.loading_popup:
                self.loading_popup.opacity = 0
                self.loading_popup.dismiss()
                self.loading_popup = None
            self._received_test_histogram = False

        if obj.get('status_code') == 'E001':
            self.handle_pipe_error(error_message='test_simple_activity_A_failed')
            self._received_test_histogram = False

        if obj.get('status_code') == 'E002':
            self.handle_pipe_error(error_message='ini_error_message_E2')
            self._received_test_histogram = False

    def on_pipe_coordinate(self, obj):
        """
        Handle coordinate pipe data.
        """
        if obj.get('status_code') == 'D029' and obj.get('data'):
            self._received_coordinate = True
            self.update_register_coordinate_db(pose_file_path=obj.get('data'))
            def update_ui(dt):
                self.form_mapping['a_coordinate_label'].text_key = 'coordinate_registered'
                self.update_navigation_buttons()
            Clock.schedule_once(update_ui, -1)
        if obj.get('status_code') == 'D030':
            if self.loading_popup:
                self.loading_popup.opacity = 0
                self.loading_popup.dismiss()
                self.loading_popup = None
            self._received_coordinate = False
        if obj.get('status_code') == 'E001':
            self._received_coordinate = False
            self.handle_pipe_error(error_message='register_coordinate_A_failed')

    def on_pipe_verify_coordinate(self, obj):
        """
        Handle verify coordinate pipe data.
        """
        if obj.get('status_code') == 'D030':
            if self.loading_popup:
                self.loading_popup.opacity = 0
                self.loading_popup.dismiss()
                self.loading_popup = None
            self._received_coordinate = False
        if obj.get('status_code') == 'E001':
            self._received_coordinate = False
            self.handle_pipe_error(error_message='register_coordinate_A_failed')

    @contextmanager
    def process_context(self, pipe_mode, error_message, cleanup_functions=None):
        """
        Common context manager for all processes in SensorSettingsScreen

        Args:
            pipe_mode (str): Mode for pipe ('calibration', 'angle', 'speed', 'test')
            error_message (str): Message to display when error occurs
            cleanup_functions (list): List of additional cleanup functions
        """
        self.set_left_mouse_disabled(True)
        self.pipe_mode = pipe_mode

        # Set thread running flag based on mode
        thread_flag_name = f'_{pipe_mode}_thread_running'
        setattr(self, thread_flag_name, False)

        try:
            yield
        except Exception:
            traceback.print_exc()

            # Run cleanup functions if any
            if cleanup_functions:
                for cleanup_func in cleanup_functions:
                    try:
                        cleanup_func()
                    except Exception:
                        traceback.print_exc()

            self.__show_popup(
                title='error_popup',
                message=error_message
            )
            raise
        finally:
            # Only unlock if thread has not been started
            if not getattr(self, thread_flag_name, False):
                self.set_left_mouse_disabled(False)

    def _maybe_int_arg(self, command, flag, value):
        """
        Add integer argument to command if value is valid.

        Args:
            command: Command list to append to
            flag: Flag to add before value
            value: Value to convert to int and add
        """
        if value is None:
            return
        if isinstance(value, str):
            v = value.strip()
            if not v:
                return
            try:
                v = int(v)
            except Exception:
                return
            command.extend([flag, str(v)])
        else:
            command.extend([flag, str(value)])


    def find_subsection_by_field_id(self, field_id):
        """
        Find subsection containing a specific field ID.

        Args:
            field_id: ID of the field to find

        Returns:
            Subsection key if found, None otherwise
        """
        for subsection_key, subsection_data in self.error_mapping.items():
            if 'fields' in subsection_data:
                fields = subsection_data['fields']
                if field_id in fields:
                    return subsection_key

        return None

    def _handle_validation_errors(
        self,
        errors,
        json_errors,
        error_message=None,
        cleanup_functions=None,
    ):
        """
        Handle validation errors by showing popup and scrolling to first error

        Args:
            errors: List of (widget_id, error_msg) tuples for input validation errors
            json_errors: List of (widget_id, error_msg) tuples for json validation errors
            error_message: Message to show in error popup
            cleanup_functions: Optional list of cleanup functions to run
        """

        error_widgets = []
        has_any_error = False
        first_error_widget_id = None

        if errors:
            for error_id, error_msg, should_scroll in errors:
                if error_id in self.ids:
                    self.ids[error_id].validate_text(error_msg)
                    if self.ids[error_id].error_message:
                        has_any_error = True

                        widget_y = self.ids[error_id].y
                        if should_scroll:
                            error_widgets.append((error_id, widget_y))

        if json_errors:
            has_any_error = True
            for error_id, error_msg, should_scroll in json_errors:
                if error_id in self.ids:
                    self.ids[error_id].error_message = error_msg

                    widget_y = self.ids[error_id].y
                    if should_scroll:
                        error_widgets.append((error_id, widget_y))

        if error_widgets:
            error_widgets.sort(key=lambda x: x[1], reverse=True)
            first_error_widget_id = error_widgets[0][0]

        if has_any_error:
            if not error_message:
                if first_error_widget_id:
                    subsection = self.find_subsection_by_field_id(first_error_widget_id)
                    if subsection is not None and isinstance(subsection, int):
                        self.reset_subsection(subsection=subsection)
                    scroll_to_widget(
                        scroll_view=self.form_mapping['scroll_screen_A_sensor_settings'],
                        widget=self.ids[first_error_widget_id]
                        )
                return True
            else:
                def on_popup_dismiss():
                    if cleanup_functions:
                        for cleanup_fn in cleanup_functions:
                            try:
                                cleanup_fn()
                            except Exception:
                                traceback.print_exc()

                    if first_error_widget_id:
                        subsection = self.find_subsection_by_field_id(first_error_widget_id)
                        if subsection is not None and isinstance(subsection, int):
                            self.reset_subsection(subsection=subsection)
                        scroll_to_widget(
                            scroll_view=self.form_mapping['scroll_screen_A_sensor_settings'],
                            widget=self.ids[first_error_widget_id]
                        )

                popup = self.popup.create_adaptive_popup(
                    title='error_popup',
                    message=error_message
                )
                popup.bind(on_dismiss=lambda *args: on_popup_dismiss())
                popup.open()
                return True
        return False


    def validate_margins(self):
        """
        Validate margin inputs
        Returns: (is_valid, error_message_key, margin_values)
        """
        margin_left = self.form_mapping['margin_left'].ids.margin_input.text.strip()
        margin_top = self.form_mapping['margin_top'].ids.margin_input.text.strip()
        margin_right = self.form_mapping['margin_right'].ids.margin_input.text.strip()
        margin_bottom = self.form_mapping['margin_bottom'].ids.margin_input.text.strip()

        margin_values = [margin_top, margin_bottom, margin_left, margin_right]

        if not any(margin_values):
            return (True, None, margin_values)

        processed_margins = []
        for m in margin_values:
            if m and m.isdigit():
                processed_margins.append(int(m))
            else:
                processed_margins.append(None)

        if not (len(processed_margins) == 4 and all(v is not None for v in processed_margins)):
            return (False, 'range_int_num_message', margin_values)

        if not all(0 <= v <= 1280 for v in processed_margins if v is not None):
            return (False, 'range_int_num_message', margin_values)

        return (True, None, margin_values)

    def _init_galleries(self):
        """Initialize gallery widgets with empty state."""
        a_acquired_image_gallery = self.form_mapping['a_acquired_image_gallery']
        a_acquired_image_gallery.show_no_data_message()
        a_acquired_image_gallery.do_scroll_x = False
        a_acquired_image_gallery.do_scroll_y = False
        a_acquired_image_gallery.scroll_x = 0
        a_acquired_image_gallery.scroll_y = 1


        a_dot_box_dir_image_list = self.form_mapping['a_dot_box_dir_image_list']
        a_dot_box_dir_image_list.show_no_data_message()
        a_dot_box_dir_image_list.do_scroll_x = False
        a_dot_box_dir_image_list.do_scroll_y = False
        a_dot_box_dir_image_list.scroll_x = 0
        a_dot_box_dir_image_list.scroll_y = 1

    def _init_galleries_preview(self):
        """Initialize gallery widgets with empty state."""
        a_dot_box_dir_image_list_preview = self.form_mapping['a_dot_box_dir_image_list_preview']
        a_dot_box_dir_image_list_preview.enable_select = False
        a_dot_box_dir_image_list_preview.show_no_data_message()
        a_dot_box_dir_image_list_preview.do_scroll_x = False
        a_dot_box_dir_image_list_preview.do_scroll_y = False
        a_dot_box_dir_image_list_preview.scroll_x = 0
        a_dot_box_dir_image_list_preview.scroll_y = 1

    def _process_dot_box_dir(self):
        """Process dot box directory selection"""
        dot_box_dir = None
        if getattr(self.form_mapping['save_to_dot_box'].ids.checkbox, "active"):
            dot_box_path_text = self.dot_box_path_value
            if (
                dot_box_path_text
                and os.path.normcase(dot_box_path_text) != os.path.normcase(DOT_BOX_PATH)
            ):
                dot_box_dir = os.path.join(dot_box_path_text, "dot")
            else:
                dot_box_dir = DOT_BOX_PATH
                self.set_dot_box_path_to_value(os.path.normpath(DOT_BOX_PATH), preview=False)
        else:
            self.set_dot_box_path_to_placeholder(preview=False)
        return dot_box_dir

    def _process_dot_box_dir_preview(self):
        """Process dot box directory selection"""
        dot_box_dir = None
        if getattr(self.form_mapping['save_to_dot_box_preview'].ids.checkbox, "active"):
            dot_box_path_text = self.dot_box_path_preview_value
            if (
                dot_box_path_text
                and os.path.normcase(dot_box_path_text) != os.path.normcase(DOT_BOX_PATH_PREVIEW)
            ):
                dot_box_dir = os.path.join(dot_box_path_text, "dot_preview")
            else:
                dot_box_dir = DOT_BOX_PATH_PREVIEW
                self.set_dot_box_path_to_value(os.path.normpath(DOT_BOX_PATH_PREVIEW), preview=True)
        else:
            self.set_dot_box_path_to_placeholder(preview=True)
        return dot_box_dir

    def collect_calibration_data(self):
        """Collect calibration data from sensor."""
        cleanup_functions = [
            self.init_empty_dot_box_dir_list,
            self.init_empty_gallery
        ]

        with self.process_context(
            pipe_mode='calibration',
            error_message='get_correction_data_A_failed',
            cleanup_functions=cleanup_functions
        ):
            self.reset_error_screen_a()

            self._init_galleries()

            errors, json_errors = self.validate_fields(key_validation='calibration')

            if self._handle_validation_errors(
                errors=errors,
                json_errors=json_errors,
                error_message='get_correction_data_A_failed',
                cleanup_functions=cleanup_functions,
            ):
                return

            dot_box_dir = self._process_dot_box_dir()

            if dot_box_dir:
                delete_images_in_folders(
                    folder_paths=[dot_box_dir, OUTPUT_INTRINSIC_PATH]
                )
            else:
                delete_images_in_folders(
                    folder_paths=[OUTPUT_INTRINSIC_PATH]
                )

            self._calibration_thread_running = True
            def run_process():
                try:
                    return self._collect_calibration_data(
                        raw_path=RAW_PATH,
                        **self.args_mapping['calibration'],
                        dot_box_dir=dot_box_dir,
                        export_dir=OUTPUT_INTRINSIC_PATH,
                    )
                finally:
                    self._calibration_thread_running = False

            self._run_task_in_thread(run_process)
    def _collect_calibration_data(
        self,
        raw_path: str,
        delta_t: int,
        intrinsics_path: str,
        pattern_cols: int,
        pattern_rows: int,
        dot_pattern_path: str,
        export_dir: str,
        resize_dot_pattern: int = '',
        dot_box_dir: str = None,
        bias_path: str = None,
    ):
        dot_score = self.get_dot_score_from_db()

        try:
            use_sensor = self.validate_use_sensor(USE_SENSOR)
        except ValueError as e:
            print(f"Warning: {e}. Using default value '1'")
            use_sensor = "1"

        command = [
            "--raw_path", fr"{raw_path}",
            "--delta_t", str(delta_t),
            "--intrinsics_path", fr"{intrinsics_path}",
            "--pattern_cols", str(pattern_cols),
            "--pattern_rows", str(pattern_rows),
            "--export_dir", fr"{export_dir}",
            "--use_sensor", use_sensor
        ]
        if bias_path is not None and bias_path != '':
            command.extend(["--bias_path", fr"{bias_path}"])
        if dot_pattern_path is not None:
            command.extend(["--dot_pattern_path", fr"{dot_pattern_path}"])

        if dot_score is not None:
            command.extend(["--dot_score", str(dot_score)])

        self._maybe_int_arg(command, "--resize_dot_pattern", resize_dot_pattern)

        if dot_box_dir is not None:
            command.extend(["--dot_box_dir", dot_box_dir])

        result = self._run_cli(
            script_path=os.path.join(BE_FOLDER, 'flows', 'settings', 'export_dot_pattern_image.py'),
            use_module=False,
            arg_list=command,
            title_window_focus=["Dot Detector"],
            cwd=BE_FOLDER,
            use_pipe_server=True
        )
        return result

    def collect_angle_calibration_data(self):
        """Collect angle calibration data from sensor."""
        with self.process_context(
            pipe_mode='angle',
            error_message='get_perspective_correction_A_failed'
        ):
            self.reset_error_screen_a()
            self.form_mapping['a_perspective_json_select'].text = ''

            errors, json_errors, margin_values = self.validate_fields(key_validation='angle')

            if self._handle_validation_errors(
                errors=errors,
                json_errors=json_errors,
                error_message='get_perspective_correction_A_failed'
            ):
                return

            self._angle_thread_running = True
            def run_process():
                try:
                    return self._collect_angle_calibration_data(
                        **self.args_mapping['angle'],
                        export_dir=PERSPECTIVE_PATH,
                        margin=f"{margin_values[0]}, {margin_values[1]}, {margin_values[2]}, {margin_values[3]}" if any(margin_values) else None,
                    )
                finally:
                    self._angle_thread_running = False

            self._run_task_in_thread(run_process)

    def _collect_angle_calibration_data(
        self,
        pattern_cols: int,
        pattern_rows: int,
        export_dir: str,
        dot_pattern_path: str,
        pattern_path: str,
        margin: Optional[List[int]],
        resize_dot_pattern: int = None,
        ratio_perspective: float = 1.0,
    ):
        dot_score = self.get_dot_score_from_db()

        command = [
            "--ratio_perspective", str(ratio_perspective),
            "--pattern_cols", str(pattern_cols),
            "--pattern_rows", str(pattern_rows),
            "--export_dir", fr"{export_dir}",
        ]

        if dot_pattern_path is not None:
            command.extend(["--dot_pattern_path", fr"{dot_pattern_path}"])

        if pattern_path is not None:
            command.extend(["--pattern_path", fr"{pattern_path}"])

        if margin is not None:
            command.extend(["--margin", margin])

        if dot_score is not None:
            command.extend(["--dot_score", str(dot_score)])

        self._maybe_int_arg(command, "--resize_dot_pattern", resize_dot_pattern)

        result = self._run_cli(
            script_path=os.path.join(BE_FOLDER, 'flows', 'settings', 'export_perspective_settings_margin.py'),
            use_module=False,
            arg_list=command,
            title_window_focus=["Dot Detector"],
            cwd=BE_FOLDER,
            use_pipe_server=True
        )
        return result

    def collect_speed_calibration_data(self):
        """Collect speed calibration data from sensor."""
        cleanup_functions = [
            self.init_empty_dot_box_dir_list_preview,
        ]
        with self.process_context(
            pipe_mode='speed',
            error_message='get_motion_correction_A_failed',
            cleanup_functions=cleanup_functions
        ):
            self.reset_error_screen_a()

            self._init_galleries_preview()

            self.form_mapping['a_speed_json_select'].text = ''

            errors, json_errors = self.validate_fields(key_validation='speed')

            if self._handle_validation_errors(
                errors=errors,
                json_errors=json_errors,
                error_message='get_motion_correction_A_failed'
            ):
                return

            dot_box_dir_preview = self._process_dot_box_dir_preview()

            if dot_box_dir_preview:
                delete_images_in_folders(
                    folder_paths=[dot_box_dir_preview]
                )

            self._speed_thread_running = True
            def run_process():
                try:
                    return self._collect_speed_calibration_data(
                        raw_path=RAW_PATH,
                        export_dir=SPEED_PATH,
                        dot_box_dir_preview=dot_box_dir_preview,
                        **self.args_mapping['speed'],
                    )
                finally:
                    self._speed_thread_running = False

            self._run_task_in_thread(run_process)


    def _collect_speed_calibration_data(
        self,
        raw_path: str,
        delta_t: int,
        intrinsics_path: str,
        perspective_path: str,
        pattern_cols: int,
        pattern_rows: int,
        dot_pattern_path: str,
        export_dir: str,
        resize_dot_pattern: int = '',
        bias_path: str = None,
        dot_box_dir_preview: str = None,
    ):
        dot_score = self.get_dot_score_from_db()

        try:
            use_sensor = self.validate_use_sensor(USE_SENSOR)
        except ValueError as e:
            print(f"Warning: {e}. Using default value '1'")
            use_sensor = "1"

        command = [
            "--raw_path", fr"{raw_path}",
            "--delta_t", str(delta_t),
            "--intrinsics_path", fr"{intrinsics_path}",
            "--perspective_path", fr"{perspective_path}",
            "--pattern_cols", str(pattern_cols),
            "--pattern_rows", str(pattern_rows),
            "--export_dir", fr"{export_dir}",
            "--use_sensor", use_sensor

        ]
        if dot_score is not None:
            command.extend(["--dot_score", str(dot_score)])

        self._maybe_int_arg(command, "--resize_dot_pattern", resize_dot_pattern)

        if dot_pattern_path is not None:
            command.extend(["--dot_pattern_path", fr"{dot_pattern_path}"])
        if bias_path is not None:
            command.extend(["--bias_path", fr"{bias_path}"])
        if dot_box_dir_preview is not None:
            command.extend(["--dot_box_dir", fr"{dot_box_dir_preview}"])

        result = self._run_cli(
            script_path=os.path.join(BE_FOLDER, 'flows', 'settings', 'export_speed_settings.py'),
            use_module=False,
            arg_list=command,
            title_window_focus=["Dot Detector"],
            cwd=BE_FOLDER,
            use_pipe_server=True
        )
        return result

    def test_simple_activity(self):
        """Test simple activity with current sensor settings."""
        with self.process_context(
            pipe_mode='test',
            error_message='test_simple_activity_A_failed'
        ):
            self.reset_error_screen_a()

            errors, json_errors = self.validate_fields(key_validation='test')

            if self._handle_validation_errors(
                errors=errors,
                json_errors=json_errors,
                error_message='test_simple_activity_A_failed',
            ):
                return

            delete_images_in_folders(folder_paths=[HISTOGRAM_TEST_PATH])

            self._test_thread_running = True
            def run_process():
                try:
                    self._test_simple_activity(
                        raw_path=RAW_PATH,
                        **self.args_mapping['test'],
                    )
                finally:
                    self._test_thread_running = False

            self._run_task_in_thread(run_process)

    def _test_simple_activity(
        self,
        raw_path: str,
        delta_t: int,
        intrinsics_path: str,
        perspective_path: str,
        speed_path: str,
        histogram_add_pixel_params: float = 0.8,
        bias_path: str = None,
        export_dir: str = HISTOGRAM_TEST_PATH,
    ):
        try:
            with get_db() as db:
                configs = db.query(SystemConfig.key, SystemConfig.value) \
                    .filter(SystemConfig.key.in_([
                        "SHOW_HIS_IMAGE_WINDOW_WIDTH",
                        "SHOW_HIS_IMAGE_WINDOW_HEIGHT",
                        "SHOW_IMAGE_WINDOW_WIDTH",
                        "SHOW_IMAGE_WINDOW_HEIGHT"
                    ])).all()

                config_dict = {key: value for key, value in configs}
                show_his_image_window = f"{config_dict.get('SHOW_HIS_IMAGE_WINDOW_WIDTH', '')}x{config_dict.get('SHOW_HIS_IMAGE_WINDOW_HEIGHT', '')}"
                show_image_window = f"{config_dict.get('SHOW_IMAGE_WINDOW_WIDTH', '')}x{config_dict.get('SHOW_IMAGE_WINDOW_HEIGHT', '')}"
                debug_flag = int(get_debug_status(db))
        except Exception:
            show_his_image_window = None
            show_image_window = None
            debug_flag = 0
            traceback.print_exc()

        try:
            use_sensor = self.validate_use_sensor(USE_SENSOR)
        except ValueError as e:
            print(f"Warning: {e}. Using default value '1'")
            use_sensor = "1"

        command = [
            "--raw_path", fr"{raw_path}",
            "--delta_t", str(delta_t),
            "--intrinsics_path", fr"{intrinsics_path}",
            "--perspective_path", fr"{perspective_path}",
            "--speed_path", fr"{speed_path}",
            "--histogram_add_pixel_params", str(histogram_add_pixel_params),
            "--export_dir", fr"{export_dir}",
            "--use_sensor", use_sensor,
            "--mask_his_cut_flag", "0",
            "--debug", str(debug_flag),
            "--ini_path", INI_PATH
        ]

        if show_his_image_window is not None:
            command.extend(["--show_his_image_window", fr"{show_his_image_window}"])

        if show_image_window is not None:
            command.extend(["--show_image_window", fr"{show_image_window}"])

        if bias_path is not None and bias_path != '':
            command.extend(["--bias_path", fr"{bias_path}"])

        result = self._run_cli(
            script_path=os.path.join(BE_FOLDER, 'flows', 'tile', 'ir_histogram.py'),
            use_module=False,
            arg_list=command,
            title_window_focus=["Sensor", "Histogram"],
            cwd=BE_FOLDER,
            use_pipe_server=True
        )
        return result

    def load_dot_pattern_images(self, dt=None, preserve_selected=False):
        """Load dot pattern images from the directory ordered by index or creation time"""
        try:
            folder_paths = {
                "a_dot_pattern_list": DOT_PATTERN_PATH,
            }
            for list_id, folder_path in folder_paths.items():
                content_layout = self.ids[list_id].children[0]

                prev_selected = None
                if preserve_selected:
                    try:
                        if list_id == "a_dot_pattern_list":
                            prev_selected = self.get_selected_dot_pattern()
                    except Exception:
                        traceback.print_exc()
                        prev_selected = None

                content_layout.clear_widgets()
                if not os.path.exists(folder_path):
                    os.makedirs(folder_path)

                metadata = self.rebuild_metadata()

                # Get list of image files and creation time
                image_files = []
                for f in os.listdir(folder_path):
                    if f.lower().endswith(('.png')):
                        file_path = os.path.join(folder_path, f)
                        creation_time = os.path.getmtime(file_path)
                        image_files.append((f, file_path, creation_time))

                # Classify files by whether they have custom index or not
                # {index: (filename, filepath, creation_time)}
                indexed_files = {}
                non_indexed_files = []

                for file_data in image_files:
                    filename = file_data[0]

                    # Check custom index from metadata
                    if filename in metadata and 'index' in metadata[filename]:
                        custom_index = metadata[filename]['index']
                        indexed_files[custom_index] = file_data
                    else:
                        non_indexed_files.append(file_data)

                # Sort non_indexed_files by creation time
                non_indexed_files.sort(key=lambda x: x[2])

                # Create final list for display
                final_items = []

                # 1. Find highest index to know how many positions have index
                max_index = max(indexed_files.keys()) if indexed_files else -1

                # 2. Create array to fill positions
                position_array = [None] * \
                    (max_index + 1) if max_index >= 0 else []

                # 3. Place files with index in correct positions
                for index, file_data in indexed_files.items():
                    position_array[index] = file_data

                # 4. Fill empty positions with files without index
                non_indexed_iter = iter(non_indexed_files)
                for i, value in enumerate(position_array):
                    if value is None:
                        try:
                            position_array[i] = next(non_indexed_iter)
                        except StopIteration:
                            break  # No more files to fill

                # 5. Add remaining files without index to end
                remaining_files = list(non_indexed_iter)

                # 6. Create final_items from position_array
                main_item_set = False
                first_non_none_idx = next(
                    (i for i, f in enumerate(position_array) if f is not None), None)
                for i, file_data in enumerate(position_array):
                    if file_data is not None:
                        if (i == 0) or (first_non_none_idx == i and not main_item_set):
                            display_text = f"{file_data[0]}"
                            is_main_item = True
                            main_item_set = True
                        else:
                            display_text = f"{file_data[0]}"
                            is_main_item = False

                        final_items.append({
                            'file': file_data[0],
                            'path': file_data[1],
                            'display_text': display_text,
                            'is_main_item': is_main_item,
                            'index': i,
                            'has_custom_index': file_data in indexed_files.values()
                        })

                # 7. Add remaining files to end
                for idx, file_data in enumerate(remaining_files):
                    position = len(final_items)

                    # If no file has index, first file will be default
                    if not main_item_set and idx == 0:
                        display_text = f"{file_data[0]}"
                        is_main_item = True
                        main_item_set = True
                    else:
                        display_text = f"{file_data[0]}"
                        is_main_item = False

                    final_items.append({
                        'file': file_data[0],
                        'path': file_data[1],
                        'display_text': display_text,
                        'is_main_item': is_main_item,
                        'index': position,
                        'has_custom_index': False
                    })

                # Create UI items
                for item_info in final_items:
                    item = Factory.ImageSelectionItem(
                        image_source=item_info['path'],
                        text=item_info['display_text'],
                        group='gallery_group',
                        active=item_info['is_main_item'],
                        index=item_info['index'],
                    )
                    content_layout.add_widget(item)

                    if item_info['is_main_item']:
                        width = item.get_image_width()
                        if width is not None and 'a_resize_dot_pattern' in self.ids:
                            self.ids.a_resize_dot_pattern.text = str(width)

                self.ids[list_id].do_scroll_y = len(final_items) > 3

                if preserve_selected and prev_selected:
                    for child in content_layout.children:
                        if isinstance(child, Factory.ImageSelectionItem):
                            is_active = getattr(child, 'image_source', None) == prev_selected
                            child.active = is_active
                            for sub_child in getattr(child, 'children', []):
                                if hasattr(sub_child, 'ids') and hasattr(sub_child.ids, 'checkbox'):
                                    sub_child.ids.checkbox.active = is_active

                if not final_items:
                    label = KeyLabel(
                        text_key='no_data_placeholder',
                        halign='center',
                        valign='middle',
                        color=[0.6, 0.6, 0.6, 1],
                        font_size=dp(20),
                        size_hint_y=None,
                        height=dp(100),
                        padding=[0, dp(50), 0, 0]
                    )
                    content_layout.add_widget(label)

        except Exception:
            traceback.print_exc()

    def move_image(self):
        """Copy selected image from dot_box_dir_image_list to dot_pattern_list with index = 2"""
        try:
            errors = []
            self.reset_error_screen_a()
            # 1. Get selected item from a_dot_box_dir_image_list
            selected_image_path = self.get_selected_dot_box_dir_images()

            if not selected_image_path:
                return
            elif not os.path.exists(os.path.normpath(selected_image_path)):
                errors.append(("a_dot_box_dir_image_list_error",
                              "file_not_found_error_message"))
            # 2. Copy image file from dot_box_dir to dot_pattern folder
            if errors:
                for error_id, error_msg in errors:
                    if error_id in self.ids:
                        self.ids[error_id].error_message = error_msg
                return

            # Ensure DOT_PATTERN_PATH directory exists
            if not os.path.exists(DOT_PATTERN_PATH):
                os.makedirs(DOT_PATTERN_PATH)

            # Find largest number used for custom_dot_template_*.png
            max_num = 0
            for f in os.listdir(DOT_PATTERN_PATH):
                if f.startswith("custom_dot_template_") and f.lower().endswith(('.png')):
                    try:
                        num = int(f.split("_")[-1].split(".")[0])
                        if num > max_num:
                            max_num = num
                    except Exception:
                        continue
            new_num = max_num + 1
            new_filename = f"custom_dot_template_{new_num}.png"

            destination_path = os.path.join(DOT_PATTERN_PATH, new_filename)

            # Copy file
            shutil.copy2(selected_image_path, destination_path)
            now = time.time()
            os.utime(destination_path, (now, now))

            self.load_dot_pattern_images(preserve_selected=True)

        except Exception:
            traceback.print_exc()

    def rebuild_metadata(self):
        """
        Always rebuild metadata based on existing PNG files in directory.
        Logic:
        - If default_dot_template.png exists: set index = 0, other files sort by time desc from index 1
        - If default_dot_template.png doesn't exist: sort all files by time desc from index 0
        """
        metadata_file = os.path.join(
            DOT_PATTERN_PATH, "dot_pattern_metadata.json")

        # --- REBUILD metadata logic ---
        rebuilt_metadata = {}
        all_png_files = []

        # Scan all PNG files in directory and get creation time
        for filename in os.listdir(DOT_PATTERN_PATH):
            if filename.lower().endswith('.png'):
                file_path = os.path.join(DOT_PATTERN_PATH, filename)
                creation_time = os.path.getmtime(file_path)
                all_png_files.append((filename, creation_time))

        # Sort files by creation time (desc - newest first)
        all_png_files.sort(key=lambda x: x[1], reverse=True)

        # Check if default_dot_template.png exists
        has_default = any(
            filename == "default_dot_template.png" for filename, _ in all_png_files)

        if has_default:
            # If default_dot_template.png exists then set index = 0
            rebuilt_metadata["default_dot_template.png"] = {"index": 0}

            # Remaining files (not default) are sorted by time and assigned index from 1
            other_files = [(fname, ftime) for fname,
                           ftime in all_png_files if fname != "default_dot_template.png"]
            for i, (filename, _) in enumerate(other_files):
                rebuilt_metadata[filename] = {"index": i + 1}
        else:
            # If no default_dot_template.png then sort all by time
            # Newest file (index 0) will be first file in sorted list
            for i, (filename, _) in enumerate(all_png_files):
                rebuilt_metadata[filename] = {"index": i}

        # Save newly rebuilt metadata file
        try:
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(rebuilt_metadata, f, ensure_ascii=False, indent=4)
        except Exception:
            traceback.print_exc()
        return rebuilt_metadata

    def get_selected_dot_pattern(self):
        """Get path of selected dot pattern image"""
        content_layout = self.form_mapping['a_dot_pattern_list'].children[0]
        for child in content_layout.children:
            # Check if it's an ImageSelectionItem and has active property
            if isinstance(child, Factory.ImageSelectionItem) and hasattr(child, 'active'):
                # Find the FormCheckBox inside the ImageSelectionItem
                for checkbox_child in child.children:
                    if hasattr(checkbox_child, 'ids') and hasattr(checkbox_child.ids, 'checkbox'):
                        # If the checkbox is active, return this image source
                        if checkbox_child.ids.checkbox.active:
                            return child.image_source
        return None

    def get_test_bias_path(self):
        """Get bias_path for test activity, using bias_path_speed if available and exists, otherwise fallback to bias_path"""
        speed_text = self.form_mapping['a_bias_path_select_speed'].text
        if speed_text:
            bias_path_speed = os.path.join(BIAS_PATH, speed_text)
            # if os.path.exists(bias_path_speed):
            return bias_path_speed
        return os.path.join(BIAS_PATH, self.form_mapping['a_bias_path_select'].text)

    def sync_resize_speed_pattern(self, value):
        """Sync a_resize_speed_pattern when a_resize_dot_pattern text changes."""
        if not value.strip():
            # If value is empty, speed_value should also be empty
            speed_value = ""
        else:
            try:
                value_int = int(value)
            except Exception:
                value_int = 0
            speed_value = str(int(value_int * 1.25))

        if 'a_resize_speed_pattern' in self.ids:
            self.ids.a_resize_speed_pattern.text = speed_value

    def init_empty_gallery(self):
        """Initialize gallery with empty message and delete images in directory"""
        # Clear UI
        gallery = self.form_mapping['a_acquired_image_gallery']
        gallery.show_no_data_message()

    def clear_gallery_files(self):
        """Clear all PNG files from gallery output directory."""
        if os.path.exists(OUTPUT_INTRINSIC_PATH):
            for file in os.listdir(OUTPUT_INTRINSIC_PATH):
                if file.lower().endswith(('.png')):
                    os.remove(os.path.join(OUTPUT_INTRINSIC_PATH, file))

    def init_empty_dot_box_dir_list(self):
        """Initialize a_dot_box_dir_image_list with empty message"""
        try:
            gallery = self.form_mapping['a_dot_box_dir_image_list']
            gallery.show_no_data_message()
        except Exception:
            traceback.print_exc()

    def init_empty_dot_box_dir_list_preview(self):
        """Initialize a_dot_box_dir_image_list_preview with empty message"""
        try:
            gallery = self.form_mapping['a_dot_box_dir_image_list_preview']
            gallery.show_no_data_message()
        except Exception:
            traceback.print_exc()

    def folder_reload(self):
        """Reload image list from directories"""
        try:
            gallery = self.form_mapping['a_acquired_image_gallery']
            gallery.ids.content_layout.clear_widgets()
            Clock.schedule_once(lambda dt: gallery.load_images(OUTPUT_INTRINSIC_PATH), 0.5)
        except Exception:
            traceback.print_exc()

    def reset_error_screen_a(self, reset_subsection=None):
        """
        Reset error messages for screen A fields.

        Args:
            reset_subsection: Specific subsection to reset, or None for all
        """
        error_fields_map = {
            0: {
                'a_setting_name',
                'a_intrinsic_json_select',
                'a_pattern_cols',
                'a_pattern_rows',
                'a_delta_t',
                'a_bias_path_select',
            },
            1: {
                'a_dot_pattern_list_error',
                'a_resize_dot_pattern',
                'a_dot_box_dir_image_list_error',
                'a_acquired_image_gallery_error',
                'a_margin_group_error',
                'a_perspective_json_select',
            },
            2: {
                'a_resize_speed_pattern',
                'a_speed_json_select',
            },
            3: {
                'a_delta_t_speed',
                'a_bias_path_select_speed',
            },
            'save_edit': {
                'a_setting_name_edit',
            }
        }

        if reset_subsection is not None:
            fields_to_reset = error_fields_map.get(reset_subsection, set())
        else:
            fields_to_reset = set()
            for fields in error_fields_map.values():
                fields_to_reset.update(fields)

        for field in fields_to_reset:
            if field in self.ids:
                self.ids[field].error_message = ""

    def reset_screen_a(self):
        """Reset entire screen A to default state"""
        try:
            self.init_empty_gallery()
            self.init_empty_dot_box_dir_list()
            self.init_empty_dot_box_dir_list_preview()
            # Reset text inputs
            self.form_mapping['a_setting_name'].text = ""
            self.form_mapping['a_delta_t'].text = "15000"  # Default value

            self.form_mapping['a_pattern_cols'].text = '5'
            self.form_mapping['a_pattern_rows'].text = '3'

            self.form_mapping['a_delta_t_speed'].text = "15000"  # Default value

            # Reset spinners
            for spinner_id in [
                'a_intrinsic_json_select',
                'a_perspective_json_select',
                'a_speed_json_select',
                'a_bias_path_select',
                'a_bias_path_select_speed'
            ]:
                self.ids[spinner_id].hint_text = self.app.lang.get('select_placeholder')
                self.ids[spinner_id].text = ""

            # Reset margins
            self.form_mapping['margin_top'].ids.margin_input.text = ""
            self.form_mapping['margin_bottom'].ids.margin_input.text = ""
            self.form_mapping['margin_left'].ids.margin_input.text = ""
            self.form_mapping['margin_right'].ids.margin_input.text = ""

            # Reset dot box
            self.form_mapping['save_to_dot_box'].ids.checkbox.active = False
            self.form_mapping['save_to_dot_box_preview'].ids.checkbox.active = False

            self.set_dot_box_path_to_placeholder(preview=None)

            content_layout = self.form_mapping['a_dot_pattern_list'].children[0]
            for idx, child in enumerate(content_layout.children):
                if hasattr(child, 'active'):
                    is_active = idx == len(content_layout.children) - 1
                    child.active = is_active
                    # If there's FormCheckBox inside then set it too
                    for sub_child in child.children:
                        if sub_child.__class__.__name__ == 'FormCheckBox':
                            sub_child.ids.checkbox.active = is_active

            # Reset acquired images selection
            gallery = self.form_mapping['a_acquired_image_gallery']
            for child in gallery.ids.content_layout.children:
                if isinstance(child, ImageThumbnail):
                    child.selected = False

            self.reset_error_screen_a()

            # Reset editing state
            self.editing_item_name = None
            self.scroll_screen_a_to_default()

        except Exception:
            traceback.print_exc()

    def __show_popup(self, title, message):
        """
        Show popup message to user.

        Args:
            title: Title key for the popup
            message: Message key for the popup
        """
        def _show(dt):
            if self.popup:
                self.popup.create_adaptive_popup(
                    title=title,
                    message=message
                ).open()
        Clock.schedule_once(_show, 0)

    def _check_thread(self, dt, thread):
        """
        Check if the subprocess thread return/raise errors.

        Args:
            dt: Delta time from Clock scheduler
            thread: Thread object to check
        """
        if thread.is_finished():
            try:
                result = thread.result()
                self.set_left_mouse_disabled(False)
                if self.loading_popup:
                    self.loading_popup.opacity = 0
                    self.loading_popup.dismiss()
                    self.loading_popup = None
                print("Subprocess returned:", result)
            except Exception as e:
                traceback.print_exc()
                self.set_left_mouse_disabled(False)
                if self.loading_popup:
                    self.loading_popup.opacity = 0
                    self.loading_popup.dismiss()
                    self.loading_popup = None
                self.__show_popup(title="error_popup", message=f"Error: {e}")
            return False
        return True

    def delete_dot_box_path(self, preview=False):
        """Delete/clear the dot box path value."""
        self.set_dot_box_path_to_placeholder(preview=preview)
