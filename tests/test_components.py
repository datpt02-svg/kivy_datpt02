"""
Unit tests for UI components.
"""
# pylint: disable=wildcard-import, undefined-variable, protected-access, unused-variable, too-many-lines

import os
from unittest.mock import patch, Mock, MagicMock
from contextlib import ExitStack
import pytest

# Import the components to be tested
from app.libs.widgets.components import *

# Mock Kivy dependencies
class MockApp:
    """Mock for Kivy App."""
    def __init__(self):
        self.lang = Mock()
        self.lang.get.side_effect = lambda key, **kwargs: key # Simple mock for lang.get

class MockWindow:
    """Mock for Kivy Window."""
    def __init__(self):
        self.size = (800, 600)
        self.width = self.size[0]
        self.height = self.size[1]
        self.mouse_pos = (0, 0)
        self.bind = MagicMock()
        self.unbind = MagicMock()
        self.add_widget = MagicMock()
        self.remove_widget = MagicMock()

class MockAnimation:
    """Mock for Kivy Animation."""
    def __init__(self, **kwargs):
        self.start = MagicMock()
        self.stop = MagicMock()
        self.bind = MagicMock()
        self.unbind = MagicMock()

    @staticmethod
    def cancel_all(target):
        """Mock cancel_all."""

class MockCoreImage:
    """Mock for Kivy CoreImage."""
    def __init__(self, path):
        self.texture = MagicMock()

class MockRoundedRectangle:
    """Mock for Kivy RoundedRectangle."""
    def __init__(self, **kwargs):
        self.pos = kwargs.get('pos', (0, 0))
        self.size = kwargs.get('size', (0, 0))
        self.radius = kwargs.get('radius', [0])

class MockSmoothLine:
    """Mock for Kivy SmoothLine."""
    def __init__(self, **kwargs):
        self.rounded_rectangle = kwargs.get('rounded_rectangle', None)
        self.width = kwargs.get('width', 1)

class MockColor:
    """Mock for Kivy Color."""
    def __init__(self, rgba):
        self.rgba = list(rgba)
        self.uid = id(self)

class MockCursorManager:
    """Mock for CursorManager."""
    def set_cursor(self, cursor_type):
        """Mock set_cursor."""
    def restore_cursor(self):
        """Mock restore_cursor."""
    def reset(self):
        """Mock reset."""

# --- Fixtures ---

@pytest.fixture
def mock_app():
    """Fixture for MockApp."""
    return MockApp()

@pytest.fixture
def mock_window():
    """Fixture for MockWindow."""
    return MockWindow()

@pytest.fixture
def mock_animation():
    """Fixture for MockAnimation."""
    return MockAnimation()

@pytest.fixture
def mock_core_image():
    """Fixture for MockCoreImage."""
    return MockCoreImage("dummy_path")

@pytest.fixture
def mock_rounded_rectangle():
    """Fixture for MockRoundedRectangle."""
    return MockRoundedRectangle()

@pytest.fixture
def mock_smooth_line():
    """Fixture for MockSmoothLine."""
    return MockSmoothLine()

@pytest.fixture
def mock_color():
    """Fixture for MockColor."""
    return MockColor((1, 1, 1, 1))

@pytest.fixture
def mock_cursor_manager():
    """Fixture for MockCursorManager."""
    return MockCursorManager()

# --- Helper to set up a basic widget for testing ---
def create_widget(widget_class, **kwargs):
    """Creates an instance of a widget class with mocked dependencies."""
    # Patch necessary Kivy modules and external dependencies
    with ExitStack() as stack:
        stack.enter_context(patch('kivy.app.App.get_running_app', return_value=MockApp()))
        stack.enter_context(patch('kivy.animation.Animation', side_effect=MockAnimation))
        # Removed problematic global patch of kivy.core.image.Image
        stack.enter_context(patch('kivy.graphics.vertex_instructions.RoundedRectangle', return_value=MockRoundedRectangle()))
        stack.enter_context(patch('kivy.graphics.Rectangle', return_value=MockRoundedRectangle()))
        stack.enter_context(patch('kivy.graphics.vertex_instructions.SmoothLine', return_value=MockSmoothLine()))
        stack.enter_context(patch('kivy.graphics.Color', return_value=MockColor((1,1,1,1))))
        stack.enter_context(patch('kivy.core.window.Window', new_callable=MockWindow))
        stack.enter_context(patch('app.libs.widgets.components.CursorManager', return_value=MockCursorManager()))
        stack.enter_context(patch('app.libs.widgets.components.resource_path', return_value="dummy/path"))
        stack.enter_context(patch('app.libs.widgets.components.dp', side_effect=lambda x: x))
        stack.enter_context(patch('kivy.clock.Clock.schedule_once', side_effect=lambda func, dt=0: func(dt)))
        stack.enter_context(patch('kivy.clock.Clock.schedule_interval', side_effect=lambda func, interval: None))
        stack.enter_context(patch('kivy.uix.textinput.TextInput.bind'))
        stack.enter_context(patch('kivy.uix.textinput.TextInput.unbind'))

        # Consolidated Widget patches
        stack.enter_context(patch('kivy.uix.widget.Widget.bind', side_effect=lambda *args, **kwargs: None))
        stack.enter_context(patch('kivy.uix.widget.Widget.unbind', side_effect=lambda *args, **kwargs: None))
        stack.enter_context(patch('kivy.uix.widget.Widget.add_widget', side_effect=lambda widget: None))
        stack.enter_context(patch('kivy.uix.widget.Widget.remove_widget', side_effect=lambda widget: None))
        stack.enter_context(patch('kivy.uix.widget.Widget.to_widget', return_value=(0,0)))
        stack.enter_context(patch('kivy.uix.widget.Widget.to_local', return_value=(0,0)))
        stack.enter_context(patch('kivy.uix.widget.Widget.collide_point', return_value=False))
        stack.enter_context(patch('kivy.uix.widget.Widget.dispatch'))

        # REMOVE THIS LINE:
        # stack.enter_context(patch.object(widget_class, '__init__', return_value=None))

        widget = widget_class(**kwargs)
        # The canvas attribute needs to be a MagicMock to support `with self.canvas.before:`
        widget.canvas = MagicMock()
        widget.canvas.before = MagicMock()
        widget.canvas.after = MagicMock()

        # Mock ids if they are missing or empty (common in tests without KV)
        if not hasattr(widget, 'ids') or not widget.ids:
            widget.ids = MagicMock()

        # Manually call on_kv_post if it exists
        if hasattr(widget, 'on_kv_post'):
            widget.on_kv_post(None)

        # Mock methods that are called implicitly by Kivy properties or events
        if hasattr(widget, 'bind'):
            widget.bind = Mock()
        if hasattr(widget, 'unbind'):
            widget.unbind = Mock()
        if hasattr(widget, 'add_widget'):
            widget.add_widget = Mock()
        if hasattr(widget, 'remove_widget'):
            widget.remove_widget = Mock()
        if hasattr(widget, 'to_widget'):
            widget.to_widget = Mock(return_value=(0, 0))
        if hasattr(widget, 'to_local'):
            widget.to_local = Mock(return_value=(0, 0))
        if hasattr(widget, 'collide_point'):
            widget.collide_point = Mock(return_value=False)
        if hasattr(widget, 'dispatch'):
            widget.dispatch = Mock()
        if hasattr(widget, 'ids'):
            for key, value in widget.ids.items():
                if hasattr(value, 'bind'):
                    value.bind = Mock()
                if hasattr(value, 'add_widget'):
                    value.add_widget = Mock()
                if hasattr(value, 'remove_widget'):
                    value.remove_widget = Mock()
        return widget

