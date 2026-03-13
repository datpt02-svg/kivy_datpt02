"""
Unit tests for the SystemSettingsScreen.
"""
# pylint: disable=wildcard-import, undefined-variable, protected-access, unused-variable, too-many-lines, invalid-name, redefined-outer-name, unnecessary-dunder-call

from unittest.mock import patch, Mock, MagicMock
import pytest
from app.screen.PyModule.E_SystemSettingsScreen import SystemSettingsScreen

# Mock Kivy's App and other dependencies
class MockKivyApp:
    """Mock for Kivy App."""
    def get_running_app(self):
        """Mock get_running_app."""
        return Mock()

class MockPopup:
    """Mock for MyPopup."""
    def __init__(self):
        self.create_loading_popup = MagicMock(return_value=Mock(open=Mock(), dismiss=Mock()))
        self.create_adaptive_popup = MagicMock(return_value=Mock(open=Mock(), dismiss=Mock(), bind=Mock()))

@pytest.fixture
def system_settings_screen_instance():
    """Fixture to create a SystemSettingsScreen instance with mocked Kivy dependencies."""
    with patch('kivy.app.App.get_running_app') as MockApp, \
         patch('app.screen.PyModule.E_SystemSettingsScreen.MyPopup', new_callable=MockPopup), \
         patch('app.screen.PyModule.E_SystemSettingsScreen.IniEditor') as MockIniEditor, \
         patch.object(SystemSettingsScreen, '__init__', return_value=None):

        screen = SystemSettingsScreen()
        screen.app = MockApp.get_running_app()
        screen.app.lang.get = Mock(return_value="mocked_translation") # Mock translation
        screen.popup = MockPopup()
        screen.ini_editor = MockIniEditor()

        screen.ids = {
            'main_scroll_view': MagicMock(scroll_y=0),
            'debug': MagicMock(selected_index=0, text=""),
            'dot_point': MagicMock(ids=MagicMock(form_input=MagicMock(text="", error_message=""))),
            'detect_area_split': MagicMock(ids=MagicMock(form_spinner=MagicMock(text=""))),
            'show_image_window_width': MagicMock(ids=MagicMock(form_input=MagicMock(text="", error_message=""))),
            'show_image_window_height': MagicMock(ids=MagicMock(form_input=MagicMock(text="", error_message=""))),
            'show_his_image_window_width': MagicMock(ids=MagicMock(form_input=MagicMock(text="", error_message=""))),
            'show_his_image_window_height': MagicMock(ids=MagicMock(form_input=MagicMock(text="", error_message=""))),
            'patch_size_list': MagicMock(ids=MagicMock(form_input=MagicMock(text="", error_message=""))),
            'input_size_list': MagicMock(ids=MagicMock(form_input=MagicMock(text="", error_message=""))),
            'backup_path': MagicMock(path_text=MagicMock(text=""), error_message=""),
            'auto_cleaner_checkbox': MagicMock(active=False),
            'auto_cleaner_days_to_keep': MagicMock(text="", error_message=""),
        }
        screen.on_kv_post(None) # This populates form_mapping

        # Now that form_mapping is populated, mock these methods
        screen.load_system_settings = Mock()
        screen.load_delete_setting_ini = Mock()
        screen.reset_val_status = Mock()

        return screen

