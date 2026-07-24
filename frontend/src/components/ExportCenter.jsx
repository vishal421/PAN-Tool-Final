import React, { useEffect, useState } from 'react'
import { exportPreview, exportDownloadPath, excelExportPath, downloadPath, triggerDownload } from '../api'

const SECTIONS = [
  { key: 'addresses', label: 'Address Objects' },
  { key: 'address_groups', label: 'Address Groups' },
  { key: 'services', label: 'Services' },
  { key: 'service_groups', label: 'Service Groups' },
  { key: 'interfaces', label: 'Interfaces' },
  { key: 'zones', label: 'Zones' },
  { key: 'virtual_routers', label: 'Virtual Routers' },
  { key: 'routes', label: 'Static Routes' },
  { key: 'nat_rules', label: 'NAT Policies' },
  { key: 'security_rules', label: 'Security Policies' },
]

const STORAGE_KEY = 'fwc:lastExportSections'

export default function ExportCenter({ jobId, jobStatus }) {
  const [selected, setSelected] = useState(() => {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
      if (Array.isArray(saved) && saved.length) return new Set(saved)
    } catch { /* ignore malformed storage */ }
    return new Set(SECTIONS.map((s) => s.key)) // default: everything
  })
  const [preview, setPreview] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [filter, setFilter] = useState('')
  const [downloadError, setDownloadError] = useState(null)

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify([...selected]))
  }, [selected])

  const allSelected = selected.size === SECTIONS.length
  const noneSelected = selected.size === 0

  const toggle = (key) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key); else next.add(key)
      return next
    })
  }

  const selectAll = () => setSelected(new Set(SECTIONS.map((s) => s.key)))
  const deselectAll = () => setSelected(new Set())

  const sectionsParam = allSelected || noneSelected ? null : [...selected]

  const runPreview = async () => {
    setLoading(true)
    setError(null)
    try {
      const resp = await exportPreview(jobId, sectionsParam)
      setPreview(resp)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const copyToClipboard = () => {
    if (preview?.cli) navigator.clipboard.writeText(preview.cli)
  }

  const download = async (path, filename) => {
    setDownloadError(null)
    try {
      await triggerDownload(path, filename)
    } catch (e) {
      setDownloadError(e.message)
    }
  }

  const displayedLines = preview
    ? preview.cli.split('\n').filter((l) => !filter.trim() || l.toLowerCase().includes(filter.trim().toLowerCase()))
    : []

  return (
    <div className="card">
      <h2>Selective Export</h2>
      <p className="hint">Choose exactly which sections to generate as Palo Alto CLI. Your last selection is remembered.</p>

      <div className="actions-row" style={{ justifyContent: 'flex-start', marginBottom: 12 }}>
        <button className="btn btn-secondary" onClick={selectAll}>Select All</button>
        <button className="btn btn-secondary" onClick={deselectAll}>Deselect All</button>
      </div>

      <div className="export-checklist">
        {SECTIONS.map((s) => (
          <label key={s.key} className="export-check-item">
            <input type="checkbox" checked={selected.has(s.key)} onChange={() => toggle(s.key)} />
            {s.label}
          </label>
        ))}
      </div>

      <div className="actions-row" style={{ justifyContent: 'flex-start', marginTop: 16 }}>
        <button className="btn btn-primary" onClick={runPreview} disabled={loading}>
          {loading ? 'Generating…' : 'Generate Preview'}
        </button>
        {preview && (
          <button
            className="btn btn-secondary"
            onClick={() => download(exportDownloadPath(jobId, sectionsParam), 'paloalto_selected.txt')}
          >
            Download CLI (.txt)
          </button>
        )}
      </div>

      {error && <div className="error-box">{error}</div>}

      {preview && (
        <div style={{ marginTop: 20 }}>
          <div className="actions-row" style={{ justifyContent: 'space-between' }}>
            <div className="hint">
              {preview.command_count} command{preview.command_count === 1 ? '' : 's'} across {preview.sections.length} section{preview.sections.length === 1 ? '' : 's'}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                className="grid-search"
                placeholder="Filter preview lines…"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              />
              <button className="btn btn-secondary" onClick={copyToClipboard}>Copy</button>
            </div>
          </div>
          <pre className="cli-preview">{displayedLines.join('\n')}</pre>
        </div>
      )}

      <div className="divider" />

      <h2>Other Formats</h2>
      <p className="hint">These export the full configuration summary (not section-filtered).</p>
      {downloadError && <div className="error-box">{downloadError}</div>}
      <div className="actions-row" style={{ justifyContent: 'flex-start' }}>
        <button className="btn btn-secondary" onClick={() => download(excelExportPath(jobId), 'configuration_summary.xlsx')}>
          Excel (.xlsx)
        </button>
        <button
          className={`btn btn-secondary ${jobStatus !== 'completed' ? 'btn-disabled' : ''}`}
          onClick={() => jobStatus === 'completed' && download(downloadPath(jobId, 'csv'), 'objects_summary.csv')}
          title={jobStatus !== 'completed' ? 'Available after completing Interface Mapping' : undefined}
        >
          CSV
        </button>
        <button
          className={`btn btn-secondary ${jobStatus !== 'completed' ? 'btn-disabled' : ''}`}
          onClick={() => jobStatus === 'completed' && download(downloadPath(jobId, 'json'), 'normalized_config.json')}
          title={jobStatus !== 'completed' ? 'Available after completing Interface Mapping' : undefined}
        >
          JSON
        </button>
      </div>
    </div>
  )
}
