#if defined(WIN32) || defined(_WIN32) || defined(__WIN32__) || defined(__NT__)

#include "win_tsf.h"
#include <algorithm>
#include <cstring>
#include <olectl.h>   // CONNECT_E_NOCONNECTION

// The single fixed view cookie used throughout this implementation.
static const TsViewCookie VIEW_COOKIE = 1;

// ---------------------------------------------------------------------------
// Construction / Destruction
// ---------------------------------------------------------------------------

KivyTSFManager::KivyTSFManager()
    : m_cRef(1), m_hwnd(NULL), m_pThreadMgr(NULL), m_clientId(TF_CLIENTID_NULL),
      m_pDocMgr(NULL), m_pPrevDocMgr(NULL), m_pContext(NULL),
      m_editCookie(0), m_pSink(NULL), m_dwSinkMask(0),
      m_cursorPos(0), m_selStart(0), m_selEnd(0),
      m_dwLockType(0), m_fPendingLockUpgrade(false),
      m_pfnCallback(NULL), m_pCallbackData(NULL), m_fEnabled(false) {
    SetRectEmpty(&m_cursorRect);
}

KivyTSFManager::~KivyTSFManager() {
    // Destroy() should have been called before the destructor.
}

// ---------------------------------------------------------------------------
// KivyTSFManager::Create
// ---------------------------------------------------------------------------

/* static */
KivyTSFManager *KivyTSFManager::Create(void *hwnd_ptr) {
    HWND hwnd = reinterpret_cast<HWND>(hwnd_ptr);
    // COM must already be initialised on this thread (SDL3 does this).
    ITfThreadMgr *pThreadMgr = NULL;
    HRESULT hr = TF_CreateThreadMgr(&pThreadMgr);
    if (FAILED(hr) || !pThreadMgr)
        return NULL;

    TfClientId clientId = TF_CLIENTID_NULL;
    hr = pThreadMgr->Activate(&clientId);
    if (FAILED(hr)) {
        pThreadMgr->Release();
        return NULL;
    }

    ITfDocumentMgr *pDocMgr = NULL;
    hr = pThreadMgr->CreateDocumentMgr(&pDocMgr);
    if (FAILED(hr)) {
        pThreadMgr->Deactivate();
        pThreadMgr->Release();
        return NULL;
    }

    KivyTSFManager *pMgr = new (std::nothrow) KivyTSFManager();
    if (!pMgr) {
        pDocMgr->Release();
        pThreadMgr->Deactivate();
        pThreadMgr->Release();
        return NULL;
    }

    pMgr->m_hwnd = hwnd;
    pMgr->m_pThreadMgr = pThreadMgr;
    pMgr->m_clientId = clientId;
    pMgr->m_pDocMgr = pDocMgr;

    // Create a context and push it onto the document manager.
    ITfContext *pContext = NULL;
    TfEditCookie editCookie = 0;
    hr = pDocMgr->CreateContext(clientId, 0,
                                static_cast<ITextStoreACP2 *>(pMgr),
                                &pContext, &editCookie);
    if (FAILED(hr)) {
        pMgr->Release();
        return NULL;
    }

    hr = pDocMgr->Push(pContext);
    pContext->Release(); // pDocMgr holds a ref
    if (FAILED(hr)) {
        pMgr->Release();
        return NULL;
    }

    // Re-query to get a stable pointer (Push may adjust refcounts).
    hr = pDocMgr->GetTop(&pMgr->m_pContext);
    if (FAILED(hr) || !pMgr->m_pContext) {
        pMgr->Release();
        return NULL;
    }
    pMgr->m_editCookie = editCookie;

    return pMgr;
}

// ---------------------------------------------------------------------------
// KivyTSFManager::Destroy
// ---------------------------------------------------------------------------