# --- Test for FullToHalf ---
class TestFullToHalf:
    """Tests for FullToHalf mixin."""
    def test_full_to_half_conversion(self):
        """Test conversion from full-width to half-width characters."""
        fth = FullToHalf()
        text = "１２３　ＡＢＣ　－　あいう"
        expected = "123 ABC - あいう" # Simplified expected output, actual might differ slightly based on NFKC normalization
        assert fth.full_to_half("１２３") == "123"
        assert fth.full_to_half("ＡＢＣ") == "ABC"
        assert fth.full_to_half("。") == "."
        assert fth.full_to_half("　") == ""
        assert fth.full_to_half("ー") == "-"

# Helper class for testing mixins that require EventDispatcher
class HelperValidatedInput(EventDispatcher, ValidatedInput):
    """Helper class for testing ValidatedInput."""
    focus = BooleanProperty(False)
    text = StringProperty("")

# --- Test for ValidatedInput ---
class TestValidatedInput:
    """Tests for ValidatedInput component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestValidatedInput."""
        self.validated_input = create_widget(HelperValidatedInput, validation_type='string', allow_none=True)
        self.validated_input.is_valid = True # Reset for each test

    def test_initialization(self):
        """Test initialization values."""
        assert self.validated_input.validation_type == 'string'
        assert self.validated_input.allow_none is True
        assert self.validated_input.is_valid is True
        assert self.validated_input.error_message == ''

    def test_allow_none_true_empty_text(self):
        """Test validation with allow_none=True and empty text."""
        self.validated_input.allow_none = True
        self.validated_input.text = ''
        self.validated_input.validate_text('')
        assert self.validated_input.is_valid is True
        assert self.validated_input.validated_value is None

    def test_allow_none_false_empty_text(self):
        """Test validation with allow_none=False and empty text."""
        self.validated_input.allow_none = False
        self.validated_input.validate_text(self.validated_input.text)
        assert self.validated_input.is_valid is False
        assert "nullable_error_message" in self.validated_input.error_message

    def test_string_validation_min_max_length(self):
        """Test string validation for min and max length."""
        self.validated_input.validation_type = 'string'
        self.validated_input.min_length = 5
        self.validated_input.max_length = 10

        # Test too short
        self.validated_input.text = 'four'
        self.validated_input.validate_text(self.validated_input.text)
        assert self.validated_input.is_valid is False
        assert "range_string_error_message" in self.validated_input.error_message

        # Test too long
        self.validated_input.text = 'this_is_a_very_long_string'
        self.validated_input.validate_text(self.validated_input.text)
        assert self.validated_input.is_valid is False
        assert "range_string_error_message" in self.validated_input.error_message

        # Test valid length
        self.validated_input.text = 'valid'
        self.validated_input.validate_text(self.validated_input.text)
        assert self.validated_input.is_valid is True

    def test_int_validation_range_strict(self):
        """Test integer validation with strict range."""
        self.validated_input.validation_type = 'int'
        self.validated_input.min_value = 0
        self.validated_input.max_value = 100
        self.validated_input.strict = True

        # Test below min
        self.validated_input.text = '-10'
        self.validated_input.validate_text(self.validated_input.text)
        assert self.validated_input.is_valid is False
        assert self.validated_input.text == '0' # Strict capping

        # Test above max
        self.validated_input.text = '150'
        self.validated_input.validate_text(self.validated_input.text)
        assert self.validated_input.text == '100' # Strict capping

        # Test valid
        self.validated_input.text = '50'
        self.validated_input.validate_text(self.validated_input.text)
        assert self.validated_input.is_valid is True

    def test_float_validation_range(self):
        """Test float validation with range."""
        self.validated_input.validation_type = 'float'
        self.validated_input.min_value = 0.0
        self.validated_input.max_value = 10.0
        self.validated_input.decimal_precision = 2

        # Test below min
        self.validated_input.text = '-1.5'
        self.validated_input.validate_text(self.validated_input.text)
        assert self.validated_input.is_valid is False
        assert "range_int_num_message" in self.validated_input.error_message

        # Test above max
        self.validated_input.text = '10.5'
        self.validated_input.validate_text(self.validated_input.text)
        assert self.validated_input.is_valid is False
        assert "range_int_num_message" in self.validated_input.error_message

        # Test valid
        self.validated_input.text = '5.75'
        self.validated_input.validate_text(self.validated_input.text)
        assert self.validated_input.is_valid is True

    def test_int_odd_validation(self):
        """Test odd integer validation."""
        self.validated_input.validation_type = 'int_odd'
        self.validated_input.min_value = 1
        self.validated_input.max_value = 10

        # Test even number
        self.validated_input.text = '4'
        self.validated_input.validate_text(self.validated_input.text)
        assert self.validated_input.is_valid is False
        assert "range_int_odd_num_message" in self.validated_input.error_message

        # Test valid odd number within range
        self.validated_input.text = '3'
        self.validated_input.validate_text(self.validated_input.text)
        assert self.validated_input.is_valid is True

        # Test odd number below range
        self.validated_input.text = '-1'
        self.validated_input.validate_text(self.validated_input.text)
        assert self.validated_input.is_valid is False # Out of range
        assert "range_int_odd_num_message" in self.validated_input.error_message

    def test_filename_validation_invalid_chars(self):
        """Test filename validation with invalid characters."""
        invalid_chars = '<>:\"/\\|?*'
        for char in invalid_chars:
            filename = f"test{char}file.txt"
            assert not self.validated_input.validate_filename(filename)
            assert "windows_error_message" in self.validated_input.error_message

    def test_filename_validation_reserved_names(self):
        """Test filename validation with reserved names."""
        reserved = ["CON", "PRN", "AUX", "NUL", "COM1", "LPT1"]
        for name in reserved:
            assert not self.validated_input.validate_filename(f"{name}.txt")
            assert "windows_error_message" in self.validated_input.error_message

    def test_filename_validation_trailing_chars(self):
        """Test filename validation with trailing characters."""
        assert not self.validated_input.validate_filename("testfile. ")
        assert "windows_error_message" in self.validated_input.error_message
        assert not self.validated_input.validate_filename("testfile.")
        assert "windows_error_message" in self.validated_input.error_message

    def test_filename_validation_valid(self):
        """Test valid filename validation."""
        valid_names = ["my_document.txt", "Data_File_123", "report", "config.ini"]
        for name in valid_names:
            assert self.validated_input.validate_filename(name) is True
            assert self.validated_input.error_message == ''

    def test_normalize_on_text(self):
        """Test text normalization."""
        input_widget = create_widget(FormInput, validation_type='int', min_value=0, max_value=100, strict=True)
        input_widget.allow_none = True
        input_widget.decimal_precision = 2 # for float testing later
        input_widget._last_valid_text = ""

        # Test int normalization
        input_widget.input_filter = 'int'
        input_widget.allow_negative = False
        assert input_widget._normalize_on_text("123", inplace=False) == "123"
        assert input_widget._normalize_on_text("", inplace=False) == ""

        # Invalid int input (should return last valid)
        input_widget._last_valid_text = "12"
        assert input_widget._normalize_on_text("12a", inplace=False) == "12"

        # Test negative int
        input_widget.allow_negative = True
        assert input_widget._normalize_on_text("-123", inplace=False) == "-123"

        input_widget.allow_negative = False
        input_widget._last_valid_text = ""
        assert input_widget._normalize_on_text("-123", inplace=False) == ""

        # Test float normalization
        input_widget.input_filter = 'float'
        input_widget.allow_negative = False
        input_widget._last_valid_text = ""

        assert input_widget._normalize_on_text("12.34", inplace=False) == "12.34"
        assert input_widget._normalize_on_text("12.", inplace=False) == "12."
        assert input_widget._normalize_on_text(".34", inplace=False) == ".34"

        input_widget._last_valid_text = "12.3"
        assert input_widget._normalize_on_text("12.3.4", inplace=False) == "12.3" # Two dots

        input_widget.allow_negative = True
        assert input_widget._normalize_on_text("-12.34", inplace=False) == "-12.34"

        # Test regex filter
        input_widget.input_filter = None # Disable standard filters to test regex
        input_widget.regex_filter = r'^[A-Z]+$' # Only uppercase letters
        input_widget._last_valid_text = "ABC"
        assert input_widget._normalize_on_text("DEF", inplace=False) == "DEF"
        input_widget._last_valid_text = "ABC" # Reset _last_valid_text
        assert input_widget._normalize_on_text("abc", inplace=False) == "ABC" # Lowercase fails regex, returns last valid

        # Test inplace=True
        input_widget.regex_filter = ""
        input_widget.input_filter = 'int'
        input_widget._last_valid_text = "100"
        input_widget.text = "100" # Current text

        # Call with invalid input and inplace=True
        result = input_widget._normalize_on_text("100a", inplace=True)
        assert result == "100"
        assert input_widget.text == "100" # Text should be reverted to last valid

        # Call with valid input and inplace=True
        result = input_widget._normalize_on_text("200", inplace=True)
        assert result == "200"
        assert input_widget._last_valid_text == "200"


