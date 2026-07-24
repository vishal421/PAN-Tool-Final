import React, { useEffect, useRef, useState, Suspense, lazy } from 'react'
import {
  fetchVendors, parseConfig, fetchSummary, submitMapping, downloadPath, listJobs, fetchJob, fetchInterfaces,
  fetchMe, logout, setUnauthorizedHandler, triggerDownload, deleteJob, changePassword, updateProfile,
} from './api'
import InterfaceMappingWizard from './components/InterfaceMappingWizard'
import ConfigurationSummary from './components/ConfigurationSummary'
import Dashboard from './components/Dashboard'
const Workbench = lazy(() => import('./components/Workbench'))
import AuthScreen, { isPasswordValid, PasswordRequirements } from './components/AuthScreen'
import LandingPage from './components/LandingPage'
import FortigateMigrationPage from './pages/migration/FortigateMigrationPage'
import CheckpointMigrationPage from './pages/migration/CheckpointMigrationPage'
import CiscoMigrationPage from './pages/migration/CiscoMigrationPage'
import SophosMigrationPage from './pages/migration/SophosMigrationPage'
import BpaSeoPage from './pages/BpaSeoPage'
import NotFoundPage from './pages/NotFoundPage'
import AccountMenu from './components/AccountMenu'
import { useToast } from './components/ToastProvider'
import { useConfirmDialog } from './components/useConfirmDialog'
import { IconLoader, IconGrid, IconBook, IconLifeBuoy, IconSettings, IconShield, IconPhone, IconBuilding, IconClipboardCheck, IconBox, IconNetwork, IconShieldCheck, IconSparkles, IconChevronDown, IconArrowRight } from './components/Icons'
import { VENDOR_META } from './vendorMeta'
import { initTracking, trackActivity, trackPageView } from './tracking'
const AdminApp = lazy(() => import('./pages/admin/AdminApp'))

const STAT_LABELS = [
  ['addresses', 'Addresses'],
  ['address_groups', 'Address Groups'],
  ['services', 'Services'],
  ['service_groups', 'Service Groups'],
  ['interfaces', 'Interfaces'],
  ['policies', 'Policies'],
  ['routes', 'Routes'],
  ['nat_rules', 'NAT Rules'],
]

// Standalone SEO landing pages, keyed by pathname. These are public marketing
// pages (no auth, no app shell) and are matched before anything else renders.
const MIGRATION_ROUTES = {
  '/fortigate-to-palo-alto-migration': FortigateMigrationPage,
  '/checkpoint-to-palo-alto-migration': CheckpointMigrationPage,
  '/cisco-to-palo-alto-migration': CiscoMigrationPage,
  '/sophos-to-palo-alto-migration': SophosMigrationPage,
  '/palo-alto-bpa-report-generator': BpaSeoPage,
}

// The SEO pages live outside the SPA's client-side state, so a "Log in" /
// "Get started" click there has to do a real navigation. It lands on '/' with
// ?auth=login|signup so this app boots straight into AuthScreen in the right
// mode instead of showing the marketing landing page again.
function getAuthIntent() {
  if (typeof window === 'undefined') return null
  const v = new URLSearchParams(window.location.search).get('auth')
  return v === 'login' || v === 'signup' ? v : null
}

