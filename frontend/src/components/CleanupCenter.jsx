import React, { useEffect, useState } from 'react'
import { getCleanup, deleteCleanupObjects, cleanupReportPath, triggerDownload } from '../api'
import { useConfirmDialog } from './useConfirmDialog'
import { useToast } from './ToastProvider'
import { IconCheckCircle } from './Icons'

const CATEGORY_META = {
  unused_address: { icon: '⚠️', cls: 'cleanup-icon-warning', label: 'Unused Address Object' },
  unused_address_group: { icon: '⚠️', cls: 'cleanup-icon-warning', label: 'Unused Address Group' },
  unused_service: { icon: '⚠️', cls: 'cleanup-icon-warning', label: 'Unused Service Object' },
  unused_service_group: { icon: '⚠️', cls: 'cleanup-icon-warning', label: 'Unused Service Group' },
  empty_address_group: { icon: '⛔', cls: 'cleanup-icon-error', label: 'Empty Address Group' },
  empty_service_group: { icon: '⛔', cls: 'cleanup-icon-error', label: 'Empty Service Group' },
  duplicate_address: { icon: 'ℹ️', cls: 'cleanup-icon-info', label: 'Duplicate-Value Address' },
  duplicate_service: { icon: 'ℹ️', cls: 'cleanup-icon-info', label: 'Duplicate-Value Service' },
}

export default function CleanupCenter({ jobId, onStatsUpdated }) {
  const [findings, setFindings] = useState([])
  const [counts, setCounts] = useState({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('')
  const [ignored, setIgnored] = useState(() => new Set())
  const [selected, setSelected] = useState(() => new Set())
  const [busy, setBusy] = useState(false)
  const { confirm, ConfirmDialogElement } = useConfirmDialog()
  const showToast = useToast()

  const reload = () => {
    setLoading(true)
    setError(null)
    getCleanup(jobId)
      .then((resp) => { setFindings(resp.findings); setCounts(resp.counts) })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(reload, [jobId])

  const key = (f) => `${f.object_type}:${f.name}:${f.category}`

  const filterText = filter.trim().toLowerCase()
  const visible = findings.filter((f) => {
    if (ignored.has(key(f))) return false
    if (!filterText) return true
    return `${f.name} ${f.message} ${f.category}`.toLowerCase().includes(filterText)
  })

  const toggleSelect = (f) => {
    const k = key(f)
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(k)) next.delete(k); else next.add(k)
      return next
    })
  }

  const ignoreSelected = () => {
    setIgnored((prev) => new Set([...prev, ...selected]))
    setSelected(new Set())
  }

  const deleteSelected = async () => {
    if (selected.size === 0) return
    // Only unused_* and empty_* findings are safely deletable via this
    // action (they all map to a real object_type/name); duplicate_*
    // findings are informational (merge candidates), not delete targets.
    const toDelete = visible.filter((f) => selected.has(key(f)) && !f.category.startsWith('duplicate_'))
    if (toDelete.length === 0) return
    const ok = await confirm(`Delete ${toDelete.length} object(s)? This can't be undone.`, { confirmLabel: 'Delete Objects' })
    if (!ok) return

    setBusy(true)
    setError(null)
    try {
      // Group by object_type since the API deletes one category at a time
      const byType = {}
      for (const f of toDelete) {
        (byType[f.object_type] = byType[f.object_type] || []).push(f.name)
      }
      let resp
      for (const [objectType, names] of Object.entries(byType)) {
        resp = await deleteCleanupObjects(jobId, objectType, names)
      }
      setFindings(resp.findings)
      setCounts(resp.counts)
      setSelected(new Set())
      onStatsUpdated?.()
      showToast(`Deleted ${toDelete.length} object(s).`, 'success')
    } catch (e) {
      setError(e.message)
      showToast(e.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const downloadReport = async () => {
    try {
      await triggerDownload(cleanupReportPath(jobId), 'cleanup_report.csv')
    } catch (e) {
      setError(e.message)
    }
  }

  const totalCount = Object.values(counts).reduce((a, b) => a + b, 0)

  return (
    <div className="card">
      {ConfirmDialogElement}
      <h2>Configuration Cleanup</h2>
      <p className="hint">
        Objects that look unused, empty, or duplicated - reviewed before export so the migrated
        configuration doesn't carry over years of accumulated cruft.
      </p>

      <div className="actions-row" style={{ justifyContent: 'flex-start', marginBottom: 14, flexWrap: 'wrap' }}>
        <input className="grid-search" placeholder="Search findings…" value={filter} onChange={(e) => setFilter(e.target.value)} />
        <button className="btn btn-secondary" onClick={reload} disabled={loading}>Refresh</button>
        <button className="btn btn-secondary" onClick={ignoreSelected} disabled={selected.size === 0}>
          Ignore Selected ({selected.size})
        </button>
        <button className="btn btn-danger" onClick={deleteSelected} disabled={selected.size === 0 || busy}>
          {busy ? 'Deleting…' : `Delete Selected (${selected.size})`}
        </button>
        <button className="btn btn-secondary" onClick={downloadReport}>Download Cleanup Report (CSV)</button>
      </div>

      {error && <div className="error-box">{error}</div>}
      {loading && <div className="hint">Checking…</div>}

      {!loading && (
        <>
          <div className="hint" style={{ marginBottom: 10 }}>
            {totalCount === 0 ? (
              <span style={{ display: 'flex', alignItems: 'center', gap: 6, color: 'var(--success)' }}>
                <IconCheckCircle width={16} height={16} /> No cleanup findings - this configuration looks tidy.
              </span>
            ) : `${totalCount} finding(s) across ${Object.keys(counts).length} categor${Object.keys(counts).length === 1 ? 'y' : 'ies'}.`}
          </div>

          {visible.length > 0 && (
            <div className="summary-table-wrap">
            <table className="summary-table">
              <thead>
                <tr>
                  <th style={{ width: 32 }}></th>
                  <th>Type</th>
                  <th>Object Type</th>
                  <th>Name</th>
                  <th>Details</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((f) => {
                  const meta = CATEGORY_META[f.category] || { icon: 'ℹ️', cls: 'cleanup-icon-info', label: f.category }
                  return (
                    <tr key={key(f)}>
                      <td>
                        <input type="checkbox" checked={selected.has(key(f))} onChange={() => toggleSelect(f)} />
                      </td>
                      <td><span className={meta.cls}>{meta.icon} {meta.label}</span></td>
                      <td>{f.object_type}</td>
                      <td>{f.name}</td>
                      <td>{f.message}</td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
            </div>
          )}
        </>
      )}
    </div>
  )
}