void KivyTSFManager::Destroy() {
    Disable();

    if (m_pSink) {
        m_pSink->Release();
        m_pSink = NULL;
    }

    if (m_pContext) {
        m_pContext->Release();
        m_pContext = NULL;
    }

    if (m_pDocMgr) {
        m_pDocMgr->Pop(TF_POPF_ALL);
        m_pDocMgr->Release();
        m_pDocMgr = NULL;
    }

    if (m_pPrevDocMgr) {
        m_pPrevDocMgr->Release();
        m_pPrevDocMgr = NULL;
    }

    if (m_pThreadMgr) {
        m_pThreadMgr->Deactivate();
        m_pThreadMgr->Release();
        m_pThreadMgr = NULL;
    }

    m_clientId = TF_CLIENTID_NULL;
    Release(); // balance the ref held by the owner
}

// ---------------------------------------------------------------------------
// Public state-update methods
// ---------------------------------------------------------------------------

void KivyTSFManager::SetTextCallback(KivyTSFTextCallback cb, void *user_data) {
    m_pfnCallback = cb;
    m_pCallbackData = user_data;
}

void KivyTSFManager::SetContent(const wchar_t *text, LONG text_len,
                                 LONG cursor_pos, LONG sel_start,
                                 LONG sel_end) {
    m_text.assign(text, static_cast<size_t>(text_len));
    m_cursorPos = cursor_pos;
    m_selStart = sel_start;
    m_selEnd = sel_end;

    // Notify the TSF sink that content changed (if we have one).
    if (m_pSink && (m_dwSinkMask & TS_AS_TEXT_CHANGE)) {
        TS_TEXTCHANGE tc;
        tc.acpStart = 0;
        tc.acpOldEnd = static_cast<LONG>(m_text.size()); // approximate
        tc.acpNewEnd = text_len;
        m_pSink->OnTextChange(0, &tc);
    }
    if (m_pSink && (m_dwSinkMask & TS_AS_SEL_CHANGE)) {
        m_pSink->OnSelectionChange();
    }
}

void KivyTSFManager::SetCursorRect(LONG x, LONG y, LONG w, LONG h) {
    m_cursorRect.left = x;
    m_cursorRect.top = y;
    m_cursorRect.right = x + w;
    m_cursorRect.bottom = y + h;

    if (m_pSink && (m_dwSinkMask & TS_AS_LAYOUT_CHANGE)) {
        m_pSink->OnLayoutChange(TS_LC_CHANGE, VIEW_COOKIE);
    }
}

void KivyTSFManager::Enable() {
    if (!m_pThreadMgr || !m_pDocMgr || m_fEnabled)
        return;
    m_pThreadMgr->GetFocus(&m_pPrevDocMgr);
    m_pThreadMgr->SetFocus(m_pDocMgr);
    m_fEnabled = true;
}

void KivyTSFManager::Disable() {
    if (!m_fEnabled)
        return;
    if (m_pThreadMgr) {
        if (m_pPrevDocMgr) {
            m_pThreadMgr->SetFocus(m_pPrevDocMgr);
            m_pPrevDocMgr->Release();
            m_pPrevDocMgr = NULL;
        } else {
            m_pThreadMgr->SetFocus(NULL);
        }
    }
    m_fEnabled = false;
}

// ---------------------------------------------------------------------------
// IUnknown
// ---------------------------------------------------------------------------

STDMETHODIMP KivyTSFManager::QueryInterface(REFIID riid, void **ppvObj) {
    if (!ppvObj) return E_INVALIDARG;
    *ppvObj = NULL;
    if (IsEqualIID(riid, IID_IUnknown) ||
        IsEqualIID(riid, IID_ITextStoreACP) ||
        IsEqualIID(riid, IID_ITextStoreACP2)) {
        *ppvObj = static_cast<ITextStoreACP2 *>(this);
    } else if (IsEqualIID(riid, IID_ITfContextOwnerCompositionSink)) {
        *ppvObj = static_cast<ITfContextOwnerCompositionSink *>(this);
    } else {
        return E_NOINTERFACE;
    }
    AddRef();
    return S_OK;
}

STDMETHODIMP_(ULONG) KivyTSFManager::AddRef() {
    return InterlockedIncrement(reinterpret_cast<LONG *>(&m_cRef));
}

STDMETHODIMP_(ULONG) KivyTSFManager::Release() {
    ULONG ref = InterlockedDecrement(reinterpret_cast<LONG *>(&m_cRef));
    if (ref == 0)
        delete this;
    return ref;
}

