"""
This module implements a Windows named pipe client that continuously connects
to a server pipe defined by `PIPE_TO_UI_NAME` and listens for incoming messages.
When data is received, it decodes and forwards it to a registered callback.

It uses the `pywin32` library for pipe operations and runs the listener in
a background thread.
"""
import threading
import time
import traceback

import pywintypes
import win32file

from app.env import PIPE_TO_UI_NAME
from app.utils.log_base import logger

_pipe_data_callback = None

def set_pipe_data_callback(callback):
    """
    Register a callback function to be invoked when data is received from the pipe.

    Args:
        callback (Callable[[str], None]): Function that takes the decoded string data.
    """
    global _pipe_data_callback
    _pipe_data_callback = callback

def _pipe_client_listener_thread():
    """
    Internal thread function that connects to the named pipe and continuously
    listens for data from the server. If the connection drops, it retries automatically.
    """
    logger.info("Trying to connect to pipe: %s...", PIPE_TO_UI_NAME)
    while True:
        handle = None
        try:
            handle = win32file.CreateFile(
                PIPE_TO_UI_NAME,
                win32file.GENERIC_READ,
                0, None,
                win32file.OPEN_EXISTING,
                0, None
            )
            logger.info("Connected to server (handle: %s)", handle)
            while True:
                _, data = win32file.ReadFile(handle, 64 * 1024)
                if not data:
                    logger.info("Server closed the pipe. Trying to reconnect")
                    break
                decoded_data = data.decode('utf-8').strip()
                logger.info(decoded_data)
                if _pipe_data_callback:
                    _pipe_data_callback(decoded_data)

        except pywintypes.error as e:
            if e.winerror == 2:
                pass
            elif e.winerror == 109:
                logger.warning("The pipe has been ended.")
            elif e.winerror == 231:
                logger.error("Pipe is busy. Retrying")
            else:
                logger.error("Win32 error when connecting: %s", e)
            time.sleep(1)
        except Exception as e:
            logger.error("General error when connecting: %s", e)
            traceback.print_exc()
            time.sleep(1)

def start_pipe_client():
    """
    Start the background thread that listens for pipe messages if not already running.
    """
    global _pipe_client_thread_instance
    if _pipe_client_thread_instance is None or not _pipe_client_thread_instance.is_alive():
        _pipe_client_thread_instance = threading.Thread(target=_pipe_client_listener_thread, daemon=True)
        _pipe_client_thread_instance.start()

_pipe_client_thread_instance = None
if __name__ == '__main__':
    start_pipe_client()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.error("\nApp Client (simulated) is exiting...")
