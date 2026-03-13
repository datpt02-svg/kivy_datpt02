"""Language management module for handling multi-language support.

This module provides functionality to load and retrieve localized strings
from JSON language files.
"""

import json
import os
from app.utils.paths import resource_path

class LangManager:
    """Manages language strings and localization for the application.

    This class handles loading language files and retrieving localized strings
    with support for required field markers and color formatting.
    """
    def __init__(self, current_lang='ja', base_path=resource_path('app/libs/language')):
        """Initialize the LangManager.

        Args:
            current_lang (str, optional): The current language code. Defaults to 'ja'.
            base_path (str, optional): The base path to language files. Defaults to resource_path('app/libs/language').
        """
        self.strings = {}
        self.current_lang = current_lang
        self.base_path = base_path

    def load_language(self, lang_code='ja'):
        """Load language strings from a JSON file.

        Args:
            lang_code (str, optional): The language code to load. Defaults to 'ja'.

        Raises:
            FileNotFoundError: If the language file is not found, prints an error message.
        """
        if lang_code is not None:
            self.current_lang = lang_code
        file_path = os.path.join(self.base_path, f'strings_{lang_code}.json')
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                self.strings = json.load(f)
        except FileNotFoundError:
            print(f"ERROR: File not found '{file_path}' for language '{lang_code}'. Trying default 'ja'.")

    def get(self, key, default_text='', required=False, hex_color=None):
        """Retrieve a localized string by key.

        Args:
            key (str): The key to look up in the language strings.
            default_text (str, optional): Default text if key is not found. Defaults to ''.
            required (bool, optional): If True, adds a red asterisk marker. Defaults to False.
            hex_color (str, optional): Hex color code to wrap the text. Defaults to None.

        Returns:
            str: The localized string with optional formatting, or the key itself if not found.
        """
        if key == "":
            return ""
        value = self.strings.get(key)
        if value is None:
            print(f"DEBUG: Key '{key}' not found in language '{self.current_lang}'. Returning key name or default.")
            return key
        if required:
            if value.endswith(':'):
                value = value[:-1]
                value += ' [color=#ff0000]*[/color]:'
            elif value.endswith('：'):
                value = value[:-1]
                value += ' [color=#ff0000]*[/color]：'
            else:
                value += ' [color=#ff0000]*[/color]:' if self.current_lang == 'vi' else ' [color=#ff0000]*[/color]：'
        if hex_color:
            value = f'[color={hex_color}]{value}[/color]'
        return value
