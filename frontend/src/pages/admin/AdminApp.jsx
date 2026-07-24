import React, { useEffect, useState } from 'react'
import { IconLogOut, IconLoader } from '../../components/Icons'
import OverviewTab from './OverviewTab'
import UsersTab from './UsersTab'
import SeoTab from './SeoTab'
import './admin.css'

const TABS = [
  { key: 'overview', label: 'Overview' },
  { key: 'users', label: 'Users' },
  { key: 'seo', label: 'SEO Analytics' },
]

/**
 * Completely private internal dashboard - never linked from the product's
 * own navigation. Reachable only at the private path set by VITE_ADMIN_PATH
 * (see App.jsx), requires an authenticated is_admin account (see backend
 * app/auth/core.py::require_admin), and keeps search engines out via this
 * noindex tag - deliberately NOT listed in robots.txt, since publishing a
 * "hidden" path there is exactly how it stops being hidden.
 */
export default function AdminApp({ currentUser, onLogout }) {
  const [tab, setTab] = useState('overview')

  useEffect(() => {
    const meta = document.createElement('meta')
    meta.name = 'robots'
    meta.content = 'noindex, nofollow'
    document.head.appendChild(meta)
    const prevTitle = document.title
    document.title = 'Admin Dashboard'
    return () => {
      document.head.removeChild(meta)
      document.title = prevTitle
    }
  }, [])

  if (!currentUser.is_admin) {
    return (
      <div className="auth-shell">
        <div className="card auth-card">
          <h2>Not authorized</h2>
          <p className="hint">This account doesn't have admin access.</p>
          <button className="btn btn-secondary" onClick={() => { window.location.href = '/' }}>
            Back to the app
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="admin-shell">
      <aside className="admin-sidebar">
        <div className="admin-brand">Admin</div>
        <nav className="admin-nav">
          {TABS.map((t) => (
            <button
              key={t.key}
              className={`admin-nav-item ${tab === t.key ? 'is-active' : ''}`}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </nav>
        <div className="admin-sidebar-footer">
          <div className="admin-user-chip">{currentUser.email}</div>
          <button className="btn btn-secondary" onClick={onLogout} style={{ width: '100%' }}>
            <IconLogOut width={14} height={14} /> Log out
          </button>
        </div>
      </aside>
      <main className="admin-main">
        {tab === 'overview' && <OverviewTab />}
        {tab === 'users' && <UsersTab />}
        {tab === 'seo' && <SeoTab />}
      </main>
    </div>
  )
}

export function AdminLoading() {
  return <div className="auth-shell"><IconLoader width={28} height={28} /></div>
}
