"""
Unit tests for C3 TrainingResultsScreen — focused on features changed in current branch vs develop_ui.

Covers:
    - ValidationItem._open_preview_popup direct opening + path resolution to preview_modal
    - start_validation clears preview_modal directory
"""
# pylint: disable=wildcard-import, undefined-variable, protected-access, unused-variable, too-many-lines, redefined-outer-name

import os
import hashlib
import tempfile
from unittest.mock import patch, Mock, MagicMock, ANY, call
import pytest
from app.screen.PyModule.C_TrainingResultsScreen import TrainingResultsScreen, ValidationItem


# ── Helpers ──────────────────────────────────────────────────────────────────

class DotDict(dict):
    """A dictionary that supports dot notation access."""
    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            # For Kivy-like behavior where missing ids might be accessed
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")
    def __setattr__(self, name, value):
        self[name] = value


class MockKivyApp:
    """Mock for Kivy App."""
    def get_running_app(self):
        app = Mock()
        app.lang.get.return_value = "mock_translation"
        return app

class MockPopup:
    """Mock for MyPopup."""
    def __init__(self):
        self.create_loading_popup = MagicMock(return_value=Mock(open=Mock(), dismiss=Mock()))
        self.create_adaptive_popup = MagicMock(return_value=Mock(open=Mock(), dismiss=Mock(), bind=Mock()))
        self.create_preview_popup = MagicMock(return_value=MagicMock(open=Mock()))


def _make_form_widget(text="", error_message=""):
    """Create a mock form widget with text, error_message and validate_text."""
    widget = MagicMock()
    widget.text = text
    widget.error_message = error_message
    widget.validate_text = Mock()
    return widget


@pytest.fixture
def screen():
    """Fixture: TrainingResultsScreen with mocked Kivy dependencies."""
    with patch('kivy.app.App.get_running_app', new_callable=MockKivyApp), \
         patch('app.screen.PyModule.C_TrainingResultsScreen.MyPopup', new_callable=MockPopup), \
         patch('app.screen.PyModule.C_TrainingResultsScreen.ValidationAlbum') as mocked_album, \
         patch('app.screen.PyModule.utils.delete_images_in_folders.delete_images_in_folders'), \
         patch.object(TrainingResultsScreen, '__init__', return_value=None):

        s = TrainingResultsScreen()
        s.app = MockKivyApp().get_running_app()
        s.popup = MockPopup()
        s.display_to_model_dataset = {}
        s._heatmap_generated = False
        s._heatmap_file_hashes = {}
        s._received_generate_data = False
        s.validated_parameters = None
        s.current_export_dir = None
        s.loading_popup = None
        s.preview_popup = None
        s._preview_params_cache = {}
        s._last_validation_params = {}
        s.validated_parameters = None
        s.current_export_dir = None
        s._run_cli = Mock(return_value=True)

        # Set up ids as a DotDict to support both dot access and dict access
        mock_settings = DotDict()
        s.ids = DotDict({
            'c3_dataset_select': MagicMock(text="", values=[], error_message=""),
            'c3_settings_section': mock_settings,
            'image_album_container': MagicMock(add_widget=Mock()),
            'folder_displaying': MagicMock(directory_path=""),
            'scroll_screen_C3_training_results': MagicMock(),
            'window_explore_button': MagicMock(),
            'create_heatmap_error': MagicMock(error_message=""),
        })

        # form_mapping (mirrors on_kv_post)
        s.form_mapping = {
            "c3_dataset_select": s.ids['c3_dataset_select'],
            "c3_settings_section": mock_settings,
            "c3_blur_input": _make_form_widget(text="1"),
            "c3_min_area_input": _make_form_widget(text="50"),
            "c3_threshold_slider": _make_form_widget(text="128"),
            "c3_event_intensity": _make_form_widget(text="10000000"),
            "folder_displaying": s.ids['folder_displaying'],
            "create_heatmap_error": _make_form_widget(),
        }
        
        # Set up nested ids for c3_settings_section (dot access)
        mock_settings.ids = DotDict({
            'c3_blur_input': DotDict({'ids': DotDict({'input_box': DotDict({'text': '1'})})}),
            'c3_min_area_input': DotDict({'ids': DotDict({'input_box': DotDict({'text': '50'})})}),
            'c3_threshold_slider': DotDict({'ids': DotDict({'input_box': DotDict({'text': '128'})})}),
            'c3_event_intensity': DotDict({'ids': DotDict({'input_box': DotDict({'text': '10000000'})})}),
        })

        s._post_init(0)
        s.image_album = mocked_album.return_value
        yield s


# ═══════════════════════════════════════════════════════════════════
#  1. PREVIEW POPUP — Deferred creation + D026/D027 race condition
# ═══════════════════════════════════════════════════════════════════

