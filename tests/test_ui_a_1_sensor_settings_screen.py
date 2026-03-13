"""
Unit tests for the SensorSettingsScreen.
"""
# pylint: disable=wildcard-import, undefined-variable, protected-access, unused-variable, too-many-lines, invalid-name, redefined-outer-name

from unittest.mock import patch, Mock, MagicMock, ANY
import pytest
from app.screen.PyModule.A_SensorSettingsScreen import SensorSettingsScreen

# Mock Kivy's App and other dependencies
class MockKivyApp:
    """Mock for Kivy App."""
    def get_running_app(self):
        """Mock get_running_app."""
        # Mock the running app, including language manager
        app = Mock()
        app.lang.get.return_value = "mock_translation"
        return app

class MockPopup:
    """Mock for MyPopup."""
    def __init__(self):
        self.create_loading_popup = MagicMock(return_value=Mock(open=Mock(), dismiss=Mock()))
        self.create_adaptive_popup = MagicMock(return_value=Mock(open=Mock(), dismiss=Mock(), bind=Mock()))

class MockDataTableManager:
    """Mock for DataTableManager."""
    def __init__(self, *args, **kwargs):
        self.all_rows = []
        self.load_settings_from_db = Mock()
        self.find_page_for_record = Mock(return_value=1)

@pytest.fixture
def sensor_settings_screen_instance():
    """Fixture to create a SensorSettingsScreen instance with mocked Kivy dependencies."""
    # Create a mock for kivy.factory.Factory
    mock_factory = MagicMock()
    mock_factory.ReadOnlyInfoGroup.return_value = MagicMock(ids=MagicMock(value_label=MagicMock()))
    mock_factory.FormButton.return_value = MagicMock()
    mock_factory.Widget.return_value = MagicMock()
    mock_factory.StepIndicator.return_value = MagicMock()

    with patch('kivy.app.App.get_running_app', new_callable=MockKivyApp), \
         patch('app.screen.PyModule.A_SensorSettingsScreen.Factory', new=mock_factory), \
         patch('app.screen.PyModule.A_SensorSettingsScreen.MyPopup', new_callable=MockPopup), \
         patch('app.screen.PyModule.A_SensorSettingsScreen.DataTableManager', new=MockDataTableManager), \
         patch('app.screen.PyModule.A_SensorSettingsScreen.DatasetSpinner') as MockSpinner, \
         patch('app.screen.PyModule.utils.delete_images_in_folders.delete_images_in_folders'), \
         patch.object(SensorSettingsScreen, '__init__', return_value=None):

        screen = SensorSettingsScreen()
        screen.bind = Mock()
        screen.app = MockKivyApp().get_running_app()
        # Mock app.root.ids.screen_manager.screens to be iterable
        screen.app.root.ids.screen_manager = MagicMock(screens=[]) # Make screens iterable
        screen.popup = MockPopup()
        screen.sensor_settings_table = MockDataTableManager()
        screen.spinners = {
            'a_bias_path_select': MockSpinner(),
            'a_intrinsic_json_select': MockSpinner(),
            'a_perspective_json_select': MockSpinner(),
            'a_speed_json_select': MockSpinner(),
            'a_bias_path_select_speed': MockSpinner()
        }

        # Initialize editing_item_name as __init__ is patched
        screen.editing_item_name = None

        # Comprehensive mock of the ids dictionary
        mock_scroll_screen = MagicMock(scroll_y=0, height=200)
        mock_scroll_screen.children = [MagicMock(height=100)] # For scroll_view.children[0].height

        screen.ids = {
            'a_setting_name': MagicMock(text="", error_message=""),
            'a_intrinsic_json_select': MagicMock(text=""),
            'a_pattern_cols': MagicMock(text=""),
            'a_pattern_rows': MagicMock(text=""),
            'a_delta_t': MagicMock(text=""),
            'a_bias_path_select': MagicMock(text=""),
            'a_bias_path_select_speed': MagicMock(text=""),
            'a_dot_pattern_list': MagicMock(scroll_y=0),
            'a_resize_dot_pattern': MagicMock(text=""),
            'a_dot_box_dir_image_list': MagicMock(),
            'a_dot_box_dir_image_list_preview': MagicMock(),
            'a_acquired_image_gallery': MagicMock(),
            'a_perspective_json_select': MagicMock(text=""),
            'a_resize_speed_pattern': MagicMock(text=""),
            'a_speed_json_select': MagicMock(text=""),
            'a_delta_t_speed': MagicMock(text=""),
            'button_navigation_container': MagicMock(clear_widgets=Mock(), add_widget=Mock()),
            'main_container': MagicMock(children=[], remove_widget=Mock(), add_widget=Mock()),
            'step_indicator_container': MagicMock(add_widget=Mock()),
            'open_folder_perspective_button': MagicMock(),
            'open_folder_speed_button': MagicMock(),
            'scroll_screen_A_sensor_settings': mock_scroll_screen,
            'save_to_dot_box': MagicMock(),
            'save_to_dot_box_preview': MagicMock(),
            'margin_left': MagicMock(ids=MagicMock(margin_input=MagicMock(text=""))),
            'margin_top': MagicMock(ids=MagicMock(margin_input=MagicMock(text=""))),
            'margin_right': MagicMock(ids=MagicMock(margin_input=MagicMock(text=""))),
            'margin_bottom': MagicMock(ids=MagicMock(margin_input=MagicMock(text=""))),
            'intrinsic_info': MagicMock(ids=MagicMock(value_label=MagicMock(text=""))),
            'pattern_cols_info': MagicMock(ids=MagicMock(value_label=MagicMock(text=""))),
            'pattern_rows_info': MagicMock(ids=MagicMock(value_label=MagicMock(text=""))),
            'bias_info': MagicMock(ids=MagicMock(value_label=MagicMock(text=""))),
            'perspective_info': MagicMock(ids=MagicMock(value_label=MagicMock(text=""))),
            'speed_info': MagicMock(ids=MagicMock(value_label=MagicMock(text=""))),
            'a_setting_name_edit': MagicMock(text="", _suppress_suggestion_popup=False, focus=False),
            # Add dynamically created ids that are accessed in on_kv_post
            'previous_button': MagicMock(),
            'next_button': MagicMock(),
            'widget_button': MagicMock(),
            'coordinate_info': MagicMock(ids=MagicMock(value_label=MagicMock())),
            'register_coordinate_button': MagicMock(),
            'verify_coordinate_button': MagicMock(),
            'save_button': MagicMock(),
            'step_indicator': MagicMock(),
        }

        # Manually call on_kv_post to populate mappings
        screen.on_kv_post(None)

        # Mock methods that would be called during setup
        screen.load_dot_pattern_images = Mock()
        screen.update_dot_score = Mock()

        return screen

