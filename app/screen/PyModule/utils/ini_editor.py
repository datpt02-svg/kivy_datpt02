'''
Helper class to read and write INI files.
Allow behavior:
- Ignores invalid lines and continue.
- Skip orphan keys before any section.
- Sections with inline comments are supported (e.g., [Section]; comment).
- Duplicate sections are merged.
- Whitespace in section names is preserved (e.g., [  Section  ]).
- Empty sections [] are allowed and stored as an empty string.
- Inline comments in values are NOT stripped (e.g., key = value ; comment -> value includes "; comment").
- Keys starting with "_" are skipped during parsing.
- `save_ini` logic only updates existing keys; it does not create new sections or keys. Use `set_ini` to add new keys or sections.
'''

import os
from kivy.logger import Logger

class IniEditor:
    '''Ini Editor'''
    def __init__(self, ini_file_path, skip_key_symbols = ()):
        self.ini_file_path = ini_file_path
        self.skip_key_symbols = skip_key_symbols
        #self.is_contain_invalid_line = False

    def create_ini(self):
        '''Create an empty INI file.'''
        if os.path.exists(self.ini_file_path):
            Logger.info("IniEditor: File already exists at '%s', skipping creation.", self.ini_file_path)
            return
        try:
            with open(self.ini_file_path, 'w', encoding='utf-8') as f:
                f.write('')  # Create an empty file
            Logger.info("IniEditor: Created empty INI file at '%s'", self.ini_file_path)
        except Exception as e:
            Logger.error("IniEditor: Error creating INI file at '%s'.", self.ini_file_path, exc_info=1)
            raise Exception("IniEditor: Error creating INI file.") from e

    def parse_ini(self):
        '''Parse the INI file and return a dictionary.'''
        data = {} # { section: { key: value } }
        n_line = 0
        current_section = None
        #self.is_contain_invalid_line = False
        try:
            with open(self.ini_file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    n_line += 1
                    line = line.strip()
                    # skip comments and empty
                    if not line or line.startswith((';', '#')):
                        continue
                    # find section
                    section_end = line.find(']')
                    if line.startswith('[') and section_end != -1:
                        suffix = line[section_end+1:].strip()
                        if not suffix or suffix.startswith((';', '#')):
                            current_section = line[1:section_end]
                            if current_section not in data:
                                data[current_section] = {}
                            continue
                    # find key
                    if '=' in line and current_section is not None:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        if key == '':
                            Logger.warning("IniEditor: Invalid .ini format detected at line %d:'%s'", n_line, line)
                            continue
                        value = value.strip()
                        # Custom skip key logic.
                        if self.skip_key_symbols:
                            if key.startswith(self.skip_key_symbols):
                                Logger.info("IniEditor: Skipping key '%s' due to skip_key_symbols.", key)
                                continue
                        data[current_section][key] = value
                    # if not a comment, section or key value pair
                    else:
                        #self.is_contain_invalid_line = True
                        Logger.warning("IniEditor: Invalid .ini format detected at line %d:'%s'", n_line, line)
            return data
        except FileNotFoundError:
            Logger.error("IniEditor: File not found '%s'", self.ini_file_path)
            raise
        except Exception as e:
            raise Exception("IniEditor: Error while parsing ini file.") from e

    def set_ini(self, section, key, value):
        '''Set a key-value pair in a specific section.
        Creates the section or key if they do not exist.
        '''
        try:
            with open(self.ini_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            section_found = False
            key_updated = False
            in_section = False
            section_line_index = -1

            # Find if section and key exist, and update if so
            for i, line in enumerate(lines):
                stripped = line.strip()

                if stripped.startswith('[') and ']' in stripped:
                    section_end = stripped.find(']')
                    suffix = stripped[section_end+1:].strip()
                    if not suffix or suffix.startswith((';', '#')):
                        current_section_name = stripped[1:section_end]
                        if current_section_name == section:
                            section_found = True
                            in_section = True
                            section_line_index = i
                        else:
                            in_section = False

                if in_section and (stripped.startswith(key + '=') or stripped.startswith(key + ' =')):
                    indent = line[:len(line) - len(line.lstrip())]
                    lines[i] = f"{indent}{key} = {value}\n"
                    key_updated = True
                    break

            if not key_updated:
                if section_found:
                    # Insert key into existing section
                    insert_pos = len(lines)  # Default to end of file
                    for i in range(section_line_index + 1, len(lines)):
                        stripped = lines[i].strip()
                        if stripped.startswith('[') and ']' in stripped:
                            section_end = stripped.find(']')
                            suffix = stripped[section_end+1:].strip()
                            if not suffix or suffix.startswith((';', '#')):
                                insert_pos = i
                                break
                    lines.insert(insert_pos, f"{key} = {value}\n")
                else:
                    # Append new section and key
                    if lines and not lines[-1].endswith('\n'):
                        lines.append('\n')
                    if lines:
                        lines.append('\n')
                    lines.append(f'[{section}]\n')
                    lines.append(f'{key} = {value}\n')

            with open(self.ini_file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
        except FileNotFoundError:
            Logger.error("IniEditor: File not found '%s'", self.ini_file_path)
            raise
        except Exception as e:
            Logger.error("IniEditor: Error while setting key '%s' in section '%s'.", key, section, exc_info=1)
            raise Exception(f"IniEditor: Error while setting key '{key}'.") from e

    def save_ini(self, entries:dict):
        '''Save the entries back to the INI file.'''
        new_lines = []
        current_section = None

        pending_keys = set()
        for section, keys in entries.items():
            for key in keys:
                pending_keys.add((section, key))

        try:
            # read ini file
            with open(self.ini_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in lines:
                stripped = line.strip()
                # parse section
                if stripped.startswith('[') and ']' in stripped:
                    section_end = stripped.find(']')
                    suffix = stripped[section_end+1:].strip()
                    if not suffix or suffix.startswith((';', '#')):
                        current_section = stripped[1:section_end]
                        new_lines.append(line)
                        continue
                # parse key value
                if not stripped.startswith((';', '#')) and '=' in stripped:
                    parts = stripped.split('=', 1) # [0] key [1] value
                    current_key = parts[0].strip()

                    if current_key in entries.get(current_section, {}):
                        # remove newline symbol
                        new_value = str(entries[current_section][current_key]).replace('\n', '').replace('\r', '')
                        prefix = line.split('=', 1)[0] + '= '
                        if line.endswith('\n'):
                            new_line = f"{prefix}{new_value}\n"
                        else:
                            new_line = f"{prefix}{new_value}"
                        new_lines.append(new_line)
                        pending_keys.discard((current_section, current_key))
                    else:
                        new_lines.append(line)
                else:
                    new_lines.append(line)

            if pending_keys:
                raise Exception(f"The following keys were not found in the INI file: {pending_keys}")

            with open(self.ini_file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            Logger.info("IniEditor: Ini settings updated.")
        except Exception as e:
            Logger.error("IniEditor: Error while saving ini file.", exc_info=1)
            raise Exception("IniEditor: Error while saving ini file.") from e