class TestPreviewPopupDirectOpening:
    """Tests for direct popup opening (replaces deferred logic)."""

    def test_d026_loads_image_into_existing_popup(self, screen):
        """D026 with existing preview_popup should load new image."""
        screen.preview_popup = MagicMock()
        screen.preview_popup.c3_section = MagicMock()
        screen.preview_popup._old_result_label = MagicMock()

        screen.on_pipe({'status_code': 'D026', 'data': '/path/to/new.png'})

        screen.preview_popup._load_image_to_preview_popup.assert_called_once_with(
            image_path='/path/to/new.png'
        )

    def test_d027_dismisses_loading_popup(self, screen):
        """D027 should dismiss the loading popup (used for interactive preview updates)."""
        mock_popup = MagicMock()
        mock_popup.process = 'preview'
        screen.loading_popup = mock_popup

        screen.on_pipe({'status_code': 'D027'})

        mock_popup.dismiss.assert_called_once()
        assert screen.loading_popup is None

    def test_d026_updates_params_on_existing_popup(self, screen):
        """D026 with existing popup should update params via _old_result_label."""
        mock_c3 = MagicMock()
        mock_c3.ids.c3_blur_input.ids.input_box.text = '5'
        mock_c3.ids.c3_min_area_input.ids.input_box.text = '100'
        mock_c3.ids.c3_threshold_slider.ids.input_box.text = '200'
        mock_c3.ids.c3_event_intensity.ids.input_box.text = '9999'

        mock_label = MagicMock()
        screen.preview_popup = MagicMock()
        screen.preview_popup.c3_section = mock_c3
        screen.preview_popup._old_result_label = mock_label

        screen.on_pipe({'status_code': 'D026', 'data': '/img.png'})

        # Should update format_args and _validated_parameters
        assert mock_label.format_args is not None
        assert screen.preview_popup._validated_parameters is not None


class TestPreviewParamsCache:
    """Tests for the parameter-based caching mechanism."""

    def test_start_validation_clears_cache(self, screen):
        """start_validation should reset the cache."""
        screen._preview_params_cache = {"some_img": {"blur": "3"}}
        screen._validate_data_file = Mock(return_value=True)
        screen._heatmap_generated = True  # Required to enter the block
        screen._build_gen_validation_command = Mock(return_value=['mock', 'cmd'])
        
        # Mocking for start_validation dependencies
        screen._validate_inputs = Mock(return_value=({}, {'model_name': 'M', 'dataset_name': 'D'}, None, True))
        screen._handle_validation_errors = Mock(return_value=False)
        screen._get_validation_data = Mock(return_value={'work_config_id': '1', 'model_name': 'M', 'dataset_id': 1})
        screen._get_histogram_dir_from_data_txt = Mock(return_value="/hist_dir")
        screen._verify_heatmap_integrity = Mock(return_value=True)
        
        # Mock folder_displaying path resolution
        screen.ids.folder_displaying.directory_path = os.path.normpath("D:/project/datasets/1/dataset1/model1/evaluation")
        
        with patch('app.screen.PyModule.C_TrainingResultsScreen.os.path.exists', return_value=True), \
             patch('app.screen.PyModule.C_TrainingResultsScreen.os.path.isdir', return_value=True), \
             patch('app.screen.PyModule.C_TrainingResultsScreen.delete_images_in_folders'), \
             patch('app.screen.PyModule.C_TrainingResultsScreen.PropagatingThread'): # avoid starting real thread
            screen.start_validation()
            
        assert screen._preview_params_cache == {}

    def test_on_preview_uses_cache_and_skips_cli(self, screen):
        """on_preview should skip CLI and reload locally if params match cache."""
        item = ValidationItem()
        item.screen = screen
        item.source = os.path.normpath("D:/data/eval/thumbnail/img.png")
        screen.current_export_dir = "D:/data/export"
        screen._run_cli.reset_mock()
        
        # Mock on_preview dependencies
        screen._validate_parameters = Mock(return_value=({}, {}, None, True))
        screen._handle_validation_errors = Mock(return_value=False)
        item._validate_file_paths = Mock(return_value={"valid": True, "histogram_path": "/h", "heatmap_path": "/n"})
        
        # Match fixture's default values for cache hit
        params = {
            'blur': '1', 'min_area': '50', 'threshold': '128',
            'event_intensity': '10000000', 'show_bbox': '1', 'show_info': '1', 'overlay': '0.50'
        }
        screen._preview_params_cache['img'] = params.copy()
        screen._last_validation_params = params.copy()
        screen.preview_popup = MagicMock()
        
        with patch('app.screen.PyModule.utils.delete_images_in_folders.delete_images_in_folders'), \
             patch('app.screen.PyModule.C_TrainingResultsScreen.os.path.exists', return_value=True):
            item._open_preview_popup()
        
        screen._run_cli.assert_not_called()
        
        # Verify the path is inside evaluation/preview_modal (sibling to thumbnail)
        expected_path = os.path.normpath("D:/data/eval/preview_modal/img.png")
        
        with patch('kivy.clock.Clock.schedule_once') as mock_schedule:
            on_preview = screen.popup.create_preview_popup.call_args.kwargs['on_preview']
            on_preview(params)
            
            # Manually extract the lambda from Clock.schedule_once
            args, _ = mock_schedule.call_args
            scheduled_func = args[0]
            
            # Call the lambda
            scheduled_func(0)

        screen.preview_popup._load_image_to_preview_popup.assert_called_once_with(image_path=expected_path)

    def test_on_preview_cache_miss_runs_cli(self, screen):
        """on_preview should run CLI and update cache if params differ."""
        item = ValidationItem()
        item.screen = screen
        item.source = os.path.normpath("D:/data/eval/thumbnail/img.png")
        screen.current_export_dir = "D:/data/export"
        screen._run_cli.reset_mock()
        
        # Mock on_preview dependencies
        screen._validate_parameters = Mock(return_value=({}, {}, None, True))
        screen._handle_validation_errors = Mock(return_value=False)
        item._validate_file_paths = Mock(return_value={"valid": True, "histogram_path": "/h", "heatmap_path": "/n"})
        
        # Setup cache with DIFFERENT params (blur: 99)
        screen._preview_params_cache['img'] = {'blur': '99'}
        screen._last_validation_params = {'blur': '100'} # Example baseline to ensure it doesn't crash on copy
        screen.preview_popup = MagicMock()
        
        # Mock command builder and threaded runner
        item._build_command_preview_heatmap = Mock(return_value=['mock', 'cmd'])
        screen._run_task_in_thread = Mock(side_effect=lambda task_fn, **kwargs: task_fn())
        
        # Set base values in screen before opening popup
        screen.ids.c3_settings_section.ids.c3_event_intensity.ids.input_box.text = '1000'
        
        with patch('app.screen.PyModule.utils.delete_images_in_folders.delete_images_in_folders'), \
             patch('app.screen.PyModule.C_TrainingResultsScreen.os.path.exists', return_value=True):
            item._open_preview_popup() # This records '1000' into cache
            
        on_preview = screen.popup.create_preview_popup.call_args.kwargs['on_preview']
        
        # Now call with a DIFFERENT value to trigger a miss
        new_params = {
            'blur': '1', 'min_area': '50', 'threshold': '128',
            'event_intensity': '9999', 'show_bbox': '1', 'show_info': '1', 'overlay': '0.50'
        }
        on_preview(new_params)
        
        assert screen._run_cli.called
        # Verify CLI was launched with the correct output directory (evaluation/preview_modal)
        call_args = item._build_command_preview_heatmap.call_args
        assert call_args.kwargs['export_heatmap_dir'] == os.path.normpath("D:/data/eval/preview_modal")
        
        assert screen._preview_params_cache['img']['event_intensity'] == '9999'


