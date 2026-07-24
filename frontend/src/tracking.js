import { trackBeacon, trackEvent, trackPageview } from './api'

// --- Visitor / session identifiers ----------------------------------------
// Visitor id is long-lived (localStorage - survives tab close, matches the
// "first visit / total visits" semantics). Session id is per-tab and expires
// after SESSION_IDLE_MINUTES of inactivity, tracked via a timestamp also in
// localStorage (sessionStorage would reset on every new tab, which is wrong
// for "one session per ~30 idle minutes").
const VISITOR_KEY = 'fwc:visitorId'
const SESSION_KEY = 'fwc:sessionId'
const SESSION_TS_KEY = 'fwc:sessionLastSeen'
const SESSION_IDLE_MINUTES = 30

function randomId() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`
}

function getVisitorId() {
  let id = localStorage.getItem(VISITOR_KEY)
  if (!id) {
    id = randomId()
    localStorage.setItem(VISITOR_KEY, id)
  }
  return id
}

function getOrStartSession() {
  const now = Date.now()
  const lastSeen = Number(localStorage.getItem(SESSION_TS_KEY) || 0)
  let sessionId = localStorage.getItem(SESSION_KEY)
  let isNewSession = false

  if (!sessionId || now - lastSeen > SESSION_IDLE_MINUTES * 60 * 1000) {
    sessionId = randomId()
    localStorage.setItem(SESSION_KEY, sessionId)
    isNewSession = true
  }
  localStorage.setItem(SESSION_TS_KEY, String(now))
  return { sessionId, isNewSession }
}

// --- UTM / referrer capture (first touch of the session only) ------------
function captureUtmParams() {
  const params = new URLSearchParams(window.location.search)
  return {
    utm_source: params.get('utm_source') || undefined,
    utm_medium: params.get('utm_medium') || undefined,
    utm_campaign: params.get('utm_campaign') || undefined,
    utm_content: params.get('utm_content') || undefined,
  }
}

let pageEnteredAt = Date.now()
let currentPath = null
let maxScrollDepthPct = 0

function trackScrollDepth() {
  const doc = document.documentElement
  const scrollable = doc.scrollHeight - doc.clientHeight
  if (scrollable <= 0) return
  const pct = Math.min(100, Math.round((window.scrollY / scrollable) * 100))
  if (pct > maxScrollDepthPct) maxScrollDepthPct = pct
}

/** Call once on initial app load, and again on every client-side navigation. */
export function trackPageView(path, title) {
  // Send a beacon for the page we're leaving, if any, before switching.
  if (currentPath) sendExitBeacon()

  const { sessionId, isNewSession } = getOrStartSession()
  const visitorId = getVisitorId()
  currentPath = path
  pageEnteredAt = Date.now()
  maxScrollDepthPct = 0

  const payload = {
    visitor_id: visitorId,
    session_id: sessionId,
    is_new_session: isNewSession,
    path,
    title: title || document.title,
    screen_resolution: `${window.screen.width}x${window.screen.height}`,
    language: navigator.language,
  }
  if (isNewSession) {
    payload.referrer = document.referrer || undefined
    Object.assign(payload, captureUtmParams())
  }
  trackPageview(payload)
}

function sendExitBeacon() {
  const sessionId = localStorage.getItem(SESSION_KEY)
  if (!sessionId || !currentPath) return
  const seconds = Math.round((Date.now() - pageEnteredAt) / 1000)
  trackBeacon({
    session_id: sessionId, path: currentPath,
    time_on_page_seconds: seconds, scroll_depth_pct: maxScrollDepthPct,
  })
}

let listenersAttached = false

/** Call once at app startup to wire up scroll tracking + exit beacons. */
export function initTracking() {
  if (listenersAttached) return
  listenersAttached = true
  window.addEventListener('scroll', trackScrollDepth, { passive: true })
  window.addEventListener('pagehide', sendExitBeacon)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden') sendExitBeacon()
  })
}

/** Product-event tracking for the user-journey funnel (login, tool_opened, etc). */
export function trackActivity(eventType, eventData) {
  trackEvent(eventType, eventData, {
    visitor_id: localStorage.getItem(VISITOR_KEY) || undefined,
    session_id: localStorage.getItem(SESSION_KEY) || undefined,
  })
}
