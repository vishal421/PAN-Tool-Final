import React, { useEffect, useRef, useState } from 'react'
import { getObjects, saveObjects } from '../api'
import { GRID_CONFIGS, rowToDisplay, rowToPayload } from '../gridConfigs'
import { SkeletonTable } from './Skeleton'
import { useConfirmDialog } from './useConfirmDialog'
import { useToast } from './ToastProvider'
import { IconInbox } from './Icons'
import Combobox from './Combobox'

const AUTOSAVE_DELAY_MS = 900

export default function EditableGrid({ jobId, category, dynamicOptions, issues, focusName, onFocusHandled, onIssuesUpdated, onStatsUpdated, onSaved }) {
  const config = GRID_CONFIGS[category]
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(null)
  const [saveState, setSaveState] = useState('idle') // idle | saving | saved | error
  const [saveError, setSaveError] = useState(null)
  const [filter, setFilter] = useState('')
  const [sortKey, setSortKey] = useState(null)
  const [sortDir, setSortDir] = useState(1)
  const [selected, setSelected] = useState(() => new Set())
  const [bulkField, setBulkField] = useState(null)
  const [bulkValue, setBulkValue] = useState('')
  const rowRefs = useRef({})

  const debounceRef = useRef(null)
  const skipNextAutosave = useRef(true) // don't autosave on the initial load
  const { confirm, ConfirmDialogElement } = useConfirmDialog()
  const showToast = useToast()

  const bulkEditableColumns = config.columns.filter((c) => c.bulkEditable)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setLoadError(null)
    skipNextAutosave.current = true
    getObjects(jobId, category)
      .then((resp) => {
        if (cancelled) return
        setRows(resp.rows.map(rowToDisplay))
        setSelected(new Set())
        setSaveState('idle')
      })
      .catch((e) => !cancelled && setLoadError(e.message))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [jobId, category])

  const scheduleAutosave = (nextRows) => {
    if (skipNextAutosave.current) { skipNextAutosave.current = false; return }
    setSaveState('saving')
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => doSave(nextRows), AUTOSAVE_DELAY_MS)
  }

  const doSave = async (rowsToSave) => {
    try {
      const payload = rowsToSave.map(rowToPayload)
      const resp = await saveObjects(jobId, category, payload)
      setSaveState('saved')
      setSaveError(null)
      onIssuesUpdated?.(resp.issues)
      onStatsUpdated?.(resp.stats)
      onSaved?.(category, resp.rows)
    } catch (e) {
      setSaveState('error')
      setSaveError(e.message)
    }
  }

  const retrySave = () => doSave(rows)

  const updateCell = (rowIdx, key, value) => {
    setRows((prev) => {
      const next = prev.slice()
      next[rowIdx] = { ...next[rowIdx], [key]: value }
      scheduleAutosave(next)
      return next
    })
  }

  const addRow = () => {
    setRows((prev) => {
      const next = [...prev, rowToDisplay(config.newRow())]
      scheduleAutosave(next)
      return next
    })
  }

  const deleteRow = (rowIdx) => {
    setRows((prev) => {
      const next = prev.filter((_, i) => i !== rowIdx)
      scheduleAutosave(next)
      return next
    })
    setSelected((prev) => {
      const next = new Set(prev)
      next.delete(rowIdx)
      return next
    })
  }

  const deleteSelected = async () => {
    if (selected.size === 0) return
    const ok = await confirm(`Delete ${selected.size} selected row(s)?`, { confirmLabel: 'Delete Rows' })
    if (!ok) return
    setRows((prev) => {
      const next = prev.filter((_, i) => !selected.has(i))
      scheduleAutosave(next)
      return next
    })
    setSelected(new Set())
    showToast(`Deleted ${selected.size} row(s).`, 'success')
  }

  const applyBulkEdit = () => {
    if (!bulkField || selected.size === 0) return
    const col = bulkEditableColumns.find((c) => c.key === bulkField)
    let value = bulkValue
    if (col?.type === 'checkbox') value = bulkValue === 'true'
    setRows((prev) => {
      const next = prev.map((row, i) => (selected.has(i) ? { ...row, [bulkField]: value } : row))
      scheduleAutosave(next)
      return next
    })
  }

  const toggleSort = (key) => {
    if (sortKey === key) {
      setSortDir((d) => -d)
    } else {
      setSortKey(key)
      setSortDir(1)
    }
  }

  const filterText = filter.trim().toLowerCase()
  const visibleIndices = rows
    .map((row, idx) => ({ row, idx }))
    .filter(({ row }) => {
      if (!filterText) return true
      return Object.values(row).some((v) => String(v ?? '').toLowerCase().includes(filterText))
    })

  if (sortKey) {
    visibleIndices.sort((a, b) => {
      const av = String(a.row[sortKey] ?? '').toLowerCase()
      const bv = String(b.row[sortKey] ?? '').toLowerCase()
      return av < bv ? -sortDir : av > bv ? sortDir : 0
    })
  }

  // Issues are matched to rows by object name (the "name" column, which is
  // what the backend's ConversionIssue.object_name refers to). A row can
  // carry more than one issue; the worst severity present drives its style.
  const issuesByRowName = {}
  for (const iss of issues || []) {
    if (!iss.object_name) continue
    (issuesByRowName[iss.object_name] = issuesByRowName[iss.object_name] || []).push(iss)
  }
  const errorCount = (issues || []).filter((i) => i.severity === 'error').length
  const warningCount = (issues || []).filter((i) => i.severity === 'warning').length

  useEffect(() => {
    if (!focusName || loading) return
    const row = rows.find((r) => r.name === focusName)
    if (!row) return
    const idx = rows.indexOf(row)
    const el = rowRefs.current[idx]
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' })
      el.classList.add('row-flash')
      setTimeout(() => el.classList.remove('row-flash'), 2000)
    }
    onFocusHandled?.()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [focusName, loading, rows.length])

  return (
    <div className="card grid-card">
      <div className="grid-toolbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <h2 style={{ margin: 0 }}>{config.title}</h2>
          {(errorCount > 0 || warningCount > 0) && (
            <span className="hint" style={{ display: 'flex', gap: 6 }}>
              {errorCount > 0 && <span className="chip-btn active" style={{ cursor: 'default' }}>⛔ {errorCount} error{errorCount === 1 ? '' : 's'}</span>}
              {warningCount > 0 && <span className="chip-btn" style={{ cursor: 'default' }}>⚠️ {warningCount} warning{warningCount === 1 ? '' : 's'}</span>}
            </span>
          )}
        </div>
        <div className="grid-toolbar-actions">
          <input
            className="grid-search"
            placeholder={`Search ${config.title.toLowerCase()}…`}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <button className="btn btn-secondary" onClick={deleteSelected} disabled={selected.size === 0}>
            Delete Selected ({selected.size})
          </button>
          <button className="btn btn-primary" onClick={addRow}>+ Add Row</button>
          <SaveIndicator state={saveState} error={saveError} onRetry={retrySave} />
        </div>
      </div>

      {config.hint && <p className="hint" style={{ marginTop: -6 }}>{config.hint}</p>}

      {bulkEditableColumns.length > 0 && (
        <div className="bulk-edit-bar">
          <span className="hint">Bulk edit {selected.size} selected row{selected.size === 1 ? '' : 's'}:</span>
          <select className="grid-input" value={bulkField || ''} onChange={(e) => { setBulkField(e.target.value || null); setBulkValue('') }} style={{ width: 200 }}>
            <option value="">Choose a field…</option>
            {bulkEditableColumns.map((c) => <option key={c.key} value={c.key}>{c.label}</option>)}
          </select>
          {bulkField && (() => {
            const col = bulkEditableColumns.find((c) => c.key === bulkField)
            const opts = col.dynamicOptionsKey ? (dynamicOptions?.[col.dynamicOptionsKey] || []) : (col.options || [])
            if (col.type === 'checkbox') {
              return (
                <select className="grid-input" value={bulkValue} onChange={(e) => setBulkValue(e.target.value)} style={{ width: 120 }}>
                  <option value="">Choose…</option>
                  <option value="true">True</option>
                  <option value="false">False</option>
                </select>
              )
            }
            return (
              <select className="grid-input" value={bulkValue} onChange={(e) => setBulkValue(e.target.value)} style={{ width: 200 }}>
                <option value="">Choose a value…</option>
                {col.allowBlank && <option value="">(none)</option>}
                {opts.map((o) => <option key={o} value={o}>{o}</option>)}
              </select>
            )
          })()}
          <button className="btn btn-primary" onClick={applyBulkEdit} disabled={!bulkField || selected.size === 0}>
            Apply to {selected.size} selected
          </button>
        </div>
      )}

      {loading && <SkeletonTable rows={5} cols={config.columns.length} />}
      {loadError && <div className="error-box">{loadError}</div>}
      {ConfirmDialogElement}

      {!loading && !loadError && (
        <div className="grid-scroll">
          <table className="editable-grid">
            <thead>
              <tr>
                <th style={{ width: 32 }}></th>
                <th style={{ width: 24 }}></th>
                {config.columns.map((col) => (
                  <th key={col.key} style={{ minWidth: col.width }} onClick={() => toggleSort(col.key)} className="sortable-th">
                    {col.label}{sortKey === col.key ? (sortDir === 1 ? ' ▲' : ' ▼') : ''}
                  </th>
                ))}
                <th style={{ width: 60 }}></th>
              </tr>
            </thead>
            <tbody>
              {visibleIndices.map(({ row, idx }) => {
                const rowIssues = issuesByRowName[row.name] || []
                const worstSeverity = rowIssues.some((i) => i.severity === 'error')
                  ? 'error'
                  : rowIssues.some((i) => i.severity === 'warning') ? 'warning' : null
                const rowClass = worstSeverity === 'error' ? 'row-has-error' : worstSeverity === 'warning' ? 'row-has-warning' : ''
                return (
                  <tr key={idx} ref={(el) => { rowRefs.current[idx] = el }} className={rowClass}>
                    <td>
                      <input
                        type="checkbox"
                        checked={selected.has(idx)}
                        onChange={(e) => {
                          setSelected((prev) => {
                            const next = new Set(prev)
                            if (e.target.checked) next.add(idx); else next.delete(idx)
                            return next
                          })
                        }}
                      />
                    </td>
                    {worstSeverity && (
                      <td style={{ width: 24 }}>
                        <span
                          className="row-error-icon"
                          title={rowIssues.map((i) => i.message).join('\n')}
                        >
                          {worstSeverity === 'error' ? '⛔' : '⚠️'}
                        </span>
                      </td>
                    )}
                    {!worstSeverity && <td style={{ width: 24 }} />}
                    {config.columns.map((col) => (
                      <td key={col.key}>
                        <Cell
                          col={col}
                          value={row[col.key]}
                          row={row}
                          dynamicOptions={dynamicOptions}
                          rowIdx={idx}
                          onChange={(v) => updateCell(idx, col.key, v)}
                        />
                      </td>
                    ))}
                    <td>
                      <button className="btn-icon" title="Delete row" onClick={() => deleteRow(idx)}>✕</button>
                    </td>
                  </tr>
                )
              })}
              {visibleIndices.length === 0 && (
                <tr><td colSpan={config.columns.length + 3}>
                  <div className="empty-state" style={{ padding: '28px 12px' }}>
                    <IconInbox width={30} height={30} />
                    <span className="hint" style={{ margin: 0 }}>
                      {filterText ? 'No rows match your search.' : 'No rows yet - click "+ Add Row" to create one.'}
                    </span>
                  </div>
                </td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
      <div className="hint" style={{ marginTop: 8 }}>
        {rows.length} row{rows.length === 1 ? '' : 's'}{filterText ? ` · ${visibleIndices.length} shown` : ''} — edits save automatically.
      </div>
    </div>
  )
}

function MultiSelectCell({ col, value, dynamicOptions, onChange }) {
  const [open, setOpen] = useState(false)
  const [customText, setCustomText] = useState('')
  const [search, setSearch] = useState('')
  const [pos, setPos] = useState({ top: 0, left: 0 })
  const btnRef = useRef(null)
  const panelRef = useRef(null)
  const searchRef = useRef(null)

  const selected = Array.isArray(value) ? value : (value ? [value] : [])
  const baseOptions = col.dynamicOptionsKey ? (dynamicOptions?.[col.dynamicOptionsKey] || []) : (col.options || [])
  // Values already on the row but not (yet) in the known-objects list still
  // need to show up as a checked, removable entry - e.g. "any", or a zone
  // typed before it existed as a real object. In strict mode there's no
  // free-text escape hatch, but a value saved before an object was deleted
  // still needs to be visible/removable, so it's included here too.
  const restOptions = Array.from(new Set([...baseOptions, ...selected]))
    .filter((o) => o.toLowerCase() !== 'any')
    .sort((a, b) => a.localeCompare(b))
  // Security Policy fields (Source/Dest Zone & Address, Service, Application)
  // always offer "any" as a first-class, always-available choice - pinned at
  // the top rather than sorted in alphabetically, matching how it's used on
  // real Palo Alto policies.
  const allOptions = col.includeAny ? ['any', ...restOptions] : restOptions
  const visibleOptions = col.searchable && search.trim()
    ? allOptions.filter((o) => o.toLowerCase().includes(search.trim().toLowerCase()))
    : allOptions

  useEffect(() => {
    if (!open) return
    const handleOutside = (e) => {
      if (panelRef.current?.contains(e.target) || btnRef.current?.contains(e.target)) return
      setOpen(false)
    }
    const handleKey = (e) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('mousedown', handleOutside)
    document.addEventListener('keydown', handleKey)
    return () => {
      document.removeEventListener('mousedown', handleOutside)
      document.removeEventListener('keydown', handleKey)
    }
  }, [open])

  const openPanel = () => {
    const rect = btnRef.current.getBoundingClientRect()
    const panelWidth = 240
    setPos({
      top: rect.bottom + 4,
      left: Math.min(rect.left, window.innerWidth - panelWidth - 12),
    })
    setSearch('')
    setOpen(true)
    // Focus the search box once the panel is in the DOM.
    if (col.searchable) setTimeout(() => searchRef.current?.focus(), 0)
  }

  // Prevents duplicate selections by construction: toggling an already-
  // selected option only ever removes it, never adds a second copy. New
  // selections are prepended so they show up at the top of the chip list.
  const toggle = (opt) => {
    onChange(selected.includes(opt) ? selected.filter((s) => s !== opt) : [opt, ...selected])
  }

  const removeChip = (opt, e) => {
    e.stopPropagation()
    onChange(selected.filter((s) => s !== opt))
  }

  const addCustom = () => {
    const v = customText.trim()
    if (v && !selected.includes(v)) onChange([v, ...selected])
    setCustomText('')
  }

  return (
    <>
      <button
        type="button"
        className="multiselect-trigger"
        ref={btnRef}
        onClick={() => (open ? setOpen(false) : openPanel())}
      >
        {selected.length === 0 ? (
          <span className="multiselect-placeholder">— select —</span>
        ) : (
          <span className="multiselect-chips">
            {selected.map((s) => (
              <span key={s} className="ms-chip">
                {s}
                <span
                  className="ms-chip-remove"
                  role="button"
                  tabIndex={0}
                  title={`Remove ${s}`}
                  onClick={(e) => removeChip(s, e)}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); removeChip(s, e) } }}
                >
                  ×
                </span>
              </span>
            ))}
          </span>
        )}
        <span className="multiselect-caret">▾</span>
      </button>
      {open && (
        <div className="multiselect-panel" ref={panelRef} style={{ top: pos.top, left: pos.left }}>
          {col.searchable && (
            <input
              ref={searchRef}
              className="grid-input"
              type="text"
              placeholder={col.placeholder || 'Search…'}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              style={{ margin: '6px 8px 4px', width: 'calc(100% - 16px)' }}
            />
          )}
          <div className="multiselect-options">
            {allOptions.length === 0 && (
              <div className="hint" style={{ padding: '8px 10px' }}>
                {col.strict ? 'No objects available yet - add one on its own tab first.' : 'No objects yet — add a value below.'}
              </div>
            )}
            {allOptions.length > 0 && visibleOptions.length === 0 && (
              <div className="hint" style={{ padding: '8px 10px' }}>No matches.</div>
            )}
            {visibleOptions.map((o) => (
              <label key={o} className="multiselect-option">
                <input type="checkbox" checked={selected.includes(o)} onChange={() => toggle(o)} />
                <span>{o}</span>
              </label>
            ))}
          </div>
          {!col.strict && (
            <div className="multiselect-add">
              <input
                className="grid-input"
                type="text"
                placeholder="Add value (e.g. any)…"
                value={customText}
                onChange={(e) => setCustomText(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); addCustom() } }}
              />
              <button type="button" className="btn btn-secondary" onClick={addCustom}>Add</button>
            </div>
          )}
        </div>
      )}
    </>
  )
}

