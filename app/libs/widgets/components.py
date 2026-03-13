'''Widget components and helper utilities used by the UI package.'''
import gc
import math
import os
import platform
import re
import subprocess
import threading
import traceback
import unicodedata
from io import BytesIO
from calendar import Calendar
from datetime import date
from functools import partial
from pathlib import Path
from tkinter import Tk, filedialog
import colorsys
import cv2

from PIL import Image as PILImage

from kivy.uix.modalview import ModalView
from kivy.uix.anchorlayout import AnchorLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.effects.scroll import ScrollEffect
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.uix.screenmanager import Screen
from kivy.uix.recycleview import RecycleView
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.behaviors.focus import FocusBehavior
from kivy.uix.spinner import SpinnerOption
from kivy.uix.popup import Popup
from kivy.uix.dropdown import DropDown
from kivy.uix.image import AsyncImage
from kivy.metrics import dp
from kivy.core.text import Label as CoreLabel
from kivy.graphics.texture import Texture
from kivy.core.image import Image as CoreImage
from kivy.clock import Clock, mainthread
from kivy.core.window import Window
from kivy.event import EventDispatcher
from kivy.animation import Animation
from kivy.app import App
from kivy.graphics import (
    Color, Rectangle, Line, RoundedRectangle,
    StencilPush, StencilUse, StencilUnUse, StencilPop,
    Rotate, PushMatrix, PopMatrix, SmoothEllipse,
)
from kivy.graphics.vertex_instructions import SmoothLine
from kivy.logger import Logger
from kivy.properties import (
    StringProperty, BooleanProperty, ObjectProperty,
    ListProperty, NumericProperty, OptionProperty,
    ColorProperty,
)
from kivy.resources import resource_find

from app.env import ENGLISH_IME_CODE
from app.libs.constants.colors import COLORS
from app.libs.constants.default_values import DefaultAnimation, DefaultValuesC3
from app.libs.widgets.cursor_manager import CursorManager
from app.libs.widgets.hover_behavior import HoverBehavior
from app.utils.paths import resource_path

cursor_manager = CursorManager()


class FullToHalf():
    '''Class dedicated to validate japanese'''
    def __init__(self, **kwargs):
        '''Initialize FullToHalf mapping and prepare conversion table.'''
        super().__init__(**kwargs)
        # FF00-FF5F -> 0020-007E
        self.map = {'　': ' ', '。':'.', '！': '!', '＂': '"', '＃': '#', '＄': '$', '％': '%', '＆': '&',
            '＇': "'", '（': '(', '）': ')', '＊': '*', '＋': '+', '，': ',', '、': ',', '－': '-',
            '．': '.', '／': '/', '・': '/',
            '０': '0', '１': '1', '２': '2', '３': '3', '４': '4', '５': '5', '６': '6',
            '７': '7', '８': '8', '９': '9',
            '：': ':', '；': ';', '＜': '<', '＝': '=', '＞': '>', '？': '?', '＠': '@',
            'Ａ': 'A', 'Ｂ': 'B', 'Ｃ': 'C', 'Ｄ': 'D', 'Ｅ': 'E', 'Ｆ': 'F', 'Ｇ': 'G',
            'Ｈ': 'H', 'Ｉ': 'I', 'Ｊ': 'J', 'Ｋ': 'K', 'Ｌ': 'L', 'Ｍ': 'M', 'Ｎ': 'N',
            'Ｏ': 'O', 'Ｐ': 'P', 'Ｑ': 'Q', 'Ｒ': 'R', 'Ｓ': 'S', 'Ｔ': 'T', 'Ｕ': 'U',
            'Ｖ': 'V', 'Ｗ': 'W', 'Ｘ': 'X', 'Ｙ': 'Y', 'Ｚ': 'Z',
            '［': '[', '＼': '\\',
            '］': ']', '＾': '^', '＿': '_', '｀': '`', 'ー': '-',
            'ａ': 'a', 'ｂ': 'b', 'ｃ': 'c', 'ｄ': 'd', 'ｅ': 'e', 'ｆ': 'f', 'ｇ': 'g',
            'ｈ': 'h', 'ｉ': 'i', 'ｊ': 'j', 'ｋ': 'k', 'ｌ': 'l', 'ｍ': 'm', 'ｎ': 'n',
            'ｏ': 'o', 'ｐ': 'p', 'ｑ': 'q', 'ｒ': 'r', 'ｓ': 's', 'ｔ': 't', 'ｕ': 'u',
            'ｖ': 'v', 'ｗ': 'w', 'ｘ': 'x', 'ｙ': 'y', 'ｚ': 'z',
            '｛': '{', '｜': '|', '｝': '}'}

    def is_punct(self, token):
        '''Return True if the token is entirely punctuation characters.'''
        return all(unicodedata.category(char).startswith('P')
                for char in token)

    def is_full_width(self, token):
        '''Return True if all characters in the token are full-width.'''
        return all(unicodedata.east_asian_width(char) in ['W', 'F', 'A']
                for char in token)

    def is_latin(self, token):
        '''Return True if all characters in the token belong to the Latin script.'''
        return all('LATIN' in unicodedata.name(char)
                for char in token)

    def is_digit(self, token):
        '''Return True if all characters in the token are digit characters.'''
        return all('DIGIT' in unicodedata.name(char)
                for char in token)

    def to_half_width(self, token):
        '''Normalize the token to its half-width form.'''
        return unicodedata.normalize('NFKC', token)

    def full_to_half(self, text, narrow=False):
        '''Convert full-width characters to half-width ones.
        Parameters:
            text (str): the string to convert.
            narrow (bool):
                True if only convert the characters in the range [FF00, FF5F);
                False else.
        '''
        try:
            lines = [l.strip() for l in text.splitlines()]
            if narrow:
                lines = [''.join(self.map.get(c, c) for c in l) for l in lines]
            else:
                lines = [''.join(self.map.get(c, c) for c in l) for l in lines]
                lines = [self.to_half_width(l) for l in lines]
            return '\n'.join(lines)
        except Exception:
            traceback.print_exc()

class ValidatedInput():
    '''A reusable input widget mixin that provides value validation rules.'''
    validation_type = OptionProperty('string', options=['string', 'int', 'int_odd', 'float'])
    #int, float
    min_value = NumericProperty(None, allownone=True)
    max_value = NumericProperty(None, allownone=True)
    allow_negative = BooleanProperty(False)
    #string
    min_length = NumericProperty(None, allownone=True)
    max_length = NumericProperty(None, allownone=True)

    strict = BooleanProperty(False) #cap the value to max/min if exceeded
    allow_none = BooleanProperty(True) #allow empty
    is_valid = BooleanProperty(True)
    error_message = StringProperty('')

    check_duplicate_name = BooleanProperty(False)
    json_file_path = StringProperty("")
    current_editing_index = NumericProperty(
        -1, allownone=True
    )

    regex_filter = StringProperty(None)

    def __init__(self, **kwargs):
        '''Initialize validated input settings and bind focus validation.'''
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        self.f2h_engine = FullToHalf() #for japanese input
        self.bind(focus=self.validate_on_focus)
        self._last_valid_text = ''
        self._normalize_on_text_event = None
        self.regex_filter = None

    def on_min_value(self, instance, value):
        '''Adjust allow_negative when a negative min_value is set.'''
        if value is not None and value < 0:
            self.allow_negative = True

    def on_text(self, instance, value):
        '''Handle text change events by normalizing the new value.'''
        self._normalize_on_text(value)

    def _trunc_float(self, number: float, precision: int = 2) -> float:
        '''Truncate a float to a given number of decimal places without rounding.'''
        factor = 10 ** precision
        return math.trunc(number * factor) / factor

    def _convert_to_half_width(self, substring):
        '''Convert to half width in realtime. Should only apply to number fields'''
        try:
            return self.f2h_engine.full_to_half(substring)
        except Exception:
            traceback.print_exc()

    def _normalize_on_text(self, value, inplace=True):
        '''Normalize and validate text input in real time, preserving last valid value.'''
        try:
            self.unbind(text=self.on_text) #unbind to avoid loop

            if self.regex_filter:
                try:
                    re.compile(self.regex_filter)  # Test if the regex is valid
                except re.error:
                    traceback.print_exc()
                else:
                    if not re.fullmatch(self.regex_filter, value):
                        if inplace:
                            self.text = self._last_valid_text
                        return self._last_valid_text

            if self.input_filter == 'int':
                pattern = r'-?\d*' if self.allow_negative else r'\d*'
                # If filtered doesn't match the pattern, revert to last valid text
                if not re.fullmatch(pattern, value):
                    if inplace:
                        self.text = self._last_valid_text
                    return self._last_valid_text

            elif self.input_filter == 'float':
                pattern = r'-?\d*\.?\d*' if self.allow_negative else r'\d*\.?\d*'
                # If filtered doesn't match the pattern, revert to last valid text
                if not re.fullmatch(pattern, value):
                    if inplace:
                        self.text = self._last_valid_text
                    return self._last_valid_text

            self._last_valid_text = value
            return self._last_valid_text

        except Exception:
            traceback.print_exc()
            return self._last_valid_text

        finally:
            self.bind(text=self.on_text) #re-bind

    def normalize_text(self, text):
        '''Normalize the input text called on focus.'''
        if not text:
            return ''
        if self.validation_type in ['int', 'int_odd']:
            negative = text.startswith('-')
            digits = ''.join(c for c in text if c.isdigit())

            if not digits:
                trimmed = '0'
            else:
                trimmed = digits.lstrip('0') or '0'

            if negative and self.allow_negative:
                trimmed = '-' + trimmed

            return str(int(trimmed))
        elif self.validation_type == 'float':
            negative = text.startswith('-')
            filtered = ''.join(c for c in text if c.isdigit() or c == '.')
            parts = filtered.split('.', 1)

            integer_part = parts[0].lstrip('0') or '0'

            if len(parts) == 2:
                decimal_part = parts[1].rstrip('0')
                trimmed = integer_part
                if decimal_part:
                    trimmed += '.' + decimal_part
                elif filtered.endswith('.'):
                    trimmed += '.'
            else:
                trimmed = integer_part

            if negative and self.allow_negative:
                trimmed = '-' + trimmed

            return str(self._trunc_float(float(trimmed), self.decimal_precision))
        else:
            cleaned = text.strip() if text else ''
            return cleaned

    def _is_odd(self, number):
        '''Return True if the provided number is odd (integer coercion).'''
        try:
            return int(number) % 2 != 0
        except TypeError:
            return False

    def validate_on_focus(self, *args):
        '''Normalize and (optionally) re-validate text when the widget focus changes.'''
        if not self.focus:
            try:
                #self.validate_text(self.text) #turn on/off validate on focus
                self.text = str(self.normalize_text(self.text))
            except Exception:
                traceback.print_exc()
                return

    def validate_text(self, text):
        '''Validate the given text according to this widget's validation rules.

        On success this sets `validated_value` and `is_valid`. On failure
        it raises ValueError with a localization key for the error message.
        '''
        try:
            self.error_message = ''
            if not text:
                if self.allow_none:
                    self.text = ''
                    self.validated_value = None
                    self.is_valid = True
                    return
                else:
                    if isinstance(self, FormSpinner):
                        raise ValueError("no_select_error_message")
                    else:
                        raise ValueError("nullable_error_message")

            if self.validation_type == 'int':
                try:
                    value = int(text)
                except ValueError:
                    traceback.print_exc()

                if self.min_value is not None and value < self.min_value:
                    if self.strict:
                        self.text = str(self.min_value)
                    raise ValueError("range_int_num_message")
                if self.max_value is not None and value > self.max_value:
                    if self.strict:
                        self.text = str(self.max_value)
                    raise ValueError("range_int_num_message")
                self.validated_value = value
                self.is_valid = True

            elif self.validation_type == 'int_odd':
                try:
                    value = int(text)
                except ValueError:
                    traceback.print_exc()

                if not self._is_odd(value):
                    raise ValueError("range_int_odd_num_message")
                if self.min_value is not None and value < self.min_value:
                    if self.strict:
                        self.text = str(self.min_value)
                    raise ValueError("range_int_odd_num_message")
                if self.max_value is not None and value > self.max_value:
                    if self.strict:
                        self.text = str(self.max_value)
                    raise ValueError("range_int_odd_num_message")
                self.validated_value = value
                self.is_valid = True

            elif self.validation_type == 'float':
                try:
                    value = float(text)
                except ValueError:
                    traceback.print_exc()

                if self.min_value is not None and value < self.min_value:
                    if self.strict:
                        self.text = str(self.min_value)
                    raise ValueError("range_int_num_message")
                if self.max_value is not None and value > self.max_value:
                    if self.strict:
                        self.text = str(self.max_value)
                    raise ValueError("range_int_num_message")
                self.validated_value = value
                self.is_valid = True

            else:  # string
                trimmed_text = text
                if trimmed_text == '':
                    if self.allow_none:
                        self.text = ''
                        self.validated_value = None
                        self.is_valid = True
                        return
                    else:
                        if isinstance(self, FormSpinner):
                            raise ValueError("no_select_error_message")
                        else:
                            raise ValueError("nullable_error_message")
                self.text = trimmed_text
                if (
                    self.min_length is not None
                    and len(trimmed_text) < self.min_length
                ):
                    raise ValueError("range_string_error_message")
                if self.max_length is not None and len(trimmed_text) > self.max_length:
                    raise ValueError("range_string_error_message")

                self.validated_value = trimmed_text
                self.is_valid = True

        except ValueError as e:
            self.error_message = str(e)
            self.is_valid = False
            self.validated_value = None
        except TypeError as e:
            self.error_message = str(e)
            self.is_valid = False
            self.validated_value = None

    def validate_filename(self, filename):
        '''
        Validate a Windows filename according to Microsoft rules.
        Return True/False
        '''
        try:
            self.error_message = ''
            # Allow empty only if allow_none
            if not filename:
                raise ValueError("nullable_error_message")

            # Check for reserved characters (<>:"/\\|?* and ASCII control chars 0–31)
            if re.search(r'[<>:"/\\|?*]', filename):
                raise ValueError("windows_error_message")
            if any(ord(ch) < 32 for ch in filename):
                raise ValueError("windows_error_message")

            # Disallow trailing space or period
            if filename[-1] in (' ', '.'):
                raise ValueError("windows_error_message")

            # Check reserved device names (case-insensitive)
            reserved_names = {
                "CON", "PRN", "AUX", "NUL",
                *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10)),
                "COM¹", "COM²", "COM³",
                "LPT¹", "LPT²", "LPT³"
            }
            name_upper = filename.upper().split('.')[0] # Check before extension
            if name_upper in reserved_names:
                raise ValueError("windows_error_message")

            self.is_valid = True
            return True
        except Exception as e:
            self.error_message = str(e)
            self.is_valid = False
            return False

class NumericInput():
    '''Mixin providing numeric input utilities and validation helpers.'''
    def __init__(self, **kwargs):
        '''Initialize numeric-specific input behavior and defaults.'''
        super().__init__(**kwargs)
        #self.bind(focus=self.validate_on_focus)
        self.triangle_rect1 = None    # Bottom triangle
        self.triangle_rect2 = None    # Top triangle
        self.hover_rect1 = None       # Bottom hover
        self.hover_rect2 = None       # Top hover
        self.step = 1 #placeholder

        # Load textures
        try:
            self.decrease_texture = CoreImage(resource_path('app/libs/assets/icons/down.png')).texture
            self.increase_texture = CoreImage(resource_path('app/libs/assets/icons/up.png')).texture
            self.decrease_hover_texture = CoreImage(resource_path('app/libs/assets/icons/down_hover.png')).texture
            self.increase_hover_texture = CoreImage(resource_path('app/libs/assets/icons/up_hover.png')).texture
        except Exception:
            self.decrease_texture = None
            self.increase_texture = None
            self.decrease_hover_texture = None
            self.increase_hover_texture = None

        self.show_triangles = False
        self._last_touch_pos = None
        self._long_press_event = None
        self._long_press_action = None
        self._long_press_delay = 0.5
        self._repeat_interval = 0.1

        self.triangle_bottom_x = dp(25)
        self.triangle_top_x = dp(25)

    def on_mouse_pos(self, window, pos):
        '''Handle mouse movement and update triangle hover state.'''
        if not self.show_triangles or not self.show_triangle_buttons:
            return
        local_pos = self.to_widget(*pos)

        if self._is_point_in_triangle(local_pos, 'bottom'):
            if not self.hover_rect1:
                self._on_bottom_triangle_hover()
        else:
            if self.hover_rect1:
                self._clear_bottom_triangle_hover()

        if self._is_point_in_triangle(local_pos, 'top'):
            if not self.hover_rect2:
                self._on_top_triangle_hover()
        else:
            if self.hover_rect2:
                self._clear_top_triangle_hover()

    def _draw_triangles(self):
        '''Draw the increment/decrement triangle controls on the widget.'''
        if not self.show_triangles or not self.show_triangle_buttons:
            return

        with self.canvas.after:
            if self.decrease_texture:
                self.triangle_rect1 = Rectangle(
                    texture=self.decrease_texture,
                    pos=(self.right - self.triangle_bottom_x, self.center_y - dp(11)),
                    size=(dp(12), dp(12))
                )
            if self.increase_texture:
                self.triangle_rect2 = Rectangle(
                    texture=self.increase_texture,
                    pos=(self.right - self.triangle_top_x, self.center_y - dp(2)),
                    size=(dp(12), dp(12))
                )

    def _clear_triangles(self):
        '''Remove triangle graphics from the canvas.'''
        if self.triangle_rect1:
            self.canvas.after.remove(self.triangle_rect1)
            self.triangle_rect1 = None

        if self.triangle_rect2:
            self.canvas.after.remove(self.triangle_rect2)
            self.triangle_rect2 = None

        self._clear_triangle_hovers()

    def update_triangles(self, *args):
        '''Update triangle positions and hover state when layout changes.'''
        if self.triangle_rect1:
            self.triangle_rect1.pos = (self.right - self.triangle_bottom_x, self.center_y - dp(11))

        if self.triangle_rect2:
            self.triangle_rect2.pos = (self.right - self.triangle_top_x, self.center_y - dp(2))

    def _start_long_press(self, action):
        '''Begin a long-press action which will repeat after a delay.'''
        self._long_press_action = action

        self._long_press_event = Clock.schedule_once(
            self._begin_repeat, self._long_press_delay)

    def _begin_repeat(self, dt):
        '''Execute initial action for long-press and schedule repeating calls.'''
        if self._long_press_action:
            if self._long_press_action == 'increase':
                self._increase_value()
            elif self._long_press_action == 'decrease':
                self._decrease_value()

            # Schedule repeat interval
            self._long_press_event = Clock.schedule_interval(
                self._repeat_action, self._repeat_interval)

    def _repeat_action(self, dt):
        '''Called repeatedly during a long-press to perform the action.'''
        if self._long_press_action == 'increase':
            self._increase_value()
        elif self._long_press_action == 'decrease':
            self._decrease_value()
        return True

    def _stop_long_press(self):
        '''Stop any ongoing long-press repeat and clean up.'''
        if self._long_press_event:
            Clock.unschedule(self._long_press_event)
            self._long_press_event = None
        self._long_press_action = None

    def _focus_without_selection(self):
        '''Focus the widget without selecting existing text.'''
        if not self.focus:
            self.focus = True

        self.cursor = (len(self.text), 0)

        if hasattr(self, 'selection_text'):
            self.selection_text = ''

    def _is_point_in_triangle(self, pos, triangle_type):
        '''Return True if the given local point is inside a triangle control region.'''
        x, y = pos
        if triangle_type == 'bottom':
            if self.right - self.triangle_bottom_x <= x <= self.right - self.triangle_bottom_x + dp(14) and self.center_y - dp(14) <= y <= self.center_y - dp(4):
                return True
        elif triangle_type == 'top':
            if self.right - self.triangle_top_x <= x <= self.right - self.triangle_top_x + dp(14) and self.center_y - dp(3) <= y <= self.center_y + dp(6):
                return True
        return False

    def _on_bottom_triangle_hover(self):
        '''Show hover graphic for bottom triangle control.'''
        if not self.hover_rect1:
            with self.canvas.after:
                if self.decrease_hover_texture:
                    self.hover_rect1 = Rectangle(
                        texture=self.decrease_hover_texture,
                        pos=(self.right - self.triangle_bottom_x, self.center_y - dp(11)),
                        size=(dp(12), dp(12))
                    )

    def _on_top_triangle_hover(self):
        '''Show hover graphic for top triangle control.'''
        if not self.hover_rect2:
            with self.canvas.after:
                if self.increase_hover_texture:
                    self.hover_rect2 = Rectangle(
                        texture=self.increase_hover_texture,
                        pos=(self.right - self.triangle_top_x, self.center_y - dp(2)),
                        size=(dp(12), dp(12))
                    )

    def _clear_bottom_triangle_hover(self):
        '''Remove hover graphic for bottom triangle control.'''
        if self.hover_rect1:
            self.canvas.after.remove(self.hover_rect1)
            self.hover_rect1 = None

    def _clear_top_triangle_hover(self):
        '''Remove hover graphic for top triangle control.'''
        if self.hover_rect2:
            self.canvas.after.remove(self.hover_rect2)
            self.hover_rect2 = None

    def _clear_triangle_hovers(self):
        '''Clear both triangle hover graphics.'''
        self._clear_bottom_triangle_hover()
        self._clear_top_triangle_hover()

    def _increase_value(self):
        '''Increase the numeric value by one step respecting min/max constraints.'''
        try:
            type_converter = self._get_converter()
            current_value = type_converter(self.text) if self.text else 0

            if type_converter == float:
                #avoid floating-point precision problem
                new_value = round(current_value + self.step, self.decimal_precision)
            else:
                new_value = current_value + self.step

            # Check min_value/max_value constraint
            if hasattr(self, 'max_value') and self.max_value is not None:
                if new_value > self.max_value:
                    #self.text = str(self.max_value)
                    return

            self.text = str(new_value)
        except ValueError:
            traceback.print_exc()
            return

    def _decrease_value(self):
        '''Decrease the numeric value by one step respecting min/max constraints.'''
        try:
            type_converter = self._get_converter()
            current_value = type_converter(self.text) if self.text else 0

            if type_converter == float:
                #avoid floating-point precision problem
                new_value = round(current_value - self.step, self.decimal_precision)
            else:
                new_value = current_value - self.step

            # Check min_value/max_value constraint
            if hasattr(self, 'min_value') and self.min_value is not None:
                if new_value < self.min_value:
                    #self.text = str(self.min_value)
                    return

            self.text = str(new_value)
        except ValueError:
            traceback.print_exc()
            return

    def _get_converter(self):
        '''Return the right type converter based on input_filter.'''
        if self.input_filter == 'int':
            return int
        elif self.input_filter == 'float':
            return float
        return None

