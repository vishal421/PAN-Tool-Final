import React, { useEffect, useState } from 'react'
import EditableGrid from './EditableGrid'
import ValidationCenter from './ValidationCenter'
import ExportCenter from './ExportCenter'
import ConfigurationSummary from './ConfigurationSummary'
import ProfilesEditor from './ProfilesEditor'
import CleanupCenter from './CleanupCenter'
import { getValidation, getProfiles, getObjects, generateConfig } from '../api'
import { OBJECT_TYPE_TO_CATEGORY } from '../gridConfigs'
import { useToast } from './ToastProvider'

// Every editable-grid-backed section, keyed the same way the sidebar (in
// App.jsx) links to them. System Settings (LDAP/RADIUS/TACACS+/SNMP/
// Syslog/NTP/DNS) has been removed from the product entirely - it no
// longer appears here or anywhere else in the navigation.
const GRID_CATEGORIES = [
  'addresses', 'address_groups', 'services', 'service_groups', 'interfaces', 'zones', 'routes', 'nat_rules',
  'policies',
]

export default function Workbench({ job, summary, activeTab, onTabChange, onExitToHome, onDeleteJob, onStatsUpdated }) {
  const tab = activeTab || 'summary'
  const [stats, setStatsState] = useState(job.stats || {})
  // Wraps setStats so every place that updates the local workbench stats
  // also pushes the same numbers up to App's sidebar (Objects/Network/
  // Policies counts), instead of duplicating the getValidation() calls.
  const setStats = (next) => {
    setStatsState(next)
    onStatsUpdated?.(next)
  }
  const [issueCount, setIssueCount] = useState(null)
  const [allIssues, setAllIssues] = useState([])
  const [focusTarget, setFocusTarget] = useState(null) // { category, name } | null
  const [jobStatus, setJobStatus] = useState(job.status)
  const [dynamicOptions, setDynamicOptions] = useState({
    interface_names: [], log_forwarding_profiles: [], security_profile_groups: [],
    zone_names: [], address_names: [], service_names: [], application_names: [],
    address_object_names: [], service_object_names: [], nat_interface_options: [], interface_ip_by_name: {},
  })

  const [generating, setGenerating] = useState(false)
  const [generateResult, setGenerateResult] = useState(null) // { blocking, issues, message } | null
  const showToast = useToast()

  const refreshInterfaceNames = () => {
    getObjects(job.id, 'interfaces')
      .then((resp) => {
        const names = resp.rows.map((r) => r.pan_name).filter(Boolean)
        // For NAT rules whose translated source is "the egress interface's
        // own IP" (PAN-OS: source-translation dynamic-ip-and-port
        // interface-address), the grid needs the mapped PAN interface
        // names as pickable options (stored as "interface:<pan_name>",
        // the exact marker the generator looks for) plus a name -> IP
        // lookup so the grid can show which IP that interface will
        // actually translate to.
        const natInterfaceOptions = names.map((n) => `interface:${n}`)
        const interfaceIpByName = {}
        resp.rows.forEach((r) => { if (r.pan_name) interfaceIpByName[r.pan_name] = r.ip_address || '' })
        setDynamicOptions((prev) => ({
          ...prev, interface_names: names, nat_interface_options: natInterfaceOptions, interface_ip_by_name: interfaceIpByName,
        }))
      })
      .catch(() => {})
  }

  const refreshZoneNames = () => {
    Promise.all([getObjects(job.id, 'zones'), getObjects(job.id, 'interfaces')])
      .then(([zonesResp, ifacesResp]) => {
        const fromZones = zonesResp.rows.map((r) => r.name).filter(Boolean)
        const fromInterfaces = ifacesResp.rows.map((r) => r.zone).filter(Boolean)
        const names = Array.from(new Set([...fromZones, ...fromInterfaces])).sort()
        setDynamicOptions((prev) => ({ ...prev, zone_names: names }))
      })
      .catch(() => {})
  }

  const refreshAddressNames = () => {
    Promise.all([getObjects(job.id, 'addresses'), getObjects(job.id, 'address_groups')])
      .then(([addrResp, groupResp]) => {
        const objectNames = Array.from(new Set(addrResp.rows.map((r) => r.name))).filter(Boolean).sort()
        const names = Array.from(new Set([
          ...addrResp.rows.map((r) => r.name), ...groupResp.rows.map((r) => r.name),
        ])).filter(Boolean).sort()
        setDynamicOptions((prev) => ({ ...prev, address_names: names, address_object_names: objectNames }))
      })
      .catch(() => {})
  }

  const refreshServiceNames = () => {
    Promise.all([getObjects(job.id, 'services'), getObjects(job.id, 'service_groups')])
      .then(([svcResp, groupResp]) => {
        const objectNames = Array.from(new Set(svcResp.rows.map((r) => r.name))).filter(Boolean).sort()
        const names = Array.from(new Set([
          ...svcResp.rows.map((r) => r.name), ...groupResp.rows.map((r) => r.name),
        ])).filter(Boolean).sort()
        setDynamicOptions((prev) => ({ ...prev, service_names: names, service_object_names: objectNames }))
      })
      .catch(() => {})
  }

  const refreshApplicationNames = () => {
    getObjects(job.id, 'policies')
      .then((resp) => {
        const names = Array.from(new Set(
          resp.rows.flatMap((r) => (Array.isArray(r.application) ? r.application : [])),
        )).filter((n) => n && n.toLowerCase() !== 'any').sort()
        setDynamicOptions((prev) => ({ ...prev, application_names: names }))
      })
      .catch(() => {})
  }

  useEffect(() => {
    getValidation(job.id)
      .then((resp) => { setStats(resp.stats); setIssueCount(resp.issues.length); setAllIssues(resp.issues) })
      .catch(() => {})
    getProfiles(job.id)
      .then((resp) => setDynamicOptions((prev) => ({
        ...prev, log_forwarding_profiles: resp.log_forwarding_profiles, security_profile_groups: resp.security_profile_groups,
      })))
      .catch(() => {})
    refreshInterfaceNames()
    refreshZoneNames()
    refreshAddressNames()
    refreshServiceNames()
    refreshApplicationNames()
  }, [job.id])

  const handleGenerate = async () => {
    setGenerating(true)
    setGenerateResult(null)
    try {
      const resp = await generateConfig(job.id)
      setGenerateResult({
        blocking: resp.validation.blocking,
        issues: resp.validation.issues,
        message: resp.message,
      })
      if (!resp.validation.blocking && resp.job.status === 'completed') {
        setJobStatus('completed')
        setStats(resp.job.stats || stats)
        showToast('Configuration generated successfully.', 'success')
      } else if (resp.validation.blocking) {
        showToast('Fix the flagged interface fields before generating.', 'error')
      }
    } catch (e) {
      setGenerateResult({ blocking: true, issues: [], message: e.message })
      showToast(e.message, 'error')
    } finally {
      setGenerating(false)
    }
  }

  const issueCountByCategory = allIssues.reduce((acc, iss) => {
    const cat = OBJECT_TYPE_TO_CATEGORY[iss.object_type]
    if (cat) acc[cat] = (acc[cat] || 0) + 1
    return acc
  }, {})

  const navigateToIssue = (category, name) => {
    onTabChange?.(category)
    setFocusTarget({ category, name })
  }

  const onGridSaved = (category) => {
    if (category === 'interfaces') { refreshInterfaceNames(); refreshZoneNames() }
    if (category === 'zones') refreshZoneNames()
    if (category === 'addresses' || category === 'address_groups') refreshAddressNames()
    if (category === 'services' || category === 'service_groups') refreshServiceNames()
    if (category === 'policies') refreshApplicationNames()
  }

  const goToSummary = () => onTabChange?.('summary')

  return (
    <div className="workbench-shell">
      <div className="workbench-topbar">
        <button className="workbench-title-btn" onClick={goToSummary} title="Back to job summary">
          {job.job_name || job.original_filename}
        </button>
      </div>

      <div className="workbench">
        <div className="workbench-content">
          {tab === 'summary' && (
            summary ? (
              <>
                <ConfigurationSummary jobId={job.id} summary={summary} onContinue={null} />

                <div className="card">
                  <h2>Generate Palo Alto Configuration</h2>
                  <p className="hint">
                    Map interfaces to zones, virtual routers, and (optionally) subinterfaces on the
                    <strong> Interface Mapping</strong> section under Network (create new zones on the
                    <strong> Zones</strong> section if you need one that doesn't exist yet), then generate here - no separate wizard step.
                  </p>
                  <button className="btn btn-primary" onClick={handleGenerate} disabled={generating}>
                    {generating ? 'Generating…' : 'Generate Configuration'}
                  </button>

                  {generateResult && (
                    <div style={{ marginTop: 14 }}>
                      {generateResult.blocking ? (
                        <div className="error-box">
                          <strong>{generateResult.message}</strong>
                          {generateResult.issues.length > 0 && (
                            <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
                              {generateResult.issues.map((iss, i) => (
                                <li key={i}>[{iss.severity}] {iss.object_type} "{iss.object_name}": {iss.message}</li>
                              ))}
                            </ul>
                          )}
                        </div>
                      ) : (
                        <div className="success-box">
                          {generateResult.message} <button className="link-btn" onClick={() => onTabChange?.('export')}>Go to Export →</button>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                <div className="card">
                  <h2 style={{ color: 'var(--error)' }}>Danger Zone</h2>
                  <p className="hint">Permanently deletes this job, its saved objects, and any generated output files.</p>
                  <button className="btn btn-danger" onClick={onDeleteJob}>Delete This Job</button>
                </div>
              </>
            ) : <div className="card hint">Loading summary…</div>
          )}

          {tab === 'validation' && (
            <ValidationCenter
              jobId={job.id}
              onNavigateToGrid={navigateToIssue}
              onStatsUpdated={(s) => setStats(s)}
              onIssuesUpdated={(issues) => { setAllIssues(issues); setIssueCount(issues.length) }}
            />
          )}

          {tab === 'profiles' && (
            <ProfilesEditor
              jobId={job.id}
              onProfilesChanged={(resp) => setDynamicOptions((prev) => ({
                ...prev, log_forwarding_profiles: resp.log_forwarding_profiles, security_profile_groups: resp.security_profile_groups,
              }))}
            />
          )}

          {tab === 'cleanup' && (
            <CleanupCenter jobId={job.id} onStatsUpdated={() => {
              getValidation(job.id).then((resp) => setStats(resp.stats)).catch(() => {})
            }} />
          )}

          {GRID_CATEGORIES.includes(tab) && (
            <EditableGrid
              jobId={job.id}
              category={tab}
              dynamicOptions={dynamicOptions}
              issues={allIssues.filter((iss) => OBJECT_TYPE_TO_CATEGORY[iss.object_type] === tab)}
              focusName={focusTarget?.category === tab ? focusTarget.name : null}
              onFocusHandled={() => setFocusTarget(null)}
              onIssuesUpdated={(issues) => { setIssueCount(issues.length); setAllIssues(issues) }}
              onStatsUpdated={(s) => setStats(s)}
              onSaved={onGridSaved}
            />
          )}

          {tab === 'export' && <ExportCenter jobId={job.id} jobStatus={jobStatus} />}
        </div>
      </div>
    </div>
  )
}

export { GRID_CATEGORIES as WORKBENCH_GRID_CATEGORIES }
