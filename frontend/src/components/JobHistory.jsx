import React, { useState } from 'react'
import { SkeletonTable } from './Skeleton'
import { IconPlus, IconInbox } from './Icons'

const STATUS_LABEL = {
  parsing: 'Parsing…',
  awaiting_mapping: 'Awaiting interface mapping',
  completed: 'Completed',
  failed: 'Failed',
}

function formatDate(iso) {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

export default function JobHistory({
  jobs, loading, error, onStartNew, onResume, onRefresh, onDelete, confirm,
  title = 'Firewall Config Converter',
  hint = 'Start a new conversion, or pick up a saved job where you left off.',
}) {
  const [deletingId, setDeletingId] = useState(null)
  const [deleteError, setDeleteError] = useState(null)

  const handleDelete = async (job) => {
    const ok = confirm
      ? await confirm(`Delete "${job.job_name || job.original_filename}"? This can't be undone.`, { confirmLabel: 'Delete Job' })
      : window.confirm(`Delete "${job.job_name || job.original_filename}"? This can't be undone.`)
    if (!ok) return
    setDeletingId(job.id)
    setDeleteError(null)
    try {
      await onDelete(job)
    } catch (e) {
      setDeleteError(e.message)
    } finally {
      setDeletingId(null)
    }
  }

  return (
    <div className="card">
      <h2>{title}</h2>
      <p className="hint">{hint}</p>

      <div className="actions-row" style={{ justifyContent: 'flex-start', marginBottom: 24 }}>
        {onStartNew && (
          <button className="btn btn-primary" onClick={onStartNew}>
            <IconPlus width={14} height={14} /> New Conversion
          </button>
        )}
        <button className="btn btn-secondary" onClick={onRefresh} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </div>

      {error && <div className="error-box">{error}</div>}
      {deleteError && <div className="error-box">{deleteError}</div>}

      {loading && jobs.length === 0 && <SkeletonTable rows={4} cols={6} />}

      {!loading && jobs.length === 0 && !error && (
        <div className="empty-state">
          <IconInbox width={40} height={40} />
          <div className="empty-state-title">No saved jobs yet</div>
          <p className="hint" style={{ margin: 0 }}>Start a new conversion above to see it appear here.</p>
        </div>
      )}

      {jobs.length > 0 && (
        <div className="summary-table-wrap">
        <table className="summary-table">
          <thead>
            <tr>
              <th>Job Name</th>
              <th>Vendor</th>
              <th>File</th>
              <th>Status</th>
              <th>Created</th>
              <th style={{ width: 90 }}></th>
              <th style={{ width: 90 }}></th>
            </tr>
          </thead>
          <tbody>
            {jobs.map((job) => (
              <tr key={job.id}>
                <td>{job.job_name || <span style={{ color: 'var(--text-secondary)' }}>(unnamed)</span>}</td>
                <td>{job.vendor}</td>
                <td>{job.original_filename}</td>
                <td>
                  <span className="status-line">
                    <span className={`dot ${job.status === 'completed' ? 'completed' : job.status === 'failed' ? 'failed' : 'parsing'}`} />
                    {STATUS_LABEL[job.status] || job.status}
                  </span>
                </td>
                <td>{formatDate(job.created_at)}</td>
                <td>
                  <button className="btn btn-secondary" onClick={() => onResume(job)}>
                    {job.status === 'completed' ? 'View' : job.status === 'failed' ? 'Details' : 'Resume'}
                  </button>
                </td>
                <td>
                  <button
                    className="btn btn-danger"
                    onClick={() => handleDelete(job)}
                    disabled={deletingId === job.id}
                  >
                    {deletingId === job.id ? '…' : 'Delete'}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        </div>
      )}
    </div>
  )
}