class FormInput(TextInput, ValidatedInput, FocusBehavior, HoverBehavior, NumericInput):
    '''A text input widget with integrated validation and hover/focus behaviors.'''
    show_triangle_buttons = BooleanProperty(False)
    show_border = BooleanProperty(True)
    show_focus_glow = BooleanProperty(True)
    allow_negative = BooleanProperty(False)
    force_half_width = BooleanProperty(False)
    step = NumericProperty(1)
    bg_color = ColorProperty(COLORS['WHITE'])
    hint_text_color = ColorProperty(COLORS['LIGHT_BLACK'])
    text_color = ColorProperty(COLORS['BLACK'])
    cursor_color = ColorProperty(COLORS['MEDIUM_GRAY'])
    border_color = ColorProperty(COLORS['VERY_LIGHT_GRAY'])
    focus_border_color = ColorProperty(COLORS['BLUE'])
    _original_ime = None
    _numeric_input_count = 0
    _ime_monitor_event = None

    def __init__(self, **kwargs):
        super(FormInput, self).__init__(**kwargs)
        with self.canvas.before:
            self.bg_color_instruction = Color(rgba=self.bg_color)
            self.rect = RoundedRectangle(
                pos=(self.x + dp(1), self.y + dp(1)),
                size=(self.width - dp(2), self.height - dp(2)),
                radius=[dp(4)]
            )
        self.bind(bg_color=self._update_background_color)
        self.bind(pos=self._update_background, size=self._update_background)
        self.foreground_color = self.text_color
        self._update_event = None
        self.border_line = None
        self.focus_glow = None
        self.focus_line = None
        self.focus_glow_color = [min(1, c * 1.15) for c in self.focus_border_color[:3]] + [self.focus_border_color[3] * 0.15]

        self.decimal_precision = 0 #int
        self.bind(step=self._update_decimal_precision)
        # Initialize IME controller and store previous IME
        # Lazy import to avoid circular dependency
        from app.screen.PyModule.utils.change_ime import WindowsKeyboardIME  # pylint: disable=import-outside-toplevel
        self.ime_controller = WindowsKeyboardIME()

        if FormInput._original_ime is None:
            try:
                FormInput._original_ime = self.ime_controller.get_current_ime()
            except Exception:
                traceback.print_exc()
                FormInput._original_ime = ENGLISH_IME_CODE  # fallback to English

        if FormInput._ime_monitor_event is None:
            FormInput._ime_monitor_event = Clock.schedule_interval(
                self._monitor_ime_changes, 0
            )

    @classmethod
    def _monitor_ime_changes(cls, dt):
        '''Monitor system IME changes and force English IME when numeric inputs are active.'''
        try:
            # Lazy import to avoid circular dependency
            from app.screen.PyModule.utils.change_ime import WindowsKeyboardIME  # pylint: disable=import-outside-toplevel
            temp_controller = WindowsKeyboardIME()
            current_ime = temp_controller.get_current_ime()

            if current_ime is None:
                return

            if cls._numeric_input_count > 0:
                if current_ime != ENGLISH_IME_CODE:
                    cls._original_ime = current_ime
                    temp_controller.set_ime(ENGLISH_IME_CODE)

            else:
                if current_ime != cls._original_ime:
                    cls._original_ime = current_ime

        except Exception:
            traceback.print_exc()

    def on_kv_post(self, base_widget):
        '''Post-KV initialization: bind properties and enable triangle buttons where needed.'''
        self.bind(show_border=self._update_border, pos=self._update_border, size=self._update_border)
        self.bind(text=self._reset_scroll)

        if self.validation_type in ['int', 'float']:
            self.input_filter = self.validation_type
        if self.validation_type == 'int_odd':
            self.input_filter = 'int'

        if self.input_filter in ['int', 'float']:
            self.show_triangle_buttons = True

        return super().on_kv_post(base_widget)

    def _update_background_color(self, instance, value):
        '''Update the background color RGBA instruction when `bg_color` changes.'''
        if self.bg_color_instruction:
            self.bg_color_instruction.rgba = value

    def _update_background(self, *args):
        '''Adjust the background rectangle position/size to match widget geometry.'''
        self.rect.pos = (self.x + dp(1), self.y + dp(1))
        self.rect.size = (self.width - dp(2), self.height - dp(2))

    def _update_decimal_precision(self, *args):
        '''Recompute decimal precision based on the current step value.'''
        try:
            self.decimal_precision = int(str(self.step)[::-1].find('.'))
            if self.decimal_precision < 0:
                self.decimal_precision = 0
        except Exception:
            traceback.print_exc()
            self.decimal_precision = 0

    def _reset_scroll(self, *args):
        if not self.multiline and self.scroll_x > 0:
            # Estimate if scroll is needed or not
            text_width = self._get_text_width(self.text, self.tab_width, self._label_cached)
            if text_width < self.width:
                self.scroll_x = 0

    def _update_border(self, *args):
        if self.border_line:
            self.canvas.after.remove(self.border_line)
            self.border_line = None
        if self.show_border:
            with self.canvas.after:
                Color(rgba=self.border_color)
                self.border_line = SmoothLine(rounded_rectangle=(self.x + 0.5, self.y + 0.5, self.width - 1, self.height - 1, dp(4), 100), width=dp(1))

    def _update_lines(self, *args):
        if self.focus_glow and self.show_focus_glow:
            self.focus_glow.rounded_rectangle = (self.x + 0.5, self.y + 0.5, self.width - 1, self.height - 1, dp(4))
        if self.focus_line:
            self.focus_line.rounded_rectangle = (self.x + 0.5, self.y + 0.5, self.width - 1, self.height - 1, dp(4))

    def on_focus(self, instance, value):
        '''React to widget focus/unfocus events and manage IME for numeric inputs.'''
        if value:  # focus
            # Handle IME switching cho numeric inputs
            if self.input_filter in ['int', 'float']:
                try:
                    was_zero = FormInput._numeric_input_count == 0
                    FormInput._numeric_input_count += 1

                    if was_zero:
                        current_ime = self.ime_controller.get_current_ime()
                        if current_ime:
                            FormInput._original_ime = current_ime

                    if self.ime_controller.get_current_ime() != ENGLISH_IME_CODE:
                        self.ime_controller.set_ime(ENGLISH_IME_CODE)
                except Exception:
                    traceback.print_exc()
            self._draw_focus()
        else:  # unfocus
            if self.input_filter in ['int', 'float']:
                try:
                    FormInput._numeric_input_count = max(0, FormInput._numeric_input_count - 1)
                    if FormInput._numeric_input_count == 0 and FormInput._original_ime is not None:
                        self.ime_controller.set_ime(FormInput._original_ime)
                except Exception:
                    traceback.print_exc()
            self._clear_ime()
            self._clear_focus()

    def _draw_focus(self):
        '''Draw focus glow and focus line on the widget.'''
        with self.canvas.after:
            if not self.focus_glow and self.show_focus_glow:
                padding = dp(1.5)
                Color(rgba=self.focus_glow_color)
                self.focus_glow = SmoothLine(rounded_rectangle=(self.x - padding + 0.5, self.y - padding + 0.5, self.width + 2 * padding - 1, self.height + 2 * padding - 1, dp(4) + padding, 100), width=padding)
            if not self.focus_line:
                self.show_border = False
                Color(rgba=self.focus_border_color)
                self.focus_line = SmoothLine(rounded_rectangle=(self.x + 0.5, self.y + 0.5, self.width - 1, self.height - 1, dp(4), 100), width=dp(1))
        self.bind(pos=self._update_lines, size=self._update_lines)

    def _clear_focus(self):
        '''Clear any focus-related canvas instructions and bindings.'''
        if self.focus_glow:
            self.canvas.after.remove(self.focus_glow)
            self.focus_glow = None
        if self.focus_line:
            self.show_border = True
            self.canvas.after.remove(self.focus_line)
            self.focus_line = None
        self.unbind(pos=self._update_lines, size=self._update_lines)

    def _clear_ime(self):
        '''Force clear IME metadata.'''
        ime = getattr(self, '_ime_composition', '')  # private attribute used by TextInput
        if ime:
            # clear the IME metadata
            self._ime_composition = ''
            if hasattr(self, '_ime_cursor'):
                self._ime_cursor = None

            try: # move cursor to end of committed text
                self.cursor = (len(self.text), 0)
            except Exception:
                pass

    def window_on_textedit(self, window, ime_input):
        '''Handle IME composition. Overwrite kivy original window_on_textedit.'''
        if self.input_filter == 'int' or self.input_filter == 'float' or self.force_half_width: # IME filter
            ime_input = self._convert_to_half_width(ime_input)
            norm = self._normalize_on_text(ime_input, inplace=False)
            if norm != ime_input:
                print("Unfocused due to error in IME input.")
                self.focus = False
                self._ime_cursor = None
                self._ime_composition = ''
                return

        text_lines = self._lines or ['']
        if self._ime_composition:
            pcc, pcr = self._ime_cursor
            text = text_lines[pcr]
            len_ime = len(self._ime_composition)
            if text[pcc - len_ime:pcc] == self._ime_composition:  # always?
                remove_old_ime_text = text[:pcc - len_ime] + text[pcc:]
                ci = self.cursor_index()
                self._refresh_text_from_property(
                    "insert",
                    *self._get_line_from_cursor(pcr, remove_old_ime_text)
                )
                self.cursor = self.get_cursor_from_index(ci - len_ime)

        if ime_input:
            if self._selection:
                self.delete_selection()
            _, cr = self.cursor #cc, cr
            text = text_lines[cr]
            #new_text = text[:cc] + ime_input + text[cc:]
            # self._refresh_text_from_property( #default behaviour, this will bypass insert_text and direcly change self.text
            #     "insert", *self._get_line_from_cursor(cr, new_text)
            # )
            self.insert_text(ime_input)
            self.cursor = self.get_cursor_from_index(
                self.cursor_index() + len(ime_input)
            )

        self._ime_composition = ime_input
        self._ime_cursor = self.cursor

    def on_enter(self):
        '''Called when mouse enters the widget: enable triangles if configured.'''
        if self.show_triangle_buttons:
            self.show_triangles = True
            self._draw_triangles()

            self.bind(pos=self.update_triangles, size=self.update_triangles)
            Window.bind(mouse_pos=self.on_mouse_pos)

    def on_leave(self):
        '''Called when mouse leaves the widget: disable triangles and hover effects.'''
        if self.show_triangle_buttons:
            self.show_triangles = False
            self._clear_triangles()

            self.unbind(pos=self.update_triangles, size=self.update_triangles)
            Window.unbind(mouse_pos=self.on_mouse_pos)

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
        '''Handle touch up events and stop any long-press repetition.'''
        self._stop_long_press()
        return super().on_touch_up(touch)

    def on_double_tap(self):
        '''Handle double-tap events relative to triangle controls.'''
        if (self._last_touch_pos and self.show_triangles and self.show_triangle_buttons):
            if self._is_point_in_triangle(self._last_touch_pos, 'bottom'):
                return
            elif self._is_point_in_triangle(self._last_touch_pos, 'top'):
                return

        return super().on_double_tap()

    def on_touch_move(self, touch):
        if self.show_triangles and self.show_triangle_buttons:
            # Check hover state for triangles
            if self._is_point_in_triangle(touch.pos, 'bottom'):
                if not self.hover_rect1:
                    self._on_bottom_triangle_hover()
            else:
                if self.hover_rect1:
                    self._clear_bottom_triangle_hover()

            if self._is_point_in_triangle(touch.pos, 'top'):
                if not self.hover_rect2:
                    self._on_top_triangle_hover()
            else:
                if self.hover_rect2:
                    self._clear_top_triangle_hover()
        else:
            self._clear_triangle_hovers()

        return super().on_touch_move(touch)

    def insert_text(self, substring, from_undo=False):
        # Block minus sign for int/float fields when allow_negative=False
        if (self.input_filter in ['int', 'float']) and not self.allow_negative and substring == '-':
            return

        # Validate against regex_filter BEFORE insertion to prevent cursor jump
        if self.regex_filter and substring and not from_undo:
            try:
                # Simulate what the text would be after insertion
                cc, cr = self.cursor
                text_lines = self._lines or ['']
                current_line = text_lines[cr] if cr < len(text_lines) else ''
                simulated_text = current_line[:cc] + substring + current_line[cc:]

                # Check if simulated text matches regex
                if not re.fullmatch(self.regex_filter, simulated_text):
                    # Invalid input - block insertion
                    Logger.debug("[INSERT DEBUG] Blocked: simulated_text='%s' doesn't match regex", simulated_text)
                    return
            except Exception:
                traceback.print_exc()

        if self.input_filter == 'int' or self.input_filter == 'float' or self.force_half_width:
            substring = self._convert_to_half_width(substring)
        #print(f"inserting: {substring}")
        return super().insert_text(substring, from_undo=from_undo)

class FormScreen(Screen):
    '''Base screen class for forms, providing common form-related helpers.'''
    blocker = ObjectProperty(None, allownone=True)

    def disable_click(self, all_widget=True, allow_widget=None):
        '''Add a transparent overlay that blocks clicks but lets scroll through.'''
        if allow_widget is None:
            allow_widget=[]
        if not self.blocker:
            if all_widget:
                self.blocker = TouchBlocker(allow_widget=allow_widget) #block all
            else:
                self.blocker = TouchBlocker(size=self.size, pos=self.pos, allow_widget=allow_widget) #inside screen only
            Window.add_widget(self.blocker)

    def enable_click(self):
        '''Remove the overlay and restore normal behavior.'''
        if self.blocker:
            Window.remove_widget(self.blocker)
            self.blocker = None

    def validate(self, val_list):
        '''Validate immediately on demand.'''
        for widget_id in val_list:
            # Trigger focus-out validation logic first to normalize text
            if hasattr(widget_id, 'focus'):
                widget_id.focus = False
            # Main validation
            if hasattr(widget_id, 'validate_text') and callable(getattr(widget_id, 'validate_text')):
                widget_id.validate_text(widget_id.text)

    def check_val_status(self, val_list, error_message="overall_error_popup"):
        '''Raise exception if error_message exist.'''
        for widget_id in val_list:
            if hasattr(widget_id, 'error_message'):
                if widget_id.error_message != "":
                    raise Exception(error_message)

    def custom_val_status(self, component, message):
        '''Change validation message.'''
        if hasattr(component, 'error_message'):
            component.error_message = message

    def reset_val_status(self, val_list):
        '''Reset validation status'''
        for widget_id in val_list:
            if hasattr(widget_id, 'error_message'):
                widget_id.error_message = ""

class FormGroup(BoxLayout):
    '''Container grouping form controls and labels.'''

class FormLabel(Label):
    '''Styled label used alongside form controls.'''
    text_key = StringProperty('')
    format_args = ObjectProperty(None)

class CustomSpinnerOption(SpinnerOption, HoverBehavior):
    '''Individual item in the dropdown list'''
    def __init__(self,
                 text_color=COLORS['BLACK'],
                 bg_color=COLORS['WHITE'],
                 hover_text_color=COLORS['WHITE'],
                 hover_bg_color=COLORS['SKY_BLUE'],
                 **kwargs):
        super().__init__(**kwargs)
        self.text_color = text_color
        self.bg_color = bg_color
        self.hover_text_color = hover_text_color
        self.hover_bg_color = hover_bg_color
        self._bg_color = None
        self._bg_rect = None
        self.parent_dropdown = None
        self._is_hovered = False
        Clock.schedule_once(self._init_canvas, 0)
        Clock.schedule_interval(lambda dt: self._check_mouse_over(), 0.05)

    def on_parent(self, instance, parent):
        '''Detect and store reference to parent CustomDropdown if present.'''
        if parent and parent.parent and isinstance(parent.parent, CustomDropdown):
            self.parent_dropdown = parent.parent

    def _init_canvas(self, dt):
        '''Initialize canvas background rectangle and color for the option.'''
        with self.canvas.before:
            self._bg_color = Color(rgba=self.bg_color)
            self._bg_rect = Rectangle(pos=self.pos, size=self.size)
        self.color = self.text_color
        self.bind(pos=self._update_graphics, size=self._update_graphics)

    def _update_graphics(self, *args):
        '''Update background rectangle geometry to follow the widget.'''
        if self._bg_rect:
            self._bg_rect.pos = self.pos
            self._bg_rect.size = self.size

    def reset_to_normal(self):
        '''Reset visual state to the non-hovered appearance.'''
        self._is_hovered = False
        if self._bg_color:
            Animation.cancel_all(self._bg_color)
            anim = Animation(rgba=self.bg_color, d=DefaultAnimation.HOVER_DURATION, t=DefaultAnimation.HOVER_TRANSITION)
            anim.start(self._bg_color)
        self.color = self.text_color

    def _check_mouse_over(self):
        '''Hover helper function for edge cases where on_enter fail, check if the mouse is currently inside widget. If yes, trigger on_enter().'''
        if not self.get_root_window() or not self.parent_dropdown or self._is_hovered:
            return

        mx, my = Window.mouse_pos
        dropdown_x, dropdown_y = self.parent_dropdown.to_window(*self.parent_dropdown.pos)
        dropdown_w, dropdown_h = self.parent_dropdown.size

        # Check if mouse is inside both this widget and its parent dropdown
        inside_widget = self.collide_point(*self.to_widget(mx, my))
        inside_dropdown = (
            dropdown_x <= mx <= dropdown_x + dropdown_w and
            dropdown_y <= my <= dropdown_y + dropdown_h
        )

        # Only trigger hover if inside both
        if inside_widget and inside_dropdown:
            self.on_enter()

    def on_enter(self):
        '''Handle pointer entering the option area and update visuals.'''
        if self.parent_dropdown:
            if (
                self.parent_dropdown.last_hovered
                and self.parent_dropdown.last_hovered is not self
            ):
                self.parent_dropdown.last_hovered.reset_to_normal()
            if (
                self.parent_dropdown.selected_option
                and self.parent_dropdown.selected_option is not self
            ):  # ensure the last selected is reset to normal
                self.parent_dropdown.selected_option.reset_to_normal()

            self._is_hovered = True
            if self._bg_color:
                Animation.cancel_all(self._bg_color)
                anim = Animation(rgba=self.hover_bg_color, d=DefaultAnimation.HOVER_DURATION, t=DefaultAnimation.HOVER_TRANSITION)
                anim.start(self._bg_color)
            self.color = self.hover_text_color
            self.parent_dropdown.last_hovered = self  # update last_hovered

    def on_press(self):
        '''Handle press on an option and mark it selected on its dropdown.'''
        if self.parent_dropdown:
            self.parent_dropdown.selected_option = self
        return super().on_press()

class CustomDropdown(DropDown):
    '''Custom dropdown attached to FormSpinner'''
    def __init__(self, border_color=COLORS['VERY_LIGHT_GRAY'], max_height=dp(300), **kwargs):
        super().__init__(**kwargs)
        self.border_color = border_color
        self.max_height = max_height
        self.app = App.get_running_app()
        self._border_color_instruction = None
        self._border_line = None
        self.selected_option = None
        self.last_hovered = None
        self._init_border()

    def _init_border(self):
        with self.canvas.after:
            self._border_color_instruction = Color(rgba=self.border_color)
            self._border_line = SmoothLine(width=dp(1))

        self.bind(pos=self._update_border, size=self._update_border)

    def _update_border(self, *args):
        if self._border_line:
            self._border_line.rounded_rectangle = (
                self.x, self.y,
                self.width, self.height,
                dp(0)
            )

    def highlight_selected_option(self):
        '''Highlight the currently selected dropdown option visually.'''
        if self.selected_option:
            self.selected_option._is_hovered = True # pylint: disable=protected-access
            if self.selected_option._bg_color: # pylint: disable=protected-access
                self.selected_option._bg_color.rgba = self.selected_option.hover_bg_color # pylint: disable=protected-access
            self.selected_option.color = self.selected_option.hover_text_color

    def open(self, widget):
        super(CustomDropdown, self).open(widget)
        parent_spinner = getattr(self, 'attach_to', None)
        if parent_spinner:
            if not self.container.children:
                no_data_option = NoDataSpinnerOption(
                    text_color=parent_spinner.hint_text_color,
                    bg_color=parent_spinner.dropdown_bg_color,
                )
                super().add_widget(no_data_option)

            if parent_spinner.text: #edge case where text init earlier than options, options re-init or text re-assign
                if not self.selected_option or self.selected_option.text != parent_spinner.text:
                    if self.selected_option:
                        self.selected_option.reset_to_normal()
                        self.selected_option = None
                    self.on_select(parent_spinner.text)

            scrollview = self.container.parent
            def adjust_scroll(dt):
                if not scrollview:
                    return
                if self.selected_option:  # scroll to selected
                    selected_option_y_pos = float(self.selected_option.y + self.selected_option.height / 2.0)
                    norm_y_pos = selected_option_y_pos / float(max(1, self.container.height)) # normalized between 0 and 1
                    # snap to edges if close
                    if norm_y_pos < DefaultAnimation.EDGE_SNAP_THRESHOLD:
                        norm_y_pos = 0.0
                    elif norm_y_pos > (1-DefaultAnimation.EDGE_SNAP_THRESHOLD):
                        norm_y_pos = 1.0
                    scrollview.scroll_y = min(max(norm_y_pos, 0.0), 1.0) # clamp between 0 and 1
                else:  # no selection or text is empty, scroll to top
                    scrollview.scroll_y = 1.0
            Clock.schedule_once(adjust_scroll, -1)
        self.highlight_selected_option()

    def on_select(self, data):
        if not self.selected_option:
            #fallback
            for child in self.container.children: #NOTE: this assume that options are unique, if it is not then the first one the loop see will be selected
                if getattr(child, 'text', None) == data:
                    self.selected_option = child
                    break
        self.highlight_selected_option()
        return super().on_select(data)

    def on_dismiss(self):
        if self.last_hovered:
            self.last_hovered.reset_to_normal()
            self.last_hovered = None
        return super().on_dismiss()