// ---------------------------------------------------------------------------
// ITfTextStoreACP2 – sink management
// ---------------------------------------------------------------------------

STDMETHODIMP KivyTSFManager::AdviseSink(REFIID riid, IUnknown *punk,
                                         DWORD dwMask) {
    if (!IsEqualIID(riid, IID_ITextStoreACPSink))
        return E_INVALIDARG;

    ITextStoreACPSink *pNewSink = NULL;
    HRESULT hr = punk->QueryInterface(IID_ITextStoreACPSink,
                                      reinterpret_cast<void **>(&pNewSink));
    if (FAILED(hr))
        return hr;

    if (m_pSink) {
        if (m_pSink == pNewSink) {
            m_dwSinkMask = dwMask;
            pNewSink->Release();
            return S_OK;
        }
        m_pSink->Release();
    }

    m_pSink = pNewSink;
    m_dwSinkMask = dwMask;
    return S_OK;
}

STDMETHODIMP KivyTSFManager::UnadviseSink(IUnknown *punk) {
    if (!m_pSink)
        return CONNECT_E_NOCONNECTION;
    ITextStoreACPSink *pSink = NULL;
    HRESULT hr = punk->QueryInterface(IID_ITextStoreACPSink,
                                      reinterpret_cast<void **>(&pSink));
    if (FAILED(hr))
        return hr;
    bool match = (pSink == m_pSink);
    pSink->Release();
    if (!match)
        return CONNECT_E_NOCONNECTION;
    m_pSink->Release();
    m_pSink = NULL;
    m_dwSinkMask = 0;
    return S_OK;
}

// ---------------------------------------------------------------------------
// ITfTextStoreACP2 – lock
// ---------------------------------------------------------------------------

STDMETHODIMP KivyTSFManager::RequestLock(DWORD dwLockFlags,
                                          HRESULT *phrSession) {
    if (!phrSession)
        return E_INVALIDARG;

    if (m_dwLockType != 0) {
        // Already locked – handle upgrade or pending
        if ((dwLockFlags & TS_LF_READWRITE) == TS_LF_READWRITE &&
            (m_dwLockType & TS_LF_READWRITE) != TS_LF_READWRITE) {
            // Upgrade request
            m_fPendingLockUpgrade = true;
            *phrSession = TS_S_ASYNC;
            return S_OK;
        }
        *phrSession = TS_E_SYNCHRONOUS;
        return E_FAIL;
    }

    m_dwLockType = dwLockFlags & TS_LF_READWRITE;
    *phrSession = m_pSink->OnLockGranted(m_dwLockType);
    m_dwLockType = 0;

    if (m_fPendingLockUpgrade) {
        m_fPendingLockUpgrade = false;
        m_dwLockType = TS_LF_READWRITE;
        m_pSink->OnLockGranted(m_dwLockType);
        m_dwLockType = 0;
    }

    return S_OK;
}

// ---------------------------------------------------------------------------
// ITfTextStoreACP2 – document queries
// ---------------------------------------------------------------------------

STDMETHODIMP KivyTSFManager::GetStatus(TS_STATUS *pdcs) {
    if (!pdcs) return E_INVALIDARG;
    pdcs->dwDynamicFlags = 0;
    pdcs->dwStaticFlags = TS_SS_NOHIDDENTEXT;
    return S_OK;
}

STDMETHODIMP KivyTSFManager::QueryInsert(LONG acpTestStart, LONG acpTestEnd,
                                          ULONG /*cch*/,
                                          LONG *pacpResultStart,
                                          LONG *pacpResultEnd) {
    if (!pacpResultStart || !pacpResultEnd) return E_INVALIDARG;
    LONG docLen = static_cast<LONG>(m_text.size());
    *pacpResultStart = max(0L, min(acpTestStart, docLen));
    *pacpResultEnd = max(0L, min(acpTestEnd, docLen));
    return S_OK;
}

