"""
Unit tests for the IniSettingsScreen.
"""
# pylint: disable=wildcard-import, undefined-variable, protected-access, unused-variable, too-many-lines, invalid-name, redefined-outer-name, unnecessary-dunder-call

from unittest.mock import patch, Mock, MagicMock
import pytest
from app.screen.PyModule.E_IniSettingsScreen import IniSettingsScreen

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
def ini_settings_screen_instance():
    """Fixture to create a IniSettingsScreen instance with mocked Kivy dependencies."""
    with patch('kivy.app.App.get_running_app', return_value=MockKivyApp()), \
         patch('app.screen.PyModule.E_IniSettingsScreen.MyPopup', new_callable=MockPopup), \
         patch('app.screen.PyModule.E_IniSettingsScreen.IniEditor') as MockIniEditor, \
         patch('app.screen.PyModule.E_IniSettingsScreen.SaveButton') as MockSaveButton, \
         patch('app.screen.PyModule.E_IniSettingsScreen.FormLabel') as MockFormLabel, \
         patch.object(IniSettingsScreen, '__init__', return_value=None):

        screen = IniSettingsScreen()
        screen.app = MockKivyApp()
        screen.popup = MockPopup()
        screen.ini_editor = MockIniEditor()
        screen.ini_section_list = []
        screen.ids = {
            'main_scroll_view': MagicMock(scroll_y=0),
            'ini_section_layout': MagicMock(add_widget=Mock(), clear_widgets=Mock()),
            'save_button_layout': MagicMock(add_widget=Mock(), clear_widgets=Mock()),
        }
        screen.on_kv_post(None)

        return screen

class TestIniSettingsScreen:
    """Tests for IniSettingsScreen."""
    @pytest.fixture(autouse=True)
    def setup_screen(self, ini_settings_screen_instance):
        """Setup the screen for testing."""
        self.screen = ini_settings_screen_instance

    def test_screen_initialization(self):
        """Test that the screen can be initialized."""
        assert self.screen is not None
        assert isinstance(self.screen, IniSettingsScreen)

    def test_on_pre_enter(self):
        """Test the on_pre_enter method."""
        screen = self.screen
        screen.build_dynamic_form = Mock() # Mock for this specific test
        with patch('app.screen.PyModule.E_IniSettingsScreen.FormScreen.on_pre_enter') as mock_super:
            screen.on_pre_enter()
            mock_super.assert_called_once()

        screen.build_dynamic_form.assert_called_once()
        assert screen.ids['main_scroll_view'].scroll_y == 1

    def test_on_pre_leave(self):
        """Test that the on_pre_leave method calls reset_form."""
        screen = self.screen
        screen.reset_form = Mock() # Mock for this specific test
        with patch('app.screen.PyModule.E_IniSettingsScreen.FormScreen.on_pre_leave') as mock_super:
            screen.on_pre_leave()
            mock_super.assert_called_once()
        screen.reset_form.assert_called_once()

    def test_build_dynamic_form_with_settings(self):
        """Test that the save button is created if settings are found."""
        screen = self.screen
        screen._read_ini_settings = Mock(return_value=True) # Pretend settings were read

        screen.build_dynamic_form()

        screen.form_mapping['save_button_layout'].add_widget.assert_called_once()

    def test_build_dynamic_form_without_settings(self):
        """Test that the save button is not created if no settings are found."""
        screen = self.screen
        screen._read_ini_settings = Mock(return_value=False) # Pretend no settings

        screen.build_dynamic_form()

        screen.form_mapping['save_button_layout'].add_widget.assert_not_called()

    @patch('app.screen.PyModule.E_IniSettingsScreen.IniSectionBlock')
    def test_read_ini_settings_success(self, MockIniSectionBlock):
        """Test reading and parsing a valid INI file."""
        # Mock the instance that will be created
        mock_block_instance = MockIniSectionBlock.return_value

        screen = self.screen
        # Unmock the method under test
        screen._read_ini_settings = IniSettingsScreen._read_ini_settings.__get__(screen)

        screen.ini_editor.parse_ini.return_value = {"section1": {"key1": "value1"}}

        result = screen._read_ini_settings()

        assert result is True
        # Assert that an IniSectionBlock was instantiated and used
        MockIniSectionBlock.assert_called_once()
        mock_block_instance.set_section_name.assert_called_once_with("section1")
        mock_block_instance.set_key_value_pair.assert_called_once_with("key1", "value1")
        screen.form_mapping['ini_section_layout'].add_widget.assert_called_once_with(mock_block_instance)
        assert len(screen.ini_section_list) == 1


    def test_read_ini_settings_file_not_found(self):
        """Test handling of FileNotFoundError when reading INI."""
        screen = self.screen
        screen._read_ini_settings = IniSettingsScreen._read_ini_settings.__get__(screen)
        screen.ini_editor.parse_ini.side_effect = FileNotFoundError

        result = screen._read_ini_settings()

        assert result is False
        # It should add a FormLabel with an error message
        screen.form_mapping['ini_section_layout'].add_widget.assert_called_once()

    def test_read_ini_settings_empty_file(self):
        """Test reading an empty or invalid INI file."""
        screen = self.screen
        screen._read_ini_settings = IniSettingsScreen._read_ini_settings.__get__(screen)
        screen.ini_editor.parse_ini.return_value = {}

        result = screen._read_ini_settings()

        assert result is False
        # It should add a FormLabel with a 'not setup' message
        screen.form_mapping['ini_section_layout'].add_widget.assert_called_once()

    def test_save_ini_settings_success(self):
        """Test the success path for saving INI settings."""
        screen = self.screen
        screen._save_ini_settings = IniSettingsScreen._save_ini_settings.__get__(screen)
        screen._export_data = Mock(return_value={"section1": {"key1": "new_value"}})
        screen.ini_editor.save_ini.return_value = None # No exception

        screen._save_ini_settings()

        screen.ini_editor.save_ini.assert_called_once_with(entries={"section1": {"key1": "new_value"}})
        screen.popup.create_adaptive_popup.assert_called_once_with(
            title="notification_popup",
            message="save_ini_success_message"
        )

    def test_save_ini_settings_failure(self):
        """Test the failure path for saving INI settings."""
        screen = self.screen
        screen._save_ini_settings = IniSettingsScreen._save_ini_settings.__get__(screen)
        screen._export_data = Mock(return_value={})
        screen.ini_editor.save_ini.side_effect = Exception("Disk is full")

        screen._save_ini_settings()

        screen.popup.create_adaptive_popup.assert_called_once_with(
            title="error_popup",
            message="save_ini_failed_message"
        )
