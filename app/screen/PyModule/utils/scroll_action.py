"""
This module provides utility functions to control scroll behavior in Kivy
ScrollView widgets. It includes helpers to automatically scroll to a specific
widget or to the first visible error message widget on the screen.

Functions:
    - scroll_to_first_error(scroll_view, padding=150):
        Smoothly scrolls to the first ErrorMessage widget that contains text.
    - scroll_to_widget(scroll_view, widget, padding=0):
        Smoothly scrolls the ScrollView to the specified target widget.

These functions are commonly used to improve user experience in forms or
validation flows where automatic focus or scrolling feedback is required.
"""

from kivy.animation import Animation
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.logger import Logger
from kivy.clock import Clock

from app.libs.constants.default_values import DefaultAnimation

def scroll_to_first_error(scroll_view: ScrollView, padding: int = 150) -> None:
    '''Scroll the given ScrollView to the first visible ErrorMessage widget with non-empty text.'''
    def scroll_action(*args):
        try:
            error_widgets = [
                w for w in scroll_view.walk(restrict=True)
                if w.__class__.__name__ == "ErrorMessage" and w.text.strip()
            ]
            if not error_widgets:
                return
            # Get the topmost ErrorMessage
            first_error = max(error_widgets, key=lambda w: w.to_window(w.x, w.y)[1])
            y_pos = float(first_error.y + first_error.height + padding) / float(max(1, scroll_view.children[0].height)) #avoid div by 0
            norm_y_pos = min(max(y_pos, 0), 1)#clamp
            # snap to edges if close
            if norm_y_pos < DefaultAnimation.EDGE_SNAP_THRESHOLD:
                norm_y_pos = 0.0
            elif norm_y_pos > (1-DefaultAnimation.EDGE_SNAP_THRESHOLD):
                norm_y_pos = 1.0

            Animation.cancel_all(scroll_view, 'scroll_y')
            Animation(scroll_y=norm_y_pos, d=0.4, t='out_quad').start(scroll_view)
        except Exception:
            Logger.error("ScrollError: Failed to scroll to first error")
    Clock.schedule_once(scroll_action, 0)

def scroll_to_widget(scroll_view: ScrollView, widget: Widget, padding: int = 0) -> None:
    '''Scroll the given ScrollView to the specified widget.'''
    def scroll_action(*args):
        try:
            y_pos = float(widget.y + widget.height + padding) / float(max(1, scroll_view.children[0].height)) #avoid div by 0
            norm_y_pos = min(max(y_pos, 0), 1)#clamp
            # snap to edges if close
            if norm_y_pos < DefaultAnimation.EDGE_SNAP_THRESHOLD:
                norm_y_pos = 0.0
            elif norm_y_pos > (1-DefaultAnimation.EDGE_SNAP_THRESHOLD):
                norm_y_pos = 1.0

            Animation.cancel_all(scroll_view, 'scroll_y')
            Animation(scroll_y=norm_y_pos, d=0.4, t='out_quad').start(scroll_view)
        except Exception:
            Logger.error("ScrollError: Failed to scroll to widget %s", widget)
    Clock.schedule_once(scroll_action, 0)