STDMETHODIMP KivyTSFManager::GetSelection(ULONG ulIndex, ULONG ulCount,
                                           TS_SELECTION_ACP *pSelection,
                                           ULONG *pcFetched) {
    if (!pSelection || !pcFetched) return E_INVALIDARG;
    *pcFetched = 0;
    if (m_dwLockType == 0) return TS_E_NOLOCK;
    if (ulCount == 0) return S_OK;
    if (ulIndex != TF_DEFAULT_SELECTION && ulIndex != 0)
        return E_INVALIDARG;

    pSelection[0].acpStart = m_selStart;
    pSelection[0].acpEnd = m_selEnd;
    pSelection[0].style.fInterimChar = FALSE;
    pSelection[0].style.ase = (m_selStart == m_selEnd) ? TS_AE_END
                                                        : TS_AE_END;
    *pcFetched = 1;
    return S_OK;
}

STDMETHODIMP KivyTSFManager::SetSelection(ULONG ulCount,
                                           const TS_SELECTION_ACP *pSelection) {
    if (!pSelection) return E_INVALIDARG;
    if (m_dwLockType == 0) return TS_E_NOLOCK;
    if (ulCount > 0) {
        m_selStart = pSelection[0].acpStart;
        m_selEnd = pSelection[0].acpEnd;
        m_cursorPos = m_selEnd;
    }
    return S_OK;
}

STDMETHODIMP KivyTSFManager::GetText(LONG acpStart, LONG acpEnd,
                                      WCHAR *pchPlain, ULONG cchPlainReq,
                                      ULONG *pcchPlainRet,
                                      TS_RUNINFO *prgRunInfo,
                                      ULONG cRunInfoReq, ULONG *pcRunInfoRet,
                                      LONG *pacpNext) {
    if (!pcchPlainRet || !pcRunInfoRet || !pacpNext)
        return E_INVALIDARG;
    if (m_dwLockType == 0) return TS_E_NOLOCK;

    LONG docLen = static_cast<LONG>(m_text.size());
    if (acpEnd == -1) acpEnd = docLen;
    acpStart = max(0L, min(acpStart, docLen));
    acpEnd = max(acpStart, min(acpEnd, docLen));

    ULONG cchAvail = static_cast<ULONG>(acpEnd - acpStart);
    ULONG cchCopy = min(cchAvail, cchPlainReq);

    if (pchPlain && cchPlainReq > 0)
        wcsncpy_s(pchPlain, cchPlainReq, m_text.c_str() + acpStart, cchCopy);

    *pcchPlainRet = cchCopy;

    if (prgRunInfo && cRunInfoReq > 0) {
        prgRunInfo[0].uCount = cchCopy;
        prgRunInfo[0].type = TS_RT_PLAIN;
        *pcRunInfoRet = 1;
    } else {
        *pcRunInfoRet = 0;
    }

    *pacpNext = acpStart + static_cast<LONG>(cchCopy);
    return S_OK;
}

STDMETHODIMP KivyTSFManager::SetText(DWORD /*dwFlags*/, LONG acpStart,
                                      LONG acpEnd, const WCHAR *pchText,
                                      ULONG cch, TS_TEXTCHANGE *pChange) {
    if (!pchText && cch > 0) return E_INVALIDARG;
    if (m_dwLockType == 0) return TS_E_NOLOCK;

    LONG docLen = static_cast<LONG>(m_text.size());
    acpStart = max(0L, min(acpStart, docLen));
    acpEnd = max(acpStart, min(acpEnd, docLen));

    std::wstring newText(pchText, cch);
    m_text.replace(static_cast<size_t>(acpStart),
                   static_cast<size_t>(acpEnd - acpStart), newText);

    if (pChange) {
        pChange->acpStart = acpStart;
        pChange->acpOldEnd = acpEnd;
        pChange->acpNewEnd = acpStart + static_cast<LONG>(cch);
    }

    m_selStart = m_selEnd = m_cursorPos =
        acpStart + static_cast<LONG>(cch);

    // Notify Python of the change (not a commit).
    if (m_pfnCallback)
        m_pfnCallback(m_pCallbackData, newText.c_str(), false);

    return S_OK;
}

