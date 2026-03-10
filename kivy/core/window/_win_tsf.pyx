# cython: language_level=3
"""
Windows TSF (Text Services Framework) bridge for Kivy.

This module provides WinTSFBridge, a thin Cython wrapper around the
KivyTSFManager C++ class.  It is only compiled on Windows (platform == 'win32'
in setup.py) and is imported conditionally at runtime.

Usage::

    from kivy.core.window._win_tsf import WinTSFBridge
    bridge = WinTSFBridge()
    bridge.init_tsf(hwnd, on_composition)
    # when TextInput focuses:
    bridge.enable()
    # on cursor / text change:
    bridge.update_content(text, cursor_index, sel_start, sel_end)
    bridge.update_cursor_rect(screen_x, screen_y, width, height)
    # when TextInput unfocuses:
    bridge.disable()
    # on window destroy:
    bridge.destroy()

The *on_composition* callback has the signature::

    def on_composition(text: str, is_commit: bool) -> None: ...

*text* is the current composition string (empty string clears it).
*is_commit* is True when the composition is being committed (the final text
is delivered via SDL_EVENT_TEXT_INPUT / on_textinput as usual).
"""

from libc.stdint cimport uintptr_t

# ---------------------------------------------------------------------------
# C++ declarations
# ---------------------------------------------------------------------------

cdef extern from "win_tsf.h":
    ctypedef void (*KivyTSFTextCallback)(void *user_data,
                                         const wchar_t *text,
                                         bint is_commit)

    cdef cppclass KivyTSFManager:
        @staticmethod
        KivyTSFManager *Create(void *hwnd)
        void Destroy()
        void SetTextCallback(KivyTSFTextCallback cb, void *user_data)
        void SetContent(const wchar_t *text, long text_len,
                        long cursor_pos, long sel_start, long sel_end)
        void SetCursorRect(long x, long y, long w, long h)
        void Enable()
        void Disable()

# ---------------------------------------------------------------------------
# C-level callback – called from C++ on the Kivy main thread (with GIL)
# ---------------------------------------------------------------------------

cdef void _tsf_text_callback(void *user_data,
                              const wchar_t *text,
                              bint is_commit) noexcept with gil:
    cdef WinTSFBridge bridge = <WinTSFBridge>user_data
    if bridge._composition_callback is None:
        return
    # Convert wchar_t* to Python str.  An empty wchar_t* pointer is safe here
    # because we always pass at least L"" from C++.
    cdef str py_text = (<bytes>(<char *>text)).decode('utf-16-le') \
        if text != NULL else u''
    # The wchar_t conversion above works on little-endian systems (all modern
    # x86/x86-64 Windows).  We use the raw bytes approach to avoid needing
    # wcslen in Cython.  For correctness we rely on NULL-terminated wchar_t.
    try:
        bridge._composition_callback(py_text, bool(is_commit))
    except Exception:
        pass  # never let Python exceptions propagate into C++

# ---------------------------------------------------------------------------
# Helper: convert Python str to wchar_t bytes for SetContent
# ---------------------------------------------------------------------------

cdef inline bytes _to_wchar_bytes(str s):
    """Encode *s* as UTF-16-LE bytes (native wchar_t representation on Win)."""
    return s.encode('utf-16-le')

# ---------------------------------------------------------------------------
# Public Python class
# ---------------------------------------------------------------------------

cdef class WinTSFBridge:
    """Thin Cython wrapper around KivyTSFManager.

    All methods are safe to call from Python.  They silently no-op when the
    manager has not been initialised or has already been destroyed.
    """

    cdef KivyTSFManager *_manager
    cdef object _composition_callback  # callable(text: str, is_commit: bool)

    def __cinit__(self):
        self._manager = NULL
        self._composition_callback = None

    def __dealloc__(self):
        self.destroy()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def init_tsf(self, uintptr_t hwnd, object composition_callback):
        """Initialise TSF on *hwnd*.

        *composition_callback* is called with ``(text: str, is_commit: bool)``
        whenever a composition event occurs.
        """
        if self._manager != NULL:
            return  # already initialised

        self._composition_callback = composition_callback
        self._manager = KivyTSFManager.Create(<void *>hwnd)
        if self._manager == NULL:
            raise RuntimeError("KivyTSFManager.Create() failed – "
                               "TSF not available on this system")
        # Register the C-level callback.  We pass *self* as user_data; the GIL
        # callback wrapper above recovers it via a cast.
        self._manager.SetTextCallback(_tsf_text_callback, <void *>self)

    def destroy(self):
        """Release all TSF resources.  Safe to call multiple times."""
        if self._manager != NULL:
            self._manager.Destroy()
            self._manager = NULL
        self._composition_callback = None

    # ------------------------------------------------------------------
    # Focus management
    # ------------------------------------------------------------------

    def enable(self):
        """Focus this document in the TSF thread manager (TextInput got focus)."""
        if self._manager != NULL:
            self._manager.Enable()

    def disable(self):
        """Unfocus this document (TextInput lost focus)."""
        if self._manager != NULL:
            self._manager.Disable()

    # ------------------------------------------------------------------
    # Content / cursor updates
    # ------------------------------------------------------------------

    def update_content(self, str text, int cursor_index,
                       int sel_start, int sel_end):
        """Push the current TextInput content to the TSF document store.

        Must be called after every text or cursor change so that the IME has
        accurate surrounding-text context.
        """
        if self._manager == NULL:
            return
        cdef bytes encoded = _to_wchar_bytes(text)
        # Number of *wchar_t* characters (each UTF-16-LE unit = 2 bytes).
        cdef long text_len = <long>(len(encoded) // 2)
        self._manager.SetContent(<const wchar_t *>(<char *>encoded),
                                 text_len,
                                 cursor_index, sel_start, sel_end)

    def update_cursor_rect(self, int x, int y, int w, int h):
        """Provide the screen-space bounding rect of the cursor.

        The TSF framework uses this to position the IME candidate window so
        that it appears near the text insertion point.
        """
        if self._manager != NULL:
            self._manager.SetCursorRect(x, y, w, h)