class FormSpinner(Spinner, ValidatedInput, HoverBehavior):
    '''Spinner widget with validation and hover behavior.'''
    text = StringProperty("")
    hint_text = StringProperty("")
    focus = BooleanProperty(False)
    show_border = BooleanProperty(True)
    show_focus_glow = BooleanProperty(True)
    enable_hover = BooleanProperty(False)
    selected_index = NumericProperty(None, allownone=True)
    bg_color = ColorProperty(COLORS['WHITE'])
    text_color = ColorProperty(COLORS['BLACK'])
    hint_text_color = ColorProperty(COLORS['LIGHT_BLACK'])
    border_color = ColorProperty(COLORS['VERY_LIGHT_GRAY'])
    focus_border_color = ColorProperty(COLORS['BLUE'])
    dropdown_bg_color = ColorProperty(COLORS['WHITE'])
    dropdown_text_color = ColorProperty(COLORS['BLACK'])
    dropdown_border_color = ColorProperty(COLORS['LIGHT_GRAY'])
    dropdown_hover_color = ColorProperty(COLORS['SKY_BLUE'])
    dropdown_hover_text_color = ColorProperty(COLORS['WHITE'])
    global cursor_manager # pylint: disable=global-variable-not-assigned
    arrow_texture_path = StringProperty(resource_path('app/libs/assets/icons/spinner.png'))
    def __init__(self, **kwargs):
        '''Initialize generic form input properties and bind events.'''
        super().__init__(**kwargs)
        with self.canvas.before:
            self.bg_color_instruction = Color(rgba=self.bg_color)
            self.rect = RoundedRectangle(
                pos=(self.x + dp(1), self.y + dp(1)),
                size=(self.width - dp(2), self.height - dp(2)),
                radius=[dp(4)]
            )
        self.bind(bg_color=self._update_background_color)
        self.bind(pos=self._update_background, size=self._update_background)
        self.hint_label = None
        self.border_line = None
        self.focus_glow = None
        self.focus_line = None
        self.dropdown_arrow = None
        self.focus_glow_color = [min(1, c * 1.15) for c in self.focus_border_color[:3]] + [self.focus_border_color[3] * 0.15]
        self.hover_darken_per = 0.1
        self.hover_color = [max(c - self.hover_darken_per, 0) for c in self.bg_color[:3]] + [self.bg_color[3]]

    def _update_background_color(self, instance, value):
        if self.bg_color_instruction:
            self.bg_color_instruction.rgba = value
        if self.enable_hover:
            self.hover_color = [max(c - self.hover_darken_per, 0) for c in value[:3]] + [value[3]]

    def _update_background(self, *args):
        self.rect.pos = (self.x + dp(1), self.y + dp(1))
        self.rect.size = (self.width - dp(2), self.height - dp(2))

    def _get_selected_index(self):
        """Return the index of the selected option widget in the values list."""
        if not self._dropdown or not self._dropdown.selected_option:
            return None
        try:
            selected_widget = self._dropdown.selected_option
            options = list(reversed(self._dropdown.container.children))  # match values order
            return options.index(selected_widget)
        except Exception:
            return None

    def on_kv_post(self, base_widget):
        try: # Load arrow
            self.arrow_texture = CoreImage(self.arrow_texture_path).texture
        except Exception:
            self.arrow_texture = None
            Logger.warning("FormSpinner: Could not load dropdown arrow texture")
        self.dropdown_cls = partial(
            CustomDropdown,
            border_color=self.dropdown_border_color,
            max_height=dp(300)
        )
        self.option_cls = partial(
            CustomSpinnerOption,
            text_color=self.dropdown_text_color,
            bg_color=self.dropdown_bg_color,
            hover_text_color=self.dropdown_hover_text_color,
            hover_bg_color=self.dropdown_hover_color
        )
        self._init_hint_text()
        Window.bind(on_touch_up=self._check_global_touch)
        Clock.schedule_once(self._add_arrow_image, 0)
        self.bind(hint_text=self._update_hint_text)
        self.bind(show_border=self._update_border, pos=self._update_border, size=self._update_border)
        return super().on_kv_post(base_widget)

    def on_values(self, *args):
        '''Called when spinner values change; clear selected option.'''
        self._dropdown.selected_option = None

    def on_text(self, instance, value):
        if value:
            self.color = self.text_color
            if self.hint_label:
                self.hint_label.opacity = 0
        else:
            self.color = self.hint_text_color
            if self.hint_label:
                self.hint_label.opacity = 1
            if self._dropdown and hasattr(self._dropdown, "selected_option"): #remove selected if text is empty
                if self._dropdown.selected_option:
                    self._dropdown.selected_option.reset_to_normal()
                    self._dropdown.selected_option = None

        self._select(value) # select new value
        self._set_focus(False) # unfocus if picked an option
        self.selected_index = self._get_selected_index()

    def on_enter(self):
        self._is_hovered = True
        if not self.enable_hover:
            return
        cursor_manager.set_cursor('hand')
        if not self.bg_color_instruction or not self.hover_color:
            return
        Animation.cancel_all(self.bg_color_instruction)
        anim = Animation(rgba=self.hover_color, d=DefaultAnimation.HOVER_DURATION, t=DefaultAnimation.HOVER_TRANSITION)
        anim.start(self.bg_color_instruction)

    def on_leave(self):
        self._is_hovered = False
        if not self.enable_hover:
            return
        cursor_manager.reset()
        if  not self.bg_color_instruction or not self.hover_color:
            return
        Animation.cancel_all(self.bg_color_instruction)
        anim = Animation(rgba=self.bg_color, d=DefaultAnimation.HOVER_DURATION, t=DefaultAnimation.HOVER_TRANSITION)
        anim.start(self.bg_color_instruction)

    def on_is_open(self, *args):
        if not self.is_open:
            self._set_focus(False)
        else:
            self._set_focus(True)
        super().on_is_open(*args)

    def _select(self, value):
        '''Utility function, ensure that "select in code" is identical to "select in UI".'''
        if value not in self.values:
            return
        if not self._dropdown:
            self._build_dropdown()  # ensure dropdown exists
        self._dropdown.select(value)

    def _update_hint_text(self, instance, value):
        """Update hint text when hint_text property changes"""
        if not self.hint_label:
            self._init_hint_text()
        if self.hint_label:
            self.hint_label.text = value

    def _init_hint_text(self, *args):
        if not self.text or self.text == "":
            self.hint_label = Label(
                text=self.hint_text,
                color=self.hint_text_color,
                font_size=dp(14),
                size_hint=(1, 1),
                valign='middle',
                halign='left',
                padding=[14, 0]
            )
            self.hint_label.bind(size=self._update_hint_text_size)
            self.add_widget(self.hint_label)
            self.bind(size=self._update_hint_label, pos=self._update_hint_label)
        else:
            self.color = self.text_color

    def _add_arrow_image(self, *args):
        if self.arrow_texture:
            with self.canvas.after:
                arrow_x = self.x + self.width - dp(20)
                self.dropdown_arrow = Rectangle(
                    texture=self.arrow_texture,
                    pos=(arrow_x, self.center_y - dp(6)),
                    size=(dp(12), dp(12))
                )
            self.bind(pos=self._update_arrow_position, size=self._update_arrow_position)

    def _update_arrow_position(self, *args):
        if self.dropdown_arrow:
            arrow_x = self.x + self.width - dp(20)
            self.dropdown_arrow.pos = (arrow_x, self.center_y - dp(6))
            self.dropdown_arrow.size = (dp(12), dp(12))

    def _update_hint_text_size(self, instance, value):
        instance.text_size = instance.size

    def _update_hint_label(self, *args):
        if self.hint_label:
            self.hint_label.size = self.size
            self.hint_label.pos = self.pos
            self.hint_label.text_size = self.hint_label.size

    def _draw_focus(self):
        with self.canvas.after:
            if not self.focus_glow and self.show_focus_glow:
                padding = dp(1.5)
                Color(rgba=self.focus_glow_color)
                self.focus_glow = SmoothLine(rounded_rectangle=(self.x - padding + 0.5, self.y - padding + 0.5, self.width + 2 * padding - 1, self.height + 2 * padding - 1, dp(4) + padding, 100), width=padding)
            if not self.focus_line:
                self.show_border = False
                Color(rgba=self.focus_border_color)
                self.focus_line = SmoothLine(rounded_rectangle=(self.x + 0.5, self.y + 0.5, self.width - 1, self.height - 1, dp(4), 100), width=dp(1))
        self.bind(pos=self._update_lines, size=self._update_lines)

    def _clear_focus(self):
        if self.focus_glow:
            self.canvas.after.remove(self.focus_glow)
            self.focus_glow = None
        if self.focus_line:
            self.show_border = True
            self.canvas.after.remove(self.focus_line)
            self.focus_line = None
        self.unbind(pos=self._update_lines, size=self._update_lines)

    def _set_focus(self, state):
        self.focus = state
        if state:
            self._draw_focus()
        else:
            self._clear_focus()

    def _check_global_touch(self, window, touch):
        if touch.button != "left": #ensure it's left click
            return
        if self._dropdown.collide_point(*touch.pos) and self.is_open:
            self._set_focus(True)
        else:
            self._set_focus(False)

    def _toggle_dropdown(self, *largs):
        '''Overwrite default, dropdown will open even without data'''
        # if self.values:
        #     self.is_open = not self.is_open
        self.is_open = not self.is_open

    def _update_border(self, *args):
        if self.border_line:
            self.canvas.after.remove(self.border_line)
            self.border_line = None
        if self.show_border:
            with self.canvas.after:
                Color(rgba=self.border_color)
                self.border_line = SmoothLine(rounded_rectangle=(self.x + 0.5, self.y + 0.5, self.width - 1, self.height - 1, dp(4), 100), width=dp(1))

    def _update_lines(self, *args):
        if self.focus_glow and self.show_focus_glow:
            self.focus_glow.rounded_rectangle = (self.x + 0.5, self.y + 0.5, self.width - 1, self.height - 1, dp(4))
        if self.focus_line:
            self.focus_line.rounded_rectangle = (self.x + 0.5, self.y + 0.5, self.width - 1, self.height - 1, dp(4))

class FormButton(Button, HoverBehavior):
    '''Button variant used in forms with hover behavior.'''
    bg_color = ColorProperty(COLORS['LIGHT_BLACK'])
    text_color = ColorProperty(COLORS['WHITE'])
    min_width = NumericProperty(dp(100))
    enable_hover = BooleanProperty(True)
    text_key = StringProperty('')
    global cursor_manager # pylint: disable=global-variable-not-assigned

    def __init__(self, **kwargs):
        super(FormButton, self).__init__(**kwargs)
        with self.canvas.before:
            self.bg_color_instruction = Color(rgba=self.bg_color)
            self.rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(4)]
            )
        self.bind(bg_color=self._update_background_color)
        self.bind(pos=self._update_background, size=self._update_background)

        self.hover_darken_per = 0.1
        self.hover_color = [max(c - self.hover_darken_per, 0) for c in self.bg_color[:3]] + [self.bg_color[3]]

    def on_kv_post(self, base_widget):
        self.bind(texture_size=self._update_size)
        return super().on_kv_post(base_widget)

    def _update_background_color(self, instance, value):
        if self.bg_color_instruction:
            self.bg_color_instruction.rgba = value
        if self.enable_hover:
            self.hover_color = [max(c - self.hover_darken_per, 0) for c in value[:3]] + [value[3]]

    def _update_background(self, *args):
        if self.rect:
            self.rect.pos = self.pos
            self.rect.size = self.size

    def _update_size(self, *args):
        padding = dp(30)
        if self.texture_size[0] > 1:
            self.width = max(self.min_width, self.texture_size[0] + padding)
        self.height = dp(40)

    def on_disabled(self, instance, value):
        '''React to disabled state changes and update hover/cursor behavior.'''
        if isinstance(value, bool):
            self.enable_hover = not value
        if hasattr(self, '_is_hovered') and self._is_hovered:
            if value:
                cursor_manager.restore_cursor()
                if self.bg_color_instruction and self.bg_color:
                    Animation.cancel_all(self.bg_color_instruction)
                    anim = Animation(rgba=self.bg_color, d=DefaultAnimation.HOVER_DURATION, t=DefaultAnimation.HOVER_TRANSITION)
                    anim.start(self.bg_color_instruction)
            else:
                cursor_manager.set_cursor('hand')
                if self.bg_color_instruction and self.bg_color:
                    Animation.cancel_all(self.bg_color_instruction)
                    anim = Animation(rgba=self.hover_color, d=DefaultAnimation.HOVER_DURATION, t=DefaultAnimation.HOVER_TRANSITION)
                    anim.start(self.bg_color_instruction)

    def on_enter(self):
        self._is_hovered = True
        if not self.enable_hover:
            return
        cursor_manager.set_cursor('hand')
        if not self.bg_color_instruction or not self.hover_color:
            return
        Animation.cancel_all(self.bg_color_instruction)
        anim = Animation(rgba=self.hover_color, d=DefaultAnimation.HOVER_DURATION, t=DefaultAnimation.HOVER_TRANSITION)
        anim.start(self.bg_color_instruction)

    def on_leave(self):
        self._is_hovered = False
        if not self.enable_hover:
            return
        cursor_manager.reset()
        if  not self.bg_color_instruction or not self.hover_color:
            return
        Animation.cancel_all(self.bg_color_instruction)
        anim = Animation(rgba=self.bg_color, d=DefaultAnimation.HOVER_DURATION, t=DefaultAnimation.HOVER_TRANSITION)
        anim.start(self.bg_color_instruction)

class WindowResizeDetector:
    """Detects and tracks window resize events with start, during, and stop callbacks.

    Monitors the window size at regular intervals and triggers callbacks when
    resizing begins, continues, and ends. Useful for optimizing resize-dependent
    operations by distinguishing between active resizing and resize completion.
    """
    def __init__(self, interval=0.1, stop_delay=0.3, **kwargs):
        super().__init__(**kwargs)
        self._last_size = Window.size
        self._resizing = False
        self._stop_timer = None
        self._interval = interval
        self._stop_delay = stop_delay
        Clock.schedule_interval(self._check_resize, interval)

    def _check_resize(self, dt):
        size = Window.size
        if size == self._last_size:
            return

        if not self._resizing:
            self._resizing = True
            self.on_resize_start(size)
        else:
            self.on_resizing(size)

        self._last_size = size
        if self._stop_timer:
            self._stop_timer.cancel()
        self._stop_timer = Clock.schedule_once(self._end_resize, self._stop_delay)

    def _end_resize(self, *_):
        if self._resizing:
            self._resizing = False
            self.on_resize_stop(self._last_size)

    def on_resize_start(self, size):
        """Called when the user starts resizing the window."""
        pass # pylint: disable=unnecessary-pass

    def on_resizing(self, size):
        """Called repeatedly while the user is resizing the window."""
        pass # pylint: disable=unnecessary-pass

    def on_resize_stop(self, size):
        """Called when the user finishes resizing the window."""
        pass # pylint: disable=unnecessary-pass

class FormContent(BoxLayout, WindowResizeDetector):
    '''Layout container for main content areas of form screens.'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._old_height = self.height
        self.bind(height=self._on_height_change)

    def _on_height_change(self, instance, new_height):
        '''Persistent height'''
        sv = self.parent
        if self._resizing:
            return
        if not isinstance(sv, ScrollView):
            return
        old_height = self._old_height
        self._old_height = new_height

        distance_from_top = (1 - sv.scroll_y) * (old_height - sv.height)

        def restore(*_):
            if new_height > sv.height:
                calculated_scroll_y = 1 - distance_from_top / max((new_height - sv.height), 1)
                # Clamp scroll_y to valid range [0, 1]
                sv.scroll_y = max(0, min(1, calculated_scroll_y))
            else:
                sv.scroll_y = 1
        Clock.schedule_once(restore, -1)

class PaginationButton(Button, HoverBehavior):
    '''Button used for pagination controls with hover support.'''
    active = BooleanProperty(False)

    def __init__(self, **kwargs):
        super(PaginationButton, self).__init__(**kwargs)
        self.disabled_color = [0.6, 0.6, 0.6, 1]
        self.hover_color_instruction = None
        self.hover_rect = None
        self.hover_rgba = [0, 0, 0, 0]  # initial transparent background

        self._init_hover_effect()

    def _init_hover_effect(self):
        """Initialize persistent canvas instructions"""
        with self.canvas.after:
            self.hover_color_instruction = Color(rgba=self.hover_rgba)
            self.hover_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(4)])

        self.bind(pos=self._update_graphics, size=self._update_graphics)

    def _update_graphics(self, *args):
        if self.hover_rect:
            self.hover_rect.pos = self.pos
            self.hover_rect.size = self.size

    def on_disabled(self, instance, value):
        '''Placeholder for disabled state; appearance unchanged by default.'''

    def on_enter(self):
        if not self.disabled and not self.active:
            Animation.cancel_all(self.hover_color_instruction)
            anim = Animation(rgba=[0, 0, 0, 0.1], d=DefaultAnimation.HOVER_DURATION, t=DefaultAnimation.HOVER_TRANSITION)
            anim.start(self.hover_color_instruction)

    def on_leave(self):
        if not self.disabled and not self.active:
            Animation.cancel_all(self.hover_color_instruction)
            anim = Animation(rgba=[0, 0, 0, 0], d=DefaultAnimation.HOVER_DURATION, t=DefaultAnimation.HOVER_TRANSITION)
            anim.start(self.hover_color_instruction)

class FormCheckBox(BoxLayout):
    '''Checkbox control wrapped with label and layout for forms.'''
    group = StringProperty(None)
    text = StringProperty('')
    target_id = StringProperty('')
    active = BooleanProperty(False)
    on_checkbox = ObjectProperty(None)
    enable_conditional_layout = BooleanProperty(False)

    def __init__(self, **kwargs): # pylint: disable=useless-super-delegation
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        self.ids.checkbox.background_checkbox_down = resource_path('app/libs/assets/icons/checkbox_checked_blue.png')
        self.ids.checkbox.background_checkbox_normal = resource_path('app/libs/assets/icons/checkbox_unchecked_black.png')
        self.ids.checkbox.background_radio_down = resource_path('app/libs/assets/icons/radio_checked_blue.png')
        self.ids.checkbox.background_radio_normal = resource_path('app/libs/assets/icons/radio_unchecked_black.png')
        return super().on_kv_post(base_widget)

    def on_checkbox_active(self, value):
        '''Handle checkbox state change and apply conditional layout if enabled.'''
        self.active = value #mirror
        if self.enable_conditional_layout:
            # Find target layout
            target_layout = self.parent
            target_widget = None
            while target_layout:
                if hasattr(target_layout, 'ids') and self.target_id in target_layout.ids:
                    target_widget = target_layout.ids[self.target_id]
                    break
                target_layout = target_layout.parent

            if not target_widget:
                return

            def apply_all_changes(*args):
                if value:
                    target_widget.height = target_widget.minimum_height
                    target_widget.size_hint_x = 1
                    target_widget.width = 0
                    target_widget.opacity = 1
                    target_widget.disabled = False
                    target_widget.pos_hint = {'center_x': 0.5}
                else:
                    target_widget.height = 0
                    target_widget.size_hint_x = None
                    target_widget.width = 0
                    target_widget.opacity = 0
                    target_widget.disabled = True
                    target_widget.pos_hint = {'center_x': -100} #move out of the screen

            Clock.schedule_once(apply_all_changes, 0)

class FormMultiCheckbox(BoxLayout):
    '''Group of checkboxes allowing multiple selections.'''
    label = ListProperty([])
    multi = BooleanProperty(True)
    def __init__(self, **kwargs):
        '''Initialize FormMultiCheckbox and bind label updates.'''
        super().__init__(**kwargs)
        self.bind(label=self.build_checkboxes, multi=self.update_behavior)

    def build_checkboxes(self, *args):
        '''Rebuild checkbox widgets from current label list.'''
        self.clear_widgets()
        for text in self.label:
            checkbox = FormCheckBox(text=text)
            checkbox.on_checkbox_active = self.make_handler(checkbox)
            self.add_widget(checkbox)

    def make_handler(self, current_checkbox):
        '''Return a handler function for checkbox changes (supports single-select mode).'''
        def handler(value):
            if not self.multi and value:
                # Uncheck all others
                for child in self.children:
                    if child is not current_checkbox:
                        child.ids.checkbox.active = False
        return handler

    def update_behavior(self, *args):
        '''Update handlers for child checkboxes when behavior flags change.'''
        for child in self.children:
            child.on_checkbox_active = self.make_handler(child)

class FormRadioButton(BoxLayout):
    '''Radio button group control for single-selection choices.'''
    label = ListProperty([])
    group = StringProperty(None)
    text = StringProperty(None)
    selected_index = NumericProperty(None, allownone=True)

    target_ids = ListProperty([])
    enable_conditional_layout = BooleanProperty(False)

    def on_kv_post(self, base_widget):
        self.build_radio_buttons()
        self.bind(label=self.on_label_change)
        return super().on_kv_post(base_widget)

    def on_label_change(self, instance, value):
        """Được gọi khi label thay đổi (danh sách text của radio buttons)"""
        self.build_radio_buttons(preserve_selection=True)
        instance._previous_label = value # pylint: disable=protected-access

    def on_checkbox_active(self, checkbox, value):
        '''Handle an individual radio checkbox becoming active and update selection/index.'''
        if value:
            self.text = checkbox.parent.text
            self.selected_index = self._get_radio_index(checkbox.parent.text)

            if self.enable_conditional_layout and self.target_ids:
                if self.selected_index is not None:
                    self._handle_conditional_layout(self.selected_index)

    def on_selected_index(self, instance, value):
        '''Update component text.'''
        if value is not None and 0 <= value < len(self.label):
            self.text = self.label[value] #will trigger on_text

    def _get_radio_index(self, selected_text):
        """Tìm index của radio button được chọn"""
        try:
            return self.label.index(selected_text)
        except ValueError:
            return None

    def build_radio_buttons(self, preserve_selection=False):
        """
        Xây dựng lại các radio buttons

        Args:
            preserve_selection (bool): True để giữ nguyên lựa chọn theo index,
                                     False để reset về lựa chọn đầu tiên (mặc định)
        """
        preserve_index = None
        if preserve_selection and self.selected_index is not None:
            if 0 <= self.selected_index < len(self.label):
                preserve_index = self.selected_index
            else:
                print(f"[DEBUG] Cannot preserve index {self.selected_index}, out of range for {len(self.label)} items")

        self.clear_widgets()

        if preserve_index is not None:
            active_index = preserve_index
            self.text = self.label[active_index]
        else:
            if self.label:
                active_index = 0
                self.text = self.label[0]
                self.selected_index = 0
            else:
                active_index = None

        for i, text in enumerate(self.label):
            is_active = i == active_index
            radio = FormCheckBox(text=text, group=self.group, active=is_active)
            radio.ids.checkbox.bind(active=self.on_checkbox_active)
            self.add_widget(radio)

    def on_text(self, instance, text):
        '''Sync checkbox active states to match the radio group's text value.'''
        for child in self.children:
            if hasattr(child, 'text') and child.text == text:
                child.ids.checkbox.active = True
                return

    def _handle_conditional_layout(self, selected_index):
        """Handle conditional layout logic với multiple target_ids"""
        if selected_index >= len(self.target_ids):
            return

        target_layout = self.parent
        scroll_view = None

        # Find ScrollView parent
        parent = self
        while parent:
            if hasattr(parent, 'scroll_y'):  # Found ScrollView
                scroll_view = parent
                break
            parent = parent.parent

        if not scroll_view:
            return

        # Get current scroll_y BEFORE any changes
        original_scroll_y = scroll_view.scroll_y


        all_target_widgets = []

        for i, target_id in enumerate(self.target_ids):
            if target_id:
                widget = self._find_target_widget(target_layout, target_id)
                if widget:
                    all_target_widgets.append((widget, i == selected_index))

        if not all_target_widgets:
            return

        # Get content and important positions BEFORE changes
        content = scroll_view.children[0] if scroll_view.children else None
        if not content:
            return

        # Get content height before changes
        content_height_before = content.height

        # Create a function to apply all changes in a single frame
        def apply_all_changes(*args):
            for widget, should_show in all_target_widgets:
                old_height = widget.height
                if should_show:
                    widget.height = widget.minimum_height
                    widget.size_hint_x = 1
                    widget.width = 0
                    widget.opacity = 1
                    widget.disabled = False
                else:
                    widget.height = 0
                    widget.size_hint_x = None
                    widget.width = 0
                    widget.opacity = 0
                    widget.disabled = True
                print(f"Widget {widget.__class__.__name__}: {old_height} -> {widget.height}")
            for widget, _ in all_target_widgets:
                widget.do_layout()
            content.do_layout()

            def calculate_scroll_after_layout(*args):
                # Now calculate scroll position with updated height
                scrollable_height_before = max(0, content_height_before - scroll_view.height)
                pixels_from_top = (1.0 - original_scroll_y) * scrollable_height_before

                content_height_after = content.height
                scrollable_height_after = max(0, content_height_after - scroll_view.height)

                if scrollable_height_after > 0:
                    new_scroll_y = 1.0 - (pixels_from_top / scrollable_height_after)
                    new_scroll_y = max(0.0, min(1.0, new_scroll_y))
                    scroll_view.scroll_y = new_scroll_y

                Clock.schedule_once(lambda dt: print(f"Verified scroll_y: {scroll_view.scroll_y}"), 0.1)

            # Schedule scroll calculation for next frame
            Clock.schedule_once(calculate_scroll_after_layout, 0)

        Clock.schedule_once(apply_all_changes, 0)

    def _find_target_widget(self, target_layout, target_id):
        """Tìm target widget theo ID"""
        current_layout = target_layout
        while current_layout:
            if hasattr(current_layout, 'ids') and target_id in current_layout.ids:
                return current_layout.ids[target_id]
            current_layout = current_layout.parent
        return None