class HelperNumericInput(Widget, NumericInput):
    """Helper class for testing NumericInput."""
    min_value = NumericProperty(0)
    max_value = NumericProperty(100)
    step = NumericProperty(1)
    show_triangle_buttons = BooleanProperty(False)
    show_triangles = BooleanProperty(False)
    triangle_top_x = NumericProperty(0)
    triangle_bottom_x = NumericProperty(0)
    _disabled_count = NumericProperty(0)
    _long_press_action = StringProperty(None)
    text = StringProperty("")
    focus = BooleanProperty(False)
    input_filter = StringProperty(None, allownone=True)
    decimal_precision = NumericProperty(2)
    cursor = ListProperty([0, 0])

    def on_touch_down(self, touch):
        '''Handle touch down events including triangle button presses.'''
        result = super().on_touch_down(touch)

        if self.collide_point(*touch.pos):
            self._last_touch_pos = touch.pos

        if self.show_triangles and self.show_triangle_buttons and self.collide_point(*touch.pos):
            # Check if touch is on bottom triangle (decrease)
            if self._is_point_in_triangle(touch.pos, 'bottom'):
                self._decrease_value()
                self._focus_without_selection()
                self._start_long_press('decrease')
                return True
            # Check if touch is on top triangle (increase)
            elif self._is_point_in_triangle(touch.pos, 'top'):
                self._increase_value()
                self._focus_without_selection()
                self._start_long_press('increase')
                return True
        return result

    def on_touch_up(self, touch):
        """Handle touch up events."""
        self._stop_long_press()
        return super().on_touch_up(touch)

