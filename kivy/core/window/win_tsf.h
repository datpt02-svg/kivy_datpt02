#pragma once

#if defined(WIN32) || defined(_WIN32) || defined(__WIN32__) || defined(__NT__)

#include <windows.h>
#include <msctf.h>
#include <textstor.h>
#include <string>

// Callback invoked from C++ into Python (via Cython).
// text      - composition string (may be empty to clear composition)
// is_commit - true when text is being committed (composition ended)
typedef void (*KivyTSFTextCallback)(void *user_data, const wchar_t *text,
                                    int is_commit);

// KivyTSFManager: registers a TSF text-store document on a given HWND so that
// Windows IMEs (via TSF) can read surrounding text and correctly position the
// candidate window.  Composition events are forwarded to Python via a callback.
//
// Thread-safety: all public methods must be called from the same thread that
// called Create() (the main Kivy/SDL3 UI thread).
class KivyTSFManager : public ITextStoreACP2,
                       public ITfContextOwnerCompositionSink {
public:
    // --- Lifecycle -----------------------------------------------------------

    // Create and fully initialise a TSF store bound to |hwnd|.
    // Returns NULL on failure.
    static KivyTSFManager *Create(void *hwnd);

    // Release all TSF resources. After Destroy() the object must not be used.
    void Destroy();

    // Set the Python callback invoked on composition / commit events.
    void SetTextCallback(KivyTSFTextCallback cb, void *user_data);

    // --- State update (called from Python whenever Kivy state changes) -------

    // Update the cached document content and cursor / selection positions.
    // |text| must remain valid for the duration of the call.
    void SetContent(const wchar_t *text, LONG text_len,
                    LONG cursor_pos, LONG sel_start, LONG sel_end);

    // Update the screen rectangle of the cursor (used to position the IME
    // candidate window via GetTextExt).
    void SetCursorRect(LONG x, LONG y, LONG w, LONG h);

    // Focus / unfocus this document in the TSF thread manager.
    void Enable();
    void Disable();

    // --- IUnknown ------------------------------------------------------------
    STDMETHODIMP QueryInterface(REFIID riid, void **ppvObj) override;
    STDMETHODIMP_(ULONG) AddRef() override;
    STDMETHODIMP_(ULONG) Release() override;

    // --- ITfTextStoreACP2 ----------------------------------------------------
    // (methods that need a real implementation)
    STDMETHODIMP AdviseSink(REFIID riid, IUnknown *punk,
                            DWORD dwMask) override;
    STDMETHODIMP UnadviseSink(IUnknown *punk) override;
    STDMETHODIMP RequestLock(DWORD dwLockFlags,
                             HRESULT *phrSession) override;
    STDMETHODIMP GetStatus(TS_STATUS *pdcs) override;
    STDMETHODIMP QueryInsert(LONG acpTestStart, LONG acpTestEnd,
                             ULONG cch, LONG *pacpResultStart,
                             LONG *pacpResultEnd) override;
    STDMETHODIMP GetSelection(ULONG ulIndex, ULONG ulCount,
                              TS_SELECTION_ACP *pSelection,
                              ULONG *pcFetched) override;
    STDMETHODIMP SetSelection(ULONG ulCount,
                              const TS_SELECTION_ACP *pSelection) override;
    STDMETHODIMP GetText(LONG acpStart, LONG acpEnd, WCHAR *pchPlain,
                         ULONG cchPlainReq, ULONG *pcchPlainRet,
                         TS_RUNINFO *prgRunInfo, ULONG cRunInfoReq,
                         ULONG *pcRunInfoRet, LONG *pacpNext) override;
    STDMETHODIMP SetText(DWORD dwFlags, LONG acpStart, LONG acpEnd,
                         const WCHAR *pchText, ULONG cch,
                         TS_TEXTCHANGE *pChange) override;
    STDMETHODIMP InsertTextAtSelection(DWORD dwFlags, const WCHAR *pchText,
                                       ULONG cch, LONG *pacpStart,
                                       LONG *pacpEnd,
                                       TS_TEXTCHANGE *pChange) override;
    STDMETHODIMP GetFormattedText(LONG acpStart, LONG acpEnd,
                                  IDataObject **ppDataObject) override;
    STDMETHODIMP GetEmbedded(LONG acpPos, REFGUID rguidService, REFIID riid,
                              IUnknown **ppunk) override;
    STDMETHODIMP QueryInsertEmbedded(const GUID *pguidService,
                                     const FORMATETC *pFormatEtc,
                                     BOOL *pfInsertable) override;
    STDMETHODIMP InsertEmbedded(DWORD dwFlags, LONG acpStart, LONG acpEnd,
                                IDataObject *pDataObject,
                                TS_TEXTCHANGE *pChange) override;
    STDMETHODIMP InsertEmbeddedAtSelection(DWORD dwFlags,
                                           IDataObject *pDataObject,
                                           LONG *pacpStart, LONG *pacpEnd,
                                           TS_TEXTCHANGE *pChange) override;
    STDMETHODIMP RequestSupportedAttrs(DWORD dwFlags, ULONG cFilterAttrs,
                                       const TS_ATTRID *paFilterAttrs) override;
    STDMETHODIMP RequestAttrsAtPosition(LONG acpPos, ULONG cFilterAttrs,
                                        const TS_ATTRID *paFilterAttrs,
                                        DWORD dwFlags) override;
    STDMETHODIMP RequestAttrsTransitioningAtPosition(
        LONG acpPos, ULONG cFilterAttrs, const TS_ATTRID *paFilterAttrs,
        DWORD dwFlags) override;
    STDMETHODIMP FindNextAttrTransition(LONG acpStart, LONG acpHalt,
                                        ULONG cFilterAttrs,
                                        const TS_ATTRID *paFilterAttrs,
                                        DWORD dwFlags, LONG *pacpNext,
                                        BOOL *pfFound,
                                        LONG *pdwFoundOffset) override;
    STDMETHODIMP RetrieveRequestedAttrs(ULONG ulCount, TS_ATTRVAL *paAttrVals,
                                        ULONG *pcFetched) override;
    STDMETHODIMP GetEndACP(LONG *pacp) override;
    STDMETHODIMP GetActiveView(TsViewCookie *pvcView) override;
    STDMETHODIMP GetACPFromPoint(TsViewCookie vcView, const POINT *ptScreen,
                                  DWORD dwFlags, LONG *pacp) override;
    STDMETHODIMP GetTextExt(TsViewCookie vcView, LONG acpStart, LONG acpEnd,
                             RECT *prc, BOOL *pfClipped) override;
    STDMETHODIMP GetScreenExt(TsViewCookie vcView, RECT *prc) override;
    // GetWnd: present in some SDK versions of ITextStoreACP2; declared without
    // override to avoid C3668 on SDKs that don't include it as a pure virtual.
    STDMETHODIMP GetWnd(TsViewCookie vcView, HWND *phwnd);

    // --- ITfContextOwnerCompositionSink --------------------------------------
    STDMETHODIMP OnStartComposition(ITfCompositionView *pComposition,
                                    BOOL *pfOk) override;
    STDMETHODIMP OnUpdateComposition(ITfCompositionView *pComposition,
                                     ITfRange *pRangeNew) override;
    STDMETHODIMP OnEndComposition(ITfCompositionView *pComposition) override;

private:
    KivyTSFManager();
    ~KivyTSFManager();

    // Helpers
    HRESULT _GrantLockIfPending();

    ULONG m_cRef;

    HWND m_hwnd;
    ITfThreadMgr *m_pThreadMgr;
    TfClientId m_clientId;
    ITfDocumentMgr *m_pDocMgr;
    ITfDocumentMgr *m_pPrevDocMgr; // restored on Disable()
    ITfContext *m_pContext;
    TfEditCookie m_editCookie;

    ITextStoreACPSink *m_pSink;
    DWORD m_dwSinkMask;

    // Document state (mirroring Kivy TextInput)
    std::wstring m_text;
    LONG m_cursorPos;
    LONG m_selStart;
    LONG m_selEnd;
    RECT m_cursorRect; // screen coords of cursor, for GetTextExt

    // Lock state
    DWORD m_dwLockType; // 0 = unlocked
    bool m_fPendingLockUpgrade;

    // Composition callback to Python
    KivyTSFTextCallback m_pfnCallback;
    void *m_pCallbackData;

    bool m_fEnabled;
};

#endif // WIN32
