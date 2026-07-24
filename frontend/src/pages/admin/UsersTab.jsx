import React, { useEffect, useState } from 'react'
import { adminListUsers, adminUserExportPath, triggerDownload } from '../../api'
import { IconLoader, IconSearch } from '../../components/Icons'
import UserDetailDrawer from './UserDetailDrawer'

const PAGE_SIZE = 25

export default function UsersTab() {
  const [q, setQ] = useState('')
  const [plan, setPlan] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [data, setData] = useState(null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(true)
  const [selectedUserId, setSelectedUserId] = useState(null)

  const filters = { q, plan, status, page, page_size: PAGE_SIZE }

  useEffect(() => {
    setLoading(true)
    adminListUsers(filters)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, plan, status, page])

  const totalPages = data ? Math.max(1, Math.ceil(data.total / PAGE_SIZE)) : 1

  const exportFile = async (format) => {
    const { page: _p, page_size: _ps, ...exportFilters } = filters
    await triggerDownload(adminUserExportPath(format, exportFilters), `registered_users.${format}`)
  }

  return (
    <div>
      <h1 className="admin-h1">Registered Users</h1>

      <div className="admin-toolbar">
        <div style={{ position: 'relative' }}>
          <IconSearch width={14} height={14} style={{ position: 'absolute', left: 10, top: 10, opacity: 0.5 }} />
          <input
            className="grid-input"
            style={{ paddingLeft: 30, width: 240 }}
            placeholder="Search name, email, org…"
            value={q}
            onChange={(e) => { setPage(1); setQ(e.target.value) }}
          />
        </div>
        <select className="grid-input" value={plan} onChange={(e) => { setPage(1); setPlan(e.target.value) }}>
          <option value="">All plans</option>
          <option value="free">Free</option>
          <option value="pro">Pro</option>
        </select>
        <select className="grid-input" value={status} onChange={(e) => { setPage(1); setStatus(e.target.value) }}>
          <option value="">All statuses</option>
          <option value="active">Active</option>
          <option value="disabled">Disabled</option>
        </select>
        <div style={{ flex: 1 }} />
        <button className="btn btn-secondary" onClick={() => exportFile('csv')}>Export CSV</button>
        <button className="btn btn-secondary" onClick={() => exportFile('xlsx')}>Export Excel</button>
      </div>

      {error && <div className="error-box">{error}</div>}
      {loading && <IconLoader width={22} height={22} />}

      {data && !loading && (
        <>
          <div className="admin-table-wrap">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Name</th><th>Email</th><th>Mobile</th><th>Organization</th>
                  <th>City</th><th>Country</th><th>Registered</th><th>Last Login</th>
                  <th>Logins</th><th>Sessions</th><th>Page Views</th><th>Status</th>
                </tr>
              </thead>
              <tbody>
                {data.users.map((u) => (
                  <tr key={u.id} onClick={() => setSelectedUserId(u.id)}>
                    <td>{[u.first_name, u.last_name].filter(Boolean).join(' ') || '—'}</td>
                    <td>{u.email}</td>
                    <td>{u.mobile_country_code} {u.mobile_number}</td>
                    <td>{u.organization_name || '—'}</td>
                    <td>{u.city || '—'}</td>
                    <td>{u.country || '—'}</td>
                    <td>{formatDate(u.registration_date)}</td>
                    <td>{formatDate(u.last_login)}</td>
                    <td>{u.login_count}</td>
                    <td>{u.total_sessions}</td>
                    <td>{u.total_page_views}</td>
                    <td>
                      <span className={`admin-badge ${u.account_status}`}>{u.account_status}</span>
                      {u.is_admin && <span className="admin-badge admin" style={{ marginLeft: 4 }}>admin</span>}
                    </td>
                  </tr>
                ))}
                {data.users.length === 0 && (
                  <tr><td colSpan={12} style={{ textAlign: 'center', padding: 24 }}>No users match these filters.</td></tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="admin-pagination">
            <span>{data.total} total</span>
            <button className="btn btn-secondary" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>Prev</button>
            <span>Page {page} of {totalPages}</span>
            <button className="btn btn-secondary" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        </>
      )}

      {selectedUserId && (
        <UserDetailDrawer userId={selectedUserId} onClose={() => setSelectedUserId(null)} />
      )}
    </div>
  )
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}
