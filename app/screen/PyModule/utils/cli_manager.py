"""
CLI Manager Module
==================

This module provides the `CLIManager` class, responsible for managing and running
CLI subprocesses in the background. It handles process tracking, cleanup, and
automatic focus of application windows after launch.

Features:
- Start Python scripts or modules in subprocesses
- Manage subprocess lifecycles and clean up on exit
- Focus application windows by title
- Threaded execution for UI-friendly async tasks
"""

import atexit
import os
import subprocess
import threading
import time
import traceback
from typing import List

import psutil
import win32con
import win32gui
import win32process
from kivy.clock import Clock
from kivy.logger import Logger

from app.env import BE_FOLDER, PYTHON_RUNNER
from app.pipeline.server_manager import start_main_pipe_server_process
from app.screen.PyModule.utils.propagating_thread import PropagatingThread


class CLIManager:
    """
    A manager for handling CLI subprocesses and threading tasks within the app.

    Responsibilities:
    - Start, monitor, and clean up subprocesses
    - Focus windows based on title
    - Run background tasks in threads while showing loading popups

    Attributes:
        _active_subprocesses (set): Tracks currently active subprocesses.
        _cleanup_registered (bool): Indicates if cleanup handler was registered.
    """

    _active_subprocesses = set()
    _cleanup_registered = False

    def __init__(self):
        # Register cleanup function only once
        if not CLIManager._cleanup_registered:
            atexit.register(self._cleanup_all_subprocesses)
            CLIManager._cleanup_registered = True
    def _focus_windows(self, windows):
        """Helper method to focus a list of windows"""
        for hwnd in windows:
            try:
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                time.sleep(0.3)
                win32gui.SetForegroundWindow(hwnd)
                time.sleep(0.3)
            except Exception:
                traceback.print_exc()
        return True

    def _focus_window_by_title(self, title=None, proc=None):
        if title is None:
            return False

        found_windows = []
        max_attempts = 20
        attempt = 0

        while proc is None or proc.poll() is None:
            attempt += 1

            if attempt > max_attempts:
                break

            for t in title:
                hwnd = win32gui.FindWindow(None, t)
                if hwnd and hwnd not in found_windows:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    try:
                        pname = psutil.Process(pid).name()
                    except Exception:
                        pname = "?"
                    if pname == 'python.exe':
                        found_windows.append(hwnd)

            if len(found_windows) == len(title):
                return self._focus_windows(found_windows)

            time.sleep(0.5)

        if found_windows:
            return self._focus_windows(found_windows)

        return False

    @classmethod
    def _cleanup_all_subprocesses(cls):
        """Cleanup all active subprocesses when app exits"""
        Logger.info("CLIManager: Cleaning up %s active subprocesses...", len(cls._active_subprocesses))
        for proc in list(cls._active_subprocesses):
            try:
                if proc.poll() is None:  # Process still running
                    Logger.info("CLIManager: Terminating subprocess PID and its children: %s", proc.pid)
                    proc_parent = psutil.Process(proc.pid)
                    for proc_child in proc_parent.children(recursive=True):
                        proc_child.terminate()
                    proc_parent.terminate()
                    # Give it 3 seconds to terminate gracefully
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        Logger.warning("CLIManager: Force killing subprocess PID and its children: %s", proc.pid)
                        for proc_child in proc_parent.children(recursive=True):
                            proc_child.kill()
                        proc_parent.kill()
            except Exception as e:
                Logger.error("CLIManager: Error cleaning up subprocess PID %s: %s", proc.pid, e)
        cls._active_subprocesses.clear()
        Logger.info("CLIManager: Subprocess cleanup completed")

    @classmethod
    def terminate_all_subprocesses(cls):
        """Manually terminate all active subprocesses (for app shutdown)"""
        cls._cleanup_all_subprocesses()

    @classmethod
    def get_active_subprocess_count(cls):
        """Get count of currently active subprocesses"""
        return len(cls._active_subprocesses)

    @classmethod
    def terminate_subprocess_by_pid(cls, pid):
        """Terminate a specific subprocess by PID"""
        for proc in list(cls._active_subprocesses):
            if proc.pid == pid:
                try:
                    if proc.poll() is None:
                        proc.terminate()
                        proc.wait(timeout=3)
                    cls._active_subprocesses.discard(proc)
                    return True
                except Exception as e:
                    Logger.error("CLIManager: Error terminating subprocess PID %s: %s", pid, e)
                    return False
        return False

    def _run_cli(self,
                 arg_list,
                 script_path=None,
                 module_name=None,
                 use_module: bool = True,
                 title_window_focus: List[str] = None,
                 cwd: str = BE_FOLDER,
                 use_pipe_server: bool = True,
                 runner: str = None,
                 debug: bool = True,
                 log_callback = None):
        # Use current Python interpreter if no runner specified
        if runner is None:
            runner = PYTHON_RUNNER

        if use_module:
            if not module_name:
                raise ValueError("module_name is required when use_module=True")
            command = runner.split() + ["-m", module_name] + list(arg_list)
        else:
            if not script_path:
                raise ValueError("script_path is required when use_module=False")
            command = runner.split() + [script_path] + list(arg_list)

        Logger.info("CLIManager: Running command: %s", ' '.join(map(str, command)))

        try:
            if use_pipe_server:
                start_main_pipe_server_process()
            env = os.environ.copy()
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUNBUFFERED"] = "1"

            stderr_handling = subprocess.STDOUT if log_callback else subprocess.PIPE

            proc = subprocess.Popen(
                command,
                cwd=cwd,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                stdout=subprocess.PIPE,
                stderr=stderr_handling,
                bufsize=1 if log_callback else -1
            )

            # Track the subprocess for cleanup
            CLIManager._active_subprocesses.add(proc)
            Logger.info("CLIManager: Started subprocess PID: %s", proc.pid)

            # Start focus thread
            if title_window_focus:
                threading.Thread(
                    target=self._focus_window_by_title,
                    kwargs={"proc": proc, "title": title_window_focus},
                    daemon=True
                ).start()

            stdout = ""
            stderr = ""

            if isinstance(log_callback, bool):
                log_callback = (lambda x: Logger.info("CLIManager: %s", x)) if log_callback else None

            if log_callback:
                # Stream output
                while True:
                    line = proc.stdout.readline()
                    if not line and proc.poll() is not None:
                        break
                    if line:
                        log_callback(line.rstrip())
                        if debug:
                            stdout += line

                # Process has finished
                remaining_stdout, _ = proc.communicate()
                if debug and remaining_stdout:
                    stdout += remaining_stdout
            else:
                # Standard blocking wait
                stdout, stderr = proc.communicate()

            # Remove from tracking after completion
            CLIManager._active_subprocesses.discard(proc)
            Logger.info("CLIManager: Subprocess PID %s completed with return code: %s", proc.pid, proc.returncode)

            if debug:
                if not log_callback:
                    Logger.info("CLIManager: [OUTPUT]\n%s", stdout)
                if stderr:
                    Logger.info("CLIManager: [DEBUG]\n%s", stderr)

            return proc.returncode == 0
        except Exception as e:
            # Clean up subprocess if it was created but failed
            if 'proc' in locals():
                CLIManager._active_subprocesses.discard(proc)
                try:
                    if proc.poll() is None:
                        proc.terminate()
                except Exception:
                    traceback.print_exc()
            Logger.error("CLIManager: Error in _run_cli: %s", e)
            return False

    def _run_task_in_thread(self, task_fn, loading_title='loading_popup'):
        """
        Run a task in a background thread with loading popup

        Args:
            task_fn: Function to run in thread
            loading_title: Title for loading popup
        """
        self.loading_popup = self.popup.create_loading_popup(title=loading_title)
        self.loading_popup.open()
        thread = PropagatingThread(target=task_fn)
        thread.start()
        Clock.schedule_interval(lambda dt: self._check_thread(dt, thread), 0.5)
