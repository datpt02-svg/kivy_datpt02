"""
Unit tests for the DataGenerationScreen.
"""
# pylint: disable=wildcard-import, undefined-variable, protected-access, unused-variable, too-many-lines, invalid-name, redefined-outer-name

from unittest.mock import patch, Mock, MagicMock
import pytest
from db.models.work_configs import WorkConfigs
from app.screen.PyModule.B_DataGenerationScreen import DataGenerationScreen

class MockKivyApp:
    """Mock for Kivy App."""
    def get_running_app(self):
        """Mock get_running_app."""
        return Mock()

class MockCreateFolderModal(MagicMock):
    """Mock for CreateFolderModal."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ids = MagicMock()
        self.ids.new_folder_name = MagicMock(text="", error_message="")
        self.ids.create_folder_button = MagicMock(path="", folder_name="")
        self.ids.output_dir_label = MagicMock(id_text="", path_text="")
        self.parent_screen = None
        self.dismiss = Mock()
        self.open = Mock()

class MockPopup:
    """Mock for MyPopup."""
    def __init__(self):
        self.create_loading_popup = MagicMock(return_value=Mock(open=Mock(), dismiss=Mock()))
        self.create_adaptive_popup = MagicMock(return_value=Mock(open=Mock(), dismiss=Mock(), bind=Mock()))

@pytest.fixture
def data_generate_screen_instance():
    """Fixture to create a DataGenerationScreen instance with mocked Kivy dependencies."""
    with patch('kivy.app.App.get_running_app', return_value=MockKivyApp()), \
         patch('app.screen.PyModule.B_DataGenerationScreen.CreateFolderModal', new_callable=MockCreateFolderModal), \
         patch.object(DataGenerationScreen, '__init__', return_value=None):

        screen = DataGenerationScreen()

        screen.app = MockKivyApp()
        screen.popup = MockPopup()
        screen.create_folder_modal = MockCreateFolderModal(parent_screen=screen)

        id_label_mock = MagicMock()
        id_label_mock.ids = MagicMock()
        id_label_mock.ids.form_input = MagicMock(text="", error_message="")

        screen.ids = {
            'select_settings': MagicMock(text="", values=[], error_message=""),
            'folder_select': MagicMock(text="", folder_list=[], make_folder_text="Create New", selected_index=1, error_message=""),
            'open_folder_button': MagicMock(path=""),
            'collected_image': MagicMock(),
            'id_label': id_label_mock,
            'main_scroll_view': MagicMock(scroll_y=0)
        }
        screen.image_output_dir = ''

        # Manually call on_kv_post to populate form_mapping
        screen.on_kv_post(None)

        # Mock methods for tests
        screen.validate = Mock()
        screen.check_val_status = Mock()
        screen.reset_val_status = Mock()
        screen._get_id_by_name = Mock(return_value=1)
        screen.load_spinner_from_list_folders = Mock()
        screen.update_open_folder_path = Mock()

        return screen

class TestDataGenerationScreen:
    """Tests for DataGenerationScreen."""
    @pytest.fixture(autouse=True)
    def setup_screen(self, data_generate_screen_instance):
        """Setup the screen for testing."""
        self.screen = data_generate_screen_instance

    def test_reset_form(self):
        """Test that the reset_form method clears the form to its initial state."""
        screen = self.screen
        screen.dropdown_work_config_id = 1
        screen.form_mapping["new_folder_name"].text = "test_folder"
        screen.form_mapping["select_settings"].text = "test_config"
        screen.form_mapping["folder_select"].text = "some_folder"
        screen.form_mapping["id_label"].text = "test_id"
        screen.image_list = ["img1.png"]

        screen.reset_form()

        assert screen.dropdown_work_config_id is None
        assert screen.form_mapping["new_folder_name"].text == ""
        assert screen.form_mapping["select_settings"].text == ""
        assert screen.form_mapping["folder_select"].text == ""
        assert screen.form_mapping["id_label"].text == ""
        assert not screen.image_list
        screen.form_mapping["collected_image"].clear_widgets.assert_called_once()
        screen.reset_val_status.assert_called_once_with(screen.val_on_data_gen)

    @patch('app.screen.PyModule.B_DataGenerationScreen.get_db')
    def test_on_pre_enter(self, mock_get_db):
        """Test the on_pre_enter method."""
        screen = self.screen
        screen.reset_form = Mock()
        screen._display_work_config_options = Mock()
        with patch('app.screen.PyModule.B_DataGenerationScreen.FormScreen.on_pre_enter') as mock_super:
            screen.on_pre_enter()
            mock_super.assert_called_once()

        screen.reset_form.assert_called_once()
        screen._display_work_config_options.assert_called_once()
        assert screen.ids['main_scroll_view'].scroll_y == 1

    @patch('app.screen.PyModule.B_DataGenerationScreen.get_db')
    def test_display_work_config_options(self, mock_get_db):
        """Test that work config options are loaded into the spinner."""
        mock_db_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db_session
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [("config1",), ("config2",)]

        self.screen._display_work_config_options()

        assert self.screen.form_mapping["select_settings"].values == ["config1", "config2"]

    def test_on_work_config_selected(self):
        """Test logic when a work config is selected."""
        screen = self.screen
        screen.form_mapping["select_settings"].text = "test_config"
        screen.dropdown_work_config_id = None

        screen.on_work_config_selected()

        screen.form_mapping["collected_image"].clear_widgets.assert_called_once()
        assert screen.form_mapping["id_label"].text == ""
        screen._get_id_by_name.assert_called_once_with(WorkConfigs, "test_config")
        assert screen.dropdown_work_config_id == 1
        assert screen.form_mapping["output_dir_label"].id_text == "1"
        screen.load_spinner_from_list_folders.assert_called_once()
        screen.update_open_folder_path.assert_called_once()

    @patch('app.screen.PyModule.B_DataGenerationScreen.HISTOGRAM_FOLDER', "dummy_path")
    def test_on_folder_create_button_success(self):
        """Test folder creation button logic with valid inputs."""
        screen = self.screen
        screen.form_mapping["select_settings"].text = "test_config"
        screen.form_mapping["new_folder_name"].text = "new_folder"
        screen.form_mapping["new_folder_name"].error_message = ""
        screen.is_folder_name_duplicate = Mock(return_value=False)
        screen.check_val_status.side_effect = None

        with patch('os.path.exists', return_value=True):
            screen.on_folder_create_button()

        screen.check_val_status.assert_called_once()
        assert screen.form_mapping["create_folder_button"].folder_name == "new_folder"
        screen.create_folder_modal.dismiss.assert_called_once()

    @patch('app.screen.PyModule.B_DataGenerationScreen.HISTOGRAM_FOLDER', "dummy_path")
    def test_on_folder_create_button_failure_duplicate(self):
        """Test folder creation failure due to duplicate name."""
        screen = self.screen
        screen.form_mapping["select_settings"].text = "test_config"
        screen.form_mapping["new_folder_name"].text = "existing_folder"
        screen.form_mapping["new_folder_name"].error_message = ""
        screen.is_folder_name_duplicate = Mock(return_value=True)
        screen.check_val_status.side_effect = None


        with patch('os.path.exists', return_value=True):
            screen.on_folder_create_button()

        assert screen.form_mapping["new_folder_name"].error_message == "folder_name_already_exists"
        assert screen.form_mapping["create_folder_button"].folder_name == ""

    def test_on_folder_created(self):
        """Test actions after a folder is successfully created."""
        screen = self.screen
        screen.form_mapping["select_settings"].text = "test_config"
        screen.form_mapping["new_folder_name"].text = "newly_created"

        screen.on_folder_created()

        screen.load_spinner_from_list_folders.assert_called()
        assert screen.form_mapping["folder_select"].text == "newly_created"
        assert screen.form_mapping["new_folder_name"].text == ""

    @patch('app.screen.PyModule.B_DataGenerationScreen.BuildCommand')
    @patch('app.screen.PyModule.B_DataGenerationScreen.Clock')
    def test_run_generate_success(self, mock_clock, mock_build_command):
        """Test successful initiation of data generation."""
        screen = self.screen
        screen.form_mapping["select_settings"].text = "test_config"
        screen.form_mapping["folder_select"].text = "data_folder"
        screen.form_mapping["id_label"].text = "label1"
        screen.check_val_status.side_effect = None
        screen.validate_paths = Mock()
        screen.validate_id_label = Mock()
        screen._run_task_in_thread = Mock()

        screen.run_generate()

        screen.validate.assert_called_once_with(screen.val_on_data_gen)
        screen.validate_paths.assert_called_once()
        screen.validate_id_label.assert_called_once()
        screen.check_val_status.assert_called_once_with(screen.val_on_data_gen)
        mock_clock.schedule_once.assert_called_once()
        screen._run_task_in_thread.assert_called_once()

    def test_run_generate_validation_fail(self):
        """Test data generation failure due to validation error."""
        screen = self.screen
        screen.check_val_status.side_effect = Exception("Validation Failed")
        screen.popup.create_adaptive_popup = Mock(return_value=Mock(open=Mock()))

        screen.run_generate()

        screen.popup.create_adaptive_popup.assert_called_once_with(
            title='error_popup',
            message='generation_failed_popup_B2'
        )

    def test_validate_id_label_valid_empty(self):
        """Test id_label validation with an empty string (which is valid)."""
        screen = self.screen
        screen.form_mapping["id_label"].text = "  "
        screen.form_mapping["id_label"].error_message = "initial_error"

        screen.validate_id_label()
        assert screen.form_mapping["id_label"].text == ""
        assert screen.form_mapping["id_label"].error_message == ""


    def test_validate_id_label_invalid_char(self):
        """Test id_label validation with invalid characters."""
        screen = self.screen
        screen.form_mapping["id_label"].text = "Invalid-ID"

        screen.validate_id_label()

        assert screen.form_mapping["id_label"].error_message == 'id_label_error_message_B2'

    def test_validate_id_label_invalid_length(self):
        """Test id_label validation with excessive length."""
        screen = self.screen
        screen.form_mapping["id_label"].text = "TooLongID123"

        screen.validate_id_label()

        assert screen.form_mapping["id_label"].error_message == 'id_label_error_message_B2'

    @patch('app.screen.PyModule.B_DataGenerationScreen.get_db')
    @patch('os.path.exists')
    def test_validate_paths_file_not_found(self, mock_path_exists, mock_get_db):
        """Test path validation when a required file is missing."""
        mock_path_exists.return_value = False
        mock_db_session = MagicMock()
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        mock_work_config = MagicMock()
        mock_work_config.sensor_settings.intrinsic_path = "non_existent_path.json"
        mock_work_config.sensor_settings.perspective_path = "path/to/perspective"
        mock_work_config.sensor_settings.speed_path = "path/to/speed"
        mock_work_config.bias_path = "path/to/bias"

        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_work_config

        screen = self.screen
        screen.form_mapping["select_settings"].text = "some_config"
        screen.form_mapping["select_settings"].error_message = ""

        screen.validate_paths()

        assert screen.form_mapping["select_settings"].error_message == 'file_not_found_error_message'

    def test_on_folder_select_create_new(self):
        """Test that the create folder modal is opened when 'Create New' is selected."""
        screen = self.screen
        screen.form_mapping["folder_select"].text = "Create New"
        screen.form_mapping["folder_select"].make_folder_text = "Create New"
        screen.form_mapping["folder_select"].selected_index = 0
        screen.open_create_folder_modal = Mock()

        screen.on_folder_select()

        screen.open_create_folder_modal.assert_called_once()

    def test_on_folder_select_existing(self):
        """Test that image directory is updated when an existing folder is selected."""
        screen = self.screen
        screen.form_mapping["folder_select"].text = "existing_folder"
        screen.form_mapping["folder_select"].selected_index = 1
        screen.update_image_dir = Mock()
        screen.update_open_folder_path = Mock()

        screen.on_folder_select()

        screen.update_image_dir.assert_called_once()
        screen.update_open_folder_path.assert_called_once()