# ═══════════════════════════════════════════════════════════════════
#  2. HEATMAP GENERATION — create_heatmap + D032/D033 pipe handling
# ═══════════════════════════════════════════════════════════════════

class TestCreateHeatmap:
    """Tests for heatmap generation flow."""

    def test_create_heatmap_invalid_inputs_returns_early(self, screen):
        """create_heatmap should return early when inputs are invalid."""
        screen._validate_inputs = Mock(return_value=({}, {}, None, False))
        screen._build_npy_command = Mock()

        screen.create_heatmap()

        screen._build_npy_command.assert_not_called()

    def test_create_heatmap_calls_validate_in_npy_mode(self, screen):
        """create_heatmap should call _validate_inputs with mode='npy'."""
        screen._validate_inputs = Mock(return_value=({}, {}, None, False))

        screen.create_heatmap()

        screen._validate_inputs.assert_called_once_with(mode='npy')

    def test_create_heatmap_errors_handled_without_popup_navigate(self, screen):
        """create_heatmap should call _handle_validation_errors with mode='npy'."""
        screen._validate_inputs = Mock(return_value=(
            {'c3_dataset_select': 'error'}, {}, 'c3_dataset_select', True
        ))
        screen._handle_validation_errors = Mock(return_value=True)

        screen.create_heatmap()

        screen._handle_validation_errors.assert_called_once_with(
            {'c3_dataset_select': 'error'}, 'c3_dataset_select', mode='npy'
        )

    def test_create_heatmap_no_model_returns_early(self, screen):
        """create_heatmap should return early when model_name is None."""
        screen._validate_inputs = Mock(return_value=(
            {}, {'model_name': None, 'dataset_name': 'D'}, None, True
        ))
        screen._handle_validation_errors = Mock(return_value=False)
        screen._get_validation_data = Mock()

        screen.create_heatmap()

        screen._get_validation_data.assert_not_called()

    def test_create_heatmap_clears_errors_first(self, screen):
        """create_heatmap should clear error messages before validation."""
        screen.clear_error_messages = Mock()
        screen._validate_inputs = Mock(return_value=({}, {}, None, False))

        screen.create_heatmap()

        screen.clear_error_messages.assert_called_once()