class FormMarginInput(BoxLayout):
    '''Input control specialized for margin-related numeric values.'''
    error_message = StringProperty(None)
    min_value = NumericProperty(None, allownone=True)
    max_value = NumericProperty(None, allownone=True)
    allow_none = BooleanProperty(True)
    strict = BooleanProperty(False) #cap to min/max
    validation_type = StringProperty("int")

    def on_kv_post(self, base_widget):
        self.ids.margin_input.min_value = self.min_value
        self.ids.margin_input.max_value = self.max_value
        self.ids.margin_input.allow_none = self.allow_none
        self.ids.margin_input.strict = self.strict
        self.ids.margin_input.validation_type = self.validation_type

class ColorPalette(Widget):
    '''Simple horizontal color palette widget for visual selection.'''
    padding = NumericProperty(dp(16))
    offset_pos = NumericProperty(0)
    offset_size = NumericProperty(0)

    colormap_name = StringProperty('JET')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.texture = None
        self._create_gradient()
        self.bind(colormap_name=self._create_gradient)

    def _create_gradient(self, *args):
        '''Create a 1D texture for the rainbow gradient using selected colormap.'''
        size = 256
        texture = Texture.create(size=(size, 1), colorfmt='rgba')
        texture.min_filter = 'linear'
        texture.mag_filter = 'linear'

        buf = b""
        name = self.colormap_name.upper()

        for i in range(size):
            t = i / float(size - 1)
            r, g, b = 0, 0, 0

            if name == 'JET':
                # Jet: Blue -> Cyan -> Green -> Yellow -> Red
                r = max(0, min(1, 1.5 - abs(4.0 * t - 3.0)))
                g = max(0, min(1, 1.5 - abs(4.0 * t - 2.0)))
                b = max(0, min(1, 1.5 - abs(4.0 * t - 1.0)))

            elif name == 'AUTUMN':
                # Autumn: Red -> Yellow (Red=1, Green=0->1, Blue=0)
                r = 1.0
                g = t
                b = 0.0

            elif name == 'BONE':
                # Bone: Grayscale with a hint of blue
                # Simplified approximation
                gray = t
                r = gray
                g = gray
                b = min(1, gray * 1.3) # slightly bluish

                # Better approximation for Bone (like MATLAB):
                # R = (7*t + 0)/8
                # G = (7*t + 1)/8
                # B = (7*t + 2)/8 - capped and mapped properly
                # But simple grayscale + blue tint is often enough for visual cue
                if t < 0.75:
                    r = 0.875 * t
                    g = 0.875 * t + 0.125
                    b = 0.875 * t + 0.25
                else:
                    r = 0.875 * t + 0.125
                    g = 0.875 * t + 0.125
                    b = 0.875 * t + 0.25
                # Let's stick to a simpler standard bone-like gradient
                # 0.0 -> (0,0,0)
                # 0.4 -> (0.3, 0.3, 0.45)
                # 0.7 -> (0.6, 0.7, 0.7)
                # 1.0 -> (1, 1, 1)
                # Actually, let's just use the opencv look-alike logic if possible or simple interpolation
                # Just use the simple one: Red=t, Green=t, Blue=t (Gray) -> wait Bone is distinctive.
                # Let's use simple Gray for now if complicated, or:
                r = t
                g = t
                b = t
                # Bone adds blue component
                if t < 0.75:
                    b = min(1, t * 1.5)

            elif name == 'HOT':
                # Hot: Black -> Red -> Yellow -> White
                # 0.0 - 0.33: Black to Red
                # 0.33 - 0.66: Red to Yellow
                # 0.66 - 1.0: Yellow to White
                if t < 0.35:
                    r = t / 0.35
                    g = 0
                    b = 0
                elif t < 0.75:
                    r = 1.0
                    g = (t - 0.35) / 0.4
                    b = 0
                else:
                    r = 1.0
                    g = 1.0
                    b = (t - 0.75) / 0.25

            elif name == 'RAINBOW':
                # Rainbow: HSV Hue 0->1
                # Red -> Yellow -> Green -> Cyan -> Blue -> Magenta -> Red
                h = (1.0 - t) * 0.8 # Scale to avoid wrapping back to red if desired, or full hue
                # OpenCV Rainbow is usually HSV(h=255-i, s=255, v=255)
                h = t
                # Basic HSV to RGB
                # (Using colorsys for brevity in Rainbow)
                r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)

            else:
                # Default to Jet if unknown
                r = max(0, min(1, 1.5 - abs(4.0 * t - 3.0)))
                g = max(0, min(1, 1.5 - abs(4.0 * t - 2.0)))
                b = max(0, min(1, 1.5 - abs(4.0 * t - 1.0)))

            buf += bytes([int(r*255), int(g*255), int(b*255), 255])

        texture.blit_buffer(buf, colorfmt='rgba', bufferfmt='ubyte')
        self.texture = texture

class FormSlider(BoxLayout):
    '''Slider control wrapped for use within forms.'''
    step = NumericProperty(1)
    share_value = NumericProperty(0)
    min_value = NumericProperty(0, allownone=False)
    max_value = NumericProperty(100000, allownone=False)
    validation_type = StringProperty("int")
    allow_none = BooleanProperty(True)
    error_message = StringProperty(None)
    strict = BooleanProperty(True)
    show_color_palette = BooleanProperty(False)
    colormap_name = StringProperty('JET')

    def on_kv_post(self, base_widget):
        if self.ids.input_box:
            self.ids.input_box.bind(text=self.on_value_textinput)
        if self.ids.slider:
            self.ids.slider.bind(value=self.on_value_slider)

        self.bind(share_value=self.update_input_text)
        self.bind(share_value=self.update_slider_value)
        self.ids.input_box.bind(focus=self.strict_func)
        self.ids.slider.cursor_image = resource_path('app/libs/assets/icons/new-moon.png')
        return super().on_kv_post(base_widget)

    def update_input_text(self, instance, value):
        '''Update the input box text when share_value changes.'''
        if self.ids.input_box:
            self.ids.input_box.text = str(value)

    def update_slider_value(self, instance, value):
        '''Update the slider widget when share_value changes.'''
        if self.ids.slider:
            self.ids.slider.value = value

    def _trunc_float(self, number: float, precision: int = 2) -> float:
        '''Truncate a float to a given number of decimal places without rounding.'''
        factor = 10 ** precision
        return math.trunc(number * factor) / factor

    def on_value_textinput(self, instance, text):
        '''Text input event'''
        try:
            self.unbind(share_value=self.update_input_text) #manually update slider instead of auto

            if text in ['', '-', '-.', '.-', '.', None]: #edge cases -> display slider min
                self.ids.slider.value = self.min_value
                return
            value = int(float(text)) if self.validation_type in ["int", "int_odd"] else self._trunc_float(float(text), 2)

            if value > self.max_value:
                self.ids.slider.value = self.max_value
            elif value < self.min_value:
                self.ids.slider.value = self.min_value
            else:
                self.share_value = value
            return
        except Exception:
            traceback.print_exc()
            return
        finally:
            self.bind(share_value=self.update_input_text) #re-bind
            self.ids.input_box.cursor = (len(str(self.share_value)), 0)

    def on_value_slider(self, instance, value):
        '''Slider event'''
        try:
            self.share_value = int(value) if self.validation_type in ["int", "int_odd"] else self._trunc_float(float(value), 2)
            self.ids.input_box.cursor = (len(str(self.share_value)), 0)
        except Exception:
            traceback.print_exc()
            return

    def strict_func(self, instance, value):
        '''Custom strict rules, cap invalid values to min/max.'''
        if not instance.focus:
            try:
                if instance.text:
                    value = int(instance.text) if self.validation_type in ["int", "int_odd"] else self._trunc_float(float(instance.text), 2)
                else:
                    return
            except ValueError:
                instance.error_message = "overall_error_popup"
                return
            try:
                if instance.strict:
                    if instance.max_value is not None and value > instance.max_value:
                        instance.text = str(instance.max_value)
                    elif instance.max_value is not None and value < instance.min_value:
                        instance.text = str(instance.min_value)
            except Exception:
                traceback.print_exc()

class FormImageUploadButton(BoxLayout):
    '''Control for selecting and uploading images from disk.'''
    image_source = StringProperty("")
    __events__ = ('on_image_selected',)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.blocker = TouchBlocker(allow_scroll=False)

    def open_filechooser(self):
        """Mở hộp thoại chọn thư mục và chặn cửa sổ chính"""
        Window.add_widget(self.blocker)
        threading.Thread(target=self._open_filechooser_thread).start()

    def _open_filechooser_thread(self):
        try:
            root = Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            file_path = filedialog.askopenfilename(
                filetypes=[("Image files", "*.png;*.jpg;*.jpeg")],
                initialdir=os.path.abspath(os.sep)
            )
            root.destroy()
            self._set_image_source(file_path)
        except Exception:
            traceback.print_exc()
        finally:
            self._remove_blocker()

    @mainthread
    def _set_image_source(self, file_path):
        self.image_source = file_path
        self.dispatch('on_image_selected', self.image_source)

    @mainthread
    def _remove_blocker(self):
        Window.remove_widget(self.blocker)

    def on_image_selected(self, source_path):
        '''Event hook called when an image is selected; override as needed.'''
        pass # pylint: disable=unnecessary-pass

class FormOpenFolderButton(BoxLayout):
    '''Button to open a folder chooser dialog and return a selected path.'''
    text = StringProperty('Duyệt')
    path = StringProperty('')
    def open_directory_in_explorer(self):
        '''Opens the current path in the system's file explorer. Climbs up the path until it finds an existing directory. If no directory is found, it falls back to the root of the drive or filesystem.'''
        current_path = Path(self.path)

        while not current_path.is_dir(): # Climb up until we find an existing directory
            Logger.warning("FormOpenFolderButton: Path does not exist: %s", current_path)
            if current_path.parent == current_path:  # root
                break
            current_path = current_path.parent

        if not current_path.is_dir(): # Fallback: use root of drive or filesystem
            if platform.system() == "Windows":
                if current_path.drive:
                    current_path = Path(current_path.drive + "\\")   #"D:\\"
                else:
                    current_path = Path("C:\\")
            else:
                current_path = Path("/")

        try:
            Logger.info("FormOpenFolderButton: Opening %s", current_path)
            if platform.system() == "Windows":
                subprocess.Popen(["explorer", str(current_path)])
            else:
                subprocess.Popen(["xdg-open", str(current_path)])
        except Exception:
            Logger.exception("FormOpenFolderButton: Failed to open folder")

class FormFolderCreateButton(BoxLayout):
    '''Button that creates a new folder when activated.'''
    text = StringProperty('')
    path = StringProperty('')
    folder_name = StringProperty('')
    __events__ = ('on_press', 'on_folder_created')

    def _folder_created(self, *args):
        """Callback when folder is created"""
        self.dispatch('on_folder_created')

    def on_press(self, *args):
        '''User defined, add path and folder_name info here'''
        return

    def on_folder_created(self, *args):
        '''Event hook fired after a folder is created (override as needed).'''
        return

    def create_folder(self):
        '''Create a folder at `path/folder_name` and emit folder created event.'''
        try:
            if self.path and self.folder_name:
                os.makedirs(os.path.join(self.path, self.folder_name), exist_ok=True)
                self._folder_created()
                print(f"Created folder {self.folder_name}.")
            else:
                print(f"Path: {self.path}, Folder Name: {self.folder_name}")
                print("Cannot create folder.")
        except Exception as e:
            print(f"Error creating folder at {self.path}: {e}")

class FolderChooserButton(BoxLayout, EventDispatcher):
    '''Composite widget to choose folders and dispatch selection events.'''
    target_input = ObjectProperty(None)
    text = StringProperty("Duyệt")
    __events__ = ("on_folder_selected",)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.register_event_type('on_folder_selected')
        self.blocker = TouchBlocker(allow_scroll=False)

    def _open_folderchooser_thread(self):
        """Mở hộp thoại chọn thư mục và chặn cửa sổ chính"""
        try:
            root = Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            folder_path = filedialog.askdirectory(
                initialdir=r'C:\\'
            )
            root.destroy()
            if folder_path:
                self._folder_selected(folder_path)
        except Exception:
            traceback.print_exc()
        finally:
            self._remove_blocker()

    def choose_folder(self):
        '''Open a folder chooser in a background thread and block UI while open.'''
        Window.add_widget(self.blocker)
        threading.Thread(target=self._open_folderchooser_thread).start()

    @mainthread
    def _folder_selected(self, folder_path):
        """Callback khi thư mục được chọn"""
        if folder_path:
            if self.target_input:
                self.target_input.text = os.path.normpath(folder_path)
            self.dispatch('on_folder_selected', folder_path)

    @mainthread
    def _remove_blocker(self):
        Window.remove_widget(self.blocker)

    def on_folder_selected(self, folder_path):
        '''Event handler stub for folder selection; override as needed.'''

class Day(FormButton):
    '''Button representing a day in a calendar/date-picker.'''
    datepicker = ObjectProperty(None) # Reference to FormDatePicker

    def on_kv_post(self, base_widget):
        with self.canvas.before:
            self.bg_color = COLORS['TRANSPARENT']
            self.bg_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(4)])

        self.bind(pos=self._update_rect, size=self._update_rect)
        self.datepicker.bind(picked=self._update_color)

        self._update_rect()
        self._update_color()

    def on_release(self):
        if not self.text:
            return
        self.datepicker.picked = [
            self.datepicker.year,
            self.datepicker.month,
            int(self.text)
        ]

    def _update_rect(self, *args):
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size

    def _update_color(self, *args):
        try:
            if self.datepicker.picked:
                if (
                    self.text
                    and str(self.datepicker.year) == str(self.datepicker.picked[0])
                    and str(self.datepicker.month) == str(self.datepicker.picked[1])
                    and str(int(self.text)) == str(self.datepicker.picked[2])
                ):
                    #active
                    self.bg_color = COLORS['BLUE']
                    self.text_color = COLORS['WHITE']
                else:
                    #inactive
                    self.bg_color = COLORS['TRANSPARENT']
                    self.text_color = COLORS['MEDIUM_GRAY']
        except Exception:
            traceback.print_exc()

class FormDatePicker(BoxLayout):
    '''Date picker composed of day buttons and navigation controls.'''
    calendar = Calendar()
    months = ListProperty([str(i) for i in range(1, 13)])
    days = ListProperty()
    year = NumericProperty(2020)
    month = NumericProperty(1)
    picked = ListProperty(["2020","01","01"])
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.register_event_type("on_today_button")
        today_year, today_month, today_day = self.get_today()
        self.year = int(today_year)
        self.month = int(today_month)
        self.picked = [self.year, self.month, int(today_day)]
        self._build_date_list()
        self._build_weeks()

    def on_kv_post(self, base_widget):
        self.bind(year=self._build_date_list, month=self._build_date_list)
        self.bind(year=self._build_weeks, month=self._build_weeks)
        return super().on_kv_post(base_widget)

    def get_today(self):
        '''Return today's date as [YYYY, MM, DD] strings.'''
        today = date.today()
        return [f"{today.year:04d}", f"{today.month:02d}", f"{today.day:02d}"]

    def _build_date_list(self, *args):
        '''Rebuild the date list'''
        months_list = [str(i) for i in range(1, 13)]

        days_list = [
            (i if i > 0 else "") for i in self.calendar.itermonthdays(self.year, self.month)
        ]
        # Add padding to always fit into 6 weeks (42 days)
        while len(days_list) < 42:
            days_list.append("")

        self.months = months_list
        self.days = days_list

    def _build_weeks(self, *args):
        '''Create 6 rows x 7 Day widgets dynamically'''
        try:
            container = self.ids.weeks_container
            container.clear_widgets()

            for week in range(6):
                row = BoxLayout(spacing=dp(5))
                for day in range(7):
                    idx = week * 7 + day

                    is_future_day = False
                    is_not_empty = False
                    if self.days[idx]:
                        if self.days[idx] != "":
                            is_not_empty = True
                        if date(self.year, self.month, int(self.days[idx])) > date.today():
                            is_future_day = True

                    d = Day(
                        datepicker=self,
                        text=str(self.days[idx]) if self.days[idx] else "",
                        disabled=is_future_day or not is_not_empty,
                    )
                    row.add_widget(d)
                container.add_widget(row)
        except Exception:
            traceback.print_exc()

    def on_today_button(self):
        '''Reset picker to today's date.'''
        today_year, today_month, today_day = self.get_today()
        self.year = int(today_year)
        self.month = int(today_month)
        self.picked = [self.year, self.month, int(today_day)]

class FormDateInput(FormInput):
    '''Text input specialized for date entry with validation.'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.readonly=True
        self.cursor_width=0

        # create dropdown + datepicker once
        self.dropdown = DropDown(auto_width=False, dismiss_on_select=False, auto_dismiss=True)
        self.datepicker = FormDatePicker()

        # sync dropdown size to datepicker size
        self.dropdown.width = self.datepicker.width
        self.dropdown.max_height = self.datepicker.height

        self.dropdown.add_widget(self.datepicker)
        self.datepicker.bind(picked=self._on_date_picked)
        #self.datepicker.bind(on_today_button=self.hide_datepicker)

        self.dropdown.bind(on_dismiss=self._on_dropdown_dismiss)

        #load calendar icon
        try:
            self.calendar_texture = CoreImage(resource_path('app/libs/assets/icons/calendar.png')).texture
            self._draw_calendar()
        except Exception:
            self.calendar_texture = None

    def _draw_calendar(self):
        if self.calendar_texture:
            with self.canvas.after:
                self.calendar_icon = Rectangle(
                    texture=self.calendar_texture,
                    pos=(self.x + self.width - dp(24), self.center_y - dp(8)),
                    size=(dp(14), dp(14))
                )
            self.bind(pos=self.update_calendar_icon_pos, size=self.update_calendar_icon_pos)

    def update_calendar_icon_pos(self, *args):
        '''Reposition calendar icon to match widget geometry.'''
        if self.calendar_icon:
            self.calendar_icon.pos = (self.x + self.width - dp(24), self.center_y - dp(8))
            self.calendar_icon.size = (dp(14), dp(14))

    def on_focus(self, instance, value):
        return

    def on_touch_down(self, touch):
        super().on_touch_down(touch)
        if self.collide_point(*touch.pos):
            self._on_dropdown_open()
            self.show_datepicker()

    def _on_dropdown_dismiss(self, *args):
        self.focus = False
        super().on_focus(instance=self, value=self.focus)

    def _on_dropdown_open(self):
        self.focus = True
        super().on_focus(instance=self, value=self.focus)

    def _on_date_picked(self, instance, date): # pylint: disable=redefined-outer-name
        '''Handle when a date is chosen from the picker and update the text.'''
        self.text = f"{date[0]}/{date[1]:0>2}/{date[2]:0>2}"
        self.hide_datepicker()

    def show_datepicker(self):
        '''Open the datepicker dropdown attached to this input.'''
        if self.text:
            try:
                y, m, d = map(int, self.text.split('/'))
                self.datepicker.year = y
                self.datepicker.month = m
                self.datepicker.picked = [y, m, d]
            except Exception:
                pass
        if not self.dropdown.attach_to:
            self.dropdown.open(self)

    def hide_datepicker(self,  *args):
        '''Close the datepicker dropdown if open.'''
        if self.dropdown.attach_to:
            self.dropdown.dismiss()

    def reset_to_today(self):
        '''Reset the input to today's date and close the picker.'''
        self.datepicker.dispatch("on_today_button")
        date = self.datepicker.picked # pylint: disable=redefined-outer-name
        self.text = f"{date[0]}/{date[1]:0>2}/{date[2]:0>2}"
        self.hide_datepicker()