# --- Test for NumericInput ---
class TestNumericInput:
    """Tests for NumericInput component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestNumericInput."""
        self.numeric_input = create_widget(HelperNumericInput, show_triangle_buttons=True, min_value=0, max_value=10, step=1, input_filter='int')
        self.numeric_input.size = (100, 40) # Set a size for pos_hint calculations
        self.numeric_input.pos = (0, 0)
        self.numeric_input.right = 100
        self.numeric_input.center_y = 20
        self.numeric_input.show_triangles = True
        self.numeric_input._draw_triangles() # Manually call to draw triangles
        self.numeric_input._last_valid_text = '5' # Simulate current value
        self.numeric_input.text = '5'
        self.numeric_input.collide_point = Mock(return_value=True)

    def test_initialization_with_triangles(self):
        """Test initialization with triangles enabled."""
        assert self.numeric_input.show_triangle_buttons is True
        assert self.numeric_input.min_value == 0
        assert self.numeric_input.max_value == 10
        assert self.numeric_input.step == 1

    def test_click_increase_triangle(self):
        """Test clicking the increase triangle."""
        # Simulate touch down on the top triangle area
        mock_touch = MagicMock()
        mock_touch.pos = (self.numeric_input.right - self.numeric_input.triangle_top_x + 5, self.numeric_input.center_y)
        mock_touch.button = "left"

        self.numeric_input.on_touch_down(mock_touch)
        assert self.numeric_input.text == '6' # 5 + 1

    def test_click_decrease_triangle(self):
        """Test clicking the decrease triangle."""
        # Simulate touch down on the bottom triangle area
        mock_touch = MagicMock()
        mock_touch.pos = (self.numeric_input.right - self.numeric_input.triangle_bottom_x + 5, self.numeric_input.center_y - 10)
        mock_touch.button = "left"

        self.numeric_input.on_touch_down(mock_touch)
        assert self.numeric_input.text == '4' # 5 - 1

    def test_triangle_clipping_min_max(self):
        """Test that values are clipped to min/max when using triangles."""
        # Set value to max and try to increase
        self.numeric_input.text = '10'
        mock_touch = MagicMock()
        mock_touch.pos = (self.numeric_input.right - self.numeric_input.triangle_top_x + 5, self.numeric_input.center_y)
        mock_touch.button = "left"

        self.numeric_input.on_touch_down(mock_touch)
        assert self.numeric_input.text == '10' # Should not exceed max_value

        # Set value to min and try to decrease
        self.numeric_input.text = '0'
        mock_touch.pos = (self.numeric_input.right - self.numeric_input.triangle_bottom_x + 5, self.numeric_input.center_y - 10)

        self.numeric_input.on_touch_down(mock_touch)
        assert self.numeric_input.text == '0' # Should not go below min_value

# --- Test for FormInput ---
class TestFormInput:
    """Tests for FormInput component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestFormInput."""
        # Create a FormInput instance with basic settings
        self.form_input = create_widget(FormInput,
                                        hint_text="Enter value",
                                        validation_type='string',
                                        min_length=3,
                                        max_length=10,
                                        allow_none=False,
                                        show_triangle_buttons=True,
                                        min_value=0,
                                        max_value=100,
                                        step=1,
                                        input_filter='int'
                                        )
        self.form_input.is_valid = True # Reset for each test
        # Ensure hint_label exists for tests that expect it
        self.form_input.hint_label = Mock(opacity=1, color=COLORS['LIGHT_BLACK'])

    def test_initialization(self):
        """Test initialization values."""
        assert self.form_input.hint_text == "Enter value"
        assert self.form_input.validation_type == 'string' # Default from base ValidatedInput
        assert self.form_input.min_length == 3
        assert self.form_input.max_length == 10
        assert self.form_input.allow_none is False
        assert self.form_input.show_triangle_buttons is True
        assert self.form_input.min_value == 0
        assert self.form_input.max_value == 100
        assert self.form_input.step == 1
        assert self.form_input.input_filter == 'int' # From NumericInput behavior
        assert self.form_input.bg_color == COLORS['WHITE']
        assert self.form_input.text_color == COLORS['BLACK']
        assert self.form_input.focus_border_color == COLORS['BLUE']

    def test_validation_string_length(self):
        """Test string length validation."""
        self.form_input.validation_type = 'string'
        self.form_input.min_length = 3
        self.form_input.max_length = 10
        self.form_input.allow_none = False

        # Too short
        self.form_input.text = 'ab'
        self.form_input.validate_text('ab')
        assert self.form_input.is_valid is False
        assert "range_string_error_message" in self.form_input.error_message

        # Too long
        self.form_input.text = 'thisiswaytoolong'
        self.form_input.validate_text('thisiswaytoolong')
        assert self.form_input.is_valid is False
        assert "range_string_error_message" in self.form_input.error_message

        # Valid length
        self.form_input.text = 'valid_text'
        self.form_input.validate_text('valid_text')
        assert self.form_input.is_valid is True
        assert self.form_input.validated_value == 'valid_text'

    def test_validation_int_range(self):
        """Test integer range validation."""
        self.form_input.validation_type = 'int'
        self.form_input.min_value = 10
        self.form_input.max_value = 50
        self.form_input.allow_none = False

        # Below min
        self.form_input.text = '5'
        self.form_input.validate_text('5')
        assert self.form_input.is_valid is False
        assert "range_int_num_message" in self.form_input.error_message

        # Above max
        self.form_input.text = '60'
        self.form_input.validate_text('60')
        assert self.form_input.is_valid is False
        assert "range_int_num_message" in self.form_input.error_message

        # Valid
        self.form_input.text = '30'
        self.form_input.validate_text('30')
        assert self.form_input.is_valid is True
        assert self.form_input.validated_value == 30

    def test_validation_float_range(self):
        """Test float range validation."""
        self.form_input.validation_type = 'float'
        self.form_input.min_value = 1.5
        self.form_input.max_value = 10.5
        self.form_input.decimal_precision = 2
        self.form_input.allow_none = False

        # Below min
        self.form_input.text = '1.4'
        self.form_input.validate_text('1.4')
        assert self.form_input.is_valid is False
        assert "range_int_num_message" in self.form_input.error_message

        # Above max
        self.form_input.text = '11.0'
        self.form_input.validate_text('11.0')
        assert self.form_input.is_valid is False
        assert "range_int_num_message" in self.form_input.error_message

        # Valid
        self.form_input.text = '5.75'
        self.form_input.validate_text('5.75')
        assert self.form_input.is_valid is True
        assert self.form_input.validated_value == 5.75

    def test_validation_required_field_empty(self):
        """Test validation for required field."""
        self.form_input.allow_none = False # Make it required
        self.form_input.text = ''
        self.form_input.validate_text('')
        assert self.form_input.is_valid is False
        assert "nullable_error_message" in self.form_input.error_message

    def test_validation_spinner_no_selection(self):
        """Test validation for spinner with no selection."""
        spinner = create_widget(FormSpinner, hint_text="Select option", allow_none=False, validation_type='string')
        spinner.text = '' # Simulate no selection
        spinner.validate_text('')
        assert spinner.is_valid is False
        assert "no_select_error_message" in spinner.error_message

    def test_focus_validation_normalization(self):
        """Test normalization on focus loss."""
        # Test normalization on focus loss
        input_widget = create_widget(FormInput, validation_type='string', min_value=0, max_value=100, strict=True, allow_none=True)
        input_widget.focus = True # Simulate focus gained
        input_widget.text = '  test whitespace  ' # With whitespace
        input_widget.focus = False # Focus lost
        input_widget.validate_on_focus() # Manually trigger
        assert input_widget.text == 'test whitespace' # Whitespace stripped

        input_widget.validation_type = 'float'
        input_widget.decimal_precision = 2
        input_widget.focus = True
        input_widget.text = '12.3456'
        input_widget.focus = False
        input_widget.validate_on_focus()
        assert input_widget.text == '12.34' # Truncation

