import React, { useEffect, useRef, useState } from 'react'
import { IconLogOut, IconChevronDown } from './Icons'

export default function AccountMenu({ currentUser, onLogout }) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef(null)

  useEffect(() => {
    const onDocClick = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDocClick)
    return () => document.removeEventListener('mousedown', onDocClick)
  }, [])

  const email = currentUser?.email || ''
  const username = email.split('@')[0] || 'Account'
  const initial = username.charAt(0).toUpperCase() || '?'

  return (
    <div className="account-menu" ref={rootRef}>
      <button
        type="button"
        className="account-menu-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="true"
        aria-expanded={open}
        title={email}
      >
        <span className="account-avatar">{initial}</span>
        <IconChevronDown width={14} height={14} className={`account-chevron ${open ? 'is-open' : ''}`} />
      </button>

      {open && (
        <div className="account-dropdown" role="menu">
          <div className="account-dropdown-header">
            <span className="account-avatar account-avatar-lg">{initial}</span>
            <div>
              <div className="account-dropdown-name">{username}</div>
              <div className="account-dropdown-email">{email}</div>
              {currentUser?.plan && (
                <div className="account-dropdown-plan">
                  {currentUser.plan} plan
                  {currentUser.job_limit != null && ` · ${currentUser.job_count}/${currentUser.job_limit} jobs`}
                </div>
              )}
            </div>
          </div>
          <div className="account-dropdown-divider" />
          <button
            type="button"
            className="account-dropdown-item account-dropdown-item-danger"
            onClick={() => { setOpen(false); onLogout() }}
          >
            <IconLogOut width={15} height={15} /> Log out
          </button>
        </div>
      )}
    </div>
  )
}