class FormDeleteButton(Button, HoverBehavior):
    '''Button used to delete items from lists or tables.'''
    enable_hover = BooleanProperty(True)
    global cursor_manager # pylint: disable=global-variable-not-assigned

    def __init__(self, **kwargs): # pylint: disable=useless-super-delegation
        super().__init__(**kwargs)

    def on_kv_post(self, base_widget):
        self.background_normal = resource_path('app/libs/assets/icons/delete.png')
        self.background_down = resource_path('app/libs/assets/icons/delete.png')
        return super().on_kv_post(base_widget)

    def on_enter(self):
        if self.enable_hover:
            cursor_manager.set_cursor("hand")

    def on_leave(self):
        cursor_manager.restore_cursor()

class FormAsyncImage(AsyncImage):
    '''AsyncImage wrapper with additional application-specific handling.'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fallback_source = resource_path('app/libs/assets/icons/no_image.png')
        self.unbind(source=self._load_source) #unbind kivy default
        self.fbind('source', self._safe_load_source)

    def _safe_load_source(self, *args):
        src = self.source
        if src and not self.is_uri(src):
            resolved = resource_find(src)
            if not resolved or not os.path.exists(resolved):
                Logger.warning("FormAsyncImage: Missing <%s>, using fallback.", src)
                self.source = self.fallback_source
                return
        super()._load_source(*args)


#--------------------Font Size Components--------------------


class SectionHeader(Label):
    '''Large header label used to separate sections in the UI.'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.bold = True
        self.font_size = dp(22.4)
        self.color = COLORS['BLUE_BLACK']
        self.padding = [dp(14), 0, dp(14), 0]  # left, top, right, bottom
        self.text_size = (self.width, None)

        # Bind updates when size or texture changes
        self.bind(width=self._update_text_size)
        self.bind(texture_size=self._update_height)
        self.bind(pos=self._update_canvas, size=self._update_canvas)

        with self.canvas.before:
            self._color = COLORS['CYAN']
            self._rect = Rectangle()

        self._update_text_size()
        self._update_height()
        self._update_canvas()

    def _update_text_size(self, *args):
        self.text_size = (self.width, None)
        self._update_height()

    def _update_height(self, *args):
        # Height = text height + dp(30)
        self.height = self.texture_size[1] + dp(30)
        self._update_canvas()

    def _update_canvas(self, *args):
        # Rectangle pos and size (vertical bar on left)
        self._rect.pos = (self.x, self.y + dp(5))
        self._rect.size = (dp(4), self.height - dp(15))


class SubSectionHeader(Label):
    '''Smaller header label used for subsections.'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.bold = True
        self.font_size = dp(19.2)
        self.color = COLORS['BLUE_BLACK']
        self.padding = [0, 0, 0, dp(10)]
        self.text_size = (self.width, None)

        self.bind(width=self._update_text_size)
        self.bind(texture_size=self._update_height)
        self.bind(pos=self._update_canvas, size=self._update_canvas)

        with self.canvas.after:
            self._color = Color(*COLORS['LIGHT_BLUE_GRAY'])
            self._line = SmoothLine(width=dp(1))

        self._update_text_size()
        self._update_height()
        self._update_canvas()

    def _update_text_size(self, *args):
        self.text_size = (self.width, None)
        self._update_height()

    def _update_height(self, *args):
        self.height = self.texture_size[1] + dp(20)
        self._update_canvas()

    def _update_canvas(self, *args):
        y_line = self.y + dp(7.5)
        self._line.points = [self.x, y_line, self.x + self.width, y_line]



#--------------------Table Components--------------------


class TableHeaderCell(BoxLayout):
    '''Header cell used in data table column headers.'''
    text = StringProperty(None)

    def __init__(self, **kwargs):
        '''Initialize TableHeaderCell and bind width updates.'''
        super().__init__(**kwargs)
        self.bind(width=self.update_size_hint_x) # this can be overwrite by DataTable cols_width

    def update_size_hint_x(self, *args):
        '''Update size_hint_x'''
        scaling_factor = 0.06 # Adjust this to control the influence of text length
        self.size_hint_x = min(len(self.text) * scaling_factor, 1)
        #print(self.text, self.size_hint_x)

class TableCell(BoxLayout):
    '''Standard data cell used inside tables.'''
    min_height = NumericProperty(dp(50))
    text = StringProperty(None)
    text_key = StringProperty("")
    format_args = ObjectProperty(None)
    row_index = NumericProperty(0)
    text_color = ListProperty([])
    enable_markup = BooleanProperty(False)

    def __init__(self, **kwargs):
        '''Initialize TableCell and bind width updates.'''
        super().__init__(**kwargs)
        self.bind(width=self.update_size_hint_x) # this can be overwrite by DataTable cols_width

    def update_size_hint_x(self, *args):
        '''Update size_hint_x'''
        scaling_factor = 0.06  # Adjust this to control the influence of text length
        self.size_hint_x = min(len(self.text) * scaling_factor, 1)
        #print(self.text, self.size_hint_x)

class TableImageCell(BoxLayout):
    '''Table cell that displays an image thumbnail.'''
    min_height = NumericProperty(dp(50))
    image_source = StringProperty(None)
    row_index = NumericProperty(0)

class TableButtonCell(BoxLayout): # Edit and Delete buttons
    '''Cell containing action buttons such as Edit and Delete.'''
    min_height = NumericProperty(dp(50))
    row_index = NumericProperty(0)
    table_manager = ObjectProperty(None)
    custom_message = BooleanProperty(False)  # Allow custom delete message
    def __init__(self, **kwargs):
        '''Initialize TableButtonCell and get application instance.'''
        super().__init__(**kwargs)
        self.app = App.get_running_app()

    def on_kv_post(self, base_widget):
        '''Post-KV initialization: prepare confirmation popup instance.'''
        self.popup = MyPopup()
        return super().on_kv_post(base_widget)

    def edit_item(self):
        '''Load the corresponding table row into the form for editing.'''
        actual_index = ((self.table_manager.current_page - 1) *
                       self.table_manager.rows_per_page + self.row_index)

        if actual_index >= len(self.table_manager.all_rows):
            return

        item = self.table_manager.all_rows[actual_index]
        screen = self.table_manager.screen

        try:
            screen.load_item_to_form(item)
            return True
        except Exception:
            traceback.print_exc()
            error_popup = self.popup.create_adaptive_popup(
                title="error_popup",
                message="Lỗi khi tải lại dữ liệu"
            )
            error_popup.open()
            return False

    def on_delete_button(self):
        '''Prompt for confirmation and delete the associated item on confirm.'''
        if not self.table_manager:
            return

        actual_index = ((self.table_manager.current_page - 1) *
                        self.table_manager.rows_per_page + self.row_index)

        if actual_index >= len(self.table_manager.all_rows):
            return

        item = self.table_manager.all_rows[actual_index]
        screen = self.table_manager.screen

        def on_confirm():
            try:
                screen.delete_item(item) # Define delete_item function in the screen

                # Pagination logic fix
                total_rows = len(self.table_manager.all_rows)
                rows_per_page = self.table_manager.rows_per_page
                total_pages = max(1, math.ceil(total_rows / rows_per_page))
                if self.table_manager.current_page > total_pages:
                    self.table_manager.current_page = total_pages
                start = (self.table_manager.current_page - 1) * rows_per_page
                if start >= total_rows and self.table_manager.current_page > 1:
                    self.table_manager.current_page -= 1

                self.table_manager.display_current_page()
                self.table_manager.create_pagination_controls()
                return True

            except Exception:
                traceback.print_exc()
                return False

        confirmation_popup = self.popup.create_confirmation_popup(
            title='confirm_popup',
            message= screen.get_delete_warning_message(item), # Define get_delete_warning_message function in the screen
            on_confirm=on_confirm
        )
        def _on_confirmation_popup_dismiss(popup_instance):
            """Handle khi popup bị dismiss (đóng mà không confirm)"""
            cursor_manager.reset()
        confirmation_popup.bind(on_dismiss=_on_confirmation_popup_dismiss)
        confirmation_popup.open()

class TableBackupButtonCell(BoxLayout): #Backup button
    '''Cell containing a backup action button.'''
    min_height = NumericProperty(dp(50))
    row_index = NumericProperty(0)
    table_manager = ObjectProperty(None)
    custom_message = BooleanProperty(False)  # Allow custom delete message
    _is_ready = BooleanProperty(False)

    def on_parent(self, instance, value):
        '''Check if the widget is ready'''
        if value:
            Clock.schedule_once(lambda dt: setattr(self, '_is_ready', True), 0)
        else:
            self._is_ready = False

    def on_kv_post(self, base_widget):
        '''Post-KV: prepare popup instance for backup actions.'''
        self.popup = MyPopup()
        return super().on_kv_post(base_widget)

    def edit_item(self):
        '''Trigger backup action for the row associated with this cell.'''
        # Fix ghost clicks
        if not self._is_ready or not self.parent or not self.table_manager:
            return

        actual_index = ((self.table_manager.current_page - 1) *
                       self.table_manager.rows_per_page + self.row_index)

        if actual_index >= len(self.table_manager.all_rows):
            return

        item = self.table_manager.all_rows[actual_index]
        screen = self.table_manager.screen

        try:
            screen.backup_item(item) #define in screen
            return True
        except Exception:
            traceback.print_exc()
            error_popup = self.popup.create_adaptive_popup(
                title="Lỗi",
                message="Lỗi khi sao lưu dữ liệu."
            )
            error_popup.open()
            return False


class TableCopyButtonCell(BoxLayout): #Copy button
    '''Cell containing a copy-to-clipboard action button.'''
    min_height = NumericProperty(dp(50))
    row_index = NumericProperty(0)
    table_manager = ObjectProperty(None)
    custom_message = BooleanProperty(False)  # Allow custom delete message
    disable_edit_button = BooleanProperty(False)

    def __init__(self, **kwargs):
        '''Initialize TableCopyButtonCell and obtain app instance.'''
        super().__init__(**kwargs)
        self.app = App.get_running_app()

    def on_kv_post(self, base_widget):
        '''Post-KV setup: prepare popup instance for copy actions.'''
        self.popup = MyPopup()
        return super().on_kv_post(base_widget)
    def edit_item(self):
        '''Open the item in edit mode in the target screen.'''
        actual_index = ((self.table_manager.current_page - 1) *
                       self.table_manager.rows_per_page + self.row_index)

        if actual_index >= len(self.table_manager.all_rows):
            return

        item = self.table_manager.all_rows[actual_index]
        screen = self.table_manager.screen

        try:
            screen.load_item_to_form(item, edit_mode=True)
            return True
        except Exception:
            traceback.print_exc()
            error_popup = self.popup.create_adaptive_popup(
                title="error_popup",
                message="Lỗi khi tải lại dữ liệu"
            )
            error_popup.open()
            return False

    def copy_item(self):
        '''Copy the item into a new form instance (non-edit mode).'''
        actual_index = ((self.table_manager.current_page - 1) *
                       self.table_manager.rows_per_page + self.row_index)

        if actual_index >= len(self.table_manager.all_rows):
            return

        item = self.table_manager.all_rows[actual_index]
        screen = self.table_manager.screen

        try:
            screen.load_item_to_form(item, edit_mode=False)
            return True
        except Exception:
            traceback.print_exc()
            error_popup = self.popup.create_adaptive_popup(
                title="error_popup",
                message="Lỗi khi sao chép dữ liệu"
            )
            error_popup.open()
            return False

    def on_delete_button(self):
        '''Handle delete events with confirmation for copy cell variant.'''
        if not self.table_manager:
            return

        actual_index = ((self.table_manager.current_page - 1) *
                        self.table_manager.rows_per_page + self.row_index)

        if actual_index >= len(self.table_manager.all_rows):
            return

        item = self.table_manager.all_rows[actual_index]
        screen = self.table_manager.screen

        def on_confirm():
            try:
                screen.delete_item(item) # Define delete_item function in the screen

                # Pagination logic fix
                total_rows = len(self.table_manager.all_rows)
                rows_per_page = self.table_manager.rows_per_page
                total_pages = max(1, math.ceil(total_rows / rows_per_page))
                if self.table_manager.current_page > total_pages:
                    self.table_manager.current_page = total_pages
                start = (self.table_manager.current_page - 1) * rows_per_page
                if start >= total_rows and self.table_manager.current_page > 1:
                    self.table_manager.current_page -= 1

                self.table_manager.display_current_page()
                self.table_manager.create_pagination_controls()
                return True

            except Exception:
                traceback.print_exc()
                return False

        confirmation_popup = self.popup.create_confirmation_popup(
            title='confirm_popup',
            message= screen.get_delete_warning_message(item), # Define get_delete_warning_message function in the screen
            on_confirm=on_confirm
        )
        def _on_confirmation_popup_dismiss(popup_instance):
            """Handle khi popup bị dismiss (đóng mà không confirm)"""
            cursor_manager.reset()
        confirmation_popup.bind(on_dismiss=_on_confirmation_popup_dismiss)
        confirmation_popup.open()


class DataTable(GridLayout):
    '''Grid-based table widget for displaying tabular data.'''
    border_color = ListProperty([0.5, 0.5, 0.5, 1])  # default gray
    cols_width = ListProperty(None)
    cols = NumericProperty(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._schedule_redraw, size=self._schedule_redraw,
                  cols=self._schedule_redraw, rows=self._schedule_redraw)
        if self.cols_width:
            if len(self.cols_width) != self.cols:
                raise ValueError("'cols_width' len  must be equal to 'cols'")

    def _schedule_redraw(self, *args):
        #Clock.unschedule(self._redraw)
        Clock.schedule_once(self._redraw, -1)

    def _redraw(self, *args):
        if not self.children or not self.cols:
            return

        rows = {}
        self.canvas.before.clear()
        self.canvas.after.clear()

        with self.canvas.before:
            StencilPush()
            Rectangle(pos=self.pos, size=self.size)  # clipping mask
            StencilUse()

            for child in self.children:
                if child.x == 0 or child.y == 0:
                    return
                rows.setdefault(child.y, []).append(child)

            rows = dict(sorted(rows.items(), reverse=True))

            for idx, (row_y, row_children) in enumerate(rows.items()):
                row_height = max(c.height for c in row_children) #equalize height for each cell added in the row (horizontally)
                if idx == 0:
                    # header
                    Color(rgba=COLORS['BLUE_BLACK'])
                    Rectangle(pos=(self.x, row_y), size=(self.width, row_height))
                elif self.has_data and idx % 2 == 1: # zebra stripes
                    Color(rgba=COLORS['WHITE_SMOKE'])
                    Rectangle(pos=(self.x, row_y), size=(self.width, row_height))

        with self.canvas.after:
            StencilUnUse()
            Rectangle(pos=self.pos, size=self.size)
            StencilPop()



#--------------------Composite Components--------------------


class CompFormInput(FormGroup):
    '''Component wrapper for a labeled form input.'''
    #LABEL PROPERTIES
    use_label_text_key =  BooleanProperty(True)
    label_markup = BooleanProperty(True)# must be True if using suggest_text
    label_text = StringProperty('')
    label_required = BooleanProperty(False)
    label_width = NumericProperty(dp(300), allownone=True)
    label_bold = BooleanProperty(True)
    suggest_text = StringProperty('')
    suggest_text_font_size = NumericProperty(dp(12))

    #VALIDATION PROPERTIES
    validation_type = OptionProperty('string', options=['string', 'int', 'int_odd', 'float'])
    min_value = NumericProperty(None, allownone=True)#for int, float
    max_value = NumericProperty(None, allownone=True)
    allow_negative = BooleanProperty(False)
    min_length = NumericProperty(None, allownone=True)#for string
    max_length = NumericProperty(None, allownone=True)
    strict = BooleanProperty(False) #cap the value to max/min if exceeded
    allow_none = BooleanProperty(True) #allow empty

    #FORMINPUT PROPERTIES
    hint_text = StringProperty('')
    text = StringProperty('')
    show_triangle_buttons = BooleanProperty(False)
    force_half_width = BooleanProperty(False)
    regex_filter = StringProperty(None)
    step = NumericProperty(1)
    disabled = BooleanProperty(False)

class CompFormSpinner(FormGroup):
    '''Component wrapper for a labeled spinner control.'''
    #LABEL PROPERTIES
    label_text = StringProperty('')
    label_required = BooleanProperty(False)
    label_width = NumericProperty(dp(300), allownone=True)
    label_bold = BooleanProperty(True)
    suggest_text = StringProperty('')
    suggest_text_font_size = NumericProperty(dp(12))

    #VALIDATION PROPERTIES
    validation_type = OptionProperty('string', options=['string', 'int', 'int_odd', 'float'])
    min_value = NumericProperty(None, allownone=True)#for int, float
    max_value = NumericProperty(None, allownone=True)
    allow_negative = BooleanProperty(False)
    min_length = NumericProperty(None, allownone=True)#for string
    max_length = NumericProperty(None, allownone=True)
    strict = BooleanProperty(False) #cap the value to max/min if exceeded
    allow_none = BooleanProperty(True) #allow empty

    #FORMSPINNER PROPERTIES
    hint_text = StringProperty('')
    text = StringProperty('')
    values = ListProperty([])
    callback_on_text = ObjectProperty(None, allownone=True)

class CompFormSlider(FormGroup):
    '''Component wrapper for a labeled slider control.'''
    #LABEL PROPERTIES
    label_text = StringProperty('')
    label_required = BooleanProperty(False)
    label_width = NumericProperty(dp(300), allownone=True)
    label_bold = BooleanProperty(True)
    suggest_text = StringProperty('')
    suggest_text_font_size = NumericProperty(dp(12))

    #VALIDATION PROPERTIES
    validation_type = OptionProperty('int', options=['int', 'int_odd', 'float'])
    min_value = NumericProperty(0, allownone=False)#for int, float
    max_value = NumericProperty(100000, allownone=False)
    strict = BooleanProperty(True) #cap the value to max/min if exceeded
    allow_none = BooleanProperty(True) #allow empty

    #FORMSLIDER PROPERTIES
    hint_text = StringProperty('')
    text = StringProperty('')
    values = ListProperty([])
    step = NumericProperty(1)
    show_color_palette = BooleanProperty(False)
    colormap_name = StringProperty('JET')


#--------------------Image Group Components--------------------



class ImageFrame(BoxLayout):
    '''Container framing images with optional controls.'''
    source = StringProperty("")
    placeholder = StringProperty("")
    border_color = ListProperty(COLORS['BLUE'])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._no_image_instruction = None
        self.bind(source=self._check_no_image, pos=self._check_no_image, size=self._check_no_image, placeholder=self._check_no_image)
        Clock.schedule_once(lambda dt: self._check_no_image(), 0)

    def _check_no_image(self, *args):
        if self._no_image_instruction:
            self.canvas.after.remove(self._no_image_instruction)
            self._no_image_instruction = None

        if not self.source:
            label = CoreLabel(text=self.placeholder, font_size=20)
            label.refresh()
            texture = label.texture
            tex_size = texture.size

            x = self.x + (self.width - tex_size[0]) / 2
            y = self.y + (self.height - tex_size[1]) / 2

            with self.canvas.after:
                Color(0.6, 0.6, 0.6, 1)
                self._no_image_instruction = Rectangle(
                    texture=texture,
                    pos=(x, y),
                    size=tex_size
                )

class CustomScrollView(RecycleView):
    '''Customized scroll view / recycle view for specific item rendering.'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bar_width = 0  # disable default scroll bar
        self.bar_margin = dp(-100)
        self.scroll_type = ['bars']  # only scroll content

        # variables to track dragging state
        self._is_dragging = False
        self._touch_start_y = 0
        self._drag_offset_y = 0  # offset to keep relative position while dragging
        self._is_scrollbar_visible = True
        self._hide_timer = None
        self._last_scroll_y = 0  # track previous scroll_y
        self._has_moved = False  # flag to track whether a drag occurred

        # variables for long-press logic
        self._press_event = None
        self.long_press_time = 1.0

        # initialize graphics after super().__init__ completes
        Clock.schedule_once(self._init_graphics, 0)

        # update on each scroll
        self.bind(scroll_y=self._update_bar, size=self._update_bar, pos=self._update_bar)
        # separate bind for scroll_y to detect changes
        self.bind(scroll_y=self._on_scroll_y_change)
        # bind to children changes to update
        self.bind(children=self._on_children_change)

    def _init_graphics(self, dt):
        """Initialize graphics after the widget is ready."""
        with self.canvas.after:
            self._track_color_instruction = Color(0, 0, 0, 0)
            self.track_rect = Rectangle(size=(10, 50), pos=(0, 0))

            self._bar_color_instruction = Color(0, 0, 0, 0)
            self.bar_rect = Rectangle(size=(10, 50), pos=(0, 0))

    def _on_children_change(self, *args):
        """Called when children change; schedule update after layout completes."""
        Clock.schedule_once(self._delayed_update, 0)

    def _delayed_update(self, dt):
        """Update after layout has been completed."""
        self._update_bar()

    def _on_scroll_y_change(self, instance, value):
        """Called when scroll_y changes - specific to this widget."""
        # Only show scrollbar if scroll_y actually changed
        if abs(value - self._last_scroll_y) > 0.001:  # threshold to avoid floating point errors
            self._show_scrollbar()
            self._schedule_hide_scrollbar()
            self._last_scroll_y = value

    def _calculate_bar_size(self):
        """Calculate scrollbar size based on the viewport/content ratio."""
        min_height = 40
        if not hasattr(self, 'children') or not self.children:
            return min_height  # min height same as Kivy

        child = self.children[0]

        # check if height is not set or zero
        if self.height <= 0 or child.height <= 0:
            return min_height  # fallback to min height

        if child.height <= self.height:
            return min_height  # content smaller than viewport, use min height

        # ratio viewport/content * viewport height
        ratio = self.height / child.height
        bar_height = ratio * self.height

        # ensure min height = 40 (like Kivy)
        return max(min_height, bar_height)

    def _is_scrollbar_needed(self):
        """Check whether a scrollbar is needed."""
        if not hasattr(self, 'children') or not self.children:
            return False

        child = self.children[0]
        return child.height > self.height

    def _show_scrollbar(self):
        """Show the scrollbar with a darker color."""
        if not self._is_scrollbar_needed() or not hasattr(self, '_bar_color_instruction'):
            return

        self._is_scrollbar_visible = True

        # Animate color change with transition
        if hasattr(self, '_bar_color_instruction'):
            Animation.cancel_all(self._bar_color_instruction)
            anim = Animation(
                rgba=COLORS['DARK_DOVE_WHITE'],
                duration=0,
                transition='out_quad'
            )
            anim.start(self._bar_color_instruction)
        if self._hide_timer:
            self._hide_timer.cancel()

    def _hide_scrollbar(self):
        """Hide the scrollbar with a lighter color."""
        if not hasattr(self, '_bar_color_instruction'):
            return

        if not self._is_scrollbar_needed():
            # Animate to fully transparent if not needed
            Animation.cancel_all(self._bar_color_instruction)
            anim = Animation(
                rgba=(0, 0, 0, 0),
                duration=0.3,
                transition='out_quad'
            )
            anim.start(self._bar_color_instruction)
        else:
            Animation.cancel_all(self._bar_color_instruction)
            anim = Animation(
                rgba=COLORS['DOVE_WHITE'],
                duration=0.3,
                transition='out_quad'
            )
            anim.start(self._bar_color_instruction)

        self._is_scrollbar_visible = False

    def _schedule_hide_scrollbar(self):
        """Schedule hiding the scrollbar after 1.5 seconds."""
        if self._hide_timer:
            self._hide_timer.cancel()
        self._hide_timer = Clock.schedule_once(lambda dt: self._hide_scrollbar(), 0.5)

    def _update_bar(self, *args):
        """Move and resize the rectangle according to scroll_y."""
        # check if graphics have been initialized
        if not hasattr(self, 'bar_rect') or not hasattr(self, 'track_rect'):
            return
        # check if widget isn't ready
        if self.height <= 0:
            return
        # check if scrollbar is needed
        if not self._is_scrollbar_needed():
            if hasattr(self, '_bar_color_instruction'):
                self._bar_color_instruction.rgba = (0, 0, 0, 0)  # fully hide
            return

        # update track (background)
        track_width = 10
        track_x = self.right - track_width
        self.track_rect.size = (track_width, self.height)
        self.track_rect.pos = (track_x, self.y)
        # update scrollbar thumb
        new_height = self._calculate_bar_size()
        bar_width = 10
        bar_x = self.right - track_width + 1  # 1px offset from track

        self.bar_rect.size = (bar_width, new_height)

        # update position
        scroll_y = self.scroll_y
        available_space = self.height - new_height
        pos_y = self.y + available_space * scroll_y
        self.bar_rect.pos = (bar_x, pos_y)

    def _is_touch_on_bar(self, touch):
        """Check if touch is within the scrollbar area."""
        if not self._is_scrollbar_needed():
            return False

        # expand touch area for easier tapping
        track_x = self.right - 10
        return (track_x <= touch.x <= self.right and
                self.y <= touch.y <= self.top)

    def on_touch_down(self, touch):
        if self._is_touch_on_bar(touch):
            self._has_moved = False

            if self._press_event:
                try:
                    self._press_event.cancel()
                except Exception:
                    pass
                self._press_event = None

            if hasattr(self, "bar_rect"):
                bar_x, bar_y = self.bar_rect.pos
                bar_w, bar_h = self.bar_rect.size

                if (bar_x <= touch.x <= bar_x + bar_w and
                    bar_y <= touch.y <= bar_y + bar_h):
                    self._press_event = Clock.schedule_once(self._do_long_press, self.long_press_time)
                    return True
                else:
                    # Click trên track - jump to position
                    available_space = self.height - bar_h
                    if available_space > 0:
                        relative_y = touch.y - self.y
                        scroll_y = relative_y / available_space
                        scroll_y = max(0, min(1, scroll_y))
                        self.scroll_y = scroll_y
                    self._schedule_hide_scrollbar()
                    return True
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self._press_event:
            try:
                self._press_event.cancel()
            except Exception:
                pass
            self._press_event = None
            self._start_dragging(touch)
            return True

        if self._is_dragging and hasattr(self, 'bar_rect'):
            self._has_moved = True
            bar_h = self.bar_rect.size[1]
            available_space = self.height - bar_h

            if available_space > 0:
                thumb_top = touch.y - self._drag_offset_y
                relative_y = thumb_top - self.y
                scroll_y = relative_y / available_space
                scroll_y = max(0, min(1, scroll_y))
                self.scroll_y = scroll_y
            return True
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        if self._press_event:
            try:
                self._press_event.cancel()
            except Exception:
                pass
            self._press_event = None
            self._schedule_hide_scrollbar()
            return True
        if self._is_dragging:
            self._is_dragging = False
            self._drag_offset_y = 0
            self._schedule_hide_scrollbar()
            return True
        return super().on_touch_up(touch)

    def _do_long_press(self, dt):
        """Called on long press of the thumb"""
        self._press_event = None
        self._show_scrollbar()

    def _start_dragging(self, touch):
        """Enter drag mode"""
        self._is_dragging = True
        self._touch_start_y = touch.y
        if hasattr(self, 'bar_rect'):
            self._drag_offset_y = touch.y - self.bar_rect.pos[1]
        self._show_scrollbar()