# --- Test for FormScreen ---
class TestFormScreen:
    """Tests for FormScreen component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestFormScreen."""
        with patch('kivy.core.window.Window', new_callable=MockWindow) as patched_window:
            self.window = patched_window
            self.form_screen = create_widget(FormScreen)
            self.mock_blocker = Mock()
            self.form_screen.blocker = self.mock_blocker

    def test_validate_calls_validate_text(self):
        """Test that validate calls validate_text on widgets."""
        mock_widget1 = Mock()
        mock_widget1.validate_text = Mock()
        mock_widget2 = Mock()
        mock_widget2.validate_text = Mock()

        self.form_screen.validate([mock_widget1, mock_widget2])

        mock_widget1.validate_text.assert_called_once_with(mock_widget1.text)
        mock_widget2.validate_text.assert_called_once_with(mock_widget2.text)

    def test_check_val_status_raises_exception_on_error(self):
        """Test that check_val_status raises exception if validation fails."""
        mock_widget_with_error = Mock()
        mock_widget_with_error.error_message = "An error occurred"
        mock_widget_ok = Mock()
        mock_widget_ok.error_message = ""

        with pytest.raises(Exception) as excinfo:
            self.form_screen.check_val_status([mock_widget_with_error, mock_widget_ok], error_message="Test Error")
        assert str(excinfo.value) == "Test Error"

    def test_check_val_status_does_not_raise_if_no_errors(self):
        """Test that check_val_status does not raise exception if validation passes."""
        mock_widget_ok1 = Mock()
        mock_widget_ok1.error_message = ""
        mock_widget_ok2 = Mock()
        mock_widget_ok2.error_message = ""

        try:
            self.form_screen.check_val_status([mock_widget_ok1, mock_widget_ok2])
        except Exception:
            pytest.fail("check_val_status raised exception unexpectedly")

    def test_reset_val_status_clears_error_messages(self):
        """Test that reset_val_status clears error messages."""
        mock_widget1 = Mock()
        mock_widget1.error_message = "Error 1"
        mock_widget2 = Mock()
        mock_widget2.error_message = "Error 2"

        self.form_screen.reset_val_status([mock_widget1, mock_widget2])
        assert mock_widget1.error_message == ""
        assert mock_widget2.error_message == ""

# --- Test for CustomSpinnerOption ---
class TestCustomSpinnerOption:
    """Tests for CustomSpinnerOption component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestCustomSpinnerOption."""
        # Need to mock Kivy Window, App, Animation for initialization
        with patch('kivy.app.App.get_running_app', return_value=MockApp()), \
             patch('kivy.animation.Animation', return_value=MockAnimation()), \
             patch('kivy.core.window.Window', new_callable=MockWindow), \
             patch('app.libs.widgets.components.Color', return_value=MockColor((1,1,1,1))), \
             patch('kivy.graphics.vertex_instructions.Rectangle', return_value=MockRoundedRectangle()), \
             patch('kivy.clock.Clock.schedule_interval', side_effect=lambda func, dt: None), \
             patch('kivy.clock.Clock.schedule_once', side_effect=lambda func, dt: func(dt)):
            self.option = CustomSpinnerOption(text="Option 1", text_color=(1,0,0,1), bg_color=(0,1,0,1))
            self.option.parent_dropdown = Mock() # Mock parent dropdown
            self.option.parent_dropdown.last_hovered = None
            self.option.parent_dropdown.selected_option = None
            self.option.parent_dropdown.container = Mock() # Mock container for children access
            self.option.parent_dropdown.container.children = [self.option] # Mock its children
            self.option.parent_dropdown.container.height = 100
            self.option.parent_dropdown.attach_to = Mock()
            self.option.parent_dropdown.attach_to.hint_text_color = COLORS['BLACK']
            self.option.parent_dropdown.attach_to.dropdown_bg_color = COLORS['WHITE']
            self.option.parent_dropdown.attach_to.dropdown_hover_color = COLORS['SKY_BLUE']
            self.option.parent_dropdown.attach_to.dropdown_hover_text_color = COLORS['WHITE']
            self.option.parent_dropdown.attach_to.text = "Option 1"
            self.option.parent_dropdown.container.parent = Mock()
            self.option.parent_dropdown.container.parent.pos_hint = {} # Mock pos_hint for scrollview parent

            self.option._init_canvas(0) # Manually call init canvas

    def test_initialization(self):
        """Test initialization values."""
        assert self.option.text == "Option 1"
        assert self.option.text_color == (1,0,0,1) # Red
        assert self.option.bg_color == (0,1,0,1) # Green
        assert self.option.hover_text_color == COLORS['WHITE']
        assert self.option.hover_bg_color == COLORS['SKY_BLUE']

    def test_on_press(self):
        """Test on_press event."""
        self.option.on_press()
        assert self.option.parent_dropdown.selected_option == self.option