class TestOnPipeD032HeatmapHash:
    """Tests for D032 pipe handler — heatmap file hash storage."""

    def test_d032_stores_hash_for_valid_file(self, screen):
        """D032 should compute and store MD5 hash of the .npy file."""
        with tempfile.NamedTemporaryFile(suffix='.npy', delete=False) as f:
            f.write(b'test npy data')
            temp_path = f.name

        try:
            screen.on_pipe({'status_code': 'D032', 'data': temp_path})

            assert screen._heatmap_generated is True
            assert temp_path in screen._heatmap_file_hashes
            expected_hash = hashlib.md5(b'test npy data').hexdigest()
            assert screen._heatmap_file_hashes[temp_path] == expected_hash
        finally:
            os.unlink(temp_path)

    def test_d032_nonexistent_file_sets_flag_but_no_hash(self, screen):
        """D032 with nonexistent file should still set _heatmap_generated."""
        screen.on_pipe({'status_code': 'D032', 'data': '/nonexistent/file.npy'})

        assert screen._heatmap_generated is True
        assert '/nonexistent/file.npy' not in screen._heatmap_file_hashes

    def test_d032_empty_data_ignored(self, screen):
        """D032 with empty data should not set _heatmap_generated."""
        screen.on_pipe({'status_code': 'D032', 'data': ''})

        assert screen._heatmap_generated is False

    def test_d032_multiple_files_accumulate_hashes(self, screen):
        """Multiple D032 messages should accumulate hashes."""
        files = []
        try:
            for i in range(3):
                f = tempfile.NamedTemporaryFile(suffix='.npy', delete=False)
                f.write(f'data_{i}'.encode())
                f.close()
                files.append(f.name)
                screen.on_pipe({'status_code': 'D032', 'data': f.name})

            assert len(screen._heatmap_file_hashes) == 3
            assert all(p in screen._heatmap_file_hashes for p in files)
        finally:
            for f in files:
                os.unlink(f)


class TestOnPipeD033:
    """Tests for D033 pipe handler — heatmap generation complete."""

    def test_d033_dismisses_loading_popup(self, screen):
        """D033 should dismiss loading popup."""
        mock_popup = MagicMock()
        mock_popup.process = 'heatmap'
        screen.loading_popup = mock_popup

        screen.on_pipe({'status_code': 'D033'})

        mock_popup.dismiss.assert_called_once()
        assert screen.loading_popup is None

    def test_d033_no_popup_no_crash(self, screen):
        """D033 with no loading popup should not crash."""
        screen.loading_popup = None
        screen.on_pipe({'status_code': 'D033'})
        assert screen.loading_popup is None


# ═══════════════════════════════════════════════════════════════════
#  3. HEATMAP INTEGRITY — _hash_file + _verify_heatmap_integrity
# ═══════════════════════════════════════════════════════════════════

class TestHeatmapIntegrity:
    """Tests for heatmap file integrity checking."""

    def test_hash_file_correct_md5(self):
        """_hash_file should produce correct MD5 hash."""
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b'test content')
            path = f.name
        try:
            assert TrainingResultsScreen._hash_file(path) == hashlib.md5(b'test content').hexdigest()
        finally:
            os.unlink(path)

    def test_hash_file_large_file_chunked(self):
        """_hash_file should handle files larger than chunk_size."""
        data = b'x' * 20000
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(data)
            path = f.name
        try:
            assert TrainingResultsScreen._hash_file(path) == hashlib.md5(data).hexdigest()
        finally:
            os.unlink(path)

    def test_hash_file_nonexistent_returns_none(self):
        assert TrainingResultsScreen._hash_file('/nonexistent.npy') is None

    def test_verify_empty_hashes_returns_false(self, screen):
        """No stored hashes → integrity check fails."""
        screen._heatmap_file_hashes = {}
        assert screen._verify_heatmap_integrity() is False

    def test_verify_all_intact_returns_true(self, screen):
        """All files existing with matching hashes → passes."""
        with tempfile.NamedTemporaryFile(suffix='.npy', delete=False) as f:
            f.write(b'data')
            path = f.name
        try:
            screen._heatmap_file_hashes = {path: TrainingResultsScreen._hash_file(path)}
            assert screen._verify_heatmap_integrity() is True
        finally:
            os.unlink(path)

    def test_verify_deleted_file_returns_false(self, screen):
        """Deleted file → integrity check fails."""
        screen._heatmap_file_hashes = {'/gone/file.npy': 'abc123'}
        assert screen._verify_heatmap_integrity() is False

    def test_verify_modified_file_returns_false(self, screen):
        """Modified file (different hash) → integrity check fails."""
        with tempfile.NamedTemporaryFile(suffix='.npy', delete=False) as f:
            f.write(b'original')
            path = f.name
        try:
            screen._heatmap_file_hashes = {path: TrainingResultsScreen._hash_file(path)}
            with open(path, 'wb') as f:
                f.write(b'tampered')
            assert screen._verify_heatmap_integrity() is False
        finally:
            os.unlink(path)

    def test_verify_one_missing_among_many_fails(self, screen):
        """If any file in the hash dict is missing, integrity fails."""
        with tempfile.NamedTemporaryFile(suffix='.npy', delete=False) as f:
            f.write(b'ok')
            path = f.name
        try:
            screen._heatmap_file_hashes = {
                path: TrainingResultsScreen._hash_file(path),
                '/missing.npy': 'deadbeef'
            }
            assert screen._verify_heatmap_integrity() is False
        finally:
            os.unlink(path)


# ═══════════════════════════════════════════════════════════════════
#  4. VALIDATION FLOW — start_validation with heatmap prerequisite
# ═══════════════════════════════════════════════════════════════════

