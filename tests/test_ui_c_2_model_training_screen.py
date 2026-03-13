"""
Unit tests for the ModelTrainingScreen.
"""
# pylint: disable=wildcard-import, undefined-variable, protected-access, unused-variable, too-many-lines, invalid-name, redefined-outer-name

from unittest.mock import patch, Mock, MagicMock
import pytest
from app.screen.PyModule.C_ModelTrainingScreen import ModelTrainingScreen, LearnMethod

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

@pytest.fixture
def model_training_screen_instance():
    """Fixture to create a ModelTrainingScreen instance with mocked Kivy dependencies."""
    with patch('kivy.app.App.get_running_app', new_callable=MockKivyApp), \
         patch('app.screen.PyModule.C_ModelTrainingScreen.MyPopup', new_callable=MockPopup), \
         patch('app.screen.PyModule.C_ModelTrainingScreen.psutil'), \
         patch.object(ModelTrainingScreen, '__init__', return_value=None):

        screen = ModelTrainingScreen()
        screen.app = MockKivyApp().get_running_app()
        screen.popup = MockPopup()
        screen._training_lock = Mock()
        screen._ui_lock = Mock()
        screen._training_thread = None
        screen._training_process = None
        screen._training_stopped = False # Fix AttributeError
        screen._pending_result_view = None

        screen.ids = {
            'c2_model_name_input': MagicMock(text="TestModel", error_message=""),
            'c2_dataset_select': MagicMock(text="TestDataset", values=[], error_message=""),
            'c2_epoch_input': MagicMock(text="10", error_message=""),
            'c2_training_method_select': MagicMock(text=screen.app.lang.get('learn_method_1'), label=['mock_translation']),
            'patch_size_1_select': MagicMock(ids=MagicMock(spinner=MagicMock(text="224", values=[]))),
            'input_size_1_select': MagicMock(ids=MagicMock(spinner=MagicMock(text="224", values=[]))),
            'patch_size_2_select': MagicMock(ids=MagicMock(spinner=MagicMock(text="112", values=[]))),
            'input_size_2_select': MagicMock(ids=MagicMock(spinner=MagicMock(text="112", values=[]))),
            'training_log_viewer': MagicMock(clear_logs_key=Mock(), add_log_line_key=Mock(), add_log_line=Mock()),
            'training_button': MagicMock(disabled=False, enable_hover=True),
            'stop_training_button': MagicMock(disabled=True, enable_hover=False),
            'scroll_screen_C2_model_training': MagicMock(),
        }

        return screen

class TestModelTrainingScreen:
    """Tests for ModelTrainingScreen."""
    @pytest.fixture(autouse=True)
    def setup_screen(self, model_training_screen_instance):
        """Setup the screen for testing."""
        self.screen = model_training_screen_instance

    def test_screen_initialization(self):
        """Test that the screen can be initialized."""
        assert self.screen is not None
        assert isinstance(self.screen, ModelTrainingScreen)

    @patch('app.screen.PyModule.C_ModelTrainingScreen.get_db')
    def test_on_pre_enter(self, mock_get_db):
        """Test that on_pre_enter populates the dataset spinner."""
        screen = self.screen
        screen._should_reset_screen = Mock(return_value=True) # Force reset path
        screen.reset_screen_c2 = Mock()

        # Mock DB query for datasets and system configs
        mock_db_session = MagicMock()
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [('Dataset1',), ('Dataset2',)]
        mock_db_session.query.return_value.filter.return_value.all.return_value = [('PATCH_SIZE_LIST', '224,112'), ('INPUT_SIZE_LIST', '224,112')]
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        screen.on_pre_enter()

        assert screen.ids.c2_dataset_select.values == ['Dataset1', 'Dataset2']
        screen.reset_screen_c2.assert_called_once()

    def test_start_training_validation_fail(self):
        """Test that training does not start if validation fails."""
        screen = self.screen
        screen.start_log_thread = Mock()
        validation_result = {'is_valid': False, 'errors': 'some_error', 'show_log': None, 'training_status_placeholder': False}
        screen._validate_training_inputs = Mock(return_value=validation_result)
        screen._handle_validation_errors = Mock()

        # We need to enter the context manager for the test
        with patch.object(screen, 'training_session', return_value=MagicMock(__enter__=Mock(return_value=True), __exit__=Mock())):
            screen.start_training()

        screen.start_log_thread.assert_not_called()
        screen._handle_validation_errors.assert_called_once_with('some_error', None, False)

    @patch('app.screen.PyModule.C_ModelTrainingScreen.get_db')
    def test_prepare_training_data(self, mock_get_db):
        """Test the preparation of training data and DB interaction for a new model."""
        screen = self.screen

        mock_dataset = MagicMock(id=1, work_config_id=123)
        mock_db_session = MagicMock()
        # Mock dataset query (1st call) and existing model query (2nd call)
        mock_db_session.query.return_value.filter.return_value.filter.return_value.first.side_effect = [mock_dataset, None]
        mock_get_db.return_value.__enter__.return_value = mock_db_session

        params = screen._prepare_training_data()

        assert params is not None
        assert params['model_name'] == 'TestModel'
        assert params['learn_method'] == LearnMethod.PATCH
        assert 'data.txt' in params['data_root']

    def test_stop_training(self):
        """Test the process of stopping a training session."""
        screen = self.screen
        screen._is_training_running = Mock(return_value=True)
        screen._handle_stop_confirmation = Mock(return_value=True)

        screen.stop_training()

        # Assert that a confirmation popup is shown
        screen.popup.create_confirmation_popup.assert_called_once_with(
            title='confirm_popup',
            message='stop_training_confirm_C2',
            on_confirm=screen._handle_stop_confirmation
        )
