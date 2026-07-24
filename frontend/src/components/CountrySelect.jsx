import React, { useEffect, useMemo, useRef, useState } from 'react'
import { IconChevronDown } from './Icons'

// Renders each country as "India" (mode="country") or "India (+91)"
// (mode="dial") — plain text only, no flag icons.
export default function CountrySelect({ countries, value, onChange, mode = 'country', placeholder }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const rootRef = useRef(null)

  const selected = useMemo(
    () => countries.find((c) => (mode === 'country' ? c.iso2 === value : c.dial_code === value)),
    [countries, value, mode],
  )

  useEffect(() => {
    const onOutside = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [])

  const filtered = useMemo(() => {
    if (!query) return countries
    const q = query.toLowerCase()
    return countries.filter((c) => c.name.toLowerCase().includes(q) || c.dial_code.includes(q))
  }, [countries, query])

  const commit = (c) => {
    onChange(mode === 'country' ? c.iso2 : c.dial_code)
    setOpen(false)
    setQuery('')
  }

  return (
    <div className="combobox" ref={rootRef}>
      <button
        type="button"
        className="grid-input combobox-input"
        style={{ textAlign: 'left', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
        onClick={() => setOpen((o) => !o)}
      >
        <span>
          {selected ? (mode === 'country' ? selected.name : `${selected.name} (${selected.dial_code})`) : (placeholder || 'Select…')}
        </span>
        <IconChevronDown width={14} height={14} />
      </button>

      {open && (
        <div className="combobox-menu" role="listbox" style={{ padding: 0 }}>
          <input
            autoFocus
            type="text"
            className="grid-input"
            placeholder="Search country or code…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ width: '100%', border: 'none', borderBottom: '1px solid var(--border, #333)', borderRadius: 0 }}
          />
          <div style={{ maxHeight: 240, overflowY: 'auto' }}>
            {filtered.length === 0 && <div className="combobox-option">No matches</div>}
            {filtered.map((c) => (
              <div
                key={c.iso2}
                role="option"
                aria-selected={selected?.iso2 === c.iso2}
                className={`combobox-option ${selected?.iso2 === c.iso2 ? 'is-selected' : ''}`}
                onMouseDown={(e) => { e.preventDefault(); commit(c) }}
              >
                {mode === 'country' ? c.name : `${c.name} (${c.dial_code})`}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
