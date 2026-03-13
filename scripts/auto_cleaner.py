"""
Auto Cleaner Script
This script is designed to automatically clean up old files from a specified directory.
It is intended to be scheduled via Windows Task Scheduler to run periodically.

CLI Arguments:
python auto_cleaner.py --log_dir /path/to/logs --ini_dir /path/to/ini
--log_dir: Directory to store log folder.
--ini_dir: Directory containing delete_setting.ini.

Usage:
1. Ensure 'delete_setting.ini' exists in the working directory.
   Example 'delete_setting.ini' content:
       [general]
       enabled = True
       enabled_logging = True
       log_file = auto_cleaner.log

       [detection_results]
       target_dir = C:\\path\\to\\data
       days_to_keep = 7

2. Schedule this script using Windows Task Scheduler.
   - Action: Start a program
   - Program/script: C:\\path\\to\\python.exe
   - Add arguments: C:\\path\\to\\auto_cleaner.py --log_dir C:\\path\\to\\log_dir --ini_dir C:\\path\\to\\ini_folder
   - Start in (Optional): None

Exit Codes:
- 0: Success
- 0x8007054F: Internal error (visible in Task Scheduler)
"""

import os
import sys
import logging
import configparser
import argparse
from datetime import datetime, timedelta
logger = logging.getLogger("auto_cleaner_logger")
logger.setLevel(logging.INFO)

INI_FILENAME = "delete_setting.ini"

def delete_files(delete_path:str, days_to_keep:int) -> bool:
    '''Delete a file if it is older than the specified number of days.'''
    if os.path.exists(delete_path):
        try:
            creation_time = datetime.fromtimestamp(os.path.getctime(delete_path))
            if datetime.now() - creation_time > timedelta(days=days_to_keep):
                os.remove(delete_path)
                logger.info("Auto Cleaner: Removed file: %s", delete_path)
                return True
        except OSError as e:
            logger.warning("Auto Cleaner: Failed to remove file %s: %s", delete_path, e)
    return False

def config_logger(log_dir: str, filename:str = "auto_cleaner.log", enabled_logging:bool = True):
    '''Configure the logger to write to a file.'''
    if logger.handlers:
        logger.handlers.clear()
    if not enabled_logging:
        return
    log_file_path = os.path.join(log_dir, filename)
    os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

def get_hex(hex_code):
    '''Convert an unsigned hex code to a signed 32-bit integer.'''
    # If the code is larger than the max signed 32-bit int (0x7FFFFFFF),
    # we must convert it to its negative signed equivalent.
    if hex_code > 0x7FFFFFFF:
        # This bitwise operation converts the unsigned bit pattern to a signed python int
        hex_code = hex_code - 0x100000000
    return hex_code

def main():
    '''Main function to execute the auto cleaner logic.'''
    parser = argparse.ArgumentParser(description="Auto-cleaner for detection results.")
    parser.add_argument('--log_dir', default=os.getcwd(), help="Directory to store log folder.")
    parser.add_argument('--ini_dir', default=os.getcwd(), help="Directory containing delete_setting.ini.")
    args = parser.parse_args()

    log_dir = os.path.join(args.log_dir, "logs")
    ini_path = os.path.join(args.ini_dir, INI_FILENAME)
    try:
        config = configparser.ConfigParser(strict=False, interpolation=None, inline_comment_prefixes=(';', '#'))

        if not os.path.exists(ini_path):
            raise FileNotFoundError(f"File not found '{ini_path}'")
        try:
            config.read(ini_path, encoding='utf-8')
        except Exception as e:
            raise Exception("Error while parsing ini file.") from e

        # Config logger
        log_filename = config.get('general', 'log_file', fallback="auto_cleaner.log") # Fallback to "auto_cleaner.log" if no [general] or log_file provided
        enable_logging = config.getboolean('general', 'enabled_logging', fallback=True) # Similarly, fallback to True
        config_logger(log_dir, log_filename, enabled_logging=enable_logging)

        # Validate
        if not config.sections():
            raise Exception("No settings found in 'delete_setting.ini'.")
        if not config.has_section("general"):
            raise Exception("No [general] section found in 'delete_setting.ini'.")
        if not config.has_section("detection_results"):
            raise Exception("No [detection_results] section found in 'delete_setting.ini'.")
        target_dir = config.get("detection_results", "target_dir", fallback="")
        if not target_dir:
            raise Exception("No 'target_dir' found in 'delete_setting.ini'.")
        if not os.path.exists(target_dir):
            raise Exception(f"'target_dir' does not exist, path: '{target_dir}'")
        if not config.getboolean("general", "enabled", fallback=True):
            logger.info("Auto Cleaner: File deletion is disabled in 'delete_setting.ini'. Skipping file deletion.")
            sys.exit(0)
        days_to_keep = config.getint("detection_results", "days_to_keep", fallback=None)
        if days_to_keep is None or days_to_keep <= 0 or days_to_keep > 999:
            raise Exception("Invalid or missing 'days_to_keep' value in 'delete_setting.ini', must be an integer between 1 and 999.")

        # Execute
        deleted_info = []
        if os.path.exists(target_dir):
            for root, _, files in os.walk(target_dir, topdown=False):
                for file in files:
                    file_path = os.path.join(root, file)
                    is_deleted = delete_files(
                        file_path,
                        days_to_keep=days_to_keep
                    )
                    if is_deleted:
                        deleted_info.append(file_path)

                if os.path.abspath(root) != os.path.abspath(target_dir):
                    try:
                        if not os.listdir(root):
                            os.rmdir(root)
                            logger.info("Auto Cleaner: Removed empty directory: %s", root)
                    except OSError as e:
                        logger.warning("Auto Cleaner: Failed to delete directory %s: %s", root, e)

        logger.info("Auto Cleaner: File deletion completed. Deleted %s files.", len(deleted_info))
        sys.exit(0)

    except Exception as e:
        # Ensure logger is configured (fallback) if an error occurred before config was loaded
        if not logger.handlers:
            config_logger(log_dir)
        error_message = f"Auto Cleaner: An error occurred. Details: {e}"
        logger.error(error_message)
        sys.exit(get_hex(hex_code=0x8007054F)) # display "An internal error occurred" in Task Scheduler

if __name__ == "__main__":
    main()