class TestSystemSettingsScreen:
    """Tests for SystemSettingsScreen."""
    @pytest.fixture(autouse=True)
    def setup_screen(self, system_settings_screen_instance):
        """Setup the screen for testing."""
        self.screen = system_settings_screen_instance

    def test_screen_initialization(self):
        """Test that the screen can be initialized."""
        assert self.screen is not None
        assert isinstance(self.screen, SystemSettingsScreen)

    def test_on_pre_enter(self):
        """Test the on_pre_enter method."""
        screen = self.screen
        screen.on_pre_enter()

        screen.load_system_settings.assert_called_once()
        screen.load_delete_setting_ini.assert_called_once()
        assert screen.ids['main_scroll_view'].scroll_y == 1
        assert screen.reset_val_status.call_count == 3

    @patch('app.screen.PyModule.E_SystemSettingsScreen.update_system_config')
    @patch('app.screen.PyModule.E_SystemSettingsScreen.create_system_config')
    @patch('app.screen.PyModule.E_SystemSettingsScreen.read_system_config')
    @patch('app.screen.PyModule.E_SystemSettingsScreen.get_db')
    def test_save_system_settings_success(self, mock_get_db, mock_read, mock_create, mock_update):
        """Test successful saving of system settings."""
        screen = self.screen
        # Mock validation to pass
        screen.validate = Mock()
        screen.check_val_status = Mock()
        screen.validate_paths = Mock()
        screen.update_delete_setting_ini = Mock()
        screen._are_multiples_of_n = Mock(return_value=True)

        screen.save_system_settings()

        screen.check_val_status.assert_called()
        mock_read.assert_called()
        screen.update_delete_setting_ini.assert_called_once()
        screen.popup.create_adaptive_popup.assert_called_with(
            title="notification_popup",
            message="save_settings_success_popup_E1"
        )

    def test_save_system_settings_validation_fail(self):
        """Test that saving fails if validation throws an error."""
        screen = self.screen
        # Mock validation to fail
        screen.validate = Mock()
        screen.check_val_status = Mock(side_effect=Exception("Validation failed"))
        screen.validate_paths = Mock()
        screen._are_multiples_of_n = Mock(return_value=True)

        screen.save_system_settings()

        screen.popup.create_adaptive_popup.assert_called_with(
            title="error_popup",
            message="save_settings_failed_popup_E1"
        )

    def test_save_system_settings_list_validation_fail(self):
        """Test that saving fails if the patch/input list validation fails."""
        screen = self.screen
        # Un-mock the validation methods for this test
        screen.validate = SystemSettingsScreen.validate.__get__(screen, SystemSettingsScreen)
        screen.check_val_status = SystemSettingsScreen.check_val_status.__get__(screen, SystemSettingsScreen)

        screen.validate_paths = Mock()
        # Make the custom list validation fail
        screen._are_multiples_of_n = Mock(return_value=False)

        screen.save_system_settings()

        # Assert that an error message was set and the error popup was called
        assert screen.form_mapping["patch_size_list"].error_message == "patch_size_validate_message_E1"
        assert screen.form_mapping["input_size_list"].error_message == "input_size_validate_message_E1"
        screen.popup.create_adaptive_popup.assert_called_with(
            title="error_popup",
            message="save_settings_failed_popup_E1"
        )

    @patch('app.screen.PyModule.E_SystemSettingsScreen.read_system_config')
    @patch('app.screen.PyModule.E_SystemSettingsScreen.get_db')
    def test_load_system_settings(self, mock_get_db, mock_read):
        """Test that system settings are loaded into the form correctly."""
        screen = self.screen
        screen.load_system_settings = SystemSettingsScreen.load_system_settings.__get__(screen) # Un-mock for this test

        # Mock the return value from the database
        def read_side_effect(db, key):
            config = Mock()
            config.value = f"value_for_{key}"
            return config
        mock_read.side_effect = read_side_effect

        screen.load_system_settings()

        # Assert that form fields are populated with values from the mocked DB
        assert screen.form_mapping["dot_point"].text == "value_for_DOT_POINT"
        assert screen.form_mapping["backup_path"].path_text.text == "value_for_BACKUP_PATH"
        assert mock_read.call_count == len(screen.settings_default_value)

    def test_are_multiples_of_n(self):
        """Test the custom validation for lists of numbers."""
        screen = self.screen
        assert screen._are_multiples_of_n("224, 448, 672", n=224) is True
        assert screen._are_multiples_of_n("224", n=224) is True
        assert screen._are_multiples_of_n(" 224,448 ", n=224) is True
        assert screen._are_multiples_of_n("223, 448", n=224) is False
        assert screen._are_multiples_of_n("abc, 448", n=224) is False
        assert screen._are_multiples_of_n("224,", n=224) is False
