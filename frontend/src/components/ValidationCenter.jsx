import React, { useEffect, useState } from 'react'
import { getValidation, getObjects, saveObjects } from '../api'
import { rowToDisplay, rowToPayload, OBJECT_TYPE_TO_CATEGORY } from '../gridConfigs'

const SEVERITY_ORDER = { error: 0, warning: 1, unsupported: 2, information: 3 }
const SEVERITY_ICON = { error: '⛔', warning: '⚠️', unsupported: 'ℹ️', information: '💡' }

function isRenameFixable(issue) {
  return /Invalid character|capped at|reserved word|^Duplicate/.test(issue.message)
}

export default function ValidationCenter({ jobId, onNavigateToGrid, onStatsUpdated, onIssuesUpdated }) {
  const [issues, setIssues] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [severityFilter, setSeverityFilter] = useState('all')

  const reload = () => {
    setLoading(true)
    setError(null)
    getValidation(jobId)
      .then((resp) => {
        setIssues(resp.issues)
        onStatsUpdated?.(resp.stats)
        onIssuesUpdated?.(resp.issues)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(reload, [jobId])

  const sorted = [...issues].sort((a, b) => (SEVERITY_ORDER[a.severity] ?? 9) - (SEVERITY_ORDER[b.severity] ?? 9))
  const filtered = severityFilter === 'all' ? sorted : sorted.filter((i) => i.severity === severityFilter)

  const counts = issues.reduce((acc, i) => { acc[i.severity] = (acc[i.severity] || 0) + 1; return acc }, {})

  return (
    <div className="card">
      <h2>Validation Center</h2>
      <p className="hint">
        Live check of the current configuration - re-runs every time you open this page or save an edit.
        Fixing a name here saves immediately; no need to re-upload.
      </p>

      <div className="actions-row" style={{ justifyContent: 'flex-start', gap: 8, marginBottom: 16 }}>
        {['all', 'error', 'warning', 'unsupported', 'information'].map((sev) => (
          <button
            key={sev}
            className={`chip-btn ${severityFilter === sev ? 'active' : ''}`}
            onClick={() => setSeverityFilter(sev)}
          >
            {sev === 'all' ? `All (${issues.length})` : `${SEVERITY_ICON[sev]} ${sev} (${counts[sev] || 0})`}
          </button>
        ))}
        <button className="btn btn-secondary" onClick={reload}>Refresh</button>
      </div>

      {loading && <div className="hint">Checking…</div>}
      {error && <div className="error-box">{error}</div>}

      {!loading && !error && filtered.length === 0 && (
        <div className="empty-table-note">
          {issues.length === 0 ? 'No issues found. This configuration looks clean.' : 'No issues match this filter.'}
        </div>
      )}

      {!loading && !error && filtered.length > 0 && (
        <div className="summary-table-wrap">
        <table className="summary-table">
          <thead>
            <tr>
              <th>Severity</th>
              <th>Object Type</th>
              <th>Object Name</th>
              <th>Message</th>
              <th>Fix</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((issue, i) => (
              <IssueRow
                key={i}
                jobId={jobId}
                issue={issue}
                onFixed={reload}
                onNavigateToGrid={onNavigateToGrid}
              />
            ))}
          </tbody>
        </table>
        </div>
      )}
    </div>
  )
}

function IssueRow({ jobId, issue, onFixed, onNavigateToGrid }) {
  const category = OBJECT_TYPE_TO_CATEGORY[issue.object_type]
  const [editing, setEditing] = useState(false)
  const [newName, setNewName] = useState(issue.object_name)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)

  const applyRename = async () => {
    if (!category) return
    setBusy(true)
    setErr(null)
    try {
      const { rows } = await getObjects(jobId, category)
      const idx = rows.findIndex((r) => r.name === issue.object_name)
      if (idx === -1) {
        setErr('Could not find that object anymore - it may have already been edited or deleted.')
        setBusy(false)
        return
      }
      const displayRows = rows.map(rowToDisplay)
      displayRows[idx] = { ...displayRows[idx], name: newName }
      await saveObjects(jobId, category, displayRows.map(rowToPayload))
      setEditing(false)
      onFixed()
    } catch (e) {
      setErr(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <tr>
      <td>{SEVERITY_ICON[issue.severity]} {issue.severity}</td>
      <td>{issue.object_type}</td>
      <td>{issue.object_name}</td>
      <td>
        {issue.message}
        {err && <div className="error-box" style={{ marginTop: 6 }}>{err}</div>}
      </td>
      <td>
        {isRenameFixable(issue) && category ? (
          editing ? (
            <div style={{ display: 'flex', gap: 6 }}>
              <input className="grid-input" value={newName} onChange={(e) => setNewName(e.target.value)} style={{ width: 140 }} />
              <button className="btn btn-primary" onClick={applyRename} disabled={busy}>{busy ? '…' : 'Apply'}</button>
              <button className="btn btn-secondary" onClick={() => setEditing(false)} disabled={busy}>Cancel</button>
            </div>
          ) : (
            <button className="btn btn-secondary" onClick={() => setEditing(true)}>Rename</button>
          )
        ) : category ? (
          <button className="btn btn-secondary" onClick={() => onNavigateToGrid?.(category, issue.object_name)}>
            Open {category.replace('_', ' ')}
          </button>
        ) : (
          <span className="hint">—</span>
        )}
      </td>
    </tr>
  )
}
