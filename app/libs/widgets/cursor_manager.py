"""Module providing cursor management utilities for Kivy applications.

This module defines the `CursorManager` class, which handles system cursor
changes in a stack-based manner to ensure consistent cursor state management.
"""
from collections import deque
from kivy.core.window import Window
from kivy.logger import Logger
from kivy.clock import Clock

class CursorManager:
    """Manages system cursor changes with a stack-based approach.

    Handles cursor state transitions, maintains a stack of cursor requests,
    and provides safe fallback mechanisms for cursor operations.
    """
    def __init__(self):
        self._cursor_options = ['arrow', 'hand', 'wait', 'crosshair', 'no']
        self._cursor_stack = deque()   # track requests
        self._cursor_changed = False
        self._current_cursor = 'arrow'
        Window.bind(mouse_pos=self._on_mouse_move)  # one-time global binding

    def _on_mouse_move(self, *args):
        '''Force refresh cursor on mouse move'''
        try:
            Window.set_system_cursor(self._current_cursor)
        except Exception:
            Logger.error("CursorManager: Failed to set cursor", exc_info=True)

    def _apply_cursor(self, *args):
        '''Apply top of stack or fallback to arrow.'''
        new_cursor = self._cursor_stack[-1] if self._cursor_stack else 'arrow'
        if new_cursor != self._current_cursor:
            try:
                Window.set_system_cursor(new_cursor)
                self._current_cursor = new_cursor
                self._cursor_changed = new_cursor != 'arrow'
            except Exception:
                try: #safe fallback
                    Window.set_system_cursor('arrow')
                    self._current_cursor = 'arrow'
                    self._cursor_changed = False
                except Exception:
                    Logger.error("CursorManager: Even fallback cursor failed", exc_info=True)

    def _schedule_apply(self):
        Clock.schedule_once(self._apply_cursor, 0)

    def get_current_cursor(self):
        '''Return current cursor type.'''
        return self._current_cursor

    def set_cursor(self, cursor_type='arrow'):
        '''Request a cursor change. Push to stack.'''
        if cursor_type not in self._cursor_options:
            Logger.error("CursorManager: Invalid cursor type: %s", cursor_type)
            return
        if cursor_type == self._current_cursor:
            return
        if len(self._cursor_stack) >= 50: # Safety check: avoid unbounded growth
            Logger.warning(
                "CursorManager: Stack too large (%s), "
                "possible leak. Resetting to 'arrow'.",
                len(self._cursor_stack)
            )
            self.reset()  # clear stack + apply arrow
            return
        self._cursor_stack.append(cursor_type)
        self._schedule_apply()

    def restore_cursor(self):
        '''Release last cursor request. Pop from stack.'''
        if self._cursor_stack:
            self._cursor_stack.pop()
        self._schedule_apply()

    def reset(self):
        '''Clear all cursor requests.'''
        self._cursor_stack.clear()
        self._schedule_apply()
