const API_BASE = import.meta.env.VITE_API_BASE || '/api'

// --- Session handling ------------------------------------------------------
// The session itself now lives in an HttpOnly cookie set by the backend
// (see auth/core.py::set_session_cookies) - JS never touches the actual
// token, which is what makes it immune to theft via any XSS bug. The one
// thing the frontend still needs to do is echo back the CSRF cookie's
// value as a header on every mutating request (see authFetch below) -
// that's the non-HttpOnly `fwc_csrf` cookie, readable via document.cookie.
function readCookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : null
}

let unauthorizedHandler = () => {}
// App.jsx registers this once at startup so any 401 (expired/invalid
// session) anywhere in the app bounces the user back to the login screen.
export function setUnauthorizedHandler(fn) {
  unauthorizedHandler = fn
}

const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

async function authFetch(path, options = {}) {
  const method = (options.method || 'GET').toUpperCase()
  const headers = { ...(options.headers || {}) }
  if (MUTATING_METHODS.has(method)) {
    const csrfToken = readCookie('fwc_csrf')
    if (csrfToken) headers['X-CSRF-Token'] = csrfToken
  }
  // credentials: 'include' is required for the session cookie to be sent
  // (and Set-Cookie to be honored) across subdomains (login./signup./
  // dash.pan-tool.com all hitting the same API) - without it, the browser
  // treats these as separate, cookie-less requests.
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers, credentials: 'include' })
  if (res.status === 401) {
    unauthorizedHandler()
  }
  return res
}

async function authFetchJson(path, options = {}) {
  const res = await authFetch(path, options)
  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (body?.detail) message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch {
      const text = await res.text().catch(() => '')
      if (text) message = text
    }
    throw new Error(message)
  }
  return res.json()
}

// Every downloadable artifact requires an authenticated session, which a
// plain <a href> can't carry across subdomains - so downloads go through
// fetch (with credentials) + a blob URL instead of a real navigation.
export async function triggerDownload(path, filename) {
  const res = await authFetch(path)
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `Download failed (${res.status})`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}

// --- Auth ----------------------------------------------------------------
export async function signup(data) {
  return authFetchJson('/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function verifyEmail(email, otp) {
  return authFetchJson('/auth/verify-email', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, otp }),
  })
}

