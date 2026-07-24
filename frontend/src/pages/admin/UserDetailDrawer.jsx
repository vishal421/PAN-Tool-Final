import React, { useEffect, useState } from 'react'
import { adminGetUser, adminSetUserAdmin, adminSetUserStatus } from '../../api'
import { IconLoader, IconX } from '../../components/Icons'

export default function UserDetailDrawer({ userId, onClose }) {
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const load = () => adminGetUser(userId).then(setDetail).catch((e) => setError(e.message))

  useEffect(() => { load() }, [userId]) // eslint-disable-line react-hooks/exhaustive-deps

  const toggleAdmin = async () => {
    setBusy(true)
    try { await adminSetUserAdmin(userId, !detail.user.is_admin); await load() } finally { setBusy(false) }
  }
  const toggleStatus = async () => {
    setBusy(true)
    try { await adminSetUserStatus(userId, detail.user.account_status !== 'active'); await load() } finally { setBusy(false) }
  }

  return (
    <div className="admin-drawer-overlay" onClick={onClose}>
      <div className="admin-drawer" onClick={(e) => e.stopPropagation()}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <h3 style={{ margin: 0 }}>User Detail</h3>
          <button className="theme-toggle" onClick={onClose} style={{ width: 28, height: 28 }}><IconX width={14} height={14} /></button>
        </div>

        {error && <div className="error-box">{error}</div>}
        {!detail && !error && <IconLoader width={22} height={22} />}

        {detail && (
          <>
            <h2 style={{ marginBottom: 2 }}>
              {[detail.user.first_name, detail.user.last_name].filter(Boolean).join(' ') || detail.user.email}
            </h2>
            <div className="hint" style={{ marginTop: 0 }}>{detail.user.email}</div>

            <div className="admin-detail-grid">
              <Field label="Mobile" value={`${detail.user.mobile_country_code || ''} ${detail.user.mobile_number || '—'}`} />
              <Field label="Organization" value={detail.user.organization_name} />
              <Field label="Job Title" value={detail.user.job_title} />
              <Field label="Location" value={[detail.user.city, detail.user.state, detail.user.country].filter(Boolean).join(', ')} />
              <Field label="Registered" value={fmt(detail.user.registration_date)} />
              <Field label="Last Login" value={fmt(detail.user.last_login)} />
              <Field label="Login Count" value={detail.user.login_count} />
              <Field label="Plan" value={`${detail.user.plan} · ${detail.job_count} jobs`} />
              <Field label="Total Sessions" value={detail.user.total_sessions} />
              <Field label="Total Page Views" value={detail.user.total_page_views} />
              <Field label="Last Activity" value={fmt(detail.user.last_activity)} />
              <Field label="Latest IP" value={detail.user.ip_address} />
              <Field label="Browser / OS" value={[detail.user.browser, detail.user.os].filter(Boolean).join(' / ')} />
              <Field label="Device Type" value={detail.user.device_type} />
              <Field label="Referrer Source" value={detail.user.referrer_source} />
              <Field label="UTM" value={[detail.user.utm_source, detail.user.utm_medium, detail.user.utm_campaign].filter(Boolean).join(' / ')} />
            </div>

            <div className="actions-row">
              <button className="btn btn-secondary" disabled={busy} onClick={toggleStatus}>
                {detail.user.account_status === 'active' ? 'Disable account' : 'Re-enable account'}
              </button>
              <button className="btn btn-secondary" disabled={busy} onClick={toggleAdmin}>
                {detail.user.is_admin ? 'Revoke admin' : 'Make admin'}
              </button>
            </div>

            <div className="admin-section-title">Recent Logins</div>
            {detail.recent_logins.length === 0 && <div className="hint">No login history yet.</div>}
            {detail.recent_logins.map((l, i) => (
              <div key={i} className="hint" style={{ marginBottom: 4 }}>
                {fmt(l.occurred_at)} · {l.method} · {l.browser || '—'} / {l.os || '—'} ({l.device_type || '—'}) · {l.ip_address || '—'}
              </div>
            ))}

            <div className="admin-section-title">Recent Activity</div>
            {detail.recent_activity.length === 0 && <div className="hint">No tracked activity yet.</div>}
            {detail.recent_activity.map((a, i) => (
              <div key={i} className="hint" style={{ marginBottom: 4 }}>
                {fmt(a.occurred_at)} · <strong>{a.event_type}</strong>
                {a.event_data && Object.keys(a.event_data).length > 0 && ` · ${JSON.stringify(a.event_data)}`}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  )
}

function Field({ label, value }) {
  return (
    <div>
      <dt style={{ display: 'block' }}>{label}</dt>
      <dd>{value || '—'}</dd>
    </div>
  )
}

function fmt(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}
