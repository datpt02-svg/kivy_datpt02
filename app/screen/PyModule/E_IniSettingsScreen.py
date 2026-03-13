'''Screen E2: IniSettingsScreen'''

from kivy.logger import Logger
from kivy.properties import StringProperty
#from kivy.core.window import Window

from app.screen.PyModule.utils.ini_editor import IniEditor
from app.libs.widgets.components import MyPopup, FormScreen, FormGroup, FormLabel, FormButton, CompFormInput
from app.env import INI_PATH

class IniSettingsScreen(FormScreen):
    '''E2 main class.'''
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.popup = MyPopup()
        self.ini_section_list = []
        self.ini_editor = IniEditor(ini_file_path=INI_PATH, skip_key_symbols=('_'))

    def on_kv_post(self, base_widget):
        self.form_mapping = {
            "ini_section_layout": self.ids.ini_section_layout,
            "save_button_layout": self.ids.save_button_layout
        }
        return super().on_kv_post(base_widget)

    def on_pre_enter(self, *args):
        #Window.bind(focus=self.on_window_focus)
        self.ids.main_scroll_view.scroll_y = 1
        self.build_dynamic_form()
        return super().on_pre_enter(*args)

    def on_pre_leave(self, *args):
        #Window.unbind(focus=self.on_window_focus)
        self.reset_form()
        return super().on_pre_leave(*args)

    def on_window_focus(self, instance, value):
        '''Handle window focus event to reload settings. Note: Not used atm.'''
        if value:
            Logger.info("IniSettingsScreen: Window refocused. Reloading settings.")
            self.build_dynamic_form()

    def _export_data(self):
        '''Export current UI data to a dictionary.'''
        data = {} # { section: { key: value } }
        for block in self.ini_section_list:
            section_name = block.section_name
            key_value_dict = block.key_value_dict
            data[section_name] = key_value_dict
        return data

    def _read_ini_settings(self):
        '''Read INI settings and populate the UI.'''
        try:
            ini_data = self.ini_editor.parse_ini() # { section: { key: value } }
            if ini_data:
                for section_name, key_value_dict in ini_data.items():
                    block = IniSectionBlock()
                    block.set_section_name(section_name)
                    for key, value in key_value_dict.items():
                        block.set_key_value_pair(key, value)
                    self.form_mapping['ini_section_layout'].add_widget(block)
                    self.ini_section_list.append(block)
                return True
            else: # (not data and is_contain_invalid_line) or (not data)
                block = FormLabel(text_key='not_setup_ini_message_E2')
                self.form_mapping['ini_section_layout'].add_widget(block)
                return False
        except FileNotFoundError:
            block = FormLabel(text_key='no_ini_settings_message_E2')
            self.form_mapping['ini_section_layout'].add_widget(block)
            return False
        except Exception:
            Logger.error("Error reading ini file.", exc_info=1)
            block = FormLabel(text_key='ini_error_message_E2')
            self.form_mapping['ini_section_layout'].add_widget(block)
            return False

    def _save_ini_settings(self):
        '''Save current settings to the INI file.'''
        try:
            self.ini_editor.save_ini(entries=self._export_data())
            success_popup = self.popup.create_adaptive_popup(
                title="notification_popup",
                message="save_ini_success_message"
            )
            success_popup.open()
        except Exception:
            failed_popup = self.popup.create_adaptive_popup(
                title="error_popup",
                message="save_ini_failed_message"
            )
            failed_popup.open()

    def reset_form(self):
        '''Clear all widgets from the INI section layout.'''
        self.form_mapping['save_button_layout'].clear_widgets()
        self.form_mapping['ini_section_layout'].clear_widgets()
        self.ini_section_list = []

    def build_dynamic_form(self):
        '''Build dynamic UI components.'''
        self.reset_form()
        # show ini rows
        parse_ini_state = self._read_ini_settings()
        # show save button
        if parse_ini_state:
            save_button = SaveButton()
            save_button.bind(on_release=lambda *_: self._save_ini_settings())
            self.form_mapping['save_button_layout'].add_widget(save_button)

class SaveButton(FormButton):
    '''Save button for INI settings.'''

class IniSectionBlock(FormGroup):
    '''Ini file section block.'''
    section_name = StringProperty('Empty section_name')
    def __init__(self, **kwargs):
        self.key_value_dict = {}
        super().__init__(**kwargs)

    def set_section_name(self, section_name):
        '''Set the section name.'''
        self.section_name = section_name

    def set_key_value_pair(self, key, value):
        '''Add a key-value pair to the section block.'''
        key_value_pair = CompFormInput(
            orientation='vertical',
            use_label_text_key=False,
            label_bold=False,
            label_markup=False,
            label_text=key,
            text=value
        )
        key_value_pair.ids.form_input.bind(text=lambda instance, val: self.update_value(key, val))
        self.ids.key_value_group.add_widget(key_value_pair)
        self.key_value_dict[key] = value

    def update_value(self, key, value):
        '''Update the value for a specific key.'''
        self.key_value_dict[key] = value