export async function resendVerification(email) {
  return authFetchJson('/auth/resend-verification', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
}

export async function login(email, password) {
  return authFetchJson('/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  })
}

export async function logout() {
  return authFetchJson('/auth/logout', { method: 'POST' })
}

export async function fetchMe() {
  return authFetchJson('/auth/me')
}

export async function updateProfile(data) {
  return authFetchJson('/auth/me', {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function changePassword(currentPassword, newPassword) {
  return authFetchJson('/auth/change-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  })
}

export async function forgotPassword(email) {
  return authFetchJson('/auth/forgot-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
}

export async function resendPasswordOtp(email) {
  return authFetchJson('/auth/resend-password-otp', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  })
}

export async function resetPassword(email, otp, newPassword) {
  return authFetchJson('/auth/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, otp, new_password: newPassword }),
  })
}

// --- Vendors / jobs --------------------------------------------------------
export async function fetchVendors() {
  return authFetchJson('/vendors')
}

export async function convertConfig(vendor, file) {
  const form = new FormData()
  form.append('vendor', vendor)
  form.append('file', file)
  return authFetchJson('/convert', { method: 'POST', body: form })
}

export async function parseConfig(vendor, file, jobName) {
  const form = new FormData()
  form.append('vendor', vendor)
  form.append('file', file)
  if (jobName) form.append('job_name', jobName)
  return authFetchJson('/parse', { method: 'POST', body: form })
}

export async function listJobs() {
  return authFetchJson('/jobs')
}

export async function fetchJob(jobId) {
  return authFetchJson(`/jobs/${jobId}`)
}

export async function deleteJob(jobId) {
  const res = await authFetch(`/jobs/${jobId}`, { method: 'DELETE' })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(text || `Delete failed (${res.status})`)
  }
}

export async function fetchInterfaces(jobId) {
  return authFetchJson(`/jobs/${jobId}/interfaces`)
}

export async function getObjects(jobId, category) {
  return authFetchJson(`/jobs/${jobId}/objects/${category}`)
}

export async function saveObjects(jobId, category, rows) {
  return authFetchJson(`/jobs/${jobId}/objects/${category}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ rows }),
  })
}

export async function getValidation(jobId) {
  return authFetchJson(`/jobs/${jobId}/validation`)
}

export async function exportPreview(jobId, sections) {
  return authFetchJson(`/jobs/${jobId}/export/preview`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sections }),
  })
}

export function exportDownloadPath(jobId, sections) {
  const q = !sections || sections.length === 0 ? 'all' : sections.join(',')
  return `/jobs/${jobId}/export/download?sections=${encodeURIComponent(q)}`
}

export async function submitMapping(jobId, mappings, validateOnly = false) {
  return authFetchJson(`/jobs/${jobId}/mapping`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mappings, validate_only: validateOnly }),
  })
}

export async function generateConfig(jobId) {
  return authFetchJson(`/jobs/${jobId}/generate`, { method: 'POST' })
}

export async function getProfiles(jobId) {
  return authFetchJson(`/jobs/${jobId}/profiles`)
}

export async function saveProfiles(jobId, profiles) {
  return authFetchJson(`/jobs/${jobId}/profiles`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profiles),
  })
}

export async function getCleanup(jobId) {
  return authFetchJson(`/jobs/${jobId}/cleanup`)
}

export async function deleteCleanupObjects(jobId, objectType, names) {
  return authFetchJson(`/jobs/${jobId}/cleanup/delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ object_type: objectType, names }),
  })
}

export function cleanupReportPath(jobId) {
  return `/jobs/${jobId}/cleanup/report`
}

export async function fetchSummary(jobId) {
  return authFetchJson(`/jobs/${jobId}/summary`)
}

export function excelExportPath(jobId) {
  return `/jobs/${jobId}/export/excel`
}

export function downloadPath(jobId, artifact) {
  return `/jobs/${jobId}/download/${artifact}`
}

// --- Metadata --------------------------------------------------------------
export async function fetchCountries() {
  const res = await fetch(`${API_BASE}/meta/countries`)
  if (!res.ok) throw new Error('Failed to load country list')
  return res.json()
}

// --- Visitor / session tracking (fire-and-forget; failures are swallowed
// so a tracking hiccup never surfaces to the user) -----------------------
export async function trackPageview(payload) {
  try {
    await authFetch('/track/pageview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch { /* tracking must never break the app */ }
}

export function trackBeacon(payload) {
  try {
    const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' })
    if (navigator.sendBeacon) {
      navigator.sendBeacon(`${API_BASE}/track/beacon`, blob)
    }
  } catch { /* tracking must never break the app */ }
}

export async function trackEvent(eventType, eventData, ids) {
  try {
    await authFetch('/track/event', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event_type: eventType, event_data: eventData || {}, ...ids }),
    })
  } catch { /* tracking must never break the app */ }
}

// --- Admin dashboard ---------------------------------------------------------
export async function adminListUsers(params = {}) {
  const q = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null)))
  return authFetchJson(`/admin/users?${q.toString()}`)
}

export async function adminGetUser(userId) {
  return authFetchJson(`/admin/users/${userId}`)
}

export async function adminSetUserAdmin(userId, isAdmin) {
  return authFetchJson(`/admin/users/${userId}/admin`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_admin: isAdmin }),
  })
}

export async function adminSetUserStatus(userId, isActive) {
  return authFetchJson(`/admin/users/${userId}/status`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_active: isActive }),
  })
}

export function adminUserExportPath(format, params = {}) {
  const q = new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null)))
  return `/admin/users/export.${format}?${q.toString()}`
}

export async function adminOverview() {
  return authFetchJson('/admin/analytics/overview')
}

export async function adminCharts() {
  return authFetchJson('/admin/analytics/charts')
}

export async function adminSeoPages() {
  return authFetchJson('/admin/seo/pages')
}

export async function adminSeoInsights() {
  return authFetchJson('/admin/seo/insights')
}
