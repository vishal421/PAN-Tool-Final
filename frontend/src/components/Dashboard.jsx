import React, { useMemo } from 'react'
import JobHistory from './JobHistory'
import { VENDOR_META } from '../vendorMeta'
import { IconArrowRight, IconClipboardCheck, IconFolder, IconCheckCircle, IconAlertTriangle, IconTrendingUp } from './Icons'

export default function Dashboard({
  currentUser,
  jobs, jobsLoading, jobsError, onRefreshJobs, onResumeJob, onDeleteJob, confirm,
  activeVendorKeys,
  onSelectVendor,
  onOpenBpa,
}) {
  // Real aggregates derived from the jobs actually on this account — no
  // fabricated numbers. Objects Migrated sums each completed job's own
  // per-vendor stats payload (addresses, policies, services, etc.).
  const stats = useMemo(() => {
    const total = jobs.length
    const completed = jobs.filter((j) => j.status === 'completed').length
    const needsAttention = jobs.filter((j) => j.status === 'failed').length
    const objectsMigrated = jobs
      .filter((j) => j.status === 'completed' && j.stats)
      .reduce((sum, j) => sum + Object.values(j.stats).reduce((a, b) => a + (Number(b) || 0), 0), 0)
    return [
      { label: 'Migration Jobs', value: total, icon: IconFolder },
      { label: 'Completed', value: completed, icon: IconCheckCircle },
      { label: 'Needs Attention', value: needsAttention, icon: IconAlertTriangle },
      { label: 'Objects Migrated', value: objectsMigrated.toLocaleString(), icon: IconTrendingUp },
    ]
  }, [jobs])

  const displayName = currentUser?.first_name || (currentUser?.email || '').split('@')[0]

  return (
    <div>
      <div className="dashboard-welcome">
        <h1>Welcome back{displayName ? `, ${displayName}` : ''}</h1>
        <p className="hint" style={{ margin: 0 }}>Continue where you left off, or start a new migration below.</p>
      </div>

      <div className="dashboard-stats-grid">
        {stats.map((s) => (
          <div key={s.label} className="stat-tile">
            <span className="stat-tile-icon-chip"><s.icon width={16} height={16} /></span>
            <div className="value">{s.value}</div>
            <div className="label">{s.label}</div>
          </div>
        ))}
      </div>

      <JobHistory
        jobs={jobs}
        loading={jobsLoading}
        error={jobsError}
        onResume={onResumeJob}
        onRefresh={onRefreshJobs}
        onDelete={onDeleteJob}
        confirm={confirm}
        title="Job History"
        hint="Continue a previous migration job, or start a new one from the tools below."
      />

      <div className="card">
        <h2>Conversion Tool</h2>
        <p className="hint">Select a source vendor to begin a new migration to Palo Alto. Only that migration workflow will open.</p>

        <div className="migration-grid">
          {VENDOR_META.map((v) => {
            const isActive = activeVendorKeys.includes(v.key)
            return (
              <button
                key={v.key}
                type="button"
                className={`migration-card ${isActive ? '' : 'disabled'}`}
                onClick={() => isActive && onSelectVendor(v.key)}
                disabled={!isActive}
              >
                <div className="migration-card-top">
                  <span className="migration-card-icon">{v.initials}</span>
                  {!isActive && <span className="coming-soon-badge">Coming Soon</span>}
                </div>
                <div className="migration-card-title">{v.label} &rarr; Palo Alto</div>
                <p className="migration-card-desc">{v.description}</p>
                <span className="migration-card-cta">
                  {isActive ? <>Open Tool <IconArrowRight width={14} height={14} /></> : 'Not available yet'}
                </span>
              </button>
            )
          })}
        </div>
      </div>

      <div className="card">
        <h2>Best Practice Assessment</h2>
        <p className="hint">
          Automated hardening checks for your Palo Alto deployment, powered by the Palo Alto Networks BPA
          API. This opens the dedicated BPA console (bpa.{'{'}your-domain{'}'}) in a new tab — it authenticates
          directly against Palo Alto's SCM API with your own API credentials, separately from your account here.
        </p>

        <div className="assessment-grid">
          <button type="button" className="migration-card" onClick={() => onOpenBpa('ngfw')}>
            <div className="migration-card-top">
              <span className="migration-card-icon assessment-icon"><IconClipboardCheck width={18} height={18} /></span>
            </div>
            <div className="migration-card-title">Assess PA Firewall Configuration</div>
            <p className="migration-card-desc">Evaluate a Palo Alto NGFW config against best-practice hardening guidelines.</p>
            <span className="migration-card-cta">Open BPA Console <IconArrowRight width={14} height={14} /></span>
          </button>

          <button type="button" className="migration-card" onClick={() => onOpenBpa('panorama')}>
            <div className="migration-card-top">
              <span className="migration-card-icon assessment-icon"><IconClipboardCheck width={18} height={18} /></span>
            </div>
            <div className="migration-card-title">Assess Panorama Configuration</div>
            <p className="migration-card-desc">Evaluate a Panorama-managed configuration against best-practice hardening guidelines.</p>
            <span className="migration-card-cta">Open BPA Console <IconArrowRight width={14} height={14} /></span>
          </button>
        </div>
      </div>
    </div>
  )
}