STDMETHODIMP KivyTSFManager::InsertTextAtSelection(DWORD dwFlags,
                                                    const WCHAR *pchText,
                                                    ULONG cch,
                                                    LONG *pacpStart,
                                                    LONG *pacpEnd,
                                                    TS_TEXTCHANGE *pChange) {
    if (m_dwLockType == 0 && !(dwFlags & TF_IAS_QUERYONLY))
        return TS_E_NOLOCK;

    LONG insStart = m_selStart;
    LONG insEnd = m_selEnd;

    if (dwFlags & TF_IAS_QUERYONLY) {
        if (pacpStart) *pacpStart = insStart;
        if (pacpEnd) *pacpEnd = insEnd;
        return S_OK;
    }

    LONG docLen = static_cast<LONG>(m_text.size());
    insStart = max(0L, min(insStart, docLen));
    insEnd = max(insStart, min(insEnd, docLen));

    std::wstring newText(pchText, cch);
    m_text.replace(static_cast<size_t>(insStart),
                   static_cast<size_t>(insEnd - insStart), newText);

    LONG newEnd = insStart + static_cast<LONG>(cch);
    m_selStart = m_selEnd = m_cursorPos = newEnd;

    if (pacpStart) *pacpStart = insStart;
    if (pacpEnd) *pacpEnd = newEnd;
    if (pChange) {
        pChange->acpStart = insStart;
        pChange->acpOldEnd = insEnd;
        pChange->acpNewEnd = newEnd;
    }

    // Notify Python (composition update).
    if (m_pfnCallback && cch > 0)
        m_pfnCallback(m_pCallbackData, newText.c_str(), false);

    return S_OK;
}

// ---------------------------------------------------------------------------
// ITfTextStoreACP2 – geometry / view
// ---------------------------------------------------------------------------

STDMETHODIMP KivyTSFManager::GetEndACP(LONG *pacp) {
    if (!pacp) return E_INVALIDARG;
    *pacp = static_cast<LONG>(m_text.size());
    return S_OK;
}

STDMETHODIMP KivyTSFManager::GetActiveView(TsViewCookie *pvcView) {
    if (!pvcView) return E_INVALIDARG;
    *pvcView = VIEW_COOKIE;
    return S_OK;
}

STDMETHODIMP KivyTSFManager::GetACPFromPoint(TsViewCookie /*vcView*/,
                                              const POINT * /*ptScreen*/,
                                              DWORD /*dwFlags*/,
                                              LONG *pacp) {
    // Simple stub: always return cursor position.
    if (!pacp) return E_INVALIDARG;
    *pacp = m_cursorPos;
    return S_OK;
}

STDMETHODIMP KivyTSFManager::GetTextExt(TsViewCookie vcView, LONG /*acpStart*/,
                                         LONG /*acpEnd*/, RECT *prc,
                                         BOOL *pfClipped) {
    if (!prc || !pfClipped) return E_INVALIDARG;
    if (vcView != VIEW_COOKIE) return E_INVALIDARG;
    if (m_dwLockType == 0) return TS_E_NOLOCK;

    // Return the screen rect of the cursor so the IME candidate window
    // appears near the insertion point.
    *prc = m_cursorRect;
    *pfClipped = FALSE;
    return S_OK;
}

STDMETHODIMP KivyTSFManager::GetScreenExt(TsViewCookie vcView, RECT *prc) {
    if (!prc) return E_INVALIDARG;
    if (vcView != VIEW_COOKIE) return E_INVALIDARG;
    RECT rc = {};
    if (m_hwnd && IsWindow(m_hwnd))
        GetClientRect(m_hwnd, &rc);
    *prc = rc;
    return S_OK;
}

STDMETHODIMP KivyTSFManager::GetWnd(TsViewCookie vcView, HWND *phwnd) {
    if (!phwnd) return E_INVALIDARG;
    if (vcView != VIEW_COOKIE) return E_INVALIDARG;
    *phwnd = m_hwnd;
    return S_OK;
}

// ---------------------------------------------------------------------------
// ITfTextStoreACP2 – attributes (all stubbed)
// ---------------------------------------------------------------------------