class TestSensorSettingsScreen:
    """Tests for SensorSettingsScreen."""
    @pytest.fixture(autouse=True)
    def setup_screen(self, sensor_settings_screen_instance):
        """Setup the screen for testing."""
        self.screen = sensor_settings_screen_instance

    def test_screen_initialization(self):
        """Test that the screen can be initialized."""
        assert self.screen is not None
        assert isinstance(self.screen, SensorSettingsScreen)
        assert self.screen.form_mapping is not None
        assert self.screen.error_mapping is not None

    @patch('app.screen.PyModule.A_SensorSettingsScreen.delete_images_in_folders')
    def test_on_pre_enter(self, mock_delete):
        """Test the on_pre_enter lifecycle method."""
        screen = self.screen
        screen.reset_screen_a = Mock()

        screen.on_pre_enter()

        screen.reset_screen_a.assert_called_once()
        mock_delete.assert_called_once()
        screen.sensor_settings_table.load_settings_from_db.assert_called_once()
        screen.load_dot_pattern_images.assert_called_once()
        screen.update_dot_score.assert_called_once()

    @patch('app.screen.PyModule.A_SensorSettingsScreen.create_sensor_settings')
    @patch('app.screen.PyModule.A_SensorSettingsScreen.get_db')
    def test_save_sensor_settings_create_new_success(self, mock_get_db, mock_create):
        """Test successfully saving a new sensor setting."""
        screen = self.screen
        screen.editing_item_name = None

        # Mock validation to pass
        screen.validate_fields = Mock(return_value=([], []))
        screen._handle_validation_errors = Mock(return_value=False)
        # Mock internal methods that would be called by _reset_editing_state
        screen._SensorSettingsScreen__show_popup = Mock()
        screen.reset_screen_a = Mock()


        result = screen.save_prophesee_settings()

        assert result is True
        mock_create.assert_called_once()
        screen.reset_screen_a.assert_called_once()
        # The popup assertion should now be on the mocked __show_popup
        screen._SensorSettingsScreen__show_popup.assert_called_once_with(
            title='notification_popup',
            message='save_sensor_settings_popup_A_done'
        )

    def test_save_sensor_settings_validation_fail(self):
        """Test that saving fails if validation returns errors."""
        screen = self.screen
        screen.editing_item_name = None

        # Mock validation to fail
        screen.validate_fields = Mock(return_value=([('a_setting_name', '', False)], []))
        screen._handle_validation_errors = Mock(return_value=True)

        result = screen.save_prophesee_settings()

        assert result is None # Should return nothing on validation failure
        screen._handle_validation_errors.assert_called_once()

    def test_load_item_to_form(self):
        """Test loading an item's data into the form for editing."""
        screen = self.screen
        screen.get_modify_coordinate_info = Mock(return_value="coordinate_registered")

        item = {
            'name': 'Test_Setting_1',
            'config': {
                'bias_path': 'test.bias',
                'intrinsic_path': 'intrinsic.json',
                'pattern_cols': 10,
                'pattern_rows': 7,
                'perspective_path': 'perspective.json',
                'speed_path': 'speed.json'
            }
        }

        screen.load_item_to_form(item)

        assert screen.current_subsection == 4
        assert screen.editing_item_name == 'Test_Setting_1'
        assert screen.form_mapping['a_setting_name_edit'].text == 'Test_Setting_1'
        assert screen.form_mapping['a_bias_path_select_label'].text == 'test.bias'
        assert screen.form_mapping['a_intrinsic_json_select_label'].text == 'intrinsic.json'
        assert screen.form_mapping['a_pattern_cols_label'].text == '10'
        assert screen.form_mapping['a_pattern_rows_label'].text == '7'
        assert screen.form_mapping['a_perspective_json_select_label'].text == 'perspective.json'
        assert screen.form_mapping['a_speed_json_select_label'].text == 'speed.json'
        assert screen.form_mapping['a_coordinate_label'].text_key == "coordinate_registered"

    @patch('app.screen.PyModule.A_SensorSettingsScreen.recursive_delete')
    @patch('app.screen.PyModule.A_SensorSettingsScreen.get_db')
    def test_delete_item(self, mock_get_db, mock_delete):
        """Test deleting a sensor setting item."""
        screen = self.screen
        screen._get_id_by_name = Mock(return_value=123)

        item = {'name': 'Setting_to_Delete'}
        screen.delete_item(item)

        mock_delete.assert_called_once_with(ANY, 123, db_session=ANY)
        screen.sensor_settings_table.load_settings_from_db.assert_called_once()
