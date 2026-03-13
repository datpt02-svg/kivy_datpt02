"""
Server Manager Module

This module manages the lifecycle of a backend pipe server process
that communicates with UI and logic components via Windows named pipes.

Main responsibilities:
- Start and monitor the backend pipe server process.
- Detect whether the pipe server is alive and responsive.
- Gracefully shut down or terminate the server when needed.
- Send shutdown signals via named pipes.

It uses `pywin32` for pipe operations and `psutil` for process management.
"""
import subprocess
import os
import time
import threading
import psutil
import win32file
import win32pipe
import pywintypes

from app.env import BE_FOLDER, PIPE_TO_UI_NAME, PIPE_TO_LOGIC_NAME, PYTHON_RUNNER

_pipe_server_process = None
_server_monitor_thread = None
_server_running_flag = threading.Event()

def _monitor_server_process():
    """
    Background thread function that monitors the backend pipe server process.

    This thread continuously checks whether the process is still running.
    If it stops, the internal running flag is cleared so other parts of the
    system know the server is no longer active.
    """
    global _pipe_server_process, _server_running_flag
    while True:
        if _pipe_server_process and _pipe_server_process.poll() is None:
            _server_running_flag.set()
        else:
            if _server_running_flag.is_set():
                print("[Server Manager] Server has stopped.")
            _server_running_flag.clear()
            _pipe_server_process = None
        time.sleep(0.5)

def start_server_monitor():
    """Start the server monitor thread if it is not running."""
    global _server_monitor_thread
    if _server_monitor_thread is None or not _server_monitor_thread.is_alive():
        _server_monitor_thread = threading.Thread(target=_monitor_server_process, daemon=True)
        _server_monitor_thread.start()
        print("[Server Manager] Server monitor thread started.")
    else:
        print("[Server Manager] Server monitor thread is already running.")


def is_pipe_server_actually_running() -> bool:
    """Check if the server is running and the pipe can be connected."""
    # First, check the status flag updated by the monitor thread
    if not _server_running_flag.is_set():
        return False

    # Then, try to connect to confirm the pipe is active (not stuck)
    try:
        handle = win32file.CreateFile(
            PIPE_TO_UI_NAME,
            win32file.GENERIC_READ,  # Only need read permission to check existence
            0, None,
            win32file.OPEN_EXISTING,
            0, None
        )
        win32file.CloseHandle(handle)
        return True
    except pywintypes.error as e:
        if e.winerror == 2:  # ERROR_FILE_NOT_FOUND (Pipe not created by server yet)
            print(f"[Server Manager] Pipe '{PIPE_TO_UI_NAME}' not found. Server may be stopped.")
        elif e.winerror == 231:  # ERROR_PIPE_BUSY (Pipe is busy, but still considered running)
            return True
        else:
            print(f"[Server Manager] Win32 error when checking pipe server: {e}")
        _server_running_flag.clear()  # Update flag if there is a real connection error
        return False
    except Exception as e:
        print(f"[Server Manager] Unknown error when checking pipe server: {e}")
        _server_running_flag.clear()
        return False


def start_main_pipe_server_process():
    """Start the main_pipe_server process if it is not running."""
    global _pipe_server_process, _server_running_flag

    # Ensure the monitor thread is running first
    start_server_monitor()

    if is_pipe_server_actually_running():
        print("[Server Manager] Pipe Server is already running. No need to restart.")
        return True

    print("[Server Manager] Pipe Server is not running or not responding. Starting...")
    server_command = PYTHON_RUNNER.split() + [
        os.path.join(BE_FOLDER, 'flows', 'pipe', 'base_pipe_server.py'),
    ]
    env = os.environ.copy()
    env['PYTHONIOENCODING'] = 'utf-8'
    _pipe_server_process = subprocess.Popen(
        server_command,
        cwd=BE_FOLDER,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    _server_running_flag.clear()  # Clear flag for monitor thread to update

    # Quick check if process crashed immediately
    time.sleep(0.5)
    if _pipe_server_process.poll() is not None:
        stdout, stderr = _pipe_server_process.communicate(timeout=1)
        print("[Server Manager] ERROR: Server process exited immediately!")
        if stdout:
            print(f"[Server Manager] STDOUT:\n{stdout}")
        if stderr:
            print(f"[Server Manager] STDERR:\n{stderr}")
        return False

    print("[Server Manager] Waiting for Pipe Server to be ready...")
    max_retries = 30
    for i in range(max_retries):
        if is_pipe_server_actually_running():
            print("[Server Manager] Pipe Server is ready.")
            return True
        print(f"[Server Manager] Waiting for server... ({i + 1}/{max_retries})")
        time.sleep(1)

    print("[Server Manager] Error: Pipe Server is not ready after multiple attempts. Please check server logs.")
    return False

def close_handle(pipename=PIPE_TO_UI_NAME, timeout_ms=100, max_retries=3):
    """
    Try to connect to the named pipe and send '__SHUTDOWN__' signal.
    Retries if the pipe is not yet ready or busy.
    Raises an exception if all retries fail.
    """
    last_exception = None

    for attempt in range(1, max_retries + 1):
        try:
            # Wait until a server pipe instance is available
            win32pipe.WaitNamedPipe(pipename, timeout_ms)
            # Connect to existing pipe
            client = win32file.CreateFile(
                pipename,
                win32file.GENERIC_WRITE,
                0, None,
                win32file.OPEN_EXISTING,
                0, None
            )
            win32file.WriteFile(client, b'__SHUTDOWN__\n')
            win32file.CloseHandle(client)
            print(f"[Server Manager] Sent graceful shutdown signal to {pipename} (attempt {attempt}).")
            return

        except pywintypes.error as e:
            last_exception = e
            # Common transient cases
            if e.winerror in (231, 121):  # PIPE_BUSY, SEM_TIMEOUT
                print(f"[Server Manager] Pipe {pipename} not ready (attempt {attempt}/{max_retries}): {e}")
                continue
            if e.winerror == 2: # FILE_NOT_FOUND:
                print(f"[Server Manager] Pipe {pipename} not found.")
                return
            else:
                print(f"[Server Manager] Unhandled pipe error: {e}")
                break

        except Exception as e:
            last_exception = e
            print(f"[Server Manager] Unexpected exception: {e}")
            break

    raise last_exception or RuntimeError(f"[Server Manager] Failed to send shutdown signal to {pipename}.")


def terminate_main_pipe_server_process():
    """
    Terminate the backend pipe server process and its children.

    Also attempts to send a '__SHUTDOWN__' signal to related pipes
    before killing the processes.

    This ensures a clean shutdown even if the server fails to exit gracefully.
    """
    global _pipe_server_process, _server_running_flag
    print("[Server Manager] Requesting server to shut down gracefully...")

    if _pipe_server_process:
        try:
            print("[Server Manager] Terminate pipe server process and its children...")
            parent = psutil.Process(_pipe_server_process.pid)
            children = parent.children(recursive=True)
            for child in children:
                child.kill()
            _pipe_server_process.kill()
        except psutil.NoSuchProcess:
            print("[Server Manager] Pipe server process already exited.")
        except Exception as e:
            print(f"[Server Manager] Error while terminating pipe server process: {e}")
        finally:
            _pipe_server_process = None
            _server_running_flag.clear()

    pipe_names = [PIPE_TO_LOGIC_NAME, PIPE_TO_UI_NAME]
    for pipename in pipe_names:
        try:
            close_handle(pipename=pipename)
        except Exception as e:
            print(f"[Server Manager] Could not send shutdown signal to {pipename}: {e}")