class TestStartValidation:
    """Tests for start_validation with the new heatmap prerequisite check."""

    def _setup_mocks(self, screen):
        screen.disable_click = Mock()
        screen.enable_click = Mock()
        screen.set_left_mouse_disabled = Mock()

    def test_no_heatmap_shows_error(self, screen):
        """Validation without heatmap should show 'heatmap_not_created' error."""
        self._setup_mocks(screen)
        screen._heatmap_generated = False
        screen._validate_inputs = Mock(return_value=({}, {}, None, False))

        screen.start_validation()

        assert screen.form_mapping['create_heatmap_error'].error_message == 'heatmap_not_created'

    def test_integrity_failed_shows_error(self, screen):
        """Heatmap exists but files tampered → show error."""
        self._setup_mocks(screen)
        screen._heatmap_generated = True
        screen._verify_heatmap_integrity = Mock(return_value=False)
        screen._validate_inputs = Mock(return_value=({}, {}, None, True))

        screen.start_validation()

        assert screen.form_mapping['create_heatmap_error'].error_message == 'heatmap_not_created'

    def test_both_heatmap_and_input_errors_shown_simultaneously(self, screen):
        """Both heatmap error AND input validation error should appear at once."""
        self._setup_mocks(screen)
        screen._heatmap_generated = False
        # _validate_inputs returns invalid
        screen._validate_inputs = Mock(return_value=({}, {}, None, False))

        screen.start_validation()

        # Heatmap error set
        assert screen.form_mapping['create_heatmap_error'].error_message == 'heatmap_not_created'
        # Also validates inputs (dataset selection)
        screen._validate_inputs.assert_called_once_with(mode='validation')

    def test_valid_heatmap_invalid_inputs_returns_early(self, screen):
        """Valid heatmap but invalid inputs → return early, no CLI execution."""
        self._setup_mocks(screen)
        screen._heatmap_generated = True
        screen._verify_heatmap_integrity = Mock(return_value=True)
        screen._validate_inputs = Mock(return_value=({}, {}, None, False))
        screen._get_validation_data = Mock()

        screen.start_validation()

        screen._get_validation_data.assert_not_called()

    def test_start_validation_calls_validate_in_validation_mode(self, screen):
        """start_validation should call _validate_inputs with mode='validation'."""
        self._setup_mocks(screen)
        screen._heatmap_generated = True
        screen._verify_heatmap_integrity = Mock(return_value=True)
        screen._validate_inputs = Mock(return_value=({}, {}, None, False))

        screen.start_validation()

        screen._validate_inputs.assert_called_once_with(mode='validation')

    def test_start_validation_captures_validated_parameters(self, screen):
        """On successful prerequisite checks, validated_parameters should be captured."""
        self._setup_mocks(screen)
        screen._heatmap_generated = True
        screen._verify_heatmap_integrity = Mock(return_value=True)
        screen._validate_inputs = Mock(return_value=(
            {}, {'model_name': None, 'dataset_name': None}, None, True
        ))
        screen._handle_validation_errors = Mock(return_value=False)

        screen.start_validation()

        assert screen.validated_parameters == {
            'blur': '1',
            'min_area': '50',
            'threshold': '128',
            'event_intensity': '10000000'
        }

    @patch('app.screen.PyModule.C_TrainingResultsScreen.delete_images_in_folders')
    def test_start_validation_clears_preview_modal_dir(self, mock_delete, screen):
        """start_validation should clear the preview_modal directory."""
        self._setup_mocks(screen)
        screen._heatmap_generated = True
        screen._verify_heatmap_integrity = Mock(return_value=True)
        screen._validate_inputs = Mock(return_value=(
            {}, {'model_name': 'M1', 'dataset_name': 'D1'}, None, True
        ))
        screen._handle_validation_errors = Mock(return_value=False)
        screen._get_validation_data = Mock(return_value={
            'work_config_id': 1, 'model_name': 'M1', 'dataset_id': 1, 'dataset_name': 'D1',
            'learn_method': '0', 'm1_input_size': 224, 'm1_patch_size': 224,
            'm1_weight_path': 'w1', 'm1_engine_path': 'e1',
            'm2_input_size': 224, 'm2_patch_size': 224,
            'm2_weight_path': 'w2', 'm2_engine_path': 'e2',
            'heat_kernel_size': '1', 'heat_min_area': '50',
            'heat_threshold': '128', 'heat_min_intensity': '10000000'
        })
        screen._validate_data_file = Mock(return_value=True)
        screen._get_histogram_dir_from_data_txt = Mock(return_value='/hist')
        screen._execute_gen_validation_command = Mock(return_value=(True, ""))

        with patch('os.path.join', side_effect=os.path.join):
            screen.start_validation()

        # Check if delete_images_in_folders was called with preview_modal_dir
        args, kwargs = mock_delete.call_args
        folder_paths = kwargs.get('folder_paths', args[0] if args else [])
        assert any('preview_modal' in path for path in folder_paths)


# ═══════════════════════════════════════════════════════════════════
#  5. _validate_inputs MODE PARAMETER
# ═══════════════════════════════════════════════════════════════════