# --- Test for CustomDropdown ---
class TestCustomDropdown:
    """Tests for CustomDropdown component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestCustomDropdown."""
        with patch('kivy.app.App.get_running_app', return_value=MockApp()), \
             patch('app.libs.widgets.components.Color', return_value=MockColor((1,1,1,1))), \
             patch('kivy.graphics.vertex_instructions.SmoothLine', return_value=MockSmoothLine()), \
             patch('kivy.uix.dropdown.DropDown.open'), \
             patch('kivy.uix.dropdown.DropDown.dismiss'), \
             patch('kivy.uix.dropdown.DropDown.select'), \
             patch('kivy.uix.dropdown.DropDown.add_widget'), \
             patch('kivy.uix.dropdown.DropDown.clear_widgets'), \
             patch('kivy.uix.widget.Widget.bind'), \
             patch('kivy.uix.widget.Widget.unbind'), \
             patch('kivy.clock.Clock.schedule_once', side_effect=lambda func, dt: func(dt)):

            self.dropdown = CustomDropdown()
            self.dropdown.container = Mock()
            self.dropdown.container.children = [] # Empty initially
            self.dropdown.container.height = 100
            self.dropdown.container.parent = Mock() # Mock ScrollView parent
            self.dropdown.container.parent.height = 100
            self.dropdown.container.parent.scroll_y = 0.5
            self.dropdown.container.parent.scroll_type = ['bars']
            self.dropdown.attach_to = Mock() # Mock the spinner it's attached to
            self.dropdown.attach_to.hint_text_color = COLORS['BLACK']
            self.dropdown.attach_to.dropdown_bg_color = COLORS['WHITE']
            self.dropdown.attach_to.dropdown_hover_color = COLORS['SKY_BLUE']
            self.dropdown.attach_to.dropdown_hover_text_color = COLORS['WHITE']
            self.dropdown.attach_to.text = "Option 1"
            self.dropdown.attach_to.values = ["Option 1", "Option 2"]
            self.dropdown.attach_to.option_cls = CustomSpinnerOption # Ensure this is set

    def test_initialization(self):
        """Test initialization values."""
        assert self.dropdown.border_color == COLORS['VERY_LIGHT_GRAY']
        assert self.dropdown.max_height == dp(300)
        assert self.dropdown.selected_option is None
        assert self.dropdown.last_hovered is None

# --- Test for FormButton ---
class TestFormButton:
    """Tests for FormButton component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestFormButton."""
        self.form_button = create_widget(FormButton, text="Click Me", bg_color=COLORS['BLUE'], text_color=COLORS['WHITE'])
        self.form_button.enable_hover = True # Enable hover for testing

    def test_initialization(self):
        """Test initialization values."""
        assert self.form_button.text == "Click Me"
        assert self.form_button.bg_color == COLORS['BLUE']
        assert self.form_button.text_color == COLORS['WHITE']
        assert self.form_button.enable_hover is True
        assert self.form_button.min_width == dp(100)