class ImageSelectionListWidget(ScrollView):
    '''Scroll view displaying a selectable list of images.'''

class ImageSelectionItem(BoxLayout, HoverBehavior):
    '''List item representing a selectable image with hover support.'''
    image_source = StringProperty("")
    text = StringProperty("")
    group = StringProperty("")
    active = BooleanProperty(False)
    index = NumericProperty(-1)

    def __init__(self, **kwargs):
        super(ImageSelectionItem, self).__init__(**kwargs)
        self.hover_rect = None
        self.screen = None
        for child in self.children:
            if child.__class__.__name__ == 'FormCheckBox':
                child.ids.checkbox.bind(active=self.on_checkbox_active)

        Clock.schedule_once(self._post_init)

    def _post_init(self, dt):
        self.canvas.ask_update()
        # Get reference to TrainingResultsScreen
        app = App.get_running_app()
        if app and hasattr(app, 'root') and hasattr(app.root, 'ids') and hasattr(app.root.ids, 'screen_manager'):
            screen_manager = app.root.ids.screen_manager
            self.screen = screen_manager.get_screen('screen_A_sensor_settings')


    def get_image_width(self):
        """Return image width (X size) in pixels from self.image_source."""
        if not self.image_source:
            return None
        try:
            img = PILImage.open(self.image_source)
            width, _ = img.size
            img.close()
            return width
        except Exception:
            traceback.print_exc()
            return None

    def on_checkbox_active(self, instance, value):
        '''Handle checkbox state change'''
        if value and self.screen:
            width = self.get_image_width()
            if width is not None:
                width_str = str(width)
                self.screen.ids.a_resize_dot_pattern.text = width_str
                if hasattr(self.screen, 'sync_resize_speed_pattern'):
                    self.screen.sync_resize_speed_pattern(width_str)

    def on_touch_down(self, touch):
        """Handle touch events - allow clicking anywhere on the item to toggle checkbox"""
        if self.collide_point(*touch.pos):
            # Find the FormCheckBox child and toggle it
            for child in self.children:
                if child.__class__.__name__ == 'FormCheckBox':
                    if self.group:
                        # Radio behavior - always set to True
                        child.ids.checkbox.active = True
                    else:
                        # Toggle behavior
                        child.ids.checkbox.active = not child.ids.checkbox.active
                    return True
        return super().on_touch_down(touch)

    def on_enter(self):
        """Show hover effect when mouse enters"""
        with self.canvas.before:
            Color(rgba=COLORS['ALICE_BLUE'])
            self.hover_rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(4)]
            )
        self.bind(pos=self.update_hover_rect, size=self.update_hover_rect)

    def on_leave(self):
        """Hide hover effect when mouse leaves"""
        if self.hover_rect:
            self.canvas.before.remove(self.hover_rect)
            self.hover_rect = None
        self.unbind(pos=self.update_hover_rect, size=self.update_hover_rect)

    def update_hover_rect(self, *args):
        """Update hover rectangle position and size"""
        if self.hover_rect:
            self.hover_rect.pos = self.pos
            self.hover_rect.size = self.size

class ErrorMessageWrapper(EventDispatcher):
    '''Allow calling '.error_message' on custom message.'''
    error_message = StringProperty("")

class ErrorMessage(Label):
    '''Label styled to display error messages to the user.'''
    error_message = StringProperty("")
    min_value = NumericProperty(None)
    max_value = NumericProperty(None)

class TextWrapper(EventDispatcher):
    '''Allow calling '.text' on custom variable.'''
    text = StringProperty("")

class DrawingBoard(BoxLayout, HoverBehavior):
    '''Interactive drawing canvas supporting hover events.'''
    image_width = NumericProperty(None, allownone=True)
    image_height = NumericProperty(None, allownone=True)
    preview_width = NumericProperty(None, allownone=True)
    preview_height = NumericProperty(None, allownone=True)
    preview_pos_x = NumericProperty(None, allownone=True)
    preview_pos_y = NumericProperty(None, allownone=True)
    image_top_left_x = ObjectProperty()
    image_top_left_y = ObjectProperty()
    image_bottom_right_x = ObjectProperty()
    image_bottom_right_y = ObjectProperty()
    reset_draw = ObjectProperty()
    reset_coords = ObjectProperty()
    image_region = ListProperty(None, allownone=True)
    image_transform_params = ListProperty(None, allownone=True)
    global cursor_manager # pylint: disable=global-variable-not-assigned

    def __init__(self, **kwargs):
        self.eps = 0.9
        self.snap_offset_x = 4
        self.snap_offset_y = 4
        self.initial_x = None
        self.initial_y = None
        super().__init__(**kwargs)

    def _reset_initial_coord(self):
        self.initial_x = None
        self.initial_y = None

    def _snap(self, v, max_v):
        if v < 1:
            r = 0
        elif v >= max_v-self.eps:
            r = max_v
        else:
            return v
        return r

    def _is_inside_image_region(self, x, y):
        if not self.image_region or len(self.image_region) < 4:
            return False
        try:
            left, top, right, bottom = self.image_region
            left -= self.snap_offset_x
            right += self.snap_offset_x
            top += self.snap_offset_y
            bottom -= self.snap_offset_y
            return left <= x <= right and bottom <= y <= top
        except Exception:
            Logger.error("DrawingBoard: error in _is_inside_image_region", exc_info=1)
            return False

    def _widget_to_image_coords(self, x, y):
        if not self.image_transform_params:
            Logger.warning("DrawingBoard: cannot convert _widget_to_image_coords, missing self.image_transform_params")
            return None, None
        ratio, offset_x, offset_y, tex_w, tex_h = self.image_transform_params
        img_x = self._snap((x - self.preview_pos_x - offset_x) / ratio, tex_w)
        img_y = self._snap(self.image_height - (y - self.preview_pos_y - offset_y) / ratio, tex_h)
        return img_x, img_y

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos) and self._is_inside_image_region(*touch.pos):
            self.reset_draw()
            self._reset_initial_coord()
            self.reset_coords()
            x1, y1 = self._widget_to_image_coords(*touch.pos)
            if x1 is None or y1 is None:
                return super().on_touch_down(touch)
            self.initial_x = x1
            self.initial_y = y1
        return super().on_touch_down(touch)

    def on_touch_move(self, touch):
        if self.collide_point(*touch.pos) and self._is_inside_image_region(*touch.pos):
            x2, y2 = self._widget_to_image_coords(*touch.pos)
            if x2 is None or y2 is None:
                return super().on_touch_down(touch)
            if self.initial_x is not None and self.initial_y is not None:
                # Real-time normalization to top_left, bottom_right format
                top_left_x = min(self.initial_x, x2)
                top_left_y = min(self.initial_y, y2)
                bottom_right_x = max(self.initial_x, x2)
                bottom_right_y = max(self.initial_y, y2)
                # Update
                self.image_top_left_x.text = str(int(top_left_x))
                self.image_top_left_y.text = str(int(top_left_y))
                self.image_bottom_right_x.text = str(int(bottom_right_x))
                self.image_bottom_right_y.text = str(int(bottom_right_y))
        return super().on_touch_move(touch)

    def on_touch_up(self, touch):
        self._reset_initial_coord()
        return super().on_touch_up(touch)

    def on_enter(self):
        self._reset_initial_coord()
        Window.bind(mouse_pos=self.on_mouse_pos)

    def on_leave(self):
        cursor_manager.reset()
        self._reset_initial_coord()
        Window.unbind(mouse_pos=self.on_mouse_pos)

    def on_mouse_pos(self, window, pos):
        '''Handle mouse movement'''
        local_pos = self.to_widget(*pos)
        flag = self._is_inside_image_region(*local_pos)
        current_cursor = cursor_manager.get_current_cursor()
        if flag and current_cursor != "hand":
            cursor_manager.set_cursor("hand")
        elif not flag and current_cursor == "hand":
            cursor_manager.reset()

class ImageAlignmentWindow(BoxLayout):
    '''Window for aligning and transforming images interactively.'''
    image_source = StringProperty("")
    image_filename = StringProperty("")
    image_height = NumericProperty(None, allownone=True)
    image_width = NumericProperty(None, allownone=True)
    required = BooleanProperty(False)
    is_visible = BooleanProperty(True)
    overlay_opacity = NumericProperty(0.55)
    hist_dir = StringProperty("") #set in py
    alignment_dir = StringProperty("") #set in py

    error_image = ObjectProperty()
    error_alignment = ObjectProperty()
    text = StringProperty('')
    output_name = StringProperty('image_name')
    image_region = ListProperty(None, allownone=True)
    image_transform_params = ListProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.error_image = ErrorMessageWrapper()
        self.error_alignment = ErrorMessageWrapper()
        self.image_allow_none = not self.required
        self._update_draw_event = None
        self._no_image_instruction = None
        self._rect = None

    def on_kv_post(self, base_widget):
        self.popup = MyPopup()
        self.coord_inputs = [
            self.ids.image_top_left_x.ids.margin_input,
            self.ids.image_top_left_y.ids.margin_input,
            self.ids.image_bottom_right_x.ids.margin_input,
            self.ids.image_bottom_right_y.ids.margin_input
        ]
        self.update_allow_none_status()
        self.show_delete_button()
        try:
            for coord in self.coord_inputs:
                coord.bind(text=self.update_allow_none_status, focus=self.strict_func)
                coord.bind(text=self._update_draw)
                coord.bind(focus=self.format_coords)

            self.bind(image_source=self.update_allow_none_status, required=self.update_allow_none_status)
            self.bind(  image_source=self._update_draw,
                        pos=self._update_draw,
                        size=self._update_draw)
        except Exception:
            Logger.error("ImageAlignmentWindow: Binding failed", exc_info=1)
        return super().on_kv_post(base_widget)

    def validate_text(self, *args):
        '''Trigger coord_inputs validation'''
        for widget_id in self.coord_inputs:
            if hasattr(widget_id, 'validate_text') and callable(getattr(widget_id, 'validate_text')):
                widget_id.validate_text(widget_id.text)
        self.sync_error_message()

    def strict_func(self, instance, value):
        '''Custom strict rules, cap invalid values to max.'''
        if not instance.focus:
            try:
                if instance.text:
                    value = int(instance.text)
                else:
                    return
            except ValueError:
                instance.error_message = "overall_error_popup"
                return
            try:
                if instance.strict:
                    if instance.max_value is not None and value > instance.max_value or value < instance.min_value:
                        instance.text = str(instance.max_value)
                        instance.error_message = "" #no error message
            except Exception:
                traceback.print_exc()

    def _normalize_coords(self, x1:int, y1:int, x2:int, y2:int):
        '''Norm all coords to top-left, bottom-right pairs'''
        if any(v is None for v in (x1, y1, x2, y2)):
            return x1, y1, x2, y2 #keep old value
        # top_left_x, top_left_y, bottom_right_x, bottom_right_y
        return min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)

    def format_coords(self, instance, value):
        '''Norm all coords to top-left, bottom-right pairs inplace on input focus'''
        if not instance.focus:
            normalized = self._normalize_coords(*[int(inp.text) if inp.text.strip() else None for inp in self.coord_inputs])
            for input_widget, value in zip(self.coord_inputs, normalized):
                input_widget.text = "" if value is None else str(value)

    def _to_int(self, value: str):
        '''Safely convert str to int'''
        try:
            return int(value.strip())
        except (ValueError, AttributeError):
            self.reset_draw()
            return None

    def _get_int_coords(self):
        '''Convert coord_inputs values to interger'''
        return [self._to_int(coord.text) for coord in self.coord_inputs]

    def sync_error_message(self):
        '''Sync all error messages from smaller components to ImageAlignmentWindow error message.'''
        errors = [coord.error_message for coord in self.coord_inputs]
        self.error_alignment.error_message = ''
        self.error_image.error_message = ''
        if 'nullable_error_message' in errors:
            self.error_alignment.error_message = 'nullable_error_message'
        elif len("".join(errors)) != 0: #if not empty but errors still exist likely range error.
            self.error_alignment.error_message = '' #Skip
        if self.image_source == '' and not self.image_allow_none:
            self.error_image.error_message = 'missing_image_error_message'

    def reset_draw(self):
        '''Reset/remove drawing'''
        if self._rect:
            self.ids.preview_image.canvas.remove(self._rect[0])
            self.ids.preview_image.canvas.remove(self._rect[1])
            self._rect = None

    def reset_coords(self):
        '''Reset/remove coords'''
        for coord in self.coord_inputs:
            coord.text = ''

    def reset_val_status(self):
        '''Reset/remove validation status'''
        self.error_image.error_message = ''
        self.error_alignment.error_message = ''
        for coord in self.coord_inputs:
            coord.error_message = ''

    def reset_input(self):
        '''Main reset function, reset all user inputs to blank state.'''
        self.image_source = ''
        self.image_filename = ''
        self.image_width, self.image_height = None, None
        self.image_transform_params = None
        self.image_region = None
        self.reset_coords()
        self.reset_draw()
        self.reset_val_status()

    def on_image_source(self, *args):
        '''On image_source changes, update image_filename (bind to kivy Label) and calculate image dimensions. '''
        try:
            if self.image_source:
                self.image_filename = os.path.basename(self.image_source)
                self.image_width, self.image_height = PILImage.open(self.image_source).size
            self.show_delete_button()
        except Exception:
            Logger.error("ImageAlignmentWindow: error in on_image_source", exc_info=1)

    def upload_image(self, source_path):
        '''On upload image, update image_source (bind to kivy Image). '''
        try:
            if source_path:
                self.reset_input()
                self.image_source = source_path
                #call on_image_source on binding
        except Exception:
            Logger.error("ImageAlignmentWindow: error in upload_image", exc_info=1)

    def update_allow_none_status(self, *args):
        '''Disable allow none if a widget is required OR an image is uploaded OR any of the field is filled.'''
        is_any_input_filled = any(coord.text.strip() != '' for coord in self.coord_inputs)
        if self.required or self.image_source or is_any_input_filled:
            self.image_allow_none = False
            for coord in self.coord_inputs:
                coord.allow_none = False
        else:
            self.image_allow_none = True
            for coord in self.coord_inputs:
                coord.allow_none = True

    def show_delete_button(self, *args):
        '''Show/hide delete button on image_source'''
        if self.image_source:
            self.ids.image_delete_button.opacity = 1
        else:
            self.ids.image_delete_button.opacity = 0

    def delete_image(self, *args):
        '''Call by image_delete_button'''
        self.reset_input()

    def _get_image_transform_params(self):
        '''Return transformation parameters: ratio, offset_x, offset_y, tex_w, tex_h.'''
        preview = self.ids.preview_image
        if not getattr(preview, "source", None):
            return None
        tex_w, tex_h = preview.texture_size or (0, 0)
        widget_w, widget_h = preview.width, preview.height
        if not tex_w or not tex_h or not widget_w or not widget_h:
            Logger.warning("ImageAlignmentWindow: _get_image_transform_params skipped due to zero size")
            return None
        ratio = min(widget_w / tex_w, widget_h / tex_h)
        disp_w, disp_h = tex_w * ratio, tex_h * ratio
        offset_x = (widget_w - disp_w) / 2
        offset_y = (widget_h - disp_h) / 2
        return ratio, offset_x, offset_y, tex_w, tex_h

    def update_image_region(self, *args):
        '''
            Update the displayed image region and its transformation parameters.
            Bind to on_source, on_pos, on_size of the Image widget.
        '''
        try:
            preview = self.ids.preview_image
            if not getattr(preview, "source", None):
                # Logger.warning("ImageAlignmentWindow: update_image_region skipped due to no image source")
                self.image_transform_params = None
                self.image_region = None
                return
            tex_w, tex_h = preview.texture_size or (0, 0)
            widget_w, widget_h = preview.width, preview.height
            if not tex_w or not tex_h or not widget_w or not widget_h:
                Logger.warning("ImageAlignmentWindow: update_image_region skipped due to zero size")
                self.image_transform_params = None
                self.image_region = None
                return
            ratio = min(widget_w / tex_w, widget_h / tex_h)
            disp_w, disp_h = tex_w * ratio, tex_h * ratio
            offset_x = (widget_w - disp_w) / 2
            offset_y = (widget_h - disp_h) / 2
            left = self.ids.preview_image.x + offset_x
            right = left + disp_w
            bottom = self.ids.preview_image.y + offset_y
            top = bottom + disp_h
            #Update
            self.image_transform_params = [ratio, offset_x, offset_y, tex_w, tex_h]
            self.image_region = [left, top, right, bottom]
        except Exception:
            Logger.error("ImageAlignmentWindow: fail to update_image_region", exc_info=1)

    def image_to_widget_coords(self, x, y):
        '''Convert image coordinates to kivy widget coordinates'''
        try:
            if not self.image_transform_params:
                Logger.warning("ImageAlignmentWindow: cannot convert image_to_widget_coords, missing self.image_transform_params")
                return None, None
            ratio, offset_x, offset_y, _, tex_h = self.image_transform_params
            y1_flipped = tex_h - y #Flip Y-axis: top-left origin system
            widget_x = self.ids.preview_image.x + offset_x + x * ratio
            widget_y = self.ids.preview_image.y + offset_y + y1_flipped * ratio
            return widget_x, widget_y
        except Exception:
            Logger.error("ImageAlignmentWindow: error in image_to_widget_coords", exc_info=1)
            return None, None

    def _update_draw(self, *args):
        '''Async wrapper for _perform_update_draw'''
        if self._update_draw_event: # avoid clogging the event loop
            self._update_draw_event.cancel()
        self._update_draw_event = Clock.schedule_once(self._perform_update_draw, 0)

    def _perform_update_draw(self, *args):
        '''Update drawing position using coord_inputs values'''
        self.reset_draw()
        try:
            int_coords = self._get_int_coords()
            for i, coord in enumerate(int_coords):
                if coord is None or coord < 0:
                    return
                if i % 2 == 0 and coord > self.image_width: #x1, x2
                    int_coords[i] = self.image_width
                if i % 2 != 0 and coord > self.image_height: #y1, y2
                    int_coords[i] = self.image_height
            if not self.image_source:
                return

            x1, y1 = self.image_to_widget_coords(int_coords[0], int_coords[1])
            x2, y2 = self.image_to_widget_coords(int_coords[2], int_coords[3])
            if any(v is None for v in (x1, y1, x2, y2)):
                return

            width = x2 - x1
            height = y2 - y1
            with self.ids.preview_image.canvas:
                self._rect = [
                    Color(rgba=COLORS['LIGHT_RED']),
                    Line(width=1, rectangle=(x1, y1, width, height))
                ]
        except Exception:
            Logger.error("ImageAlignmentWindow: failed to update draw", exc_info=1)
            self._rect = None

    def _align_image(self):
        '''Given input coordinates, align the histogram image onto the uploaded image. Result is saved to alignment_dir/{output_name}.png'''
        # get overlay image
        if not self.hist_dir or not os.path.exists(self.hist_dir):
            #os.makedirs(hist_dir)
            raise ValueError("Histogram directory does not exist")

        # extract all hist images
        list_of_files = [
            entry.path
            for entry in os.scandir(self.hist_dir)
            if entry.is_file() and entry.name.endswith('.png') and entry.name != 'color_map.png'
        ]

        if list_of_files:
            overlay_img_path = max(list_of_files, key=os.path.getctime)
        else:
            raise ValueError("No histogram image available")

        # align image given x1, y1 (top-left), x2, y2 (bottom-right)
        int_coords = self._get_int_coords()
        if any(coord is None for coord in int_coords):
            raise ValueError("Missing coordinates")

        int_coords = self._normalize_coords(*int_coords)
        width = int_coords[2] - int_coords[0] #x2 - x1
        height = int_coords[3] - int_coords[1] #y2 - y1

        if width <= 0 or height <= 0:
            raise ValueError("Please try different coordinates")

        base_img = PILImage.open(self.image_source).convert("RGBA")
        overlay_img = PILImage.open(overlay_img_path).convert("RGBA")

        overlay_img = overlay_img.resize((width, height), PILImage.LANCZOS)
        overlay_img.putalpha(int(255 * self.overlay_opacity))
        x_offset = int_coords[0]
        y_offset = int_coords[1]

        new_img = PILImage.new("RGBA", base_img.size)
        new_img.paste(base_img, (0, 0))  # Paste the base image
        new_img.paste(overlay_img, (x_offset, y_offset), overlay_img)
        new_img = new_img.convert("RGB")
        new_img.save(os.path.join(self.alignment_dir, f'{self.output_name}.png'))

    def _show_alignment_confirm_popup(self):
        '''Display alignment confirmation popup. Call by 'Xác nhận căn chỉnh' button.'''
        # display image through a custom popup window
        try:
            #force required to ensure always validate when clicking this button
            original_required = self.required
            self.required = True
            self.validate_text()
            self.required = original_required #switch back

            if self.error_alignment.error_message == 'nullable_error_message':
                raise ValueError(self.error_alignment.error_message)
            elif self.error_image.error_message:
                raise ValueError(self.error_image.error_message)
            else:
                try:
                    self._align_image()
                    popup = self.popup.create_adaptive_image_popup(title='confirm_alignment_popup_title',
                                                                image_path=f'{self.alignment_dir}/{self.output_name}.png')
                    popup.open()
                except Exception:
                    Logger.warning("ImageAlignmentWindow: cannot perform _align_image()", exc_info=1)
                    #display 'Alignment Confirmation' without alignment anyway
                    popup = self.popup.create_adaptive_image_popup(title='confirm_alignment_popup_title',
                                                            image_path=f'{self.image_source}')
                    popup.open()

        except Exception:
            Logger.error("ImageAlignmentWindow: error in _show_alignment_confirm_popup()", exc_info=1)
            popup = self.popup.create_adaptive_popup(title='error_popup',
                                                    message="alignment_image_error_popup")
            popup.open()