class TestValidateInputsModes:
    """Tests for _validate_inputs with new mode parameter."""

    def test_npy_mode_skips_heatmap_param_validation(self, screen):
        """npy mode should NOT validate heatmap params (blur, threshold, etc)."""
        screen.display_to_model_dataset = {'M (D)': ('M', 'D')}
        screen.form_mapping['c3_dataset_select'].text = "M (D)"
        screen.form_mapping['c3_dataset_select'].error_message = ""
        screen.form_mapping['c3_blur_input'].error_message = "some_error"

        _, _, _, valid = screen._validate_inputs(mode='npy')
        assert valid is True  # heatmap param errors ignored

    def test_validation_mode_skips_weight_path_check(self, screen):
        """validation mode should NOT check weight paths."""
        screen.display_to_model_dataset = {'M (D)': ('M', 'D')}
        screen.form_mapping['c3_dataset_select'].text = "M (D)"
        screen.form_mapping['c3_dataset_select'].error_message = ""

        errors, _, _, _ = screen._validate_inputs(mode='validation')
        assert 'file_not_found_error_message' not in errors.values()

    def test_none_mode_validates_everything(self, screen):
        """None mode should validate both weight paths and heatmap params."""
        screen.display_to_model_dataset = {'M (D)': ('M', 'D')}
        screen.form_mapping['c3_dataset_select'].text = "M (D)"
        screen.form_mapping['c3_dataset_select'].error_message = ""
        screen.form_mapping['c3_blur_input'].error_message = "invalid"

        _, _, _, valid = screen._validate_inputs(mode=None)
        assert valid is False


# ═══════════════════════════════════════════════════════════════════
#  6. _handle_validation_errors MODE PARAMETER
# ═══════════════════════════════════════════════════════════════════

class TestHandleValidationErrorsModes:
    """Tests for _handle_validation_errors with mode parameter."""

    def test_no_errors_returns_false(self, screen):
        assert screen._handle_validation_errors({}, None) is False

    @patch('kivy.clock.Clock.schedule_once')
    def test_validation_mode_schedules_popup(self, mock_schedule, screen):
        """mode='validation' should schedule popup navigate."""
        errors = {'c3_dataset_select': 'no_select_error_message'}
        result = screen._handle_validation_errors(errors, 'c3_dataset_select', mode='validation')
        assert result is True
        mock_schedule.assert_called_once()

    def test_npy_mode_does_not_schedule_popup(self, screen):
        """mode='npy' should NOT schedule popup navigate."""
        errors = {'c3_dataset_select': 'no_select_error_message'}
        result = screen._handle_validation_errors(errors, 'c3_dataset_select', mode='npy')
        assert result is True


# ═══════════════════════════════════════════════════════════════════
#  7. COMMAND BUILDERS — _build_npy_command + _build_gen_validation_command
# ═══════════════════════════════════════════════════════════════════

class TestBuildCommands:
    """Tests for the split command builders (new in this branch)."""

    def test_build_npy_command_basic(self, screen):
        """_build_npy_command should include learn_method, data_root, save_dir, backbone."""
        data = {
            'learn_method': '0',
            'm1_input_size': 224, 'm1_patch_size': 224,
            'm1_weight_path': '/w1.pth', 'm1_engine_path': '/e1.engine',
        }
        cmd = screen._build_npy_command(data, '/data.txt', '/save')

        assert '--learn_method' in cmd and '0' in cmd
        assert '--data_root' in cmd and '/data.txt' in cmd
        assert '--save_dir' in cmd and '/save' in cmd
        assert '--backbone' in cmd

    def test_build_npy_command_no_heatmap_params(self, screen):
        """_build_npy_command should NOT include heat_* params (split to gen_validation)."""
        data = {
            'learn_method': '0',
            'm1_input_size': 224, 'm1_patch_size': 224,
            'm1_weight_path': '/w1.pth', 'm1_engine_path': '/e1.engine',
        }
        cmd = screen._build_npy_command(data, '/data.txt', '/save')

        assert '--heat_kernel_size' not in cmd
        assert '--heat_threshold' not in cmd
        assert '--thumbnail_flag' not in cmd

    def test_build_gen_validation_command_includes_heat_params(self, screen):
        """_build_gen_validation_command should include heat_* params + thumbnail_flag + save_dir_preview_image."""
        data = {
            'model_name': 'M',
            'heat_kernel_size': '15',
            'heat_min_area': '100',
            'heat_threshold': '128',
            'heat_min_intensity': '5000',
        }
        cmd = screen._build_gen_validation_command(data, '/hist', '/npy', '/export', save_dir_preview_image='/preview')

        assert '--data_histogram_dir' in cmd and '/hist' in cmd
        assert '--npy_dir' in cmd and '/npy' in cmd
        assert '--save_dir' in cmd and '/export' in cmd
        assert '--heat_kernel_size' in cmd and '15' in cmd
        assert '--heat_threshold' in cmd and '128' in cmd
        assert '--thumbnail_flag' in cmd and '1' in cmd
        assert '--save_dir_preview_image' in cmd and '/preview' in cmd