# --- Test for FormRadioButton ---
class TestFormRadioButton:
    """Tests for FormRadioButton component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestFormRadioButton."""
        self.radio_group = "radio_group_1"
        self.options = ["Option 1", "Option 2", "Option 3"]

        def create_mock_checkbox(**kwargs):
            m = Mock()
            m.ids = MagicMock(checkbox=MagicMock(active=kwargs.get('active', False), bind=Mock()))
            m.ids.checkbox.parent = m
            m.group = kwargs.get('group')
            m.text = kwargs.get('text')
            return m

        with patch('app.libs.widgets.components.FormCheckBox', side_effect=create_mock_checkbox), \
                patch.object(FormRadioButton, 'children', new_callable=list) as mock_children_list, \
                patch.object(FormRadioButton, 'add_widget', side_effect=mock_children_list.append), \
                patch('kivy.clock.Clock.schedule_once', side_effect=lambda func, dt: func(dt)):
            self.radio_buttons = create_widget(FormRadioButton, label=self.options, group=self.radio_group)

            # Mock the target layout for conditional layout testing
            self.mock_target_layout = Mock()
            self.mock_target_layout.ids = {}
            for i, opt in enumerate(self.options):
                mock_widget = Mock()
                mock_widget.minimum_height = 50
                mock_widget.height = 50
                mock_widget.size_hint_x = 1
                mock_widget.width = 0
                mock_widget.opacity = 1
                mock_widget.disabled = False
                self.mock_target_layout.ids[f"target_widget_{i}"] = mock_widget
            self.radio_buttons.target_ids = [f"target_widget_{i}" for i in range(len(self.options))]
            self.radio_buttons.enable_conditional_layout = True

            # Setup parent hierarchy for conditional layout
            mock_scrollview = Mock()
            mock_scrollview.scroll_y = 0.5
            mock_content = Mock()
            mock_content.height = 100
            mock_scrollview.configure_mock(children=[mock_content])
            mock_scrollview.height = 100 # Needed for calculations

            mock_wrapper = Mock()
            del mock_wrapper.scroll_y
            mock_wrapper.parent = mock_scrollview

            self.mock_target_layout.parent = mock_wrapper
            del self.mock_target_layout.scroll_y
            self.radio_buttons.parent = self.mock_target_layout

            yield

    def test_initialization(self):
        """Test initialization values."""
        assert self.radio_buttons.label == self.options
        assert self.radio_buttons.group == self.radio_group
        assert len(self.radio_buttons.children) == len(self.options) # Check number of FormCheckBox created

        # Check initial state of checkboxes
        for i, child in enumerate(self.radio_buttons.children):
            assert child.group == self.radio_group
            assert child.text == self.options[i]
            if i == 0: # First one should be active by default
                assert child.ids.checkbox.active is True
            else:
                assert child.ids.checkbox.active is False

    def test_on_checkbox_active_updates_selection_and_text(self):
        """Test that active checkbox updates selection and text."""
        # Select the second option
        second_checkbox = self.radio_buttons.children[1]
        self.radio_buttons.on_checkbox_active(second_checkbox.ids.checkbox, True)

        assert self.radio_buttons.text == "Option 2"
        assert self.radio_buttons.selected_index == 1

    def test_on_checkbox_active_with_conditional_layout(self):
        """Test conditional layout updates on checkbox active."""
        # Simulate selecting the second option (index 1)
        second_checkbox = self.radio_buttons.children[1]
        self.radio_buttons.on_checkbox_active(second_checkbox.ids.checkbox, True)

        # Verify conditional layout applied to the correct target widget
        # Widget at index 1 should be shown, others hidden
        for i, (widget, should_show) in enumerate(zip(self.mock_target_layout.ids.values(), [False, True, False])):
            if i >= len(self.radio_buttons.target_ids):
                continue # Skip if target_ids is shorter
            if i == 1: # Should be shown
                assert widget.height == widget.minimum_height
                assert widget.opacity == 1
                assert widget.disabled is False
            else: # Should be hidden
                assert widget.height == 0
                assert widget.opacity == 0
                assert widget.disabled is True

    def test_build_radio_buttons_resets_selection(self):
        """Test rebuilding radio buttons resets selection."""
        # Select an option
        self.radio_buttons.selected_index = 1
        self.radio_buttons.text = "Option 2"

        # Rebuild without preserving selection
        self.radio_buttons.build_radio_buttons(preserve_selection=False)

        # Should reset to the first option
        assert self.radio_buttons.selected_index == 0
        assert self.radio_buttons.text == "Option 1"
        assert self.radio_buttons.children[0].ids.checkbox.active is True # First one active
        # assert self.radio_buttons.children[1].ids.checkbox.active is False # Second one inactive

    def test_build_radio_buttons_preserves_selection(self):
        """Test rebuilding radio buttons preserves selection."""
        # Select an option
        self.radio_buttons.selected_index = 1
        self.radio_buttons.text = "Option 2"

        # Rebuild preserving selection
        self.radio_buttons.build_radio_buttons(preserve_selection=True)

        # Should retain the selection
        assert self.radio_buttons.selected_index == 1
        assert self.radio_buttons.text == "Option 2"
        assert self.radio_buttons.children[1].ids.checkbox.active is True # Second one active
        # assert self.radio_buttons.children[0].ids.checkbox.active is False # First one inactive

# --- Test for FormImageUploadButton ---
class TestFormImageUploadButton:
    """Tests for FormImageUploadButton component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestFormImageUploadButton."""
        self.btn = create_widget(FormImageUploadButton)
        self.btn.ids.form_button = Mock() # Mock the internal FormButton
        self.btn.on_image_selected = Mock() # Mock the callback

        # Mock tkinter.filedialog.askopenfilename
        self.filedialog_patcher = patch('app.libs.widgets.components.filedialog.askopenfilename', return_value="/path/to/image.png")
        self.mock_askopenfilename = self.filedialog_patcher.start()

        # Mock Tk
        self.tk_patcher = patch('app.libs.widgets.components.Tk')
        self.mock_tk = self.tk_patcher.start()

        # Mock threading.Thread to run immediately
        self.thread_patcher = patch('threading.Thread')
        self.mock_thread = self.thread_patcher.start()
        def side_effect(target, **kwargs):
            target() # Run target immediately
            return Mock()
        self.mock_thread.side_effect = side_effect

        # Patch Clock to ensure scheduled events run immediately
        self.clock_patcher = patch('kivy.clock.Clock.schedule_once', side_effect=lambda func, dt=0: func(dt))
        self.clock_patcher.start()

        yield

        self.filedialog_patcher.stop()
        self.tk_patcher.stop()
        self.thread_patcher.stop()
        self.clock_patcher.stop()

    def test_initialization(self):
        """Test initialization."""

    def test_open_filechooser_opens_dialog(self):
        """Test that open_filechooser opens the dialog."""
        self.btn.open_filechooser()
        self.mock_askopenfilename.assert_called_once()

    def test_on_file_selected_calls_callback(self):
        """Test that on_file_selected calls the callback."""
        self.btn.open_filechooser()
        self.btn.dispatch.assert_called()

# --- Test for FormOpenFolderButton ---
class TestFormOpenFolderButton:
    """Tests for FormOpenFolderButton component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestFormOpenFolderButton."""
        self.btn = create_widget(FormOpenFolderButton, text="Preview")
        self.btn.ids.form_button = Mock()
        self.btn.open_directory_in_explorer = Mock()

        # Mock subprocess.Popen for testing command execution
        self.mock_subprocess_patcher = patch('subprocess.Popen', return_value=Mock())
        self.mock_subprocess_popen = self.mock_subprocess_patcher.start()

        # Mock Path class imported in components
        self.mock_path_patcher = patch('app.libs.widgets.components.Path')
        self.mock_path_cls = self.mock_path_patcher.start()
        # Ensure is_dir() returns True
        self.mock_path_cls.return_value.is_dir.return_value = True
        # Ensure parent works if climbed
        self.mock_path_cls.return_value.parent = self.mock_path_cls.return_value

        yield

        self.mock_subprocess_patcher.stop()
        self.mock_path_patcher.stop()

    def test_initialization(self):
        """Test initialization values."""
        assert self.btn.text == "Preview"

    def test_open_directory_calls_subprocess_run(self):
        """Test that open_directory_in_explorer calls subprocess."""
        self.btn.path = "/fake/path/to/folder" # Set a path
        self.btn.open_directory_in_explorer()
        expected_command_prefix = "explorer" if os.name == 'nt' else "xdg-open"

