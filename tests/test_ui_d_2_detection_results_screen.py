# pylint: disable=wildcard-import, undefined-variable, protected-access, unused-variable, too-many-lines, invalid-name, redefined-outer-name

from unittest.mock import patch, Mock, MagicMock
import pytest
from app.screen.PyModule.D_DetectionResultsScreen import DetectionResultsScreen

# Mock Kivy's App and other dependencies
class MockKivyApp:
    def get_running_app(self):
        return Mock()

class MockDataTableManager:
    def __init__(self, screen, table_id, pagination_box_id, headers, db_model, types, custom_message):
        self.screen = screen
        self.table_id = table_id
        self.pagination_box_id = pagination_box_id
        self.headers = headers
        self.db_model = db_model
        self.types = types
        self.custom_message = custom_message
        self.current_page = 1
        self.all_rows = []
        self.display_current_page = Mock()
        self.create_pagination_controls = Mock()
        self.reload_data_table = Mock()

@pytest.fixture
def detection_results_screen_instance():
    """Fixture to create a DetectionResultsScreen instance with mocked Kivy dependencies."""
    with patch('kivy.app.App.get_running_app', return_value=MockKivyApp()), \
         patch('app.screen.PyModule.D_DetectionResultsScreen.DataTableManager', new=MockDataTableManager), \
         patch.object(DetectionResultsScreen, '__init__', return_value=None):

        screen = DetectionResultsScreen()
        screen.app = MockKivyApp()
        screen.ids = {
            'main_scroll_view': MagicMock(scroll_y=0),
            'data_table_d_detection_list': MagicMock(),
            'pagination_box_d_detection_list': MagicMock(),
            'open_folder_button': MagicMock(path=""),
            'select_settings': MagicMock(text="", values=["All"]),
            'detection_result_filter': MagicMock(text="", label=["All"]),
            'date_filter': MagicMock(text="", reset_to_today=Mock()),
        }

        screen.detection_results_table = MockDataTableManager(
            screen=screen,
            table_id="data_table_d_detection_list",
            pagination_box_id="pagination_box_d_detection_list",
            headers=["header1", "header2"],
            db_model=MagicMock(),
            types=['str', 'str'],
            custom_message=True
        )
        screen.load_data_table = Mock()
        screen.on_kv_post(None)


        return screen