# ═══════════════════════════════════════════════════════════════════
#  8. _get_histogram_dir_from_data_txt (NEW helper)
# ═══════════════════════════════════════════════════════════════════

class TestGetHistogramDir:
    """Tests for _get_histogram_dir_from_data_txt."""

    def test_valid_data_txt(self, screen):
        """Should extract parent dir of first valid image path."""
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False,
                                          dir=tempfile.gettempdir()) as img:
            img_path = img.name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False,
                                         encoding='utf-8') as f:
            f.write(f"{img_path} | 0\n")
            txt = f.name
        try:
            assert screen._get_histogram_dir_from_data_txt(txt) == os.path.dirname(img_path)
        finally:
            os.unlink(txt)
            os.unlink(img_path)

    def test_nonexistent_file_returns_none(self, screen):
        assert screen._get_histogram_dir_from_data_txt('/nonexistent/data.txt') is None

    def test_empty_file_returns_none(self, screen):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            txt = f.name
        try:
            assert screen._get_histogram_dir_from_data_txt(txt) is None
        finally:
            os.unlink(txt)

    def test_all_invalid_paths_returns_none(self, screen):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False,
                                         encoding='utf-8') as f:
            f.write("/nonexistent/img.png | 0\n")
            txt = f.name
        try:
            assert screen._get_histogram_dir_from_data_txt(txt) is None
        finally:
            os.unlink(txt)


# ═══════════════════════════════════════════════════════════════════
#  9. on_dataset_selection_changed — heatmap state reset
# ═══════════════════════════════════════════════════════════════════

class TestDatasetSelectionChangedHeatmapReset:
    """Tests for heatmap state reset when dataset changes."""

    def test_resets_heatmap_generated(self, screen):
        screen._heatmap_generated = True
        screen.form_mapping['c3_dataset_select'].text = ""
        screen.on_dataset_selection_changed()
        assert screen._heatmap_generated is False

    def test_clears_heatmap_file_hashes(self, screen):
        screen._heatmap_file_hashes = {'/a.npy': 'hash1', '/b.npy': 'hash2'}
        screen.form_mapping['c3_dataset_select'].text = ""
        screen.on_dataset_selection_changed()
        assert screen._heatmap_file_hashes == {}

    def test_empty_selection_clears_export_dir(self, screen):
        screen.current_export_dir = "/old/path"
        screen.form_mapping['c3_dataset_select'].text = ""
        screen.on_dataset_selection_changed()
        assert screen.current_export_dir is None


# ═══════════════════════════════════════════════════════════════════
#  10. _validate_data_file (used by both create_heatmap & start_validation)
# ═══════════════════════════════════════════════════════════════════

class TestValidateDataFile:
    """Tests for data.txt validation."""

    def test_nonexistent_returns_false(self, screen):
        screen._TrainingResultsScreen__show_popup = Mock()
        assert screen._validate_data_file('/nonexistent/data.txt') is False

    def test_empty_returns_false(self, screen):
        screen._TrainingResultsScreen__show_popup = Mock()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            txt = f.name
        try:
            assert screen._validate_data_file(txt) is False
        finally:
            os.unlink(txt)

    def test_valid_content_returns_true(self, screen):
        screen._TrainingResultsScreen__show_popup = Mock()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False,
                                         encoding='utf-8') as f:
            f.write("/img.png | 1\n/img2.png | 0\n")
            txt = f.name
        try:
            assert screen._validate_data_file(txt) is True
        finally:
            os.unlink(txt)

    def test_only_type_0_returns_false(self, screen):
        screen._TrainingResultsScreen__show_popup = Mock()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False,
                                         encoding='utf-8') as f:
            f.write("/img.png | 0\n/img2.png | 0\n")
            txt = f.name
        try:
            assert screen._validate_data_file(txt) is False
        finally:
            os.unlink(txt)


class TestValidationItemOpenPreviewPopup:
    """Tests for ValidationItem._open_preview_popup."""

    @pytest.fixture
    def item(self, screen):
        with patch.object(ValidationItem, '__init__', return_value=None):
            vi = ValidationItem()
            vi.screen = screen
            vi.source = os.path.join('dataset', 'model', 'evaluation', 'thumbnail', 'img.png')
            yield vi

    def test_open_preview_popup_resolves_sibling_preview_modal_path(self, item):
        """_open_preview_popup should point to sibling preview_modal folder."""
        # Use a realistic path that os.path functions can handle
        item.source = os.path.normpath("D:/project/datasets/1/dataset1/model1/evaluation/thumbnail/img.png")
        
        # Mock screen.popup.create_preview_popup
        mock_popup = MagicMock()
        item.screen.popup.create_preview_popup = MagicMock(return_value=mock_popup)

        # Set up a fake baseline
        item.screen._last_validation_params = {
            'blur': '1', 'min_area': '50', 'threshold': '128',
            'event_intensity': '10000000', 'show_bbox': '1', 'show_info': '1', 'overlay': '0.50'
        }
        
        # Mock os.path.exists to allow the function to proceed
        with patch('app.screen.PyModule.C_TrainingResultsScreen.os.path.exists', return_value=True):
            item._open_preview_popup()

        assert item.screen.popup.create_preview_popup.called
        # Access kwargs safely
        args, kwargs = item.screen.popup.create_preview_popup.call_args
        resolved_path = kwargs.get('image_path')
        
        assert 'preview_modal' in resolved_path
        assert resolved_path.endswith('img.png')
        assert 'evaluation' in resolved_path
        mock_popup.open.assert_called_once()

        # Verify cache was populated
        assert 'img' in item.screen._preview_params_cache
        # Verify it's a string '1', not a MagicMock
        assert item.screen._preview_params_cache['img']['blur'] == '1'

    def test_open_preview_popup_missing_file_shows_error(self, item):
        """If preview image is missing, show error popup."""
        with patch('app.screen.PyModule.C_TrainingResultsScreen.os.path.exists', return_value=False):
            item._open_preview_popup()
        
        item.screen.popup.create_adaptive_popup.assert_called_with(
            title="error_popup",
            message="file_not_found_error_message"
        )