#--------------------Utilities--------------------



class NoDataSpinnerOption(CustomSpinnerOption):
    '''Spinner option used to represent a 'no data' placeholder.'''
    def __init__(self, text_color, bg_color):
        super().__init__(
            text_color=text_color,
            bg_color=bg_color,
        )

    def on_enter(self): #override
        pass

    def on_press(self): #override
        pass

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.collide_point(*touch.pos):
            return True
        return super().on_touch_up(touch)

class PaginationInfo(Label):
    '''Label displaying pagination information like page ranges.'''
    start_record = NumericProperty(None)
    end_record = NumericProperty(None)
    total_records = NumericProperty(None)
    def __init__(self, start_record, end_record, total_records, **kwargs):
        self.start_record = start_record
        self.end_record = end_record
        self.total_records = total_records
        super().__init__(**kwargs)

class Separator(Widget):
    '''Visual separator widget used between items or sections.'''
    color = ListProperty([0.866, 0.866, 0.866, 1])  # Default: #ddd
    dashed = BooleanProperty(False)
    dash_width = NumericProperty(dp(3))
    dash_spacing = NumericProperty(dp(2))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(1)

        self.bind(
            pos=self._update_canvas,
            size=self._update_canvas,
            color=self._update_canvas,
            dashed=self._update_canvas,
            dash_width=self._update_canvas,
            dash_spacing=self._update_canvas,
        )

        self._update_canvas()

    def _update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(rgba=self.color)
            y = self.center_y - self.height / 2

            if self.dashed:
                x = self.x
                while x < self.right:
                    segment_width = min(self.dash_width, self.right - x)
                    Rectangle(pos=(x, y), size=(segment_width, self.height))
                    x += self.dash_width + self.dash_spacing
            else:
                Rectangle(pos=(self.x, y), size=(self.width, self.height))

class HyperlinkLabel(FormLabel, HoverBehavior):
    """Label styled to look like a hyperlink and support hover/click."""

    reference_id = StringProperty("")
    target_screen = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._original_text = ''
        self.bind(text=self._store_original_text)

    def _store_original_text(self, instance, value):
        """Store the original text without markup"""
        if value and not value.startswith('[u]'):
            self._original_text = value

    def on_enter(self):
        if self._original_text:
            self.text = f'[u]{self._original_text}[/u]'

    def on_leave(self):
        if self._original_text:
            self.text = self._original_text

    def on_touch_down(self, touch):
        if self.collide_point(*touch.pos):
            self.navigate_to_reference()
            return True
        return super().on_touch_down(touch)

    def navigate_to_reference(self):
        '''Navigate to ref'''
        if not self.target_screen or not self.reference_id:
            return

        app = App.get_running_app()

        screen_manager = self.find_screen_manager(app.root)
        if not screen_manager:
            return

        screen_manager.current = self.target_screen
        self._update_menu_button_state(app)
        Clock.schedule_once(lambda dt: self.scroll_to_widget(), 0.2)

    def _update_menu_button_state(self, app):
        if not app.root or not hasattr(app.root.ids, 'sidebar_menu_grid_kv'):
            return

        sidebar_grid = app.root.ids.sidebar_menu_grid_kv
        menu_buttons = self._find_menu_buttons(sidebar_grid)

        # Deactivate current button
        if app.current_screen_button:
            app.current_screen_button.active = False

        # Find and activate the button for target screen
        for button in menu_buttons:
            if hasattr(button, 'target_screen') and button.target_screen == self.target_screen:
                button.active = True
                app.current_screen_button = button
                break

    def _find_menu_buttons(self, widget):
        menu_buttons = []
        # Check if current widget is MenuButton
        if widget.__class__.__name__ == 'MenuButton':
            menu_buttons.append(widget)

        # Recursively check children
        for child in widget.children:
            menu_buttons.extend(self._find_menu_buttons(child))

        return menu_buttons


    def find_screen_manager(self, widget):
        '''Find ScreenManager id'''
        if (widget.__class__.__name__ == 'ScreenManager' or
            'ScreenManager' in str(widget.__class__) or
            hasattr(widget, 'current') and hasattr(widget, 'screens')):
            return widget

        for child in widget.children:
            result = self.find_screen_manager(child)
            if result:
                return result
        return None

    def scroll_to_widget(self):
        """Scroll to the target widget"""
        app = App.get_running_app()
        screen_manager = self.find_screen_manager(app.root)
        if not screen_manager:
            print("ERROR: ScreenManager not found!")
            return

        current_screen = screen_manager.current_screen
        target_widget = self.find_widget_by_id(current_screen, self.reference_id)

        if target_widget:
            scroll_view = self.find_scroll_view_parent(target_widget)

            if scroll_view:
                self.scroll_to_position(scroll_view, target_widget)
                self.highlight_widget(target_widget)

    def find_widget_by_id(self, parent, widget_id):
        """Tìm widget theo ID"""
        if hasattr(parent, 'ids') and widget_id in parent.ids:
            return parent.ids[widget_id]

        for child in parent.children:
            result = self.find_widget_by_id(child, widget_id)
            if result:
                return result
        return None

    def find_scroll_view_parent(self, widget):
        """Tìm ScrollView parent"""
        parent = widget.parent
        while parent:
            if parent.__class__.__name__ == 'ScrollView':
                return parent
            parent = parent.parent
        return None

    def scroll_to_position(self, scroll_view, target_widget):
        """Scroll target_widget vào giữa ScrollView theo trục OY."""

        def _scroll_to_center(*_):
            content = scroll_view.children[0] if scroll_view.children else None
            if not content:
                print("ScrollView has no content")
                return

            center_x, center_y = target_widget.to_window(
                target_widget.center_x,
                target_widget.center_y
            )
            _, y_in_content = content.to_widget(center_x, center_y)

            content_height = content.height
            scroll_view_height = scroll_view.height
            if content_height <= scroll_view_height:
                return

            distance_from_top = max(0, y_in_content - scroll_view_height)
            scrollable_height = content_height - scroll_view_height

            scroll_y = distance_from_top / scrollable_height
            if 0 <= scroll_y <= 0.25:
                scroll_y = max(0, scroll_y - 0.15)
            elif 0.75 <= scroll_y <= 1.0:
                scroll_y = min(scroll_y + 0.15, 1.0)
            else:
                scroll_y = scroll_y + 0.2

            anim = Animation(scroll_y=scroll_y, d=DefaultAnimation.SCROLL_DURATION, t=DefaultAnimation.SCROLL_TRANSITION)
            anim.start(scroll_view)

        Clock.schedule_once(_scroll_to_center, 0)

    def highlight_widget(self, widget):
        """Highlight widget tạm thời"""
        with widget.canvas.after:
            highlight_color = Color(rgba=[1, 1, 0, 0.5])  # Màu vàng highlight
            highlight_rect = Rectangle(pos=widget.pos, size=widget.size)

        def update_highlight(*args):
            highlight_rect.pos = widget.pos
            highlight_rect.size = widget.size

        widget.bind(pos=update_highlight, size=update_highlight)

        def remove_highlight(dt):
            try:
                widget.canvas.after.remove(highlight_color)
                widget.canvas.after.remove(highlight_rect)
                widget.unbind(pos=update_highlight, size=update_highlight)
            except Exception:
                return

        Clock.schedule_once(remove_highlight, 2.0)

class C3SettingsSection(BoxLayout):
    '''Settings section for C3 Training Results screen - defined in KV file.'''
    pass #pylint: disable=unnecessary-pass

class C3PreviewOptionsSection(BoxLayout):
    '''Options section for C3 preview popup - defined in KV file.'''
    pass #pylint: disable=unnecessary-pass

class PopupTitle(Label):
    '''Title label displayed at the top of popups.'''

class PopupMessage(Label):
    '''Body message label displayed within popups.'''

class MyPopup(Popup):
    '''Application popup with standardized title and message handling.'''
    def __init__(self, **kwargs):
        super(MyPopup, self).__init__(**kwargs)
        self.loading_image_path=resource_path("app/libs/assets/icons/loading.png")
        self.bind(on_kv_post=self._clear_styles)
        self.app = App.get_running_app()

    def _clear_styles(self):
        '''Reset popup styles and content to a clean default state.'''
        #set default
        self.ids.content_layout.clear_widgets()
        self.content=Label(text='No Content')
        self.title=""
        self.title_align="center"
        self.title_color= (0,0,0,0)
        self.title_color=(0,0,0,1)
        self.size_hint=(None, None)
        self.size=(dp(450), dp(200))
        self.separator_height= 0
        self.background_color= (0,0,0,0)
        self.background= ''
        self.opacity = 0

    def open(self, *args, **kwargs):
        super(MyPopup, self).open(*args, **kwargs)
        Animation(opacity=1, d=0.1, t='out_quad').start(self)

    def dismiss(self, *args, **kwargs):
        if self.opacity == 0:
            return super(MyPopup, self).dismiss(*args, **kwargs)
        anim = Animation(opacity=0, d=0.1, t='in_quad')
        anim.bind(on_complete=lambda *_: super(MyPopup, self).dismiss(*args, **kwargs))
        anim.start(self)

    def update_size(self):
        '''Update content size'''
        if self.content:
            self.content_layout_height = self.content.minimum_height
            self.content_layout_width = max(dp(400), self.content.minimum_width)
            self.size = (self.content_layout_width + dp(40), self.content_layout_height + dp(40))

    @classmethod
    def create_loading_popup(cls, title):
        '''Create a loading icon popup.'''
        popup_instance = cls()
        popup_instance._clear_styles()
        popup_instance.content = popup_instance.ids.content_layout

        if not popup_instance.loading_image_path:
            raise Exception("Missing loading_image_path!")

        title_label = PopupTitle(text=popup_instance.app.lang.get(title))
        title_label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
        popup_instance.ids.content_layout.add_widget(title_label)

        # Load image texture
        img_size = dp(50)
        core_image = CoreImage(popup_instance.loading_image_path)
        container = Widget(size_hint=(None, None), size=(img_size, img_size), pos_hint={'center_x': 0.5, 'center_y': 0.5})
        margin_top = Widget(size_hint=(None, None), size=(img_size, dp(10)))
        margin_bottom = Widget(size_hint=(None, None), size=(img_size, dp(10)))

        # ensure a dedicated canvas group
        with container.canvas.before:
            PushMatrix()
        with container.canvas:
            container._rotate = Rotate(angle=0, origin=container.pos) # pylint: disable=protected-access
            container._rect = Rectangle(texture=core_image.texture, size=(img_size, img_size)) # pylint: disable=protected-access
        with container.canvas.after:
            PopMatrix()

        def update_rect(*args):
            container._rotate.origin = container.center # pylint: disable=protected-access
            container._rect.pos = container.pos # pylint: disable=protected-access
            container._rect.size = container.size # pylint: disable=protected-access
        container.bind(pos=update_rect, size=update_rect)

        def spin(dt):
            container._rotate.angle += 5 # pylint: disable=protected-access
            container._rotate.origin = container.center # pylint: disable=protected-access
        popup_instance._spin_event = Clock.schedule_interval(spin, 1.0 / 60.0)

        popup_instance.ids.content_layout.add_widget(margin_top)
        popup_instance.ids.content_layout.add_widget(container)
        popup_instance.ids.content_layout.add_widget(margin_bottom)
        popup_instance.auto_dismiss = False

        # Update popup size after layout
        Clock.schedule_once(lambda dt: popup_instance.update_size())

        return popup_instance


    @classmethod
    def create_adaptive_image_popup(cls, title, image_path):
        '''Create a popup with image.'''
        gc.collect()

        popup_instance = cls()
        popup_instance._clear_styles()
        popup_instance.content = popup_instance.ids.content_layout

        # Title Label
        title_label = PopupTitle(text=popup_instance.app.lang.get(title))
        title_label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
        popup_instance.ids.content_layout.add_widget(title_label)

        # Image Display
        core_image = CoreImage(image_path, nocache=True)
        image_widget = AsyncImage(
            texture=core_image.texture,
            size_hint=(1, None),
            height=dp(300),
            allow_stretch=True,
            keep_ratio=True,
            nocache=True,
        )
        popup_instance.ids.content_layout.add_widget(image_widget)

        # OK Button
        ok_button = FormButton(text=popup_instance.app.lang.get("ok_popup"), min_width=dp(140), pos_hint={'center_x': 0.5})
        ok_button.bind(on_release=popup_instance.dismiss)
        popup_instance.ids.content_layout.add_widget(ok_button)

        # Update popup size after layout
        Clock.schedule_once(lambda dt: popup_instance.update_size())

        return popup_instance

    @classmethod
    def create_adaptive_popup(cls, title, message):
        '''Create a popup with messages.'''
        gc.collect()

        popup_instance = cls()
        popup_instance._clear_styles()
        popup_instance.content = popup_instance.ids.content_layout

        title_label = PopupTitle(text=popup_instance.app.lang.get(title))
        title_label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
        popup_instance.ids.content_layout.add_widget(title_label)

        message_label = PopupMessage(text=popup_instance.app.lang.get(message))
        message_label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
        popup_instance.ids.content_layout.add_widget(message_label)

        ok_button = FormButton(text=popup_instance.app.lang.get('ok_popup'), min_width=dp(140), pos_hint={'center_x': 0.5})
        ok_button.bind(on_release=popup_instance.dismiss)
        popup_instance.ids.content_layout.add_widget(ok_button)

        # Update popup size after layout
        Clock.schedule_once(lambda dt: popup_instance.update_size())

        return popup_instance

    @classmethod
    def create_confirmation_popup(
            cls, title, message,
            on_confirm, on_cancel=None,
            confirm_button_color=COLORS['RED']
        ):
        '''Create a popup with messages and event bind to cancel/confirm.'''
        gc.collect()

        popup_instance = cls()
        popup_instance._clear_styles()
        popup_instance.content = popup_instance.ids.content_layout

        title_label = PopupTitle(text=popup_instance.app.lang.get(title))
        title_label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
        popup_instance.ids.content_layout.add_widget(title_label)

        message_label = PopupMessage(text=popup_instance.app.lang.get(message))
        message_label.bind(texture_size=lambda instance, value: setattr(instance, 'height', value[1]))
        popup_instance.ids.content_layout.add_widget(message_label)

        #width b1 + width b2 + spacing to center TODO: find a better way to center
        buttons = BoxLayout(width=300, height=40, spacing=20, size_hint=(None, None), pos_hint={'center_x': 0.5})
        cancel_btn = FormButton(text=popup_instance.app.lang.get('cancel_popup'), min_width=dp(140))
        confirm_btn = FormButton(text=popup_instance.app.lang.get('ok_popup'), min_width=dp(140), bg_color=confirm_button_color)
        buttons.add_widget(cancel_btn)
        buttons.add_widget(confirm_btn)
        popup_instance.ids.content_layout.add_widget(buttons)

        def _on_cancel(instance):
            popup_instance.dismiss()
            if on_cancel:
                on_cancel()

        def _on_confirm(instance):
            result = on_confirm()
            if result:
                popup_instance.dismiss()

        cancel_btn.bind(on_release=_on_cancel)
        confirm_btn.bind(on_release=_on_confirm)

        # Update popup size after layout
        Clock.schedule_once(lambda dt: popup_instance.update_size())

        return popup_instance

    @staticmethod
    def _build_image_scroll_widget(image_path):
        img_src = cv2.imread(image_path)
        if img_src is None:
            return AsyncImage(source=image_path, size_hint=(1, 1))

        orig_h, orig_w = img_src.shape[:2]

        scroll_view = ScrollView(
            size_hint=(1, 1),
            do_scroll_x=False,
            do_scroll_y=True,
            effect_cls=ScrollEffect,
            scroll_type=['bars'],
            bar_width=dp(9),
        )
        img_widget = Widget(size_hint=(1, None), height=400)
        scroll_view.add_widget(img_widget)

        # Keep track of bound handlers so we can unbind them on re-render
        _handlers = {}

        def _do_load(dt):
            # padding right 15dp for scrollbar (old layout)
            target_w = int(img_widget.width - dp(15))
            if target_w < 100:
                Clock.schedule_once(_do_load, 0.05)
                return

            target_h = int(orig_h * target_w / orig_w)
            interp = cv2.INTER_AREA if orig_w >= target_w else cv2.INTER_LANCZOS4
            scaled = cv2.resize(img_src, (target_w, target_h), interpolation=interp)
            scaled = cv2.flip(scaled, 0)  # OpenGL origin is bottom-left

            tex = Texture.create(size=(target_w, target_h), colorfmt='bgr')
            tex.blit_buffer(scaled.tobytes(), colorfmt='bgr', bufferfmt='ubyte')
            tex.mag_filter = 'nearest'
            tex.min_filter = 'nearest'

            # cover widget height higher (or equal) than the height of ScrollView to have vertical center space
            container_h = max(target_h, scroll_view.height)
            img_widget.height = container_h

            # Offset to make the image in the center vertically in img_widget
            y_offset = (container_h - target_h) / 2.0

            img_widget.canvas.clear()

            # Unbind old handlers (if any) before binding new ones
            old_pos_handler = _handlers.get('pos')
            old_width_handler = _handlers.get('width')
            if old_pos_handler is not None:
                img_widget.unbind(pos=old_pos_handler, height=old_pos_handler)
            if old_width_handler is not None:
                img_widget.unbind(width=old_width_handler)

            with img_widget.canvas:
                rect = Rectangle(
                    texture=tex,
                    pos=(img_widget.x, img_widget.y + y_offset),
                    size=(target_w, target_h),
                )

            # Update the position when the widget moves / changes height
            def _update_rect_pos(instance, *args):
                new_offset = (img_widget.height - target_h) / 2.0
                rect.pos = (img_widget.x, img_widget.y + new_offset)

            img_widget.bind(pos=_update_rect_pos, height=_update_rect_pos)

            # Re-render if width changes significantly (popup resize after update_size())
            def _on_width_change(instance, new_w, _tw=target_w):
                if abs(int(new_w) - _tw) > 50:
                    img_widget.unbind(width=_on_width_change)
                    Clock.schedule_once(_do_load, 0)

            img_widget.bind(width=_on_width_change)

            # Save handlers for next re-render so we can unbind properly
            _handlers['pos'] = _update_rect_pos
            _handlers['width'] = _on_width_change

        Clock.schedule_once(_do_load, 0)
        return scroll_view

    @classmethod
    def create_preview_popup(
            cls, image_path,
            blur_value, min_area_value, threshold_value, event_intensity_value,
            validated_parameters=None,
            on_preview=None, on_apply=None, on_close=None, on_open_folder=None,
            button_color=COLORS['LIGHT_BLACK']
        ):
        '''Create a popup with image preview and confirmation parameters.

        Args:
            title: Title key for the popup
            image_path: Path to the preview image
            blur_value: Default value for blur input
            min_area_value: Default value for min area input
            threshold_value: Default value for threshold slider
            event_intensity_value: Default value for event intensity input
            on_preview: Callback for preview button (receives parameter dict)
            on_confirm: Callback for confirm button (receives parameter dict)
            on_cancel: Callback for cancel button
            button_color: Color for all three buttons
        '''
        gc.collect()

        popup_instance = cls()
        popup_instance._clear_styles()
        popup_instance.content = popup_instance.ids.content_layout
        popup_instance.auto_dismiss = False
        left_ratio = DefaultValuesC3.C3_PREVIEW_LEFT_RATIO / (DefaultValuesC3.C3_PREVIEW_LEFT_RATIO + DefaultValuesC3.C3_PREVIEW_RIGHT_RATIO)
        right_ratio = DefaultValuesC3.C3_PREVIEW_RIGHT_RATIO / (DefaultValuesC3.C3_PREVIEW_LEFT_RATIO + DefaultValuesC3.C3_PREVIEW_RIGHT_RATIO)

        # The root wrapper for image_container and right_column
        content_wrapper = BoxLayout(
            orientation='horizontal',
            size_hint=(1, None),
            height=Window.height * 0.5,
            spacing=dp(24)
        )

        image_container = BoxLayout(
            size_hint=(left_ratio, 1),
            padding=[dp(10), dp(10), dp(8), dp(10)]
        )
        with image_container.canvas.before:
            Color(COLORS['DOVE_WHITE'])
            bg_rect = Rectangle(pos=image_container.pos, size=image_container.size)

        image_container.bind(
            pos=lambda *_: setattr(bg_rect, 'pos', image_container.pos),
            size=lambda *_: setattr(bg_rect, 'size', image_container.size)
        )

        # Bind content_wrapper height to Window height changes
        def update_image_container_height(*args):
            content_wrapper.height = Window.height * 0.5
        Window.bind(size=update_image_container_height)

        # Image Display — load via PIL (resize if needed), then convert to Kivy texture
        scroll_view = cls._build_image_scroll_widget(image_path)
        image_container.add_widget(scroll_view)

        # Create label with initial text from validated_parameters
        initial_format_args = {}
        if validated_parameters and isinstance(validated_parameters, dict):
            initial_format_args = {
                'blur': validated_parameters.get('blur'),
                'threshold': validated_parameters.get('threshold'),
                'min_area': validated_parameters.get('min_area'),
                'event_intensity': validated_parameters.get('event_intensity'),
                'show_bbox': validated_parameters.get('show_bbox'),
                'show_info': validated_parameters.get('show_info'),
                'overlay': validated_parameters.get('overlay')
            }
        filename = os.path.basename(image_path) if image_path else ""
        lang_str = popup_instance.app.lang.get('old_result_label_C3') or "old_result_label_C3"
        fmt_args = initial_format_args or {}

        try:
            # First, check if {image_path} placeholder is in the localized string
            if "{image_path}" in lang_str:
                # Use the tag-in-variable trick to escape bolding for the path
                fmt_args['image_path'] = f"[/b]{filename}[b]"
                combined_text = f"[b]{lang_str.format(**fmt_args)}[/b]"
            else:
                # Manually append the path if it's missing from translation
                sep = " ／ " if popup_instance.app.current_language_code == 'ja' else " / "
                formatted_base = lang_str.format(**fmt_args)
                combined_text = f"[b]{formatted_base}[/b]{sep}{filename}"
        except Exception:
            # Final fallback: show key and filename to avoid empty label or crash
            combined_text = f"[b]{lang_str}[/b]   {filename}"


        old_result_label = Label(
            text=combined_text,
            size_hint=(None, None),
            height=dp(40),
            color=COLORS['MEDIUM_GRAY'],
            font_size=dp(15.2),
            padding=[0, dp(10), 0, dp(10)],
            markup=True,
            halign='left',
            valign='top',
            text_size=(None, None)
        )
        old_result_label.bind(texture_size=lambda instance, size: setattr(instance, 'width', size[0]))

        # Right side - Options UI
        right_column = C3PreviewOptionsSection(size_hint=(right_ratio, 1))

        try:
            cursor_img = resource_path('app/libs/assets/icons/new-moon.png')
        except Exception:
            cursor_img = os.path.abspath(os.path.join('app', 'libs', 'assets', 'icons', 'new-moon.png'))

        right_column.ids.transparency_slider.cursor_image = cursor_img

        # Explicitly set right column default states if provided in validated_parameters
        if validated_parameters and isinstance(validated_parameters, dict):
            if 'show_bbox' in validated_parameters:
                right_column.ids.chk_bbox.active = validated_parameters['show_bbox'] == '1'
            if 'show_info' in validated_parameters:
                right_column.ids.chk_info.active = validated_parameters['show_info'] == '1'
            if 'overlay' in validated_parameters:
                try:
                    right_column.ids.transparency_slider.value = float(validated_parameters['overlay'])
                except ValueError:
                    pass

        content_wrapper.add_widget(image_container)
        content_wrapper.add_widget(right_column)


        top_container = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
        )
        top_container.add_widget(content_wrapper)
        top_container.add_widget(old_result_label)

        popup_instance._image_container = image_container
        popup_instance._old_result_label = old_result_label
        popup_instance._validated_parameters = validated_parameters

        c3_section = C3SettingsSection()

        top_container.add_widget(c3_section)
        popup_instance.ids.content_layout.add_widget(top_container)

        # Store reference to c3_section for validation
        popup_instance.c3_section = c3_section

        # Set values after widget is added to tree (KV will handle initialization)
        c3_section.ids.c3_blur_input.ids.input_box.text = blur_value
        c3_section.ids.c3_min_area_input.ids.input_box.text = min_area_value
        c3_section.ids.c3_threshold_slider.ids.input_box.text = threshold_value
        c3_section.ids.c3_event_intensity.ids.input_box.text = event_intensity_value

        # Three Buttons
        buttons = BoxLayout(
            width=Window.width * 0.6,
            height=dp(40),
            spacing=dp(20),
            size_hint=(1, None),
        )

        preview_btn = FormButton(
            text=popup_instance.app.lang.get('preview_button'),
            min_width=dp(140),
            bg_color=button_color
        )
        apply_btn = FormButton(
            text=popup_instance.app.lang.get('apply_setting_button'),
            min_width=dp(140),
            bg_color=button_color
        )
        open_folder_btn = FormButton(
            text=popup_instance.app.lang.get('open_folder_button'),
            min_width=dp(140),
            bg_color=COLORS['BLUE']
        )
        close_btn = FormButton(
            text=popup_instance.app.lang.get('close_preview_button'),
            min_width=dp(140),
            bg_color=button_color
        )

        buttons.add_widget(Label(
            text='',
            size_hint_x=1,
            width=Window.width * 0.05))
        buttons.add_widget(preview_btn)
        buttons.add_widget(apply_btn)
        buttons.add_widget(open_folder_btn)
        buttons.add_widget(close_btn)
        buttons.add_widget(Label(
            text='',
            size_hint_x=1,
            width=Window.width * 0.05))
        buttons_anchor = AnchorLayout(
            anchor_x='center',
            anchor_y='center',
            size_hint_y=None,
            height=dp(40)
            )
        buttons_anchor.add_widget(buttons)
        popup_instance.ids.content_layout.add_widget(buttons_anchor)

        def get_parameters():
            '''Get current parameter values from inputs'''
            def _clean(t):
                return t.lstrip('0') or '0' if t and t.isdigit() else t

            return {
                'blur': _clean(popup_instance.c3_section.ids.c3_blur_input.ids.input_box.text),
                'min_area': _clean(popup_instance.c3_section.ids.c3_min_area_input.ids.input_box.text),
                'threshold': _clean(popup_instance.c3_section.ids.c3_threshold_slider.ids.input_box.text),
                'event_intensity': _clean(popup_instance.c3_section.ids.c3_event_intensity.ids.input_box.text),
                'show_bbox': str(int(right_column.ids.chk_bbox.active)),
                'show_info': str(int(right_column.ids.chk_info.active)),
                'overlay': f"{right_column.ids.transparency_slider.value:.2f}"
            }

        def _on_preview(instance):
            '''Handle preview button click'''
            if on_preview:
                params = get_parameters()
                on_preview(params)

        def _on_apply(instance):
            '''Handle apply button click'''
            if on_apply:
                params = get_parameters()
                result = on_apply(params)
                if result:
                    popup_instance.dismiss()
            else:
                popup_instance.dismiss()

        def _on_close(instance):
            '''Handle close button click'''
            popup_instance.dismiss()
            if on_close:
                on_close()

        def _on_open_folder(instance):
            '''Handle open folder button click'''
            if on_open_folder:
                on_open_folder()

        preview_btn.bind(on_release=_on_preview)
        apply_btn.bind(on_release=_on_apply)
        open_folder_btn.bind(on_release=_on_open_folder)
        close_btn.bind(on_release=_on_close)

        def update_size(*args):
            '''Update popup size after layout'''
            if popup_instance.content:
                # Make popup responsive based on screen dimensions
                # Width: 60% of screen width
                popup_instance.content_layout_width = Window.width * 0.6

                # Height: 85% of screen height
                popup_instance.content_layout_height = Window.height * 0.85

                popup_instance.size = (popup_instance.content_layout_width + dp(40), popup_instance.content_layout_height + dp(20))
                popup_instance.ids.content_layout.spacing = dp(40)

        # Initial size update
        Clock.schedule_once(lambda dt: update_size())

        # Bind to Window size changes for dynamic resizing
        Window.bind(size=update_size)

        return popup_instance

    def _remove_image_from_preview_popup(self):
        '''Delete image from image_container in preview popup (keep image_container)'''
        if not hasattr(self, '_image_container'):
            print("[PreviewPopup] Image container not found")
            return False

        image_container = self._image_container

        # Find and delete AsyncImage or ScrollView in image_container
        for widget in image_container.children[:]:
            if isinstance(widget, (AsyncImage, ScrollView)):
                image_container.remove_widget(widget)
                return True

        print("[PreviewPopup] No image found in container")
        return False

    def _load_image_to_preview_popup(self, image_path):
        '''Load image to image_container in preview popup

        Args:
            image_path: Path to the image file to load
        '''
        if not hasattr(self, '_image_container'):
            print("[PreviewPopup] Image container not found")
            return False

        if not os.path.exists(image_path):
            print(f"[PreviewPopup] Image path not found: {image_path}")
            return False

        image_container = self._image_container

        # Delete old image (if any)
        for widget in image_container.children[:]:
            if isinstance(widget, (AsyncImage, ScrollView)):
                image_container.remove_widget(widget)
                break

        # Create and add new image — load via PIL (resize if needed), then convert to Kivy texture
        try:
            scroll_view = self._build_image_scroll_widget(image_path)
            image_container.add_widget(scroll_view)
            return True
        except Exception as e:
            print(f"[PreviewPopup] Error loading image: {e}")
            return False

