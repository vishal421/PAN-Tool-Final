import React, { useEffect, useState } from 'react'
import { getProfiles, saveProfiles } from '../api'

export default function ProfilesEditor({ jobId, onProfilesChanged }) {
  const [logProfiles, setLogProfiles] = useState([])
  const [secGroups, setSecGroups] = useState([])
  const [newLog, setNewLog] = useState('')
  const [newSec, setNewSec] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [saveState, setSaveState] = useState('idle')

  useEffect(() => {
    setLoading(true)
    getProfiles(jobId)
      .then((resp) => {
        setLogProfiles(resp.log_forwarding_profiles)
        setSecGroups(resp.security_profile_groups)
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false))
  }, [jobId])

  const persist = async (nextLog, nextSec) => {
    setSaveState('saving')
    try {
      const resp = await saveProfiles(jobId, { log_forwarding_profiles: nextLog, security_profile_groups: nextSec })
      setLogProfiles(resp.log_forwarding_profiles)
      setSecGroups(resp.security_profile_groups)
      setSaveState('saved')
      setTimeout(() => setSaveState((s) => (s === 'saved' ? 'idle' : s)), 2000)
      onProfilesChanged?.(resp)
    } catch (e) {
      setError(e.message)
      setSaveState('error')
    }
  }

  const addLog = () => {
    const name = newLog.trim()
    if (!name || logProfiles.includes(name)) return
    setNewLog('')
    persist([...logProfiles, name], secGroups)
  }

  const addSec = () => {
    const name = newSec.trim()
    if (!name || secGroups.includes(name)) return
    setNewSec('')
    persist(logProfiles, [...secGroups, name])
  }

  const removeLog = (name) => persist(logProfiles.filter((n) => n !== name), secGroups)
  const removeSec = (name) => persist(logProfiles, secGroups.filter((n) => n !== name))

  if (loading) return <div className="card hint">Loading…</div>

  return (
    <div className="card">
      <h2>Policy Profiles</h2>
      <p className="hint">
        Define the names of Log Forwarding Profiles and Security Profile Groups that already exist on your
        destination Palo Alto firewall. Only the names are needed here - Security Policy rows can then pick
        one from a dropdown instead of free-typing it.
      </p>
      {error && <div className="error-box">{error}</div>}

      <div className="profile-list-editor">
        <h2 style={{ fontSize: 15 }}>Log Forwarding Profiles</h2>
        <div className="profile-chip-row">
          {logProfiles.length === 0 && <span className="hint">None defined yet.</span>}
          {logProfiles.map((name) => (
            <span key={name} className="profile-chip">
              {name}
              <button onClick={() => removeLog(name)} title="Remove">✕</button>
            </span>
          ))}
        </div>
        <div className="profile-add-row">
          <input
            className="grid-input auth-input"
            style={{ maxWidth: 260 }}
            placeholder="e.g. Branch-Office"
            value={newLog}
            onChange={(e) => setNewLog(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addLog()}
          />
          <button className="btn btn-secondary" onClick={addLog}>+ Add</button>
        </div>
      </div>

      <div className="profile-list-editor">
        <h2 style={{ fontSize: 15 }}>Security Profile Groups</h2>
        <div className="profile-chip-row">
          {secGroups.length === 0 && <span className="hint">None defined yet.</span>}
          {secGroups.map((name) => (
            <span key={name} className="profile-chip">
              {name}
              <button onClick={() => removeSec(name)} title="Remove">✕</button>
            </span>
          ))}
        </div>
        <div className="profile-add-row">
          <input
            className="grid-input auth-input"
            style={{ maxWidth: 260 }}
            placeholder="e.g. Strict"
            value={newSec}
            onChange={(e) => setNewSec(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && addSec()}
          />
          <button className="btn btn-secondary" onClick={addSec}>+ Add</button>
        </div>
      </div>

      {saveState === 'saving' && <span className="save-pill saving">Saving…</span>}
      {saveState === 'saved' && <span className="save-pill saved">Saved ✓</span>}
    </div>
  )
}