# ═══════════════════════════════════════════════════════════════════
#  11. ValidationItem._build_command_preview_heatmap — new params
# ═══════════════════════════════════════════════════════════════════

class TestValidationItemBuildCommand:
    """Tests for _build_command_preview_heatmap with new params."""

    @pytest.fixture
    def item(self):
        with patch.object(ValidationItem, '__init__', return_value=None):
            vi = ValidationItem()
            vi.screen = MagicMock()
            yield vi

    def test_includes_new_params(self, item):
        """Command should include show_bounding_box_flag, show_area_volume_flag, overlay."""
        cmd = item._build_command_preview_heatmap(
            histogram_path='/hist.png',
            heatmap_path='/heat.npy',
            heat_kernel_size='1',
            heat_min_area='50',
            heat_threshold='128',
            heat_min_intensity='10000',
            export_heatmap_dir='/export',
            show_bounding_box_flag='1',
            show_area_volume_flag='1',
            overlay='0.50'
        )

        assert '--show_bounding_box_flag' in cmd and '1' in cmd
        assert '--show_area_volume_flag' in cmd and '1' in cmd
        assert '--overlay' in cmd and '0.50' in cmd
        # Also verify legacy params still present
        assert '--histogram_path' in cmd
        assert '--heatmap_path' in cmd
        assert '--heat_kernel_size' in cmd

    def test_param_count(self, item):
        """Should produce exactly 10 key-value pairs = 20 items."""
        cmd = item._build_command_preview_heatmap(
            histogram_path='/h.png', heatmap_path='/h.npy',
            heat_kernel_size='1', heat_min_area='50',
            heat_threshold='128', heat_min_intensity='10000',
            export_heatmap_dir='/e',
            show_bounding_box_flag='1', show_area_volume_flag='1',
            overlay='0.50'
        )
        assert len(cmd) == 20  # 10 --key + 10 values


# ═══════════════════════════════════════════════════════════════════
#  12. on_pipe D017/D018 — stream image handling (reordered in diff)
# ═══════════════════════════════════════════════════════════════════

class TestOnPipeStreamImages:
    """Tests for D017/D018 pipe handling (loading popup dismiss order changed in diff)."""

    def test_d017_dismisses_popup_before_loading_image(self, screen):
        """D017 should dismiss loading popup BEFORE loading image (order changed in diff)."""
        mock_popup = MagicMock()
        mock_popup.process = 'validation'
        screen.loading_popup = mock_popup
        screen._received_generate_data = False
        screen.disable_click = Mock()
        screen.set_left_mouse_disabled = Mock()

        call_order = []
        mock_popup.dismiss.side_effect = lambda: call_order.append('dismiss')
        screen.image_album.load_stream_images.side_effect = lambda **kw: call_order.append('load')

        screen.on_pipe({
            'status_code': 'D017',
            'data': {'thumbnail_path': '/img.png'}
        })

        assert call_order == ['dismiss', 'load']

    def test_d017_first_image_clears_album(self, screen):
        screen._received_generate_data = False
        screen.disable_click = Mock()
        screen.set_left_mouse_disabled = Mock()

        screen.on_pipe({
            'status_code': 'D017',
            'data': {'thumbnail_path': '/img.png'}
        })

        screen.image_album.clear.assert_called_once_with(show_no_data_message=False)
        assert screen._received_generate_data is True

    def test_d017_subsequent_image_no_clear(self, screen):
        screen._received_generate_data = True
        screen.disable_click = Mock()
        screen.set_left_mouse_disabled = Mock()

        screen.on_pipe({
            'status_code': 'D017',
            'data': {'thumbnail_path': '/img2.png'}
        })

        screen.image_album.clear.assert_not_called()

    def test_d018_resets_flags(self, screen):
        screen._received_generate_data = True
        screen.set_left_mouse_disabled = Mock()
        screen._TrainingResultsScreen__show_popup = Mock()

        screen.on_pipe({'status_code': 'D018'})

        assert screen._received_generate_data is False
        screen.set_left_mouse_disabled.assert_called_with(False)
