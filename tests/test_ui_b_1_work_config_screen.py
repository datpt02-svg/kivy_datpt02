"""
Unit tests for the WorkConfigScreen.
"""
# pylint: disable=wildcard-import, undefined-variable, protected-access, unused-variable, too-many-lines, invalid-name, redefined-outer-name, unnecessary-dunder-call

import os
from unittest.mock import ANY, patch, Mock, MagicMock
import pytest

from app.screen.PyModule.B_WorkConfigScreen import WorkConfigScreen
from app.libs.constants.default_values import DefaultValuesB1
from app.libs.widgets.components import FormScreen, ValidatedInput

# Mock Kivy's App and relevant properties for WorkConfigScreen to initialize
class MockKivyApp:
    """Mock for Kivy App."""
    def get_running_app(self):
        """Mock get_running_app."""
        return Mock()

class MockDataTableManager:
    """Mock for DataTableManager."""
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

class MockPopup:
    """Mock for MyPopup."""
    def __init__(self):
        self.create_loading_popup = MagicMock(return_value=Mock(open=Mock(), dismiss=Mock()))
        self.create_adaptive_popup = MagicMock(return_value=Mock(open=Mock(), dismiss=Mock(), bind=Mock()))

@pytest.fixture
def work_config_screen_instance():
    """Fixture to create a WorkConfigScreen instance with mocked Kivy dependencies."""
    with patch('kivy.app.App.get_running_app', return_value=MockKivyApp()), \
         patch('app.screen.PyModule.B_WorkConfigScreen.MyPopup', new_callable=MockPopup), \
         patch('app.screen.PyModule.B_WorkConfigScreen.DataTableManager', new=MockDataTableManager), \
         patch('app.screen.PyModule.utils.dataset_spinner.DatasetSpinner.load_spinner_from_folder'): # Mock this

        # Instantiate WorkConfigScreen
        with patch.object(WorkConfigScreen, '__init__', return_value=None):
            screen = WorkConfigScreen()

        # Manually set attributes that would normally be set by Kivy's __init__ or on_kv_post
        screen.alignment_count = 3
        screen.temp_histogram = None
        screen.clock_update_temp_histogram = None
        screen.app = MockKivyApp() # Manually set the app instance
        screen.popup = MockPopup() # Manually set the popup instance
        screen.work_configs_table = MockDataTableManager(
            screen=screen,
            table_id="data_table_b_work_config",
            pagination_box_id="pagination_box_b_work_config",
            headers=["table_b1_header_1", "table_b1_header_2", "table_b1_header_3", "table_b1_header_4", "table_b1_header_5"],
            db_model=MagicMock(), # Mock the DB model
            types=['str', 'image', 'float', 'str', 'button'],
            custom_message=True
        )

        # Manually mock necessary attributes for screen.ids and form_mapping
        screen.ids = {}
        # Define mock objects with text tracking for relevant attributes
        mock_form_input_b_setting_name = MagicMock(text="")
        mock_form_spinner_prophesee_setting = MagicMock(text="")
        mock_form_input_delta_t = MagicMock(text="")
        mock_i_roi_checkbox = MagicMock(active=False)
        mock_i_roi_input = MagicMock(text="")
        mock_form_spinner_b_bias_path_select = MagicMock(text="")
        mock_sensor_filter = MagicMock(active=False, text="None")
        mock_form_input_sensor_filter_threshold = MagicMock(text="", allow_none=True)
        mock_slider_input_box_seg_kernel_size = MagicMock(text="")
        mock_slider_input_box_seg_threshold = MagicMock(text="")
        mock_slider_input_box_seg_padding = MagicMock(text="")
        mock_form_input_on_event_his_value = MagicMock(text="")
        mock_form_input_off_event_his_value = MagicMock(text="")
        mock_slider_input_box_histogram_add_pixel_params = MagicMock(text="")
        mock_form_spinner_color_map = MagicMock(text="")
        mock_margin_input_top_left_x = MagicMock(text="", allow_none=True)
        mock_margin_input_top_left_y = MagicMock(text="", allow_none=True)
        mock_margin_input_bottom_right_x = MagicMock(text="", allow_none=True)
        mock_margin_input_bottom_right_y = MagicMock(text="", allow_none=True)

        # Populate ids for form_mapping with mocks that track text
        screen.ids['b_setting_name'] = MagicMock(ids=MagicMock(form_input=mock_form_input_b_setting_name))
        screen.ids['prophesee_setting'] = MagicMock(ids=MagicMock(form_spinner=mock_form_spinner_prophesee_setting))
        screen.ids['delta_t'] = MagicMock(ids=MagicMock(form_input=mock_form_input_delta_t))
        screen.ids['i_roi_checkbox'] = mock_i_roi_checkbox
        screen.ids['i_roi_input'] = mock_i_roi_input
        screen.ids['b_bias_path_select'] = MagicMock(ids=MagicMock(form_spinner=mock_form_spinner_b_bias_path_select))
        screen.ids['sensor_filter'] = mock_sensor_filter
        screen.ids['sensor_filter_threshold'] = MagicMock(ids=MagicMock(form_input=mock_form_input_sensor_filter_threshold))
        screen.ids['seg_kernel_size'] = MagicMock(ids=MagicMock(form_slider=MagicMock(ids=MagicMock(input_box=mock_slider_input_box_seg_kernel_size))))
        screen.ids['seg_threshold'] = MagicMock(ids=MagicMock(form_slider=MagicMock(ids=MagicMock(input_box=mock_slider_input_box_seg_threshold))))
        screen.ids['seg_padding'] = MagicMock(ids=MagicMock(form_slider=MagicMock(ids=MagicMock(input_box=mock_slider_input_box_seg_padding))))
        screen.ids['on_event_his_value'] = MagicMock(ids=MagicMock(form_input=mock_form_input_on_event_his_value))
        screen.ids['off_event_his_value'] = MagicMock(ids=MagicMock(form_input=mock_form_input_off_event_his_value))
        screen.ids['histogram_add_pixel_params'] = MagicMock(ids=MagicMock(form_slider=MagicMock(ids=MagicMock(input_box=mock_slider_input_box_histogram_add_pixel_params))))
        screen.ids['color_map'] = MagicMock(ids=MagicMock(form_spinner=mock_form_spinner_color_map))
        screen.ids['top_left_x'] = MagicMock(ids=MagicMock(margin_input=mock_margin_input_top_left_x))
        screen.ids['top_left_y'] = MagicMock(ids=MagicMock(margin_input=mock_margin_input_top_left_y))
        screen.ids['bottom_right_x'] = MagicMock(ids=MagicMock(margin_input=mock_margin_input_bottom_right_x))
        screen.ids['bottom_right_y'] = MagicMock(ids=MagicMock(margin_input=mock_margin_input_bottom_right_y))

        for i in range(1, 4):
            alignment_id = f'alignment_{i}'
            align_mock = MagicMock()

            # Create specific mocks for nested inputs
            mock_align_top_left_x_input = MagicMock(text="")
            mock_align_top_left_y_input = MagicMock(text="")
            mock_align_bottom_right_x_input = MagicMock(text="")
            mock_align_bottom_right_y_input = MagicMock(text="")
            mock_align_error_image = MagicMock(opacity=0, error_message="")
            mock_align_error_alignment = MagicMock(opacity=0, error_message="")

            # Assign these mocks to the nested structure
            align_mock.ids.image_top_left_x = MagicMock(ids=MagicMock(margin_input=mock_align_top_left_x_input))
            align_mock.ids.image_top_left_y = MagicMock(ids=MagicMock(margin_input=mock_align_top_left_y_input))
            align_mock.ids.image_bottom_right_x = MagicMock(ids=MagicMock(margin_input=mock_align_bottom_right_x_input))
            align_mock.ids.image_bottom_right_y = MagicMock(ids=MagicMock(margin_input=mock_align_bottom_right_y_input))

            align_mock.error_image = mock_align_error_image
            align_mock.error_alignment = mock_align_error_alignment
            align_mock.validate_text = Mock()

            # Define reset_input to actually clear the mocked inputs
            def mock_reset_input(
                tlx=mock_align_top_left_x_input,
                tly=mock_align_top_left_y_input,
                brx=mock_align_bottom_right_x_input,
                bry=mock_align_bottom_right_y_input
            ):
                tlx.text = ""
                tly.text = ""
                brx.text = ""
                bry.text = ""
            align_mock.reset_input = Mock(side_effect=mock_reset_input)

            # Define reset_val_status to reset opacities
            def mock_reset_val_status(
                err_img=mock_align_error_image,
                err_align=mock_align_error_alignment
            ):
                err_img.opacity = 0
                err_align.opacity = 0
            align_mock.reset_val_status = Mock(side_effect=mock_reset_val_status)

            screen.ids[alignment_id] = align_mock

        screen.ids['main_scroll_view'] = MagicMock(scroll_y=0)
        screen.ids['show_confirm_hist'] = MagicMock()
        screen.ids['data_table_b_work_config'] = MagicMock()
        screen.ids['pagination_box_b_work_config'] = MagicMock()

        # Manually call on_kv_post to populate form_mapping
        screen.on_kv_post(None)

        # Mock validate methods to avoid validation errors
        screen.validate = Mock()
        screen.check_val_status = Mock()

        return screen

