'''UI Main File'''
import gc
import json

import win32api
import win32con

from kivy.animation import Animation
from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.loader import Loader
from kivy.logger import Logger
from kivy.uix.screenmanager import ScreenManager
from kivy.uix.button import Button
from kivy.properties import BooleanProperty
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import NumericProperty, ObjectProperty, StringProperty
from kivy.uix.boxlayout import BoxLayout
from kivy.metrics import dp

from app.libs.widgets.hover_behavior import HoverBehavior
from app.libs.constants.colors import COLORS
from app.pipeline.pipe_client import set_pipe_data_callback, start_pipe_client
from app.pipeline.server_manager import start_server_monitor, terminate_main_pipe_server_process
from app.screen.PyModule.utils.cli_manager import CLIManager
from app.screen.PyModule.utils.lang_manager import LangManager
from app.utils.paths import resource_path

def on_console_close(event):
    '''Handle console close events to ensure proper application shutdown.'''
    if event == win32con.CTRL_CLOSE_EVENT:
        Logger.info("Console is closed! Calling stop() manually.")
        app = App.get_running_app()
        if app:
            app.stop()
        return True  # notify that it has been handled
    return False

# Register console close handler
win32api.SetConsoleCtrlHandler(on_console_close, True)

#Add fonts
LabelBase.register(name='NotoSansJP',
                   fn_regular=resource_path('app/libs/assets/fonts/NotoSansJP-Regular.ttf'),
                   fn_bold=resource_path('app/libs/assets/fonts/NotoSansJP-Bold.ttf'))

class WindowManager(ScreenManager):
    '''ScreenManager subclass used as the application's top-level window manager.'''
    def __init__(self, **kwargs): # pylint: disable=useless-super-delegation
        super().__init__(**kwargs)

class MenuButton(Button, HoverBehavior):
    '''Button used in the menu with hover and animated background behavior.'''
    active = BooleanProperty(False)
    target_screen = StringProperty(None)
    bg_alpha = NumericProperty(0.0)

    def __init__(self, **kwargs):
        '''Initialize the menu button and prepare its background graphics.'''
        super().__init__(**kwargs)
        self.rect = None
        self.bg_color = None
        self.bg_animation = None
        self.color_animation = None
        self._create_background()

    def _create_background(self):
        '''Create and bind the background rectangle used for hover/active states.'''
        if not self.rect:
            with self.canvas.before:
                self.bg_color = Color(rgba=(0.204, 0.596, 0.859, 0))
                self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[4])
            self.bind(pos=self.update_rect, size=self.update_rect)
            self.bind(bg_alpha=self.update_bg_alpha)

    def on_touch_down(self, touch):
        '''Handle touch events; switch to the target screen when clicked.'''
        app = App.get_running_app()
        if self.collide_point(*touch.pos):
            app.switch_screen(self.target_screen, self)
            return True
        return super().on_touch_down(touch)

    def _animate_to_state(self, color_alpha, bg_alpha_value, transition='out_quart'):
        """Centralized animation method to eliminate code duplication"""
        self._stop_animations()

        self.color_animation = Animation(
            color=(1, 1, 1, color_alpha),
            duration=0.15,
            transition=transition
        )
        self.color_animation.start(self)

        self.bg_animation = Animation(
            bg_alpha=bg_alpha_value,
            duration=0.2,
            transition=transition
        )
        self.bg_animation.start(self)

    def on_enter(self):
        '''Animate to the hovered/entered visual state.'''
        self._animate_to_state(color_alpha=1.0, bg_alpha_value=1.0)

    def on_leave(self):
        '''Animate to the non-hovered visual state if not active.'''
        if not self.active:
            self._animate_to_state(color_alpha=0.7, bg_alpha_value=0.0)

    def _stop_animations(self):
        '''Stop any running animations and clear animation references.'''
        if self.bg_animation:
            self.bg_animation.cancel(self)
            self.bg_animation = None
        if self.color_animation:
            self.color_animation.cancel(self)
            self.color_animation = None

    def update_bg_alpha(self, *args):
        '''Update the background color alpha channel to match the bg_alpha property.'''
        if self.bg_color:
            self.bg_color.rgba = (0.204, 0.596, 0.859, self.bg_alpha)

    def update_rect(self, *args):
        '''Update the background rectangle position and size when the widget changes.'''
        if self.rect:
            self.rect.pos = self.pos
            self.rect.size = self.size

    def on_active(self, instance, value):
        '''React to changes in the active state to update visual appearance.'''
        if value:
            # Set active state immediately without animation
            self._stop_animations()
            self.color = (1, 1, 1, 1)
            self.bg_alpha = 1.0
        else:
            if not self.hovering:
                self._animate_to_state(color_alpha=0.7, bg_alpha_value=0.0, transition='out_cubic')