function Cell({ col, value, row, dynamicOptions, rowIdx, onChange }) {
  if (col.readonly) {
    const display = col.compute ? col.compute(row, dynamicOptions) : value
    return <span className="grid-readonly">{display ?? ''}</span>
  }

  if (col.type === 'select') {
    const opts = col.dynamicOptionsKey ? (dynamicOptions?.[col.dynamicOptionsKey] || []) : (col.options || [])
    return (
      <select className="grid-input" value={value ?? ''} onChange={(e) => onChange(e.target.value)}>
        {col.allowBlank && <option value="">—</option>}
        {opts.map((o) => <option key={o} value={o}>{o}</option>)}
      </select>
    )
  }

  if (col.type === 'combo') {
    // Predefined options via a dropdown, but still lets the user type a
    // custom value (e.g. a subinterface like "ethernet1/5.100").
    const opts = col.dynamicOptionsKey ? (dynamicOptions?.[col.dynamicOptionsKey] || []) : (col.options || [])
    return (
      <Combobox options={opts} value={value ?? ''} onChange={onChange} placeholder={col.placeholder} />
    )
  }

  if (col.type === 'multiselect') {
    return <MultiSelectCell col={col} value={value} dynamicOptions={dynamicOptions} onChange={onChange} />
  }

  if (col.type === 'checkbox') {
    return <input type="checkbox" checked={!!value} onChange={(e) => onChange(e.target.checked)} />
  }

  if (col.type === 'number') {
    return (
      <input
        className="grid-input"
        type="number"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
      />
    )
  }

  // 'text' and 'list' (list fields are edited as a plain comma-separated string)
  return (
    <input
      className="grid-input"
      type="text"
      value={value ?? ''}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

function SaveIndicator({ state, error, onRetry }) {
  if (state === 'idle') return null
  if (state === 'saving') return <span className="save-pill saving">Saving…</span>
  if (state === 'saved') return <span className="save-pill saved">Saved ✓</span>
  return (
    <span className="save-pill error" title={error}>
      Unsaved Changes — <button className="link-btn" onClick={onRetry}>Retry Save</button>
    </span>
  )
}
