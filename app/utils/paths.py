"""
Utility module for handling file paths in both development and frozen environments.
Provides functions to get runtime directory and resolve resource paths.
"""

import os
import sys


def run_dir() -> str:
    """
    Get the application's runtime directory.
    Returns the executable's directory if frozen, or project root in development.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)  # next to .exe file
    # In dev: this file is in app/utils → up 1 level to app → up again to
    # project root
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def root_path(rel: str) -> str:
    """
    Join a relative path with the runtime directory path.
    Args:
        rel: Relative path to join
    """
    return os.path.join(run_dir(), rel)


def resource_path(rel: str) -> str:
    """
    Get absolute path to resource, works for dev and for PyInstaller.
    Args:
        rel: Relative path to the resource
    """
    if getattr(sys, "frozen", False):
        # pylint: disable=protected-access
        base = sys._MEIPASS
    else:
        base = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", ".."))

    return os.path.join(base, rel).replace("\\", "/")