class RootBoxLayout(BoxLayout):
    '''Root layout that ignores right-click touch events to prevent context menus.'''

    def on_touch_down(self, touch):
        '''Ignore right-button clicks to prevent default context behavior.'''
        if touch.button == 'right':
            return True
        super().on_touch_down(touch)

class MainApp(App):
    '''Main Kivy application class responsible for initializing and running the UI.'''

    current_screen_button = ObjectProperty(None)
    current_language_code = StringProperty('ja')
    lang = ObjectProperty(None, rebind=True)

    def open_settings(self, *largs):#disable f1 settings
        '''Override to disable default open_settings behavior (F1).'''
        return

    def build(self):
        '''Build and return the root widget for the application.'''
        Window.clearcolor = COLORS['WHITE']
        Loader.loading_image = resource_path('app/libs/assets/icons/loading.gif')

        self.lang = LangManager()
        self.lang.load_language(self.current_language_code)
        self.title = self.lang.get("app_name_long")

        # read ui.kv
        ui_kv_path = resource_path("app/ui.kv")
        with open(ui_kv_path, encoding="utf-8") as f:
            kv_src = f.read()
        # patch kv file paths
        for rel in [
            "app/libs/widgets/components.kv",
            "app/screen/KivyModule/WelcomeScreen.kv",
            "app/screen/KivyModule/A_SensorSettingsScreen.kv",
            "app/screen/KivyModule/B_DataGenerationScreen.kv",
            "app/screen/KivyModule/B_WorkConfigScreen.kv",
            "app/screen/KivyModule/C_DataSelectionScreen.kv",
            "app/screen/KivyModule/C_ModelTrainingScreen.kv",
            "app/screen/KivyModule/C_TrainingResultsScreen.kv",
            "app/screen/KivyModule/D_AIDetectionExecutionScreen.kv",
            "app/screen/KivyModule/D_DetectionResultsScreen.kv",
            "app/screen/KivyModule/E_SystemSettingsScreen.kv",
            "app/screen/KivyModule/E_IniSettingsScreen.kv",
        ]:
            kv_src = kv_src.replace(rel, resource_path(rel).replace("\\", "/"))

        root_widget = Builder.load_string(kv_src)
        self.icon = resource_path("app/libs/assets/icons/icon.png")

        # Bind sidebar scroll to track state
        if 'sidebar_scroll_kv' in root_widget.ids:
            scroll_view = root_widget.ids.sidebar_scroll_kv
            self._sidebar_was_at_bottom = (scroll_view.scroll_y <= 0.02)
            scroll_view.bind(scroll_y=self._update_sidebar_scroll_state)

        return root_widget

    def switch_language(self, lang_code):
        '''Switch the application's current language and update UI text/fonts.'''
        self.current_language_code = lang_code
        new_lang = LangManager()
        new_lang.load_language(self.current_language_code)
        self.lang = new_lang
        self.title = self.lang.get("app_name_long")
        self.apply_font_to_all_widgets('NotoSansJP')

        if self.root and hasattr(self.root.ids, 'screen_manager'):
            for screen in self.root.ids.screen_manager.screens:
                if hasattr(screen, 'on_language'):
                    screen.on_language()

    def _update_sidebar_scroll_state(self, instance, value):
        '''Track if the sidebar is currently scrolled to the bottom.'''
        self._sidebar_was_at_bottom = (value <= 0.02)

    def on_sidebar_scroll_resize(self, scroll_view):
        '''Maintain scroll position or hide bar during resize.'''
        def fix_scroll(dt):
            # Check if content fits in the scrollview
            content_fits = scroll_view.viewport_size[1] <= scroll_view.height
            
            if content_fits:
                # If it fits (e.g. maximized), stay at the top and hide scrollbar
                scroll_view.scroll_y = 1
                scroll_view.bar_width = 0
            else:
                # If it doesn't fit, show scrollbar
                scroll_view.bar_width = dp(10)
                # Keep bottom position only if overflowed and was previously at bottom
                if hasattr(self, '_sidebar_was_at_bottom') and self._sidebar_was_at_bottom:
                    scroll_view.scroll_y = 0
                    
        Clock.schedule_once(fix_scroll, -1)

    def apply_font_to_all_widgets(self, font_name):
        '''Recursively apply a font name to all widgets that support font_name.'''
        # Recursively traverse all widgets to apply font_name where applicable
        def set_font(widget):
            if hasattr(widget, 'font_name'):
                widget.font_name = font_name
            for child in widget.children:
                set_font(child)

        set_font(self.root)

    def load_json(self, data: str) -> list:
        '''Load potentially multiple JSON objects concatenated in a single string.

        Returns a list of decoded JSON objects. Malformed trailing data is logged and
        causes parsing to stop early.'''
        decoder = json.JSONDecoder()
        pos = 0
        data_length = len(data)
        data_list = []

        while pos < data_length:
            try:
                obj, idx = decoder.raw_decode(data[pos:])
                pos += idx
                data_list.append(obj)
            except json.JSONDecodeError as e:
                Logger.error("Failed to parse JSON at position %d: %s", pos, e)
                break
        return data_list

    def on_start(self):
        '''Startup hook to initialize pipe callbacks, server monitor, and current screen.'''
        terminate_main_pipe_server_process()
        start_pipe_client()
        start_server_monitor()
        def pipe_callback(data):
            current_screen = self.root.ids.screen_manager.get_screen(self.root.ids.screen_manager.current)
            if hasattr(current_screen, 'on_pipe'):
                try:
                    data_list = self.load_json(data)
                    for data in data_list:
                        Clock.schedule_once(lambda dt, d=data: current_screen.on_pipe(d))
                except Exception as e:
                    Logger.error(str(e))
                    return
        set_pipe_data_callback(pipe_callback)
        if self.root and hasattr(self.root.ids, 'screen_manager') and self.root.ids.screen_manager.current:
            current_screen_widget = self.root.ids.screen_manager.get_screen(self.root.ids.screen_manager.current)
            if hasattr(current_screen_widget, 'on_language'):
                current_screen_widget.on_language()
            elif hasattr(current_screen_widget, 'on_enter'):
                current_screen_widget.on_enter()

    def _stop(self, *largs):
        '''Shutdown hook to terminate background servers and log stop events.'''
        Logger.info("Main App: Kivy application is stopping")

        # Terminate all active subprocesses
        active_count = CLIManager.get_active_subprocess_count()
        if active_count > 0:
            Logger.info("Terminating %s active subprocesses...", active_count)
            CLIManager.terminate_all_subprocesses()

        # Terminate kivy
        super()._stop()

        # Terminate pipeline server
        terminate_main_pipe_server_process()

        Logger.info("Main App: Kivy application has fully stopped")

    def switch_screen(self, screen_name, button_instance):
        '''Switch to a different screen and update the active menu button.'''
        gc.collect()
        if self.root and hasattr(self.root.ids, 'screen_manager'):
            self.root.ids.screen_manager.current = screen_name
            if self.current_screen_button:
                self.current_screen_button.active = False
            button_instance.active = True
            self.current_screen_button = button_instance