STDMETHODIMP KivyTSFManager::GetFormattedText(LONG, LONG, IDataObject **) {
    return E_NOTIMPL;
}
STDMETHODIMP KivyTSFManager::GetEmbedded(LONG, REFGUID, REFIID, IUnknown **) {
    return E_NOTIMPL;
}
STDMETHODIMP KivyTSFManager::QueryInsertEmbedded(const GUID *, const FORMATETC *,
                                                  BOOL *pfInsertable) {
    if (pfInsertable) *pfInsertable = FALSE;
    return S_OK;
}
STDMETHODIMP KivyTSFManager::InsertEmbedded(DWORD, LONG, LONG, IDataObject *,
                                             TS_TEXTCHANGE *) {
    return E_NOTIMPL;
}
STDMETHODIMP KivyTSFManager::InsertEmbeddedAtSelection(DWORD, IDataObject *,
                                                        LONG *, LONG *,
                                                        TS_TEXTCHANGE *) {
    return E_NOTIMPL;
}
STDMETHODIMP KivyTSFManager::RequestSupportedAttrs(DWORD, ULONG,
                                                    const TS_ATTRID *) {
    return S_OK;
}
STDMETHODIMP KivyTSFManager::RequestAttrsAtPosition(LONG, ULONG,
                                                     const TS_ATTRID *,
                                                     DWORD) {
    return S_OK;
}
STDMETHODIMP KivyTSFManager::RequestAttrsTransitioningAtPosition(
    LONG, ULONG, const TS_ATTRID *, DWORD) {
    return S_OK;
}
STDMETHODIMP KivyTSFManager::FindNextAttrTransition(LONG, LONG, ULONG,
                                                     const TS_ATTRID *, DWORD,
                                                     LONG *pacpNext,
                                                     BOOL *pfFound,
                                                     LONG *pdwFoundOffset) {
    if (pacpNext) *pacpNext = 0;
    if (pfFound) *pfFound = FALSE;
    if (pdwFoundOffset) *pdwFoundOffset = 0;
    return S_OK;
}
STDMETHODIMP KivyTSFManager::RetrieveRequestedAttrs(ULONG, TS_ATTRVAL *,
                                                     ULONG *pcFetched) {
    if (pcFetched) *pcFetched = 0;
    return S_OK;
}

// ---------------------------------------------------------------------------
// ITfContextOwnerCompositionSink
// ---------------------------------------------------------------------------

STDMETHODIMP KivyTSFManager::OnStartComposition(
    ITfCompositionView * /*pComposition*/, BOOL *pfOk) {
    if (pfOk) *pfOk = TRUE;
    return S_OK;
}

STDMETHODIMP KivyTSFManager::OnUpdateComposition(
    ITfCompositionView *pComposition, ITfRange * /*pRangeNew*/) {
    if (!pComposition || !m_pfnCallback)
        return S_OK;

    // Extract the current composition text.
    ITfRange *pRange = NULL;
    if (FAILED(pComposition->GetRange(&pRange)) || !pRange)
        return S_OK;

    // Convert ITfRange to ACP positions via ITfRangeACP.
    ITfRangeACP *pRangeACP = NULL;
    if (SUCCEEDED(pRange->QueryInterface(IID_ITfRangeACP,
                                         reinterpret_cast<void **>(&pRangeACP)))) {
        LONG acpStart = 0, cch = 0;
        if (SUCCEEDED(pRangeACP->GetExtent(&acpStart, &cch)) && cch > 0) {
            LONG acpEnd = acpStart + cch;
            LONG docLen = static_cast<LONG>(m_text.size());
            acpStart = max(0L, min(acpStart, docLen));
            acpEnd = max(acpStart, min(acpEnd, docLen));
            std::wstring compText = m_text.substr(
                static_cast<size_t>(acpStart),
                static_cast<size_t>(acpEnd - acpStart));
            m_pfnCallback(m_pCallbackData, compText.c_str(), false);
        }
        pRangeACP->Release();
    }
    pRange->Release();
    return S_OK;
}

STDMETHODIMP KivyTSFManager::OnEndComposition(
    ITfCompositionView * /*pComposition*/) {
    // Signal Python that composition ended (empty string = clear composition
    // preview; the committed text arrives via SDL_EVENT_TEXT_INPUT from SDL3).
    if (m_pfnCallback)
        m_pfnCallback(m_pCallbackData, L"", true);
    return S_OK;
}

#endif // WIN32