class TestWorkConfigScreen:
    """Tests for WorkConfigScreen."""
    @pytest.fixture(autouse=True)
    def setup_screen(self, work_config_screen_instance):
        """Setup the screen for testing."""
        self.screen = work_config_screen_instance

    def test_reset_form(self):
        """Test that the reset_form method clears temporary files and reloads the data table."""
        screen = self.screen

        # Mock file system operations and data table reload
        with patch('shutil.rmtree') as mock_rmtree, \
             patch('os.makedirs') as mock_makedirs, \
             patch.object(screen, 'load_data_table') as mock_load_data_table:

            # Set some values to non-default to ensure they are reset
            screen.ids['b_setting_name'].ids.form_input.text = "TestName"
            screen.ids['prophesee_setting'].ids.form_spinner.text = "Some Setting"
            screen.ids['delta_t'].ids.form_input.text = "100"
            screen.ids['i_roi_checkbox'].active = True
            screen.ids['b_bias_path_select'].ids.form_spinner.text = "/path/to/bias"
            screen.ids['sensor_filter'].active = True
            screen.ids['sensor_filter_threshold'].ids.form_input.text = "50"
            screen.ids['seg_kernel_size'].ids.form_slider.ids.input_box.text = "5"
            screen.ids['seg_threshold'].ids.form_slider.ids.input_box.text = "0.5"
            screen.ids['seg_padding'].ids.form_slider.ids.input_box.text = "1"
            screen.ids['on_event_his_value'].ids.form_input.text = "1000"
            screen.ids['off_event_his_value'].ids.form_input.text = "2000"
            screen.ids['histogram_add_pixel_params'].ids.form_slider.ids.input_box.text = "10"
            screen.ids['color_map'].ids.form_spinner.text = "JET"
            screen.ids['top_left_x'].ids.margin_input.text = "1"
            screen.ids['top_left_y'].ids.margin_input.text = "2"
            screen.ids['bottom_right_x'].ids.margin_input.text = "3"
            screen.ids['bottom_right_y'].ids.margin_input.text = "4"

            for i in range(1, screen.alignment_count + 1):
                alignment_id = f'alignment_{i}'
                screen.ids[alignment_id].ids.image_top_left_x.ids.margin_input.text = str(i * 10)
                screen.ids[alignment_id].ids.image_top_left_y.ids.margin_input.text = str(i * 11)
                screen.ids[alignment_id].ids.image_bottom_right_x.ids.margin_input.text = str(i * 12)
                screen.ids[alignment_id].ids.image_bottom_right_y.ids.margin_input.text = str(i * 13)
                screen.ids[alignment_id].error_image.opacity = 1
                screen.ids[alignment_id].error_alignment.opacity = 1

            # Call the method under test
            screen.reset_form()

            # Assert that file system operations and load_data_table were called
            assert mock_rmtree.call_count == 2
            assert mock_makedirs.call_count == 2

            mock_load_data_table.assert_called_once()
            screen.work_configs_table.display_current_page.assert_not_called()
            screen.work_configs_table.create_pagination_controls.assert_not_called()

            # Assert that all form inputs are reset to their default values
            assert screen.ids['b_setting_name'].ids.form_input.text == ""
            assert screen.ids['prophesee_setting'].ids.form_spinner.text == DefaultValuesB1.PROPHESEE_SETTING
            assert screen.ids['delta_t'].ids.form_input.text == str(DefaultValuesB1.DELTA_T)
            assert screen.ids['i_roi_checkbox'].active is True
            assert screen.ids['b_bias_path_select'].ids.form_spinner.text == DefaultValuesB1.B_BIAS_PATH_SELECT
            assert screen.ids['sensor_filter'].text == DefaultValuesB1.SENSOR_FILTER
            assert screen.ids['sensor_filter_threshold'].ids.form_input.text == str(DefaultValuesB1.SENSOR_FILTER_THRESHOLD)
            assert screen.ids['seg_kernel_size'].ids.form_slider.ids.input_box.text == str(DefaultValuesB1.SEG_KERNEL_SIZE)
            assert screen.ids['seg_threshold'].ids.form_slider.ids.input_box.text == str(DefaultValuesB1.SEG_THRESHOLD)
            assert screen.ids['seg_padding'].ids.form_slider.ids.input_box.text == str(DefaultValuesB1.SEG_PADDING)
            assert screen.ids['on_event_his_value'].ids.form_input.text == str(DefaultValuesB1.ON_EVENT_HIS_VALUE)
            assert screen.ids['off_event_his_value'].ids.form_input.text == str(DefaultValuesB1.OFF_EVENT_HIS_VALUE)
            assert screen.ids['histogram_add_pixel_params'].ids.form_slider.ids.input_box.text == str(DefaultValuesB1.HISTOGRAM_ADD_PIXEL_PARAMS)
            assert screen.ids['color_map'].ids.form_spinner.text == DefaultValuesB1.COLOR_MAP
            assert screen.ids['top_left_x'].ids.margin_input.text == ""
            assert screen.ids['top_left_y'].ids.margin_input.text == ""
            assert screen.ids['bottom_right_x'].ids.margin_input.text == ""
            assert screen.ids['bottom_right_y'].ids.margin_input.text == ""

            for i in range(1, screen.alignment_count + 1):
                alignment_id = f'alignment_{i}'
                assert screen.ids[alignment_id].ids.image_top_left_x.ids.margin_input.text == ""
                assert screen.ids[alignment_id].ids.image_top_left_y.ids.margin_input.text == ""
                assert screen.ids[alignment_id].ids.image_bottom_right_x.ids.margin_input.text == ""
                assert screen.ids[alignment_id].ids.image_bottom_right_y.ids.margin_input.text == ""
                assert screen.ids[alignment_id].error_image.opacity == 0
                assert screen.ids[alignment_id].error_alignment.opacity == 0

    def test_on_i_roi_check_box_active(self):
        """Test that when the i_roi_checkbox is active, the ROI input fields are enabled."""
        screen = self.screen
        screen.on_i_roi_check_box(active=True)

        assert screen.form_mapping["roi.top_left_x"].allow_none is False
        assert screen.form_mapping["roi.top_left_y"].allow_none is False
        assert screen.form_mapping["roi.bottom_right_x"].allow_none is False
        assert screen.form_mapping["roi.bottom_right_y"].allow_none is False

    def test_on_i_roi_check_box_inactive(self):
        """Test that when the i_roi_checkbox is inactive, the ROI input fields are disabled."""
        screen = self.screen
        screen.on_i_roi_check_box(active=False)

        assert screen.form_mapping["roi.top_left_x"].allow_none is True
        assert screen.form_mapping["roi.top_left_y"].allow_none is True
        assert screen.form_mapping["roi.bottom_right_x"].allow_none is True
        assert screen.form_mapping["roi.bottom_right_y"].allow_none is True

        assert screen.form_mapping["roi.top_left_x"].text == ''
        assert screen.form_mapping["roi.top_left_y"].text == ''
        assert screen.form_mapping["roi.bottom_right_x"].text == ''
        assert screen.form_mapping["roi.bottom_right_y"].text == ''

    def test_on_sensor_filter(self):
        """Test the logic for the on_sensor_filter method."""
        screen = self.screen

        # Test with 'STC'
        screen.form_mapping["sensor_filter"].text = 'STC'
        screen.on_sensor_filter()
        assert not screen.form_mapping["sensor_filter_threshold"].allow_none

        # Test with 'Trail'
        screen.form_mapping["sensor_filter"].text = 'Trail'
        screen.on_sensor_filter()
        assert not screen.form_mapping["sensor_filter_threshold"].allow_none

        # Test with 'None'
        screen.form_mapping["sensor_filter"].text = 'None'
        screen.on_sensor_filter()
        assert screen.form_mapping["sensor_filter_threshold"].allow_none

    def test_load_item_to_form(self):
        """Test loading an item into the form."""
        screen = self.screen
        item = {'name': 'Test Work Config'}

        mock_work_config = MagicMock()
        mock_work_config.name = 'Test Work Config'
        mock_work_config.sensor_settings.name = 'Test Sensor'
        mock_work_config.delta_t = 20000
        mock_work_config.use_roi = True
        mock_work_config.bias_path = 'test.bias'
        mock_work_config.sensor_filter = 1
        mock_work_config.sensor_filter_threshold = 60000
        mock_work_config.seg_kernel_size = 7
        mock_work_config.seg_threshold = 60
        mock_work_config.seg_padding = 25
        mock_work_config.on_event_his_value = 10
        mock_work_config.off_event_his_value = 10
        mock_work_config.speed_correction_param = 1.2
        mock_work_config.colormap = 'HOT'
        mock_work_config.roi = '10x20-100x200'
        mock_work_config.alignment_images = []

        with patch('app.screen.PyModule.B_WorkConfigScreen.get_db') as mock_get_db:
            mock_db_session = MagicMock()
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_work_config
            mock_get_db.return_value.__enter__.return_value = mock_db_session

            screen.load_item_to_form(item)

            assert screen.form_mapping["b_setting_name"].text == 'Test Work Config'
            assert screen.form_mapping["prophesee_setting"].text == 'Test Sensor'
            assert screen.form_mapping["delta_t"].text == '20000'
            assert screen.form_mapping["i_roi_checkbox"].active is True
            assert screen.form_mapping["roi.top_left_x"].text == '10'
            assert screen.form_mapping["roi.top_left_y"].text == '20'
            assert screen.form_mapping["roi.bottom_right_x"].text == '100'
            assert screen.form_mapping["roi.bottom_right_y"].text == '200'

    def test_save_work_configs_create_new(self):
        """Test saving a new work configuration."""
        screen = self.screen
        screen.editing_item_name = None

        # Set up form data
        screen.form_mapping["b_setting_name"].text = "New Config"
        screen.form_mapping["prophesee_setting"].text = "Sensor1"
        screen.form_mapping["delta_t"].text = "15000"
        screen.form_mapping["i_roi_checkbox"].active = False
        screen.form_mapping["b_bias_path_select"].text = "bias1.bias"
        screen.form_mapping["sensor_filter"].selected_index = 0
        screen.form_mapping["sensor_filter_threshold"].text = ""
        screen.form_mapping["seg_kernel_size"].text = "5"
        screen.form_mapping["seg_threshold"].text = "50"
        screen.form_mapping["seg_padding"].text = "20"
        screen.form_mapping["on_event_his_value"].text = "5"
        screen.form_mapping["off_event_his_value"].text = "5"
        screen.form_mapping["histogram_add_pixel_params"].text = "1.0"
        screen.form_mapping["color_map"].text = "JET"

        with patch('app.screen.PyModule.B_WorkConfigScreen.get_db'), \
             patch('app.screen.PyModule.B_WorkConfigScreen.create_work_config') as mock_create, \
             patch.object(screen, '_get_id_by_name', return_value=1), \
             patch.object(screen, 'save_align_images', return_value=["", "", ""]), \
             patch.object(screen, 'is_name_duplicate', return_value=False), \
             patch.object(screen, 'reset_form') as mock_reset_form, \
             patch.object(screen, 'save_histogram_image', return_value="path/to/hist.png") as mock_save_hist, \
             patch('os.path.exists', return_value=True), \
             patch.object(screen, '_reset_editing_state') as mock_reset_editing_state:

            mock_create.return_value = MagicMock(id=1)
            screen.save_work_configs()

            mock_create.assert_called_once()
            mock_save_hist.assert_called_once_with(1)
            mock_reset_form.assert_called_once()
            mock_reset_editing_state.assert_called_once()
            screen.popup.create_adaptive_popup.assert_called_with(title="notification_popup", message="save_work_config_success")

    def test_save_work_configs_edit_existing(self):
        """Test saving an existing work configuration."""
        screen = self.screen
        screen.editing_item_name = "Existing Config"

        # Set up form data
        screen.form_mapping["b_setting_name"].text = "Existing Config"
        screen.form_mapping["prophesee_setting"].text = "Sensor1"
        screen.form_mapping["delta_t"].text = "15000"
        screen.form_mapping["i_roi_checkbox"].active = False
        screen.form_mapping["b_bias_path_select"].text = "bias1.bias"
        screen.form_mapping["sensor_filter"].selected_index = 0
        screen.form_mapping["sensor_filter_threshold"].text = ""
        screen.form_mapping["seg_kernel_size"].text = "5"
        screen.form_mapping["seg_threshold"].text = "50"
        screen.form_mapping["seg_padding"].text = "20"
        screen.form_mapping["on_event_his_value"].text = "5"
        screen.form_mapping["off_event_his_value"].text = "5"
        screen.form_mapping["histogram_add_pixel_params"].text = "1.0"
        screen.form_mapping["color_map"].text = "JET"

        with patch('app.screen.PyModule.B_WorkConfigScreen.get_db'), \
             patch('app.screen.PyModule.B_WorkConfigScreen.update_work_config_with_alignment_image') as mock_update, \
             patch.object(screen, '_get_id_by_name', return_value=1), \
             patch.object(screen, 'save_align_images', return_value=["", "", ""]), \
             patch.object(screen, 'is_name_duplicate', return_value=False), \
             patch.object(screen, 'reset_form') as mock_reset_form, \
             patch.object(screen, 'save_histogram_image', return_value="path/to/hist.png") as mock_save_hist, \
             patch('os.path.exists', return_value=True), \
             patch.object(screen, '_reset_editing_state') as mock_reset_editing_state:

            screen.save_work_configs()

            mock_update.assert_called_once()
            mock_save_hist.assert_called_once()
            mock_reset_form.assert_called_once()
            mock_reset_editing_state.assert_called_once()
            screen.popup.create_adaptive_popup.assert_called_with(title="notification_popup", message="save_work_config_success")

    def test_delete_item(self):
        """Test deleting an item."""
        screen = self.screen
        screen.editing_item_name = None
        item = {'name': 'Config to Delete'}

        with patch('app.screen.PyModule.B_WorkConfigScreen.get_db'), \
             patch('app.screen.PyModule.B_WorkConfigScreen.recursive_delete') as mock_delete, \
             patch.object(screen, '_get_id_by_name', return_value=1), \
             patch.object(screen, 'load_data_table') as mock_load_data_table:

            screen.delete_item(item)

            mock_delete.assert_called_once_with(ANY, 1)
            mock_load_data_table.assert_called_with(reset_page=False)

    def test_save_work_configs_duplicate_name(self):
        """Test that saving a new work configuration with a duplicate name fails."""
        screen = self.screen
        # Restore real methods that were mocked in the fixture
        screen.check_val_status = FormScreen.check_val_status.__get__(screen, WorkConfigScreen)
        screen.reset_val_status = FormScreen.reset_val_status.__get__(screen, WorkConfigScreen)

        screen.editing_item_name = None
        screen.form_mapping["b_setting_name"].text = "Existing Config"
        screen.form_mapping["b_setting_name"].error_message = "" # Ensure it's clean before test

        with patch.object(screen, 'is_name_duplicate', return_value=True), \
             patch('app.screen.PyModule.B_WorkConfigScreen.create_work_config') as mock_create, \
             patch('os.path.exists', return_value=True):

            screen.save_work_configs()

            assert screen.form_mapping["b_setting_name"].error_message == "save_work_config_duplicated_message"
            screen.popup.create_adaptive_popup.assert_called_with(
                title="error_popup",
                message="save_work_config_fail"
            )
            mock_create.assert_not_called()

    def test_save_work_configs_missing_required_field(self):
        """Test that saving fails when a required field is empty."""
        screen = self.screen
        # Restore real methods
        screen.validate = FormScreen.validate.__get__(screen, WorkConfigScreen)
        screen.check_val_status = FormScreen.check_val_status.__get__(screen, WorkConfigScreen)
        screen.reset_val_status = FormScreen.reset_val_status.__get__(screen, WorkConfigScreen)

        # Set up a mock with validation attributes and a validate_text method
        mock_input = MagicMock()
        mock_input.text = ""
        mock_input.allow_none = False # This is a required field
        mock_input.error_message = ""
        # Attach the real validation method to our mock instance
        real_validate_text = ValidatedInput.validate_text.__get__(mock_input)
        mock_input.validate_text = Mock(wraps=real_validate_text)

        # Replace the mocked input in the screen's form_mapping
        screen.form_mapping["b_setting_name"] = mock_input
        screen.val_list_configs = [mock_input] # Isolate validation to this one widget

        screen.editing_item_name = None

        with patch('app.screen.PyModule.B_WorkConfigScreen.create_work_config') as mock_create, \
             patch('os.path.exists', return_value=True):

            screen.save_work_configs()

            # The validate_text method should have been called and set an error
            mock_input.validate_text.assert_called_with("")
            assert mock_input.error_message == "nullable_error_message"

            # The popup should have been called due to check_val_status failing
            screen.popup.create_adaptive_popup.assert_called_with(
                title="error_popup",
                message="save_work_config_fail"
            )
            mock_create.assert_not_called()

    def test_save_work_configs_invalid_path(self):
        """Test that saving fails when a file path is invalid."""
        screen = self.screen
        # Restore real methods
        screen.check_val_status = FormScreen.check_val_status.__get__(screen, WorkConfigScreen)
        screen.reset_val_status = FormScreen.reset_val_status.__get__(screen, WorkConfigScreen)

        # Setup form data
        screen.form_mapping["b_setting_name"].text = "New Config"
        screen.form_mapping["prophesee_setting"].text = "Sensor1"
        screen.form_mapping["b_bias_path_select"].text = "non_existent.bias"
        screen.form_mapping["prophesee_setting"].error_message = ""
        screen.form_mapping["b_bias_path_select"].error_message = ""

        with patch('app.screen.PyModule.B_WorkConfigScreen.get_db'), \
             patch('os.path.exists', return_value=False), \
             patch('app.screen.PyModule.B_WorkConfigScreen.create_work_config') as mock_create:

            screen.save_work_configs()

            # validate_paths should have set an error message on the widget
            assert screen.form_mapping["b_bias_path_select"].error_message == 'file_not_found_error_message'

            screen.popup.create_adaptive_popup.assert_called_with(
                title="error_popup",
                message="save_work_config_fail"
            )
            mock_create.assert_not_called()

    def test_save_histogram_image_success(self):
        """Test saving histogram image successfully."""
        screen = self.screen

        # Mock paths
        # Use absolute paths to avoid issues with abspath/commonpath logic in the method
        base_dir = os.path.abspath("data")
        hist_temp_path = os.path.join(base_dir, "tmp", "histogram")
        hist_folder_path = os.path.join(base_dir, "histogram")
        source_file = os.path.join(hist_temp_path, "new.png")

        screen.temp_histogram = source_file

        with patch('app.screen.PyModule.B_WorkConfigScreen.HISTOGRAM_FOLDER_PATH', hist_folder_path), \
             patch('os.path.exists') as mock_exists, \
             patch('shutil.rmtree') as mock_rmtree, \
             patch('os.makedirs') as mock_makedirs, \
             patch('shutil.copy2') as mock_copy2:

            # Setup mocks
            target_dir = os.path.join(hist_folder_path, "123")

            def exists_side_effect(path):
                # Check if source file exists
                if os.path.normpath(path) == os.path.normpath(source_file):
                    return True
                # Check if target dir exists (to trigger cleanup)
                if os.path.normpath(path) == os.path.normpath(target_dir):
                    return True
                return False
            mock_exists.side_effect = exists_side_effect

            # Execute
            result = screen.save_histogram_image(123)

            # Verify
            expected_dest = os.path.join(target_dir, "new.png")

            assert result == expected_dest

            # Verify cleanup of target dir
            mock_rmtree.assert_called_once_with(target_dir)

            # Verify creation of target dir
            mock_makedirs.assert_called_once_with(target_dir, exist_ok=True)

            # Verify copy
            mock_copy2.assert_called_once_with(source_file, expected_dest)

    def test_save_histogram_image_no_temp_file(self):
        """Test saving histogram image when no temp file exists."""
        screen = self.screen
        screen.temp_histogram = None

        # Mock paths
        base_dir = os.path.abspath("data")
        hist_folder_path = os.path.join(base_dir, "histogram")

        with patch('app.screen.PyModule.B_WorkConfigScreen.HISTOGRAM_FOLDER_PATH', hist_folder_path), \
             patch('os.path.exists', return_value=True), \
             patch('shutil.rmtree') as mock_rmtree:

            result = screen.save_histogram_image(123)
            assert result is None

            # Verify cleanup of target dir was attempted
            target_dir = os.path.join(hist_folder_path, "123")
            mock_rmtree.assert_called_with(target_dir)

    def test_load_item_to_form_with_histogram(self):
        """Test loading item with histogram path updates UI and alignment widgets."""
        screen = self.screen

        item = {'name': 'Test Config'}

        mock_work_config = MagicMock()
        mock_work_config.name = 'Test Config'
        mock_work_config.sensor_settings.name = 'Sensor1'
        mock_work_config.delta_t = 20000
        mock_work_config.use_roi = True
        mock_work_config.bias_path = 'test.bias'
        mock_work_config.sensor_filter = 1
        mock_work_config.sensor_filter_threshold = 60000
        mock_work_config.seg_kernel_size = 7
        mock_work_config.seg_threshold = 60
        mock_work_config.seg_padding = 25
        mock_work_config.on_event_his_value = 10
        mock_work_config.off_event_his_value = 10
        mock_work_config.speed_correction_param = 1.2
        mock_work_config.colormap = 'HOT'
        mock_work_config.roi = '10x20-100x200'
        mock_work_config.alignment_images = []

        # Histogram specific
        hist_path = os.path.normpath("data/histogram/123/hist.png")
        mock_work_config.histogram_path = hist_path

        with patch('app.screen.PyModule.B_WorkConfigScreen.get_db') as mock_get_db, \
             patch('os.path.exists', return_value=True), \
             patch.object(screen, 'apply_color_map', return_value="data/tmp/color_map.png") as mock_apply_map, \
             patch('kivy.clock.Clock.schedule_once', side_effect=lambda func, *args: func(0)):

            mock_db_session = MagicMock()
            mock_db_session.query.return_value.filter.return_value.first.return_value = mock_work_config
            mock_get_db.return_value.__enter__.return_value = mock_db_session

            screen.load_item_to_form(item)

            # Verify color map applied
            mock_apply_map.assert_called_with(hist_path)
            assert screen.ids.show_confirm_hist.source == "data/tmp/color_map.png"

            # Verify alignment widgets updated
            expected_hist_dir = os.path.dirname(hist_path)
            for i in range(1, 4):
                assert screen.form_mapping[f"alignment_{i}"].hist_dir == expected_hist_dir

    def test_run_confirmation_resets_alignment_hist_dir(self):
        """Test that running confirmation resets alignment widgets to use temp histogram dir."""
        screen = self.screen

        # Set to something else first
        for i in range(1, 4):
            screen.form_mapping[f"alignment_{i}"].hist_dir = "some/other/path"

        hist_temp_path = os.path.normpath("data/tmp/histogram")

        with patch('app.screen.PyModule.B_WorkConfigScreen.HISTOGRAM_TEMP_PATH', hist_temp_path), \
             patch('os.listdir', return_value=[]), \
             patch.object(screen, '_run_cli', return_value=True), \
             patch.object(screen, 'async_update_temp_histogram'):

            screen.run_confirmation()

            # Verify reset
            for i in range(1, 4):
                assert screen.form_mapping[f"alignment_{i}"].hist_dir == hist_temp_path
