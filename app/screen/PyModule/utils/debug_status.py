"""
Utilities for managing and applying debug settings within the application.

Functions:
- `get_debug_status(db)`: Retrieves the current debug status from the database.
- `apply_debug_setting(debug_value)`: Applies the debug setting to the Kivy Logger.
"""

from kivy.logger import Logger
from app.services.system_config import read_system_config

def get_debug_status(db):
    '''Get debug status.'''
    try:
        config = read_system_config(db, "DEBUG")
        if config:
            if str(config.value) == "1":
                return True
            elif str(config.value) == "0":
                return False
            else:
                raise ValueError("Invalid debug value")
    except Exception:
        Logger.error("Invalid debug value. Defaulting to OFF.")
    return False

def apply_debug_setting(debug_value: str) -> str:
    '''Apply debug setting.'''
    try:
        if debug_value == "0":
            Logger.info("Debug mode: OFF")
            Logger.setLevel('INFO')
            return int(debug_value)
        elif debug_value == "1":
            Logger.info("Debug mode: ON")
            Logger.setLevel('DEBUG')
            return int(debug_value)
        else:
            raise ValueError("Invalid debug value")
    except Exception:
        Logger.error("Error applying debug setting. Defaulting to OFF.", exc_info=1)
        Logger.setLevel('INFO')
        return 0
