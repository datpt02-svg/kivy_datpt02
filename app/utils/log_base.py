"""
This module sets up a logger named 'dimmer_logger' that writes log messages
to daily log files in the 'logs' directory.
"""
import datetime
import logging
import os

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
current_time_str = datetime.datetime.now().strftime("%Y-%m-%d")

LOG_FILE_NAME = f"pipe_client_{current_time_str}.log"
log_file_path = os.path.join(LOG_DIR, LOG_FILE_NAME)

logger = logging.getLogger("dimmer_logger")
logger.setLevel(logging.INFO)

if not logger.handlers:
    # Handler ghi file
    file_handler = logging.FileHandler(log_file_path, encoding='utf-8')
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # console_handler = logging.StreamHandler()
    # console_handler.setFormatter(formatter)
    # logger.addHandler(console_handler)
