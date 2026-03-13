"""
Single Instance Manager
Ensures only one instance of the application can run at a time.
"""

import logging
import atexit
import ctypes

# Set up logging for this module
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import win32 modules, with fallback
try:
    import win32api
    import win32event
    import win32con
    WIN32_AVAILABLE = True
except ImportError as e:
    logger.warning("Win32 modules not available: %s", e)
    WIN32_AVAILABLE = False
    # Create dummy classes for fallback
    class DummyWin32API:
        """Fallback dummy for win32api when Win32 modules are unavailable."""
        @staticmethod
        def GetLastError():
            """Return 0 to simulate no error."""
            return 0
        @staticmethod
        def CloseHandle(handle):
            """Do nothing when closing handle (dummy)."""
            pass

    class DummyWin32Event:
        """Fallback dummy for win32event when Win32 modules are unavailable."""
        @staticmethod
        def CreateMutex(*args, **kwargs):
            """Return None to simulate mutex creation."""
            return None

    class DummyWin32Con:
        """Fallback constants for win32con when Win32 modules are unavailable."""
        ERROR_ALREADY_EXISTS = 183
        MB_OK = 0
        MB_ICONWARNING = 48

    win32api = DummyWin32API()
    win32event = DummyWin32Event()
    win32con = DummyWin32Con()


class SingleInstanceManager:
    """Manages single instance enforcement using Windows named mutex."""

    def __init__(self, app_name="EVS-UI"):
        """
        Initialize the single instance manager.

        Args:
            app_name (str): Unique name for the application mutex
        """
        self.app_name = app_name
        self.mutex_name = f"Global\\{app_name}_SingleInstance"
        self.mutex = None
        self.is_first_instance = False

    def check_single_instance(self):
        """
        Check if this is the first instance of the application.

        Returns:
            bool: True if this is the first instance, False if another instance is already running
        """
        if not WIN32_AVAILABLE:
            logger.warning("Win32 modules not available, skipping single instance check")
            self.is_first_instance = True
            return True

        try:
            # Try to create a named mutex
            self.mutex = win32event.CreateMutex(
                None,  # Security attributes (None = default)
                False,  # Initial owner (False = not owned initially)
                self.mutex_name  # Mutex name
            )

            # Check if the mutex already existed (another instance is running)
            last_error = win32api.GetLastError()

            if last_error == 183:  # ERROR_ALREADY_EXISTS
                logger.info("Another instance of %s is already running", self.app_name)
                self.is_first_instance = False
                return False
            else:
                logger.info("Starting first instance of %s", self.app_name)
                self.is_first_instance = True
                return True

        except Exception as e:
            logger.error("Error creating mutex for single instance check: %s", e)
            # If we can't create the mutex, assume this is the first instance
            self.is_first_instance = True
            return True

    def release_mutex(self):
        """Release the mutex when the application is closing."""
        if not WIN32_AVAILABLE:
            return

        try:
            if self.mutex:
                win32api.CloseHandle(self.mutex)
                self.mutex = None
                logger.info("Released mutex for %s", self.app_name)
        except Exception as e:
            logger.error("Error releasing mutex: %s", e)

    def show_existing_instance_message(self):
        """Show a message to the user that another instance is already running."""
        if not WIN32_AVAILABLE:
            logger.info("Another instance of %s is already running (win32 not available)", self.app_name)
            return

        try:

            # Show a message box
            ctypes.windll.user32.MessageBoxW(
                0,
                f"Another instance of {self.app_name} is already running.\n"
                f"Please close the existing instance before starting a new one.",
                f"{self.app_name} - Already Running",
                win32con.MB_OK | win32con.MB_ICONWARNING
            )
        except Exception as e:
            logger.error("Error showing existing instance message: %s", e)

    def cleanup(self):
        """Clean up resources when the application exits."""
        self.release_mutex()


def ensure_single_instance(app_name="EVS-UI"):
    """
    Convenience function to ensure only one instance of the application runs.

    Args:
        app_name (str): Unique name for the application

    Returns:
        bool: True if this is the first instance, False if another instance is running
    """
    manager = SingleInstanceManager(app_name)

    if not manager.check_single_instance():
        manager.show_existing_instance_message()
        manager.cleanup()
        return False

    # Store the manager globally so it can be cleaned up later
    atexit.register(manager.cleanup)

    return True
