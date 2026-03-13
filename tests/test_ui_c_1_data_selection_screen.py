"""
Unit tests for the DataSelectionScreen.
"""
# pylint: disable=wildcard-import, undefined-variable, protected-access, unused-variable, too-many-lines, invalid-name, redefined-outer-name

from unittest.mock import patch, Mock, MagicMock, ANY
import pytest
from app.screen.PyModule.C_DataSelectionScreen import DataSelectionScreen

# Mock Kivy's App and other dependencies
class MockKivyApp:
    """Mock for Kivy App."""
    def get_running_app(self):
        """Mock get_running_app."""
        app = Mock()
        app.lang.get.return_value = "mock_translation"
        return app

class MockPopup:
    """Mock for MyPopup."""
    def __init__(self):
        self.create_loading_popup = MagicMock(return_value=Mock(open=Mock(), dismiss=Mock()))
        self.create_adaptive_popup = MagicMock(return_value=Mock(open=Mock(), dismiss=Mock(), bind=Mock()))
        self.create_confirmation_popup = MagicMock(return_value=Mock(open=Mock(), dismiss=Mock()))

class MockDataTableManager:
    """Mock for DataTableManager."""
    def __init__(self, *args, **kwargs):
        self.all_rows = []
        self.load_settings_from_db = Mock()
        self.find_page_for_record = Mock(return_value=1)
        self.display_current_page = Mock()
        self.create_pagination_controls = Mock()

class MockImageAlbum:
    """Mock for ImageAlbum."""
    def __init__(self, *args, **kwargs):
        self.items = []
        self.clear = Mock()
        self.load_images_lazy = Mock()
        self.get_all_selected_data = Mock(return_value=[])
        self.show_no_data_message = Mock()
        self.stop_monitoring = Mock()
        self.cancel_lazy_loading = Mock()

@pytest.fixture
def data_selection_screen_instance():
    """Fixture to create a DataSelectionScreen instance with mocked Kivy dependencies."""
    with patch('kivy.app.App.get_running_app', new_callable=MockKivyApp), \
         patch('app.screen.PyModule.C_DataSelectionScreen.MyPopup', new_callable=MockPopup), \
         patch('app.screen.PyModule.C_DataSelectionScreen.DataTableManager', new=MockDataTableManager), \
         patch('app.screen.PyModule.C_DataSelectionScreen.ImageAlbum') as MockedImageAlbum, \
         patch.object(DataSelectionScreen, '__init__', return_value=None):

        screen = DataSelectionScreen()
        screen.app = MockKivyApp().get_running_app()
        screen.popup = MockPopup()
        screen.data_selection_table = MockDataTableManager()
        screen.editing_item_name = None
        screen.copy_mode = False

        screen.ids = {
            'c1_dataset_name_input': MagicMock(text="", error_message=""),
            'c1_work_config_select': MagicMock(text="", values=[], error_message=""),
            'c1_folder_select': MagicMock(text="", values=[], error_message=""),
            'image_album_container': MagicMock(add_widget=Mock()),
            'image_album_error': MagicMock(error_message=""),
            'scroll_screen_C1_data_selection': MagicMock(scroll_y=1)
        }

        # Manually call post_init, which will now use the mocked ImageAlbum class
        screen.post_init(0)
        # The instance created inside post_init is what we want to use in tests
        screen.image_album = MockedImageAlbum.return_value

        return screen