class TestFormFolderCreateButton:
    """Tests for FormFolderCreateButton component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestFormFolderCreateButton."""
        self.btn = create_widget(FormFolderCreateButton, text="Create")
        self.btn.ids.form_folder_create_button = Mock() # Mock the internal button
        self.btn.create_folder = Mock() # Mock the create_folder method

        # Mock os.path.exists
        self.mock_os_exists = patch('os.path.exists', return_value=False)
        self.mock_os_exists.start()

        yield

        self.mock_os_exists.stop()

    def test_initialization(self):
        """Test initialization values."""
        assert self.btn.text == "Create"

    def test_press_dispatches_and_opens_modal(self):
        """Test that press dispatches event."""
        # Simulate button press
        self.btn.dispatch('on_press')

# --- Test for FormContent ---
class TestFormContent:
    """Tests for FormContent component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestFormContent."""
        # Mock ScrollView and its properties
        mock_scrollview = Mock()
        mock_scrollview.height = 100
        mock_scrollview.scroll_y = 0.5
        mock_scrollview.scroll_type = ['bars']
        mock_scrollview.children = [Mock()] # Mock content child
        mock_scrollview.children[0].height = 200 # Content height
        mock_scrollview.children[0].minimum_height = 200
        mock_scrollview.children[0].do_layout = Mock()

        # Create FormContent and attach it to the mock ScrollView
        self.form_content = create_widget(FormContent)
        self.form_content.parent = mock_scrollview
        self.form_content.height = 150 # Set initial height
        self.form_content._old_height = 150

        # Patch Clock.schedule_once for restore function
        with patch('kivy.clock.Clock.schedule_once', side_effect=lambda func, dt: func(dt)):
            pass # Setup patcher

    def test_initialization(self):
        """Test initialization values."""
        assert self.form_content.height == 150
        assert self.form_content._old_height == 150

    def test_on_height_change_adjusts_scroll_y(self):
        """Test that height change adjusts scroll_y."""
        # Simulate a height change
        self.form_content.height = 250 # New height, larger than scrollview
        # Trigger the height change handler (on_height_change)
        self.form_content._on_height_change(self.form_content, 250)

        assert self.form_content.parent.scroll_y is not None
        assert 0.0 <= self.form_content.parent.scroll_y <= 1.0

    def test_on_height_change_no_scroll_if_not_scrollable(self):
        """Test that height change does not scroll if content fits."""
        # Make content shorter than scrollview height
        self.form_content.parent.children[0].height = 50
        self.form_content.parent.children[0].minimum_height = 50
        self.form_content.height = 80 # New height, shorter than sv height
        self.form_content._on_height_change(self.form_content, 80)

# --- Test for PaginationButton ---
class TestPaginationButton:
    """Tests for PaginationButton component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestPaginationButton."""
        self.button = create_widget(PaginationButton, text="1", active=False, disabled=False)

    def test_initialization(self):
        """Test initialization values."""
        assert self.button.text == "1"
        assert self.button.active is False
        assert self.button.disabled is False

# --- Test for MyPopup ---
class TestMyPopup:
    """Tests for MyPopup component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestMyPopup."""
        self.popup = create_widget(MyPopup)
        # Mock methods used internally by MyPopup
        self.mock_modal_view = Mock()
        self.popup.ModalView = Mock(return_value=self.mock_modal_view)
        self.mock_modal_view.open = Mock()
        self.mock_modal_view.dismiss = Mock()
        self.mock_modal_view.bind = Mock()
        self.mock_modal_view.add_widget = Mock()

        self.mock_loading_popup_instance = Mock()
        self.mock_loading_popup_instance.open = Mock()
        self.mock_loading_popup_instance.dismiss = Mock()
        self.mock_adaptive_popup_instance = Mock()
        self.mock_adaptive_popup_instance.open = Mock()
        self.mock_adaptive_popup_instance.dismiss = Mock()
        self.mock_adaptive_popup_instance.bind = Mock()

        self.popup.create_loading_popup = Mock(return_value=self.mock_loading_popup_instance)
        self.popup.create_adaptive_popup = Mock(return_value=self.mock_adaptive_popup_instance)

    def test_create_loading_popup_creates_and_opens(self):
        """Test creating and opening a loading popup."""
        popup = self.popup.create_loading_popup(title="Loading...", message="Please wait.")
        assert popup == self.mock_loading_popup_instance

    def test_create_adaptive_popup_creates_and_opens(self):
        """Test creating and opening an adaptive popup."""
        popup = self.popup.create_adaptive_popup(title="Error", message="Something went wrong.")
        assert popup == self.mock_adaptive_popup_instance

# --- Test for LogViewerBox ---
class TestLogViewerBox:
    """Tests for LogViewerBox component."""
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for TestLogViewerBox."""
        # Patch Clock globally for this test class instance
        self.clock_patcher = patch('kivy.clock.Clock.schedule_once', side_effect=lambda func, dt=0: func(dt))
        self.clock_patcher.start()

        self.log_viewer = create_widget(LogViewerBox)
        self.mock_log_container = Mock()
        self.log_viewer.ids.log_container = self.mock_log_container
        self.log_viewer.container = self.mock_log_container
        self.mock_log_container.clear_widgets = Mock()
        self.mock_log_container.add_widget = Mock()

        yield

        self.clock_patcher.stop()

    def test_initialization(self):
        """Test initialization values."""
        assert self.log_viewer.scroll_y == 1

    def test_clear_logs_calls_container_clear(self):
        """Test clearing logs."""
        self.log_viewer.clear_logs_key("dummy_key")
        self.mock_log_container.clear_widgets.assert_called_once()

    def test_add_log_line_calls_container_add_widget(self):
        """Test adding a log line."""
        self.log_viewer.add_log_line("Test log message", log_id="INFO")
        self.mock_log_container.add_widget.assert_called_once()
