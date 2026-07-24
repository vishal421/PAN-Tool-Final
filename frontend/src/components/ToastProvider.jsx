import React, { createContext, useCallback, useContext, useRef, useState } from 'react'
import { IconCheckCircle, IconXCircle, IconInfo } from './Icons'

const ToastContext = createContext(null)

const ICONS = { success: IconCheckCircle, error: IconXCircle, info: IconInfo }

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const idRef = useRef(0)

  const dismiss = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const showToast = useCallback((message, type = 'info', durationMs = 4000) => {
    const id = ++idRef.current
    setToasts((prev) => [...prev, { id, message, type }])
    if (durationMs) setTimeout(() => dismiss(id), durationMs)
    return id
  }, [dismiss])

  return (
    <ToastContext.Provider value={showToast}>
      {children}
      <div className="toast-stack">
        {toasts.map((t) => {
          const Icon = ICONS[t.type] || IconInfo
          return (
            <div key={t.id} className={`toast toast-${t.type}`}>
              <Icon width={18} height={18} />
              <span>{t.message}</span>
              <button className="toast-close" onClick={() => dismiss(t.id)}>✕</button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) {
    // Safe no-op fallback if used outside the provider, rather than crashing
    return () => {}
  }
  return ctx
}
