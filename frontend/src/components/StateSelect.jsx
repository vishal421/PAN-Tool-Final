import React, { useEffect, useMemo, useRef, useState } from 'react'
import { State } from 'country-state-city'
import { IconChevronDown } from './Icons'

// State / province dropdown, populated from the standard country-state-city
// reference dataset and keyed off the same iso2 the country dropdown (and
// backend) already use. Falls back to a plain text input when the selected
// country has no subdivision data (e.g. small city-states) or no country has
// been chosen yet.
export default function StateSelect({ countryIso2, value, onChange, placeholder }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const rootRef = useRef(null)

  const states = useMemo(
    () => (countryIso2 ? State.getStatesOfCountry(countryIso2) : []),
    [countryIso2],
  )

  const selected = useMemo(
    () => states.find((s) => s.isoCode === value || s.name === value),
    [states, value],
  )

  useEffect(() => {
    const onOutside = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [])

  const filtered = useMemo(() => {
    if (!query) return states
    const q = query.toLowerCase()
    return states.filter((s) => s.name.toLowerCase().includes(q))
  }, [states, query])

  const commit = (s) => {
    onChange(s.name)
    setOpen(false)
    setQuery('')
  }

  // No country picked yet, or the country has no subdivision data on file —
  // fall back to a plain free-text field so the form never blocks entry.
  if (!countryIso2 || states.length === 0) {
    return (
      <input
        className="grid-input auth-input"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={countryIso2 ? 'e.g. Ontario' : 'Select a country first'}
        disabled={!countryIso2}
        autoComplete="address-level1"
      />
    )
  }

  return (
    <div className="combobox" ref={rootRef}>
      <button
        type="button"
        className="grid-input combobox-input"
        style={{ textAlign: 'left', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
        onClick={() => setOpen((o) => !o)}
      >
        <span>{selected ? selected.name : (placeholder || 'Select…')}</span>
        <IconChevronDown width={14} height={14} />
      </button>

      {open && (
        <div className="combobox-menu" role="listbox" style={{ padding: 0 }}>
          <input
            autoFocus
            type="text"
            className="grid-input"
            placeholder="Search state or province…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ width: '100%', border: 'none', borderBottom: '1px solid var(--border, #333)', borderRadius: 0 }}
          />
          <div style={{ maxHeight: 240, overflowY: 'auto' }}>
            {filtered.length === 0 && <div className="combobox-option">No matches</div>}
            {filtered.map((s) => (
              <div
                key={s.isoCode}
                role="option"
                aria-selected={selected?.isoCode === s.isoCode}
                className={`combobox-option ${selected?.isoCode === s.isoCode ? 'is-selected' : ''}`}
                onMouseDown={(e) => { e.preventDefault(); commit(s) }}
              >
                {s.name}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