class TestDataSelectionScreen:
    """Tests for DataSelectionScreen."""
    @pytest.fixture(autouse=True)
    def setup_screen(self, data_selection_screen_instance):
        """Setup the screen for testing."""
        self.screen = data_selection_screen_instance

    def test_screen_initialization(self):
        """Test that the screen and its components are initialized."""
        assert self.screen is not None
        assert isinstance(self.screen, DataSelectionScreen)
        self.screen.ids['image_album_container'].add_widget.assert_called_once()

    @patch('app.screen.PyModule.C_DataSelectionScreen.get_db')
    def test_on_pre_enter(self, mock_get_db):
        """Test the on_pre_enter method."""
        screen = self.screen
        screen.reset_form = Mock()
        screen.load_data_table = Mock()
        screen._display_work_config_options = Mock()

        screen.on_pre_enter()

        screen.reset_form.assert_called_once()
        screen.load_data_table.assert_called_once()
        screen._display_work_config_options.assert_called_once()
        assert screen.editing_item_name is None
        assert screen.copy_mode is False

    def test_reset_form(self):
        """Test that the form resets to its initial state."""
        screen = self.screen
        screen.ids.c1_dataset_name_input.text = "Old Name"

        screen.reset_form()

        assert screen.ids.c1_dataset_name_input.text == ""
        screen.image_album.clear.assert_called_once()

    @patch('app.screen.PyModule.C_DataSelectionScreen.get_db')
    def test_save_image_selections_create_success(self, mock_get_db):
        """Test successfully creating a new dataset."""
        screen = self.screen
        screen._validate_all_inputs = Mock(return_value=(True, False))
        screen._save_data = Mock() # Mock the actual save logic

        screen.save_image_selections()

        screen._validate_all_inputs.assert_called_once()
        screen._save_data.assert_called_once()
        screen.popup.create_adaptive_popup.assert_called_with(
            title='notification_popup',
            message='save_dataset_success_message'
        )

    def test_save_image_selections_validation_fail(self):
        """Test that saving fails if validation returns an error."""
        screen = self.screen
        screen._validate_all_inputs = Mock(return_value=(False, True))
        screen.navigate_to_error = Mock()

        screen.save_image_selections()

        screen._validate_all_inputs.assert_called_once()
        popup_instance = screen.popup.create_adaptive_popup.return_value
        popup_instance.bind.assert_called_once_with(on_dismiss=ANY)

        # Manually call the dismiss callback to test the navigation part
        dismiss_callback = popup_instance.bind.call_args.kwargs['on_dismiss']
        dismiss_callback()
        screen.navigate_to_error.assert_called_once()

    @patch('app.screen.PyModule.C_DataSelectionScreen.get_db')
    def test_load_item_to_form(self, mock_get_db):
        """Test loading an existing item into the form."""
        screen = self.screen

        mock_db_session = MagicMock()
        # Mock work config name query
        mock_db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.first.return_value = ('WorkConfigA',)
        # Mock images query
        mock_image = MagicMock(id=1, image_source_path='/path/to/img.png', usage_type='0', deleted_at=None)
        mock_db_session.query.return_value.filter_by.return_value.filter.return_value.all.return_value = [mock_image]
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        screen._get_id_by_name = Mock(return_value=1)
        # Mock os.path.isfile to prevent file system checks
        with patch('os.path.isfile', return_value=True):
            screen.load_item_to_form({'name': 'Dataset1'})

        assert screen.editing_item_name == 'Dataset1'
        assert screen.ids.c1_dataset_name_input.text == 'Dataset1'
        assert screen.ids.c1_work_config_select.text == 'WorkConfigA'
        screen.image_album.load_images_lazy.assert_called_once()
        # Check that the loaded selections are correct
        loaded_data = screen.image_album.load_images_lazy.call_args[0][0]
        assert len(loaded_data) == 1
        assert loaded_data[0]['source'] == '/path/to/img.png'
        assert loaded_data[0]['selected_option'] == '0'

    @patch('os.path.isdir', return_value=True)
    @patch('app.screen.PyModule.C_DataSelectionScreen.shutil.rmtree')
    @patch('app.screen.PyModule.C_DataSelectionScreen.recursive_delete')
    @patch('app.screen.PyModule.C_DataSelectionScreen.get_db')
    def test_delete_item(self, mock_get_db, mock_recursive_delete, mock_rmtree, mock_isdir):
        """Test deleting a dataset."""
        screen = self.screen
        screen.load_data_table = Mock()
        screen._get_work_config_id_by_dataset_name = Mock(return_value=123)
        screen._get_id_by_name = Mock(return_value=456)

        item = {'name': 'DatasetToDelete'}
        screen.delete_item(item)

        mock_recursive_delete.assert_called_once_with(ANY, 456, db_session=ANY)
        mock_rmtree.assert_called_once()
        screen.load_data_table.assert_called_once()
