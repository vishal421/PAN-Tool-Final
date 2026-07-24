import React, { useEffect, useRef, useState } from 'react'
import { IconChevronDown } from './Icons'

// A combobox that behaves the way people expect a dropdown to behave:
// clicking it immediately shows every option (native <input list="..."> +
// <datalist> only reliably does this once the user has already typed
// something, which is confusing - the whole option list should be visible
// on click, then narrow down as the user types). Still allows typing a
// value that isn't in the list, since some fields (subinterfaces, new zone
// names) need that.
export default function Combobox({ options, value, onChange, placeholder }) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState(value ?? '')
  const [activeIdx, setActiveIdx] = useState(-1)
  const rootRef = useRef(null)

  useEffect(() => { setDraft(value ?? '') }, [value])

  useEffect(() => {
    const onOutside = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) {
        setOpen(false)
        if (draft !== (value ?? '')) onChange(draft)
      }
    }
    document.addEventListener('mousedown', onOutside)
    return () => document.removeEventListener('mousedown', onOutside)
  }, [draft, value, onChange])

  const filtered = draft
    ? options.filter((o) => o.toLowerCase().includes(draft.toLowerCase()))
    : options

  const commit = (v) => {
    setDraft(v)
    onChange(v)
    setOpen(false)
    setActiveIdx(-1)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActiveIdx((i) => Math.min(i + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIdx((i) => Math.max(i - 1, 0))
    } else if (e.key === 'Enter') {
      if (open && activeIdx >= 0 && filtered[activeIdx]) {
        e.preventDefault()
        commit(filtered[activeIdx])
      } else {
        setOpen(false)
      }
    } else if (e.key === 'Escape') {
      setOpen(false)
      setDraft(value ?? '')
    }
  }

  return (
    <div className="combobox" ref={rootRef}>
      <input
        className="grid-input combobox-input"
        type="text"
        value={draft}
        placeholder={placeholder}
        onFocus={() => setOpen(true)}
        onClick={() => setOpen(true)}
        onChange={(e) => { setDraft(e.target.value); setOpen(true); setActiveIdx(-1) }}
        onKeyDown={handleKeyDown}
        onBlur={() => { if (draft !== (value ?? '')) onChange(draft) }}
      />
      <button
        type="button"
        className="combobox-toggle"
        tabIndex={-1}
        aria-label={open ? 'Hide options' : 'Show all options'}
        onClick={() => setOpen((o) => !o)}
      >
        <IconChevronDown width={14} height={14} />
      </button>
      {open && filtered.length > 0 && (
        <ul className="combobox-menu" role="listbox">
          {filtered.map((o, i) => (
            <li
              key={o}
              role="option"
              aria-selected={o === value}
              className={`combobox-option ${i === activeIdx ? 'is-active' : ''} ${o === value ? 'is-selected' : ''}`}
              onMouseDown={(e) => { e.preventDefault(); commit(o) }}
              onMouseEnter={() => setActiveIdx(i)}
            >
              {o}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