// step: 'dashboard' -> 'upload' -> 'summary' -> 'mapping' -> 'results' (also 'jobFailed' when resuming a failed job)
export default function App() {
  // --- Subdomain-based routing (login./signup./dash.<root domain>) --------
  // Only kicks in when actually deployed on those exact subdomains - set
  // VITE_ROOT_DOMAIN at build time (e.g. "pan-tool.com"). Any other
  // hostname (the root marketing domain, localhost in dev, a preview URL,
  // etc.) leaves these all false and the app behaves exactly as it always
  // has: one origin, AuthScreen shown inline.
  const ROOT_DOMAIN = import.meta.env.VITE_ROOT_DOMAIN
  const HOSTNAME = typeof window !== 'undefined' ? window.location.hostname : ''
  const isLoginHost = Boolean(ROOT_DOMAIN) && HOSTNAME === `login.${ROOT_DOMAIN}`
  const isSignupHost = Boolean(ROOT_DOMAIN) && HOSTNAME === `signup.${ROOT_DOMAIN}`
  const isDashHost = Boolean(ROOT_DOMAIN) && HOSTNAME === `dash.${ROOT_DOMAIN}`
  // The admin dashboard's URL is deliberately not "/admin" - anyone can type
  // that into any site and see if something's there. VITE_ADMIN_PATH lets
  // each deployment set its own private, hard-to-guess path (e.g. a random
  // slug); if it's never configured, this default is at least not the
  // first thing anyone would try. Whatever it's set to, it's still fully
  // gated behind login + the backend's is_admin check either way - this
  // only removes it as a low-effort target, it isn't the actual security
  // boundary.
  const ADMIN_PATH = import.meta.env.VITE_ADMIN_PATH || '/ops-portal-7f2k9'
  const isAdminPath = typeof window !== 'undefined' && window.location.pathname.startsWith(ADMIN_PATH)
  // Shared helper: on a real subdomain deployment, send the visitor to the
  // actual login./signup. subdomain (real cross-origin navigation, so the
  // Domain-scoped session cookie set there is visible everywhere). On a
  // plain single-origin/local deployment (ROOT_DOMAIN unset), fall back to
  // the old same-page `?auth=` query-param behavior.
  const authUrl = (mode) => (
    ROOT_DOMAIN ? `https://${mode === 'signup' ? 'signup' : 'login'}.${ROOT_DOMAIN}/` : `/?auth=${mode === 'signup' ? 'signup' : 'login'}`
  )
  // Best Practice Assessment is a fully separate app (its own Node server,
  // its own SCM API auth flow - see /bpa-tool) deployed on its own
  // subdomain, not part of this SPA. VITE_BPA_URL is the local/dev
  // fallback (defaults to the bpa-tool's own dev port).
  const bpaUrl = (deviceType) => {
    const base = ROOT_DOMAIN ? `https://bpa.${ROOT_DOMAIN}/` : (import.meta.env.VITE_BPA_URL || 'http://localhost:4021/')
    return `${base}${base.includes('?') ? '&' : '?'}device_type=${deviceType}`
  }

  const [step, setStep] = useState('dashboard')
  const [activeVendorKeys, setActiveVendorKeys] = useState([])
  const [selectedVendor, setSelectedVendor] = useState(null)
  const [jobName, setJobName] = useState('')
  const [file, setFile] = useState(null)
  const [dragActive, setDragActive] = useState(false)
  const [job, setJob] = useState(null)
  const [interfaces, setInterfaces] = useState([])
  const [summary, setSummary] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [validation, setValidation] = useState(null)

  const [jobs, setJobs] = useState([])
  const [jobsLoading, setJobsLoading] = useState(false)
  const [jobsError, setJobsError] = useState(null)

  // Which section of the open job is showing in the workbench - driven by
  // the persistent left sidebar now, not an internal toggleable nav inside
  // the workbench itself. Always starts on 'summary' the moment a job is
  // opened (fresh upload or resumed) per the "land on Summary, never the
  // edit view" requirement.
  const [workbenchTab, setWorkbenchTab] = useState('summary')
  // Mirrors Workbench's own `stats` state so the sidebar's Objects/Network/
  // Policies counts stay in sync with edits made in the grids, without the
  // sidebar needing to fetch validation data itself.
  const [jobStats, setJobStats] = useState({})

  useEffect(() => {
    setJobStats(job?.stats || {})
  }, [job?.id])

  const openBpa = (deviceType) => {
    trackActivity('tool_opened', { vendor: `bpa_${deviceType}` })
    window.open(bpaUrl(deviceType), '_blank', 'noopener')
  }

  const [currentUser, setCurrentUser] = useState(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [showLanding, setShowLanding] = useState(() => !getAuthIntent())
  const [authMode, setAuthMode] = useState(() => getAuthIntent() || 'login')

  // Dark mode has been removed - the app only supports the light theme,
  // both on the marketing/login/signup/SEO pages and the authenticated
  // tool itself.
  const theme = 'light'
  const showToast = useToast()
  const { confirm, ConfirmDialogElement } = useConfirmDialog()

  useEffect(() => {
    if (getAuthIntent()) window.history.replaceState({}, '', window.location.pathname)
  }, [])

  useEffect(() => {
    initTracking()
    trackPageView(window.location.pathname)
  }, [])

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [])

  useEffect(() => {
    if (!authChecked || isAdminPath) return
    if ((isLoginHost || isSignupHost) && currentUser) {
      window.location.href = `https://dash.${ROOT_DOMAIN}/`
    } else if (isDashHost && !currentUser) {
      window.location.href = `https://login.${ROOT_DOMAIN}/`
    }
  }, [authChecked, currentUser])

  // Keeps localStorage in sync with whichever tab is open, so a reload
  // lands back exactly where the user was instead of the dashboard.
  useEffect(() => {
    if (step === 'workbench' && job) {
      localStorage.setItem('fwc:lastJob', JSON.stringify({ id: job.id, tab: workbenchTab }))
    }
  }, [step, job, workbenchTab])

  // Once we know who's logged in (and haven't already navigated anywhere
  // via a user click), try to restore whatever job/tab was open before
  // the page was reloaded.
  useEffect(() => {
    if (!authChecked || !currentUser || job) return
    let saved = null
    try { saved = JSON.parse(localStorage.getItem('fwc:lastJob') || 'null') } catch { /* ignore malformed value */ }
    if (saved?.id) resumeJob({ id: saved.id }, saved.tab)
  }, [authChecked, currentUser])

  const inputRef = useRef(null)

  // Runs once: register the global 401 handler, then try to resume a
  // session from the (HttpOnly, invisible-to-JS) session cookie by just
  // asking the API who we are - a 401 there means "not logged in".
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setCurrentUser(null)
      setStep('dashboard')
    })
    fetchMe()
      .then((user) => setCurrentUser(user))
      .catch(() => {}) // not logged in - that's fine, AuthScreen handles it
      .finally(() => setAuthChecked(true))
  }, [])

  const handleLogout = () => {
    trackActivity('logout')
    logout().catch(() => {}) // best-effort - clear local state regardless
    setCurrentUser(null)
    setStep('dashboard')
    localStorage.removeItem('fwc:lastJob')
    showToast('Logged out.', 'info')
  }

  const handleDownload = async (path, filename) => {
    setError(null)
    try {
      await triggerDownload(path, filename)
      trackActivity(filename?.toLowerCase().includes('report') ? 'download_report' : 'download_cli', { filename })
    } catch (e) {
      setError(e.message)
    }
  }

  useEffect(() => {
    fetchVendors()
      .then((v) => setActiveVendorKeys(v.map((x) => x.key)))
      .catch(() => setActiveVendorKeys([]))
  }, [])

  useEffect(() => {
    if (step === 'dashboard' && currentUser) refreshJobs()
  }, [step, currentUser])

  const refreshJobs = async () => {
    setJobsLoading(true)
    setJobsError(null)
    try {
      const rows = await listJobs()
      setJobs(rows)
    } catch (e) {
      setJobsError(e.message)
    } finally {
      setJobsLoading(false)
    }
  }

  const goHome = () => {
    setStep('dashboard')
    setError(null)
    localStorage.removeItem('fwc:lastJob')
  }

  const handleDeleteJob = async (jobRow) => {
    await deleteJob(jobRow.id) // lets JobHistory's own try/finally handle the busy-state; error propagates to its confirm() caller
    setJobsError(null)
    await refreshJobs()
    showToast('Job deleted.', 'success')
  }

  const deleteCurrentJobAndGoHome = async () => {
    if (!job) return
    const ok = await confirm(`Delete "${job.job_name || job.original_filename}"? This can't be undone.`, { confirmLabel: 'Delete Job' })
    if (!ok) return
    setLoading(true)
    setError(null)
    try {
      await deleteJob(job.id)
      goHome()
      showToast('Job deleted.', 'success')
    } catch (e) {
      setError(e.message)
      showToast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  const startNewForVendor = (vendorKey) => {
    trackActivity('tool_opened', { vendor: vendorKey })
    setFile(null)
    setJob(null)
    setError(null)
    setSelectedVendor(vendorKey)
    setJobName('')
    setInterfaces([])
    setSummary(null)
    setValidation(null)
    setStep('upload')
  }

  const resumeJob = async (jobRow, restoreTab) => {
    setError(null)
    setLoading(true)
    try {
      const full = await fetchJob(jobRow.id)
      setJob(full)
      setJobName(full.job_name || '')
      setSelectedVendor(full.vendor)

      if (full.status === 'completed' || full.status === 'awaiting_mapping') {
        const [summaryResp, interfacesResp] = await Promise.all([
          fetchSummary(full.id),
          fetchInterfaces(full.id),
        ])
        setSummary(summaryResp)
        setInterfaces(interfacesResp)
        setWorkbenchTab(restoreTab || 'summary')
        setStep('workbench')
        localStorage.setItem('fwc:lastJob', JSON.stringify({ id: full.id, tab: restoreTab || 'summary' }))
      } else {
        // 'failed' or still 'parsing' - nothing further to resume into
        setStep('jobFailed')
        localStorage.removeItem('fwc:lastJob')
      }
    } catch (e) {
      setError(e.message)
      setStep('jobFailed')
      localStorage.removeItem('fwc:lastJob')
    } finally {
      setLoading(false)
    }
  }

  const openMappingWizard = async () => {
    setLoading(true)
    setError(null)
    try {
      const fresh = await fetchInterfaces(job.id) // re-fetch in case objects were edited in the Workbench
      setInterfaces(fresh)
      setStep('mapping')
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleFileSelect = (f) => {
    if (!f) return
    setFile(f)
    setJob(null)
    setError(null)
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragActive(false)
    if (e.dataTransfer.files?.length) handleFileSelect(e.dataTransfer.files[0])
  }

  const handleParse = async () => {
    if (!selectedVendor || !file || !jobName.trim()) return
    setLoading(true)
    setError(null)
    trackActivity('config_uploaded', { vendor: selectedVendor })
    try {
      const resp = await parseConfig(selectedVendor, file, jobName.trim())
      setJob(resp.job)
      if (resp.job.status === 'failed') {
        setError(resp.job.error_message || resp.message)
        return
      }
      trackActivity('migration_started', { vendor: selectedVendor, job_id: resp.job.id })
      setInterfaces(resp.interfaces)
      const summaryResp = await fetchSummary(resp.job.id)
      setSummary(summaryResp)
      setWorkbenchTab('summary')
      setStep('workbench')
      fetchMe().then(setCurrentUser).catch(() => {}) // refresh job-count badge, best effort
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const handleMappingSubmit = async (rows) => {
    setLoading(true)
    setError(null)
    try {
      const resp = await submitMapping(job.id, rows, false)
      setValidation(resp.validation)
      setJob(resp.job)
      if (resp.job.status === 'completed') {
        trackActivity('migration_completed', { job_id: job?.id, vendor: job?.vendor })
        setStep('results')
      } else if (resp.job.status === 'failed') {
        setError(resp.job.error_message || resp.message)
      }
      // if blocking validation errors, stay on the mapping step - the
      // wizard displays resp.validation.issues inline
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // Private admin dashboard - never linked from the app's nav, deliberately
  // gated behind the same auth session (see auth/core.py require_admin) and
  // excluded from robots.txt/sitemap.xml. Renders its own noindex meta tag.
  if (isAdminPath) {
    if (!authChecked) return <div className="auth-shell"><IconLoader width={28} height={28} /></div>
    if (!currentUser) {
      return <AuthScreen initialMode="login" onAuthed={(user) => setCurrentUser(user)} />
    }
    return (
      <Suspense fallback={<div className="auth-shell"><IconLoader width={28} height={28} /></div>}>
        <AdminApp currentUser={currentUser} onLogout={handleLogout} />
      </Suspense>
    )
  }

  // login.<domain> / signup.<domain> - always show AuthScreen in the
  // matching mode; onAuthed navigates across to dash.<domain> (a real
  // cross-origin navigation, since the session cookie is Domain-scoped to
  // the whole site and dash.<domain> will already see it on arrival).
  if (isLoginHost || isSignupHost) {
    if (!authChecked || currentUser) {
      // currentUser is briefly non-null here right after a successful auth,
      // while the redirect effect above is navigating away - show a loader
      // instead of flashing the wrong screen for that one render.
      return <div className="auth-shell"><IconLoader width={28} height={28} /></div>
    }
    return (
      <AuthScreen
        initialMode={isSignupHost ? 'signup' : 'login'}
        onAuthed={(user) => setCurrentUser(user)}
        onSwitchMode={ROOT_DOMAIN ? (mode) => { window.location.href = authUrl(mode) } : undefined}
      />
    )
  }

  // dash.<domain> - the actual authenticated tool. Not-logged-in visitors
  // get bounced to login.<domain> by the redirect effect above; this just
  // avoids rendering the app shell for the one render before that happens.
  if (isDashHost && !currentUser) {
    return <div className="auth-shell"><IconLoader width={28} height={28} /></div>
  }

  if (!isDashHost) {
    // Only the root/marketing domain (or a plain single-origin/local dev
    // deployment, where ROOT_DOMAIN is unset and none of the subdomain
    // checks above ever match) reaches the SEO landing pages below.
    const MigrationRouteComponent = typeof window !== 'undefined' ? MIGRATION_ROUTES[window.location.pathname] : null
    if (MigrationRouteComponent) {
      return <MigrationRouteComponent onGetStarted={(mode) => { window.location.href = authUrl(mode) }} />
    }

    // Anything else that isn't the homepage or a known SEO page gets a real
    // 404 instead of silently rendering the homepage - that used to happen
    // for literally any path (typo, old bookmark, bot probing for /wp-admin,
    // etc.), which is confusing for visitors and bad for SEO (every made-up
    // URL looked like duplicate homepage content to a crawler).
    const rawPath = typeof window !== 'undefined' ? window.location.pathname : '/'
    const normalizedPath = rawPath.length > 1 && rawPath.endsWith('/') ? rawPath.slice(0, -1) : rawPath
    const isKnownPath = normalizedPath === '/' || Object.prototype.hasOwnProperty.call(MIGRATION_ROUTES, normalizedPath)
    if (!isKnownPath) {
      return <NotFoundPage onGetStarted={(mode) => { window.location.href = authUrl(mode) }} />
    }
  }

  if (!authChecked) {
    return <div className="auth-shell"><IconLoader width={28} height={28} /></div>
  }

  // pan-tool.com (the root/marketing domain) always opens the public
  // homepage first - being logged in no longer auto-redirects straight
  // into the tool. The visitor has to explicitly choose to enter the app.
  if (!isDashHost && showLanding) {
    return (
      <LandingPage
        loggedIn={Boolean(currentUser)}
        onGetStarted={(mode) => {
          if (currentUser) {
            // Already authenticated - "entering the app" is still an
            // explicit action, just one that skips the login form.
            if (ROOT_DOMAIN) {
              window.location.href = `https://dash.${ROOT_DOMAIN}/`
            } else {
              setShowLanding(false)
            }
            return
          }
          if (ROOT_DOMAIN) {
            window.location.href = authUrl(mode)
          } else {
            setAuthMode(mode === 'signup' ? 'signup' : 'login')
            setShowLanding(false)
          }
        }}
      />
    )
  }

  if (!currentUser) {
    return <AuthScreen initialMode={authMode} onAuthed={(user) => { setCurrentUser(user); showToast(`Welcome, ${user.email}!`, 'success') }} />
  }

  return (
    <div className="app-layout" data-theme="light">
      <Sidebar
        step={step}
        currentUser={currentUser}
        onGoHome={goHome}
        onOpenSettings={() => setStep('settings')}
        onLogout={handleLogout}
        job={step === 'workbench' ? job : null}
        stats={jobStats}
        workbenchTab={workbenchTab}
        onSelectWorkbenchTab={setWorkbenchTab}
      />
      <div className={`app-shell ${step === 'workbench' ? 'wide' : ''}`}>
      {ConfirmDialogElement}
      <header className="app-header">
        <div className="app-title">
          <span className="mark">FC</span>
          Firewall Config Converter
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          {step !== 'dashboard' && (
            <button className="btn btn-secondary" onClick={goHome}>&larr; Home</button>
          )}
          <AccountMenu
            currentUser={currentUser}
            onLogout={handleLogout}
          />
        </div>
      </header>

      {step !== 'dashboard' && step !== 'jobFailed' && step !== 'workbench' && step !== 'settings' && <StepIndicator step={step} />}

      {step === 'dashboard' && (
        <Dashboard
          currentUser={currentUser}
          jobs={jobs}
          jobsLoading={jobsLoading}
          jobsError={jobsError}
          onRefreshJobs={refreshJobs}
          onResumeJob={resumeJob}
          onDeleteJob={handleDeleteJob}
          confirm={confirm}
          activeVendorKeys={activeVendorKeys}
          onSelectVendor={startNewForVendor}
          onOpenBpa={openBpa}
        />
      )}

      {step === 'settings' && (
        <div>
          <div className="dashboard-welcome">
            <h1>Settings</h1>
            <p className="hint" style={{ margin: 0 }}>Appearance and account details for this workspace.</p>
          </div>

          <ProfileCard currentUser={currentUser} onProfileUpdated={setCurrentUser} showToast={showToast} />

          <ChangePasswordCard showToast={showToast} />
        </div>
      )}

      {step === 'upload' && (
        <div className="card">
          <h2>1. Name This Job</h2>
          <p className="hint">Give this conversion a name so you can find and resume it later from the Home screen.</p>

          <div className="vendor-badge-row">
            <span className="vendor-badge-pill">
              {VENDOR_META.find((v) => v.key === selectedVendor)?.label || selectedVendor} &rarr; Palo Alto
            </span>
            <button className="btn btn-secondary" onClick={goHome} disabled={loading}>Change vendor</button>
          </div>

          <input
            type="text"
            className="job-name-input"
            placeholder="e.g. HQ Branch FortiGate migration"
            value={jobName}
            onChange={(e) => setJobName(e.target.value)}
          />

          <h2>2. Upload Configuration</h2>
          <p className="hint">Drop the exported config file, or click to browse.</p>
          <div
            className={`dropzone ${dragActive ? 'active' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setDragActive(true) }}
            onDragLeave={() => setDragActive(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
          >
            <div><strong>Click to upload</strong> or drag and drop</div>
            <div style={{ fontSize: 12, marginTop: 4 }}>.conf, .txt, .cfg, .xml, .export — up to 25MB</div>
            <input
              ref={inputRef}
              type="file"
              hidden
              onChange={(e) => handleFileSelect(e.target.files?.[0])}
            />
            {file && (
              <div className="file-chip">
                📄 {file.name} <span style={{ color: 'var(--text-secondary)' }}>({(file.size / 1024).toFixed(1)} KB)</span>
              </div>
            )}
          </div>

          <div className="actions-row">
            <button className="btn btn-secondary" onClick={goHome} disabled={loading}>Cancel</button>
            <button
              className="btn btn-primary"
              onClick={handleParse}
              disabled={!selectedVendor || !file || !jobName.trim() || loading}
              title={!jobName.trim() ? 'Enter a job name first' : undefined}
            >
              {loading ? 'Parsing…' : 'Parse Configuration'}
            </button>
          </div>

          {error && <div className="error-box">{error}</div>}
        </div>
      )}

      {step === 'workbench' && job && (
        <Suspense fallback={<div className="card" style={{ textAlign: 'center', padding: 60 }}><IconLoader width={28} height={28} /></div>}>
          <Workbench
            job={job}
            summary={summary}
            activeTab={workbenchTab}
            onTabChange={setWorkbenchTab}
            onExitToHome={goHome}
            onDeleteJob={deleteCurrentJobAndGoHome}
            onStatsUpdated={setJobStats}
          />
        </Suspense>
      )}

      {step === 'mapping' && (
        <>
          <InterfaceMappingWizard
            interfaces={interfaces}
            onSubmit={handleMappingSubmit}
            submitting={loading}
            validation={validation}
          />
          {error && <div className="error-box">{error}</div>}
          <div className="footer-note">
            <button className="btn btn-secondary" onClick={goHome}>Start over</button>
          </div>
        </>
      )}

      {step === 'results' && job && job.status === 'completed' && (
        <>
          <ResultsCard job={job} onDownload={handleDownload} />
          <div className="actions-row">
            <button className="btn btn-secondary" onClick={goHome}>Back to Home</button>
            <button className="btn btn-secondary" onClick={() => { setWorkbenchTab('summary'); setStep('workbench') }}>Open Editing Workbench</button>
            <button className="btn btn-primary" onClick={goHome}>Convert another file</button>
          </div>
        </>
      )}

      {step === 'jobFailed' && job && (
        <div className="card">
          <h2>{job.job_name || 'Job'} — {job.status === 'failed' ? 'Failed' : 'Still in progress'}</h2>
          <p className="hint">{job.original_filename} &middot; {job.vendor}</p>
          {(job.error_message || error) && (
            <div className="error-box">{job.error_message || error}</div>
          )}
          {job.status !== 'failed' && !job.error_message && !error && (
            <p className="hint">This job hasn't finished parsing yet - try refreshing from Home in a moment.</p>
          )}
          <div className="actions-row">
            <button className="btn btn-secondary" onClick={goHome}>Back to Home</button>
          </div>
        </div>
      )}

      <div className="footer-note">
        Your configuration data is encrypted in transit and processed securely on our servers.
      </div>
      </div>
    </div>
  )
}

// Sections shown in the left sidebar once a job is open (after uploading a
// config or resuming an existing one). Objects / Network / Policies are
// collapsible groups; everything else is a flat top-level item. Keys match
// what Workbench.jsx expects for `activeTab`.
const JOB_NAV_GROUPS = [
  { key: 'objects', label: 'Objects', icon: IconBox, items: [
    { key: 'addresses', label: 'Address Objects' },
    { key: 'address_groups', label: 'Address Groups' },
    { key: 'services', label: 'Service Objects' },
    { key: 'service_groups', label: 'Service Groups' },
  ] },
  { key: 'network', label: 'Network', icon: IconNetwork, items: [
    { key: 'zones', label: 'Zones' },
    { key: 'routes', label: 'Virtual Routers' },
    { key: 'interfaces', label: 'Interface Mapping' },
  ] },
  { key: 'policies', label: 'Policies', icon: IconShieldCheck, items: [
    { key: 'profiles', label: 'Security Profiles' },
    { key: 'profiles-log', label: 'Log Forwarding Profiles', tab: 'profiles' },
    { key: 'policies', label: 'Security Policies' },
    { key: 'nat_rules', label: 'NAT Policies' },
  ] },
]

function Sidebar({
  step, currentUser, onGoHome, onOpenSettings, onLogout,
  job, stats, workbenchTab, onSelectWorkbenchTab,
}) {
  // Reuses the sidebar's existing expand/collapse toggle pattern (chevron
  // rotate) for each collapsible group, defaulting all three open.
  const [openGroups, setOpenGroups] = useState({ objects: true, network: true, policies: true })
  const toggleGroup = (key) => setOpenGroups((g) => ({ ...g, [key]: !g[key] }))

  // Real destinations wired to actual app state; Documentation/Support are
  // placeholders (no backing pages yet) — dummy for now per explicit
  // approval, to be built out or removed in a later pass.
  const NAV = [
    { key: 'dashboard', label: 'Dashboard', icon: IconGrid, onClick: onGoHome, active: step === 'dashboard' },
    { key: 'docs', label: 'Documentation', icon: IconBook, dummy: true },
    { key: 'support', label: 'Support', icon: IconLifeBuoy, dummy: true },
    { key: 'settings', label: 'Settings', icon: IconSettings, onClick: onOpenSettings, active: step === 'settings' },
  ]

  // Collapsed icon-only rail at rest, CSS (`.app-sidebar:hover`) widens
  // it into the full labeled nav on hover as an overlay - no
  // click-to-collapse state to manage or lose on reload. `.app-shell`'s
  // left margin is sized to the collapsed rest width only, so the main
  // content never shifts on hover; the overlay may cover a little
  // content while expanded, which is fine. Everything below always
  // renders in full; the collapsed look is purely CSS hiding overflow,
  // not conditional JSX.
  return (
    <aside className="app-sidebar">
      <button className="sidebar-brand" onClick={onGoHome} title="Dashboard">
        <span className="sidebar-brand-mark"><IconShield width={18} height={18} /></span>
      </button>
      <nav className="sidebar-nav">
        {job ? (
          <>
            <button className="sidebar-nav-item" onClick={onGoHome}>
              <IconGrid width={16} height={16} />
              <span>Dashboard</span>
            </button>
            <button
              className={`sidebar-nav-item ${workbenchTab === 'summary' ? 'active' : ''}`}
              onClick={() => onSelectWorkbenchTab('summary')}
            >
              <IconClipboardCheck width={16} height={16} />
              <span>Summary</span>
            </button>

            {JOB_NAV_GROUPS.map((group) => (
              <div className="sidebar-nav-group" key={group.key}>
                <button
                  className="sidebar-nav-item sidebar-nav-group-header"
                  onClick={() => toggleGroup(group.key)}
                >
                  <group.icon width={16} height={16} />
                  <span>{group.label}</span>
                  <IconChevronDown
                    width={14}
                    height={14}
                    className={`sidebar-nav-group-chevron ${openGroups[group.key] ? 'is-open' : ''}`}
                  />
                </button>
                {openGroups[group.key] && (
                  <div className="sidebar-nav-subitems">
                    {group.items.map((item) => (
                      <button
                        key={item.key}
                        className={`sidebar-nav-item sidebar-nav-subitem ${workbenchTab === (item.tab || item.key) ? 'active' : ''}`}
                        onClick={() => onSelectWorkbenchTab(item.tab || item.key)}
                      >
                        <span>{item.label}</span>
                        {stats?.[item.key] !== undefined && (
                          <span className="sidebar-count">{stats[item.key]}</span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}

            <button
              className={`sidebar-nav-item ${workbenchTab === 'cleanup' ? 'active' : ''}`}
              onClick={() => onSelectWorkbenchTab('cleanup')}
            >
              <IconSparkles width={16} height={16} />
              <span>Config Cleanup</span>
            </button>
            <button
              className={`sidebar-nav-item ${workbenchTab === 'export' ? 'active' : ''}`}
              onClick={() => onSelectWorkbenchTab('export')}
            >
              <IconArrowRight width={16} height={16} />
              <span>Export</span>
            </button>
          </>
        ) : (
          NAV.map((n) => (
            <button
              key={n.key}
              className={`sidebar-nav-item ${n.active ? 'active' : ''}`}
              onClick={n.onClick}
              title={n.dummy ? 'Coming soon' : undefined}
            >
              <n.icon width={16} height={16} />
              <span>{n.label}</span>
            </button>
          ))
        )}
      </nav>
    </aside>
  )
}

function StepIndicator({ step }) {
  const steps = [
    { key: 'upload', label: 'Upload & Parse' },
    { key: 'summary', label: 'Configuration Summary' },
    { key: 'mapping', label: 'Interface Mapping' },
    { key: 'results', label: 'Generate & Download' },
  ]
  const activeIdx = steps.findIndex((s) => s.key === step)
  return (
    <div className="step-indicator">
      {steps.map((s, i) => (
        <div key={s.key} className={`step-pill ${i === activeIdx ? 'active' : i < activeIdx ? 'done' : ''}`}>
          <span className="step-num">{i + 1}</span>
          {s.label}
        </div>
      ))}
    </div>
  )
}

// Digits only, 7-15 characters - a loose but real minimum/maximum length
// check for an international mobile number (E.164-style, country code held
// separately in mobile_country_code).
const isValidMobileNumber = (v) => /^\d{7,15}$/.test(v.trim())

function ProfileCard({ currentUser, onProfileUpdated, showToast }) {
  const [mobileNumber, setMobileNumber] = useState(currentUser?.mobile_number || '')
  const [organizationName, setOrganizationName] = useState(currentUser?.organization_name || '')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [touched, setTouched] = useState(false)

  const phoneError = touched && mobileNumber.trim() && !isValidMobileNumber(mobileNumber)
    ? 'Enter a valid phone number (digits only, 7–15 digits).' : null

  const handleMobileChange = (e) => {
    // Hard-block anything but digits as the user types - no letters or
    // symbols can ever enter the field.
    setMobileNumber(e.target.value.replace(/[^0-9]/g, '').slice(0, 15))
  }

  const canSubmit = !saving && (!mobileNumber.trim() || isValidMobileNumber(mobileNumber))

  const handleSave = async (e) => {
    e.preventDefault()
    setTouched(true)
    if (!canSubmit) return
    setSaving(true)
    setError(null)
    try {
      const updated = await updateProfile({
        mobile_number: mobileNumber.trim(),
        organization_name: organizationName.trim(),
      })
      onProfileUpdated(updated)
      showToast('Profile updated.', 'success')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card">
      <h2>Account</h2>
      <p className="hint">Your name, mobile number, and organization for this workspace.</p>

      <div className="summary-table-wrap" style={{ marginBottom: 16 }}>
        <table className="summary-table">
          <tbody>
            <tr><td style={{ color: 'var(--text-secondary)' }}>Name</td><td>{[currentUser?.first_name, currentUser?.last_name].filter(Boolean).join(' ') || '—'}</td></tr>
            <tr><td style={{ color: 'var(--text-secondary)' }}>Email</td><td>{currentUser?.email}</td></tr>
            {currentUser?.plan && (
              <tr><td style={{ color: 'var(--text-secondary)' }}>Plan</td><td style={{ textTransform: 'capitalize' }}>{currentUser.plan}</td></tr>
            )}
            {currentUser?.job_limit != null && (
              <tr><td style={{ color: 'var(--text-secondary)' }}>Jobs used</td><td>{currentUser.job_count}/{currentUser.job_limit}</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <form onSubmit={handleSave}>
        <label className="field-label">
          <span><IconBuilding width={13} height={13} /> Organization name</span>
          <input
            type="text"
            className="grid-input auth-input"
            placeholder="e.g. Acme Networks"
            value={organizationName}
            onChange={(e) => setOrganizationName(e.target.value)}
            style={{ width: '100%', marginTop: 6, marginBottom: 16 }}
          />
        </label>

        <label className="field-label">
          <span><IconPhone width={13} height={13} /> Mobile number</span>
          <input
            type="tel"
            inputMode="numeric"
            className="grid-input auth-input"
            placeholder="Digits only, e.g. 9876543210"
            value={mobileNumber}
            onChange={handleMobileChange}
            onBlur={() => setTouched(true)}
            style={{ width: '100%', marginTop: 6, marginBottom: phoneError ? 4 : 16 }}
          />
        </label>
        {phoneError && <div className="hint" style={{ marginTop: 0, marginBottom: 16, color: 'var(--error)' }}>{phoneError}</div>}

        {error && <div className="error-box">{error}</div>}

        <div className="actions-row" style={{ justifyContent: 'flex-start' }}>
          <button type="submit" className="btn btn-primary" disabled={!canSubmit}>
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </form>
    </div>
  )
}

function ChangePasswordCard({ showToast }) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  const mismatch = confirmPassword.length > 0 && newPassword !== confirmPassword
  const canSubmit = currentPassword && isPasswordValid(newPassword) && newPassword === confirmPassword && !saving

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!canSubmit) return
    setSaving(true)
    setError(null)
    try {
      await changePassword(currentPassword, newPassword)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      showToast('Password updated.', 'success')
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card">
      <h2>Change Password</h2>
      <p className="hint">Update the password you use to log in.</p>
      <form onSubmit={handleSubmit}>
        <label className="field-label">
          <span>Current password</span>
          <input
            type="password"
            className="grid-input auth-input"
            autoComplete="current-password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            style={{ width: '100%', marginTop: 6, marginBottom: 16 }}
          />
        </label>
        <label className="field-label">
          <span>New password</span>
          <input
            type="password"
            className="grid-input auth-input"
            autoComplete="new-password"
            minLength={8}
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            style={{ width: '100%', marginTop: 6, marginBottom: 4 }}
          />
        </label>
        <PasswordRequirements password={newPassword} />
        <label className="field-label">
          <span>Confirm new password</span>
          <input
            type="password"
            className="grid-input auth-input"
            autoComplete="new-password"
            minLength={8}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            style={{ width: '100%', marginTop: 6, marginBottom: mismatch ? 4 : 16 }}
          />
        </label>
        {mismatch && <div className="hint" style={{ marginTop: 0, marginBottom: 16, color: 'var(--error)' }}>Passwords don't match.</div>}

        {error && <div className="error-box">{error}</div>}

        <div className="actions-row" style={{ justifyContent: 'flex-start' }}>
          <button type="submit" className="btn btn-primary" disabled={!canSubmit}>
            {saving ? 'Updating…' : 'Update Password'}
          </button>
        </div>
      </form>
    </div>
  )
}

function ResultsCard({ job, onDownload }) {
  const stats = job.stats || {}
  const issues = job.issues || []
  const warnings = issues.filter((i) => i.severity === 'warning')
  const errors = issues.filter((i) => i.severity === 'error')
  const unsupported = issues.filter((i) => i.severity === 'unsupported')

  return (
    <div className="card">
      <h2>Conversion Results</h2>
      <p className="hint">
        {job.original_filename} → Palo Alto CLI &middot; Job {job.id.slice(0, 8)}
      </p>

      <div className="stats-grid">
        {STAT_LABELS.map(([key, label]) => (
          <div className="stat-tile" key={key}>
            <div className="value">{stats[key] ?? 0}</div>
            <div className="label">{label}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
        {warnings.length > 0 && <span className="issue-badge warning">{warnings.length} warnings</span>}
        {errors.length > 0 && <span className="issue-badge error">{errors.length} errors</span>}
        {unsupported.length > 0 && <span className="issue-badge unsupported">{unsupported.length} unsupported</span>}
        {issues.length === 0 && <span className="issue-badge unsupported">No issues detected</span>}
      </div>

      <div className="download-row">
        <button className="btn btn-primary" onClick={() => onDownload(downloadPath(job.id, 'cli'), 'paloalto_config.txt')}>
          Download Palo Alto CLI
        </button>
        <button className="btn btn-secondary" onClick={() => onDownload(downloadPath(job.id, 'csv'), 'objects_summary.csv')}>
          Download CSV
        </button>
        <button className="btn btn-secondary" onClick={() => onDownload(downloadPath(job.id, 'json'), 'normalized_config.json')}>
          Download JSON
        </button>
      </div>
    </div>
  )
}