class MyModal(ModalView):
    '''Application modal style.'''

class LogViewerBox(ScrollView):
    '''Scroll view specialized for displaying application log entries.'''
    default_message = StringProperty("(Tiến trình và kết quả sẽ được hiển thị ở đây.)")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._user_scroll = False
        self.app = App.get_running_app()
        Clock.schedule_once(self.show_default_message, 0.1)

    def on_kv_post(self, base_widget):
        '''Kv post event handler'''
        self.container = self.ids.get('log_container', None)
        self.bind(on_scroll_start=self.scroll_binding)
        return super().on_kv_post(base_widget)

    def scroll_binding(self, *args): #check user interception
        '''Check if user is scrolling'''
        if self.collide_point(*self.to_widget(*Window.mouse_pos)) and not self._user_scroll:
            self._user_scroll = True

    def show_default_message(self, *args):
        """Show default message when log viewer is empty"""
        try:
            self.add_log_line(
                text=self.default_message,
                log_id='training_status_placeholder'
                )
        except (AttributeError, ReferenceError):
            traceback.print_exc()

    def clear_logs(self, show_default=True):
        """Clear all logs and optionally show default message"""
        self.container.clear_widgets()
        self.reset_scroll_to_top()
        if show_default:
            Clock.schedule_once(self.show_default_message, 0.1)

    def clear_logs_key(self, default_key=None):
        """Clear all logs and optionally show default message"""
        self.container.clear_widgets()
        self.reset_scroll_to_top()
        def show_default_message(*args):
            self.add_log_line_key(text_key=default_key)
        if default_key:
            Clock.schedule_once(show_default_message, 0.1)

    def clear_logs_for_training(self):
        """Clear all logs without showing default message (for training)"""
        self.clear_logs(show_default=False)

    def add_log_line_key(self, text_key, color=COLORS['WHITE'], format_args=None):
        '''Add log line to the log viewer by its key'''
        def add(*args):
            label = KeyLabel(
                text_key=text_key,
                format_args=format_args,
                color=color,
                size_hint_y=None,
                halign='left',
                valign='top'
            )
            label.bind(width=lambda *x: setattr(label, "text_size", (label.width, None)))
            label.bind(texture_size=label.setter("size"))
            self.container.add_widget(label)
            self.auto_scroll_to_latest()
        if not text_key.strip():
            text_key = " " #add empty
        Clock.schedule_once(add, 0)

    def add_log_line(self, text, color=COLORS['WHITE'], log_id=None):
        '''Add log line to the log viewer'''
        def add(*args):
            label = Label(
                text=text,
                color=color,
                size_hint_y=None,
                halign='left',
                valign='top'
            )
            if log_id:
                label.log_id = log_id

            label.bind(width=lambda *x: setattr(label, "text_size", (label.width, None)))
            label.bind(texture_size=label.setter("size"))
            self.container.add_widget(label)
            self.auto_scroll_to_latest()
        if not text.strip():
            text = " " #add empty
        Clock.schedule_once(add, 0)

    def update_log_line_by_id(self, log_id, new_text, new_color=None):
        """Update log line by its ID"""
        for label in self.container.children:
            if hasattr(label, 'log_id') and label.log_id == log_id:
                label.text = new_text
                if new_color:
                    label.color = new_color
                break


    def auto_scroll_to_latest(self):
        '''Auto scroll to the bottom of the log viewer. Deactivate if user interacted to the UI'''
        def _scroll_to_bottom(*args):
            try:
                if self._user_scroll:
                    return #no_scroll
                self.scroll_y = 0.0
            except Exception as e:
                print(f"Lỗi khi auto scroll log viewer: {e}")

        Clock.schedule_once(_scroll_to_bottom, 0.01)

    def reset_scroll_to_top(self):
        """Reset scroll của log viewer về đầu (top)"""
        try:
            self._user_scroll = False
            self.scroll_y = 1.0
        except Exception as e:
            print(f"Lỗi khi reset scroll log viewer: {e}")

class InfoBoxSimple(BoxLayout):
    '''Simple information box used to present short messages to users.'''
    directory_path = StringProperty('')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.app = App.get_running_app()
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = 44
        self.padding = [15, 10]  # padding: 10px 15px
        self.spacing = 5

        self.size_hint_x = 1

        with self.canvas.before:
            # Background #f8f9fa
            Color(0.973, 0.976, 0.980, 1)
            self.bg_rect = RoundedRectangle(radius=[4])

            # Border-left #95a5a6
            Color(0.584, 0.647, 0.651, 1)
            self.left_border = Rectangle()

        self.label_prefix = KeyLabel(
            text_key='current_directory_label_C3',
            markup_template='[b]{}[/b]',
            color=COLORS['MEDIUM_BLACK'],
            size_hint_x=None,
            width=180,
            halign='left',
            valign='middle',
        )
        self.label_prefix.bind(size=self.label_prefix.setter('text_size'))

        self.label_suffix = Label(
            text=f"[i]{self.directory_path}[/i]",
            markup=True,
            color=(0.333, 0.333, 0.333, 1),  # #555555
            halign='left',
            valign='middle',
            shorten=True,
            shorten_from='center',
            size_hint_x=1,
        )
        self.label_suffix.bind(size=self.label_suffix.setter('text_size'))

        self.add_widget(self.label_prefix)
        self.add_widget(self.label_suffix)

        self.bind(pos=self.update_canvas, size=self.update_canvas)
        self.bind(directory_path=self.update_directory_text)


    def update_directory_text(self, instance, value):
        """Callback được gọi khi directory_path thay đổi"""
        if self.label_suffix:
            self.label_suffix.text = f"[i]{value}[/i]"

    def update_canvas(self, *args):
        '''Update canvas position'''
        self.bg_rect.pos = self.pos
        self.bg_rect.size = self.size
        self.left_border.pos = (self.x, self.y)
        self.left_border.size = (3, self.height)
class KeyLabel(Label):
    '''Label used to display keyboard key names or shortcuts.'''
    text_key = StringProperty("")
    format_args = ObjectProperty(None)
    markup_template = StringProperty("")
class TouchBlocker(Widget):
    '''Widget that intercepts touch events to block interaction.'''
    def __init__(self, allow_scroll=True, allow_widget=None, **kwargs):
        kwargs.setdefault("size", Window.size)
        kwargs.setdefault("pos", (0, 0))
        super().__init__(**kwargs)
        self.allow_scroll = allow_scroll
        self.background_color = (0, 0, 0, 0.5)
        self.allow_widget = allow_widget or []

    def collide_point(self, x, y):
        """Block everywhere except where an allowed widget sits."""
        for widget in self.allow_widget:
            local_pos = widget.to_widget(x, y)
            if widget.collide_point(*local_pos):
                return False
        return super().collide_point(x, y)

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if touch.is_mouse_scrolling and self.allow_scroll:
            return False
        return True

    def on_touch_move(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if touch.is_mouse_scrolling and self.allow_scroll:
            return False
        return True

    def on_touch_up(self, touch):
        if not self.collide_point(*touch.pos):
            return False
        if touch.is_mouse_scrolling and self.allow_scroll:
            return False
        return True

class LocalTouchBlocker(Widget):
    '''Region-specific touch blocker that prevents local interactions.'''
    active = False  # toggle

    def on_touch_down(self, touch):
        if self.active and self.collide_point(*touch.pos):
            return True
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if self.active and self.collide_point(*touch.pos):
            return True
        return super().on_touch_up(touch)


class CircleWidget(Widget):
    '''Widget that renders a circle or circular indicator.'''
    circle_color = ColorProperty(COLORS['VERY_LIGHT_GRAY'])  # Default #DDDDDD

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.update_circle, size=self.update_circle)
        self.bind(circle_color=self.update_circle)
        Clock.schedule_once(lambda dt: self.draw_circle(), 0)

    def draw_circle(self):
        '''Draw circle'''
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.circle_color)
            self.ellipse = SmoothEllipse(pos=self.pos, size=self.size)

    def update_circle(self, *args):
        '''Update circle position'''
        if hasattr(self, 'ellipse'):
            self.ellipse.pos = self.pos
            self.ellipse.size = self.size
        self.draw_circle()

class StepIndicator(BoxLayout):
    '''Widget showing a multi-step progress indicator.'''
    current_step = NumericProperty(0)
    total_steps = NumericProperty(4)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.bind(current_step=self.update_steps)
        self.step_line_active = resource_path('app/libs/assets/icons/step_line_active.png')
        self.step_line_inactive = resource_path('app/libs/assets/icons/step_line_inactive.png')
        Clock.schedule_once(lambda dt: self.build_steps(), 0)

    def build_steps(self):
        """Build the step indicator UI"""
        self.clear_widgets()

        for i in range(self.total_steps):
            # Create step container
            step_container = BoxLayout(
                orientation='horizontal',
                # Give space to the connector line by expanding all but the last container
                size_hint_x=1 if i < self.total_steps - 1 else None,
                width=dp(36),
                size_hint_y=None,
                height=dp(36)
            )

            # Create circle with number overlay using FloatLayout
            circle_layout = FloatLayout(
                size_hint=(None, None),
                size=(dp(36), dp(36))
            )

            circle_widget = CircleWidget(
                circle_color=self.get_circle_color(i),
                size_hint=(None, None),
                size=(dp(36), dp(36)),
                pos_hint={'center_x': 0.5, 'center_y': 0.5}
            )
            circle_widget.step_index = i  # Store index for updates

            # Number label
            number_label = Label(
                text=str(i + 1),
                font_size=dp(18),
                bold=True,
                color=self.get_label_color(i),
                size_hint=(None, None),
                size=(dp(36), dp(36)),
                pos_hint={'center_x': 0.5, 'center_y': 0.5},
                halign='center',
                valign='middle'
            )
            number_label.step_index = i  # Store index for updates
            number_label.bind(size=number_label.setter('text_size'))

            circle_layout.add_widget(circle_widget)
            circle_layout.add_widget(number_label)
            step_container.add_widget(circle_layout)

            # Add line between steps (except for last step)
            if i < self.total_steps - 1:
                line_img = AsyncImage(
                    source=self.get_line_source(i),
                    size_hint_x=1,
                    size_hint_y=None,
                    height=dp(4),
                    pos_hint={'center_y': 0.5},
                    fit_mode='fill'
                )
                line_img.step_index = i  # Store index for updates
                step_container.add_widget(line_img)
            self.add_widget(step_container)

    def get_circle_color(self, step_index):
        """Get circle color based on current step"""
        if step_index <= self.current_step:
            return COLORS['BLUE']
        else:
            return COLORS['VERY_LIGHT_GRAY']

    def get_line_source(self, step_index):
        """Get line image source based on current step"""
        if step_index < self.current_step:
            return resource_path(self.step_line_active)
        else:
            return self.step_line_inactive

    def get_label_color(self, step_index):
        """Get label color based on current step"""
        if step_index <= self.current_step:
            return COLORS['WHITE']  # White for active/current
        else:
            return COLORS['MEDIUM_GRAY']  # Gray for inactive

    def update_steps(self, *args):
        """Update all steps when current_step changes"""
        for child in self.children:
            for widget in child.children:
                # Update direct Image widgets (the connector lines)
                if isinstance(widget, AsyncImage) and hasattr(widget, 'step_index'):
                    step_idx = widget.step_index
                    if 'line' in widget.source:
                        widget.source = self.get_line_source(step_idx)
                # Update nested widgets inside the circle container
                if hasattr(widget, 'children') and widget.children:
                    for inner_widget in widget.children:
                        if isinstance(inner_widget, CircleWidget) and hasattr(inner_widget, 'step_index'):
                            step_idx = inner_widget.step_index
                            inner_widget.circle_color = self.get_circle_color(step_idx)
                        elif isinstance(inner_widget, Label) and hasattr(inner_widget, 'step_index'):
                            step_idx = inner_widget.step_index
                            inner_widget.color = self.get_label_color(step_idx)
