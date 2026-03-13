"""
Unit tests for the AIDetectionExecutionScreen.
"""
# pylint: disable=wildcard-import, undefined-variable, protected-access, unused-variable, too-many-lines, invalid-name, redefined-outer-name

from unittest.mock import patch, Mock, MagicMock, ANY
import pytest
from app.screen.PyModule.D_AIDetectionExecutionScreen import AIDetectionExecutionScreen

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
def ai_detection_screen_instance():
    """Fixture to create a AIDetectionExecutionScreen instance with mocked Kivy dependencies."""
    with patch('kivy.app.App.get_running_app', return_value=MockKivyApp()), \
         patch('app.screen.PyModule.D_AIDetectionExecutionScreen.MyPopup', new_callable=MockPopup), \
         patch.object(AIDetectionExecutionScreen, '__init__', return_value=None):

        screen = AIDetectionExecutionScreen()
        screen.app = MockKivyApp()
        screen.popup = MockPopup()
        screen.ids = {
            'main_scroll_view': MagicMock(scroll_y=0),
            'select_models': MagicMock(value_to_name={}, ids=MagicMock(form_spinner=MagicMock(text="", values=[]))),
            'heat_kernel_size': MagicMock(ids=MagicMock(form_input=MagicMock(text=""))),
            'heat_min_area': MagicMock(ids=MagicMock(form_input=MagicMock(text=""))),
            'heat_threshold': MagicMock(ids=MagicMock(form_slider=MagicMock(ids=MagicMock(input_box=MagicMock(text=""))))),
            'heat_min_intensity': MagicMock(ids=MagicMock(form_input=MagicMock(text=""))),
            'learn_method': MagicMock(text=""),
            'input_size': MagicMock(text=""),
            'patch_size': MagicMock(text=""),
            'sensor_setting_name': MagicMock(text=""),
            'work_config_name': MagicMock(text=""),
            'display_log': MagicMock(clear_logs_key=Mock(), add_log_line_key=Mock(), add_log_line=Mock()),
            'open_folder_button': MagicMock(path=""),
        }
        screen.on_kv_post(None)
        screen.validate = Mock()
        screen.check_val_status = Mock()
        screen.reset_val_status = Mock()

        return screen

class TestAIDetectionExecutionScreen:
    """Tests for AIDetectionExecutionScreen."""
    @pytest.fixture(autouse=True)
    def setup_screen(self, ai_detection_screen_instance):
        """Setup the screen for testing."""
        self.screen = ai_detection_screen_instance

    def test_screen_initialization(self):
        """Test that the screen can be initialized."""
        assert self.screen is not None
        assert isinstance(self.screen, AIDetectionExecutionScreen)

    def test_reset_form(self):
        """Test that the reset_form method clears the form to its initial state."""
        screen = self.screen
        screen.ids['select_models'].ids.form_spinner.text = "test_model"
        screen.reset_val_status = Mock()

        screen.reset_form()

        assert screen.ids['select_models'].ids.form_spinner.text == ""
        screen.reset_val_status.assert_called_once()

    @patch('app.screen.PyModule.D_AIDetectionExecutionScreen.get_db')
    def test_on_selected_model(self, mock_get_db):
        """Test that form fields are populated correctly when a model is selected."""
        screen = self.screen

        # Mock the database query result
        mock_model = MagicMock()
        mock_model.datasets.work_config_id = 123
        mock_model.learn_method = 1
        mock_model.patch_size_1 = 224
        mock_model.patch_size_2 = 112
        mock_model.input_size_1 = 224
        mock_model.input_size_2 = 112
        mock_model.datasets.work_configs.sensor_settings.name = "Sensor_A"
        mock_model.datasets.work_configs.name = "WorkConfig_B"

        mock_db_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_model
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        # Mock dependencies
        screen.extract_model_name = Mock(return_value="test_model_name")
        screen.update_open_folder_path = Mock()

        # Set a model text and trigger the method
        screen.form_mapping["select_models"].text = "Model Display Name"
        screen.on_selected_model()

        # Assertions
        assert screen.dropdown_work_config_id == 123
        assert screen.form_mapping["learn_method"].db_data == "1"
        assert screen.form_mapping["patch_size"].text == "224 / 112"
        assert screen.form_mapping["input_size"].text == "224 / 112"
        assert screen.form_mapping["sensor_setting_name"].text == "Sensor_A"
        assert screen.form_mapping["work_config_name"].text == "WorkConfig_B"
        screen.update_open_folder_path.assert_called_once()
        screen.form_mapping["display_log"].clear_logs_key.assert_called_once_with(default_key="detection_status_placeholder_D1")

    def test_on_start_detection_success(self):
        """Test the success case for starting detection."""
        screen = self.screen
        screen.run_detect_errors = Mock()
        screen.validate_paths = Mock()
        # Make validation pass
        screen.check_val_status.return_value = None

        screen.on_start_detection()

        screen.validate.assert_called_once()
        screen.validate_paths.assert_called_once()
        screen.check_val_status.assert_called_once()
        screen.run_detect_errors.assert_called_once()
        screen.form_mapping["display_log"].add_log_line_key.assert_called_with(text_key='processing_detection', color=ANY)

    def test_on_start_detection_validation_fail(self):
        """Test the failure case for starting detection due to validation."""
        screen = self.screen
        # Make validation fail
        screen.check_val_status.side_effect = Exception("Validation Failed")

        screen.on_start_detection()

        screen.popup.create_adaptive_popup.assert_called_once_with(
            title="error_popup",
            message="detection_failed"
        )

    @patch('app.screen.PyModule.D_AIDetectionExecutionScreen.get_db')
    @patch('os.path.exists', return_value=False)
    def test_validate_paths_file_not_found(self, mock_os_exists, mock_get_db):
        """Test path validation when a required file is not found."""
        screen = self.screen

        # Mock the database query result
        mock_model = MagicMock()
        mock_model.datasets.work_configs.sensor_settings.intrinsic_path = "/invalid/path/to/intrinsic.json"
        mock_model.weight_path_1 = "/invalid/path/to/weight.pth"
        #... mock other paths as needed

        mock_db_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_model
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        # Mock other dependencies
        screen.extract_model_name = Mock(return_value="test_model_name")
        screen.form_mapping["select_models"].error_message = "" # Reset error message

        # Trigger validation
        screen.validate_paths()

        # Assertion
        assert screen.form_mapping["select_models"].error_message == 'file_not_found_error_message'