class TestDetectionResultsScreen:
    @pytest.fixture(autouse=True)
    def setup_screen(self, detection_results_screen_instance):
        self.screen = detection_results_screen_instance

    def test_screen_initialization(self):
        """Test that the screen can be initialized."""
        assert self.screen is not None
        assert isinstance(self.screen, DetectionResultsScreen)

    @patch('app.screen.PyModule.D_DetectionResultsScreen.FormScreen.on_pre_enter')
    def test_on_pre_enter(self, mock_super):
        """Test the on_pre_enter method."""
        screen = self.screen
        screen.load_filter_data_table = Mock()
        screen._display_work_config_options = Mock()

        screen.on_pre_enter()

        mock_super.assert_called_once()
        screen.load_filter_data_table.assert_called_once()
        assert screen.ids['main_scroll_view'].scroll_y == 1

    def test_reset_form(self):
        """Test that the filter form resets to default values."""
        screen = self.screen

        # Change values from default
        screen.form_mapping["select_settings"].text = "Some Work Config"
        screen.form_mapping["detection_result_filter"].text = "NG"

        screen.reset_form()

        # Assert values are reset
        assert screen.form_mapping["select_settings"].text == "All"
        assert screen.form_mapping["detection_result_filter"].text == "All"
        screen.form_mapping["date_filter"].reset_to_today.assert_called_once()

    def test_on_filter_button(self):
        """Test that filtering calls the data table loading method with correct filters."""
        screen = self.screen
        screen.load_filter_data_table = Mock(return_value=True)

        screen.form_mapping["select_settings"].text = "WorkConfigA"
        screen.form_mapping["date_filter"].text = "2023-01-01"
        screen.form_mapping["detection_result_filter"].text = "OK"

        screen.on_filter_button()

        screen.load_filter_data_table.assert_called_once_with("WorkConfigA", "2023-01-01", "OK")

    def test_on_filter_button_no_results(self):
        """Test that a popup is shown when filtering returns no results."""
        screen = self.screen
        screen.load_filter_data_table = Mock(return_value=False)
        screen.popup = Mock()

        screen.on_filter_button()

        screen.popup.create_adaptive_popup.assert_called_once_with(
            title="notification_popup",
            message="no_data_filter_popup_D2"
        )

    @patch('app.screen.PyModule.D_DetectionResultsScreen.filter_detection_results')
    @patch('os.path.exists', return_value=True)
    def test_load_filter_data_table_with_data(self, mock_exists, mock_filter):
        """Test loading data into the table when the service returns results."""
        screen = self.screen

        # Mock service result
        mock_result = MagicMock()
        mock_result.id = 1
        mock_result.detected_at = "2023-01-01T12:00:00"
        mock_result.work_configs.name = "WorkConfigA"
        mock_result.work_config_id = 101
        mock_result.thumbnail_path = "thumb/1.png"
        mock_result.heatmap_path = "heat/1.png"
        mock_result.his_img_path = "his/1.png"
        mock_result.judgment = 0 # OK
        mock_filter.return_value = [mock_result]

        screen._get_judgment_display = Mock(return_value="OK")

        result = screen.load_filter_data_table("WorkConfigA", "2023-01-01", "OK")

        assert result is True
        assert len(screen.detection_results_table.all_rows) == 1
        first_row = screen.detection_results_table.all_rows[0]
        assert first_row["index"] == 1
        assert first_row["work_config_name"] == "WorkConfigA"
        assert first_row["judgment"] == "OK"
        screen.detection_results_table.display_current_page.assert_called_once()

    @patch('app.screen.PyModule.D_DetectionResultsScreen.filter_detection_results', return_value=[])
    def test_load_filter_data_table_no_data(self, mock_filter):
        """Test loading data when the service returns no results."""
        screen = self.screen

        result = screen.load_filter_data_table("WorkConfigA", "2023-01-01", "OK")

        assert result is False
        assert len(screen.detection_results_table.all_rows) == 0
        screen.detection_results_table.display_current_page.assert_called_once()

    @patch('app.screen.PyModule.D_DetectionResultsScreen.read_system_config')
    @patch('app.screen.PyModule.D_DetectionResultsScreen.shutil.copy2')
    @patch('os.makedirs')
    @patch('os.path.exists', return_value=True)
    def test_backup_item_success(self, mock_exists, mock_makedirs, mock_copy, mock_read_config):
        """Test successful backup of an item."""
        screen = self.screen
        screen._get_image_paths_by_id = Mock(return_value=("his/1.png", "thumb/1.png", "heat/1.png"))
        mock_read_config.return_value.value = "/backup/path"
        screen.popup = Mock()

        item_to_backup = {'index': 1}
        screen.backup_item(item_to_backup)

        assert mock_copy.call_count == 3
        screen.popup.create_adaptive_popup.assert_called_with(
            title="notification_popup",
            message="backup_popup_success_D2"
        )

    @patch('app.screen.PyModule.D_DetectionResultsScreen.read_system_config')
    @patch('os.path.exists', return_value=False)
    def test_backup_item_no_backup_dir(self, mock_exists, mock_read_config):
        """Test backup failure when the backup directory does not exist."""
        screen = self.screen
        mock_read_config.return_value.value = "/invalid/backup/path"
        screen.popup = Mock()

        item_to_backup = {'index': 1}
        screen.backup_item(item_to_backup)

        screen.popup.create_adaptive_popup.assert_called_with(
            title="error_popup",
            message="backup_popup_failed_D2"
        )
