import React, { useCallback, useRef, useState } from 'react'
import { IconAlertTriangle } from './Icons'

export function useConfirmDialog() {
  const [state, setState] = useState(null) // { message, title, danger } | null
  const resolveRef = useRef(null)

  const confirm = useCallback((message, opts = {}) => {
    setState({ message, title: opts.title || 'Are you sure?', danger: opts.danger ?? true, confirmLabel: opts.confirmLabel || 'Delete' })
    return new Promise((resolve) => { resolveRef.current = resolve })
  }, [])

  const handle = (result) => {
    setState(null)
    resolveRef.current?.(result)
  }

  const ConfirmDialogElement = state ? (
    <div className="modal-overlay" onClick={() => handle(false)}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className={`modal-icon ${state.danger ? 'modal-icon-danger' : ''}`}>
          <IconAlertTriangle width={22} height={22} />
        </div>
        <h3>{state.title}</h3>
        <p className="hint">{state.message}</p>
        <div className="actions-row" style={{ justifyContent: 'flex-end', marginTop: 20 }}>
          <button className="btn btn-secondary" onClick={() => handle(false)}>Cancel</button>
          <button className={state.danger ? 'btn btn-danger-solid' : 'btn btn-primary'} onClick={() => handle(true)}>
            {state.confirmLabel}
          </button>
        </div>
      </div>
    </div>
  ) : null

  return { confirm, ConfirmDialogElement }
}
