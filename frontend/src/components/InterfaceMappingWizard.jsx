import React, { useState } from 'react'
import Combobox from './Combobox'

const ZONE_SUGGESTIONS = ['LAN', 'WAN', 'DMZ', 'TRUST', 'UNTRUST']
const INTERFACE_TYPES = [
  { value: 'layer3', label: 'Layer3' },
  { value: 'layer2', label: 'Layer2' },
  { value: 'vwire', label: 'Virtual Wire' },
]

function suggestPanInterface(index) {
  return `ethernet1/${index + 1}`
}

export default function InterfaceMappingWizard({ interfaces, onSubmit, submitting, validation }) {
  const [rows, setRows] = useState(() =>
    interfaces.map((iface, idx) => ({
      source_interface: iface.source_interface,
      hardware_name: iface.hardware_name,
      pan_interface: suggestPanInterface(idx),
      zone: iface.suggested_zone || '',
      virtual_router: iface.virtual_router || 'default',
      interface_type: 'layer3',
      ip_address: iface.ip_address || '',
      netmask: iface.netmask || '',
      description: iface.description || '',
      enabled: true,
    }))
  )

  const updateRow = (idx, field, value) => {
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, [field]: value } : r)))
  }

  const zoneOptions = Array.from(new Set([
    ...ZONE_SUGGESTIONS,
    ...rows.map((r) => r.zone).filter(Boolean),
  ]))

  const issuesByInterface = {}
  if (validation) {
    for (const issue of validation.issues) {
      if (issue.object_type === 'interface') {
        issuesByInterface[issue.object_name] = issuesByInterface[issue.object_name] || []
        issuesByInterface[issue.object_name].push(issue)
      }
    }
  }

  return (
    <div className="card">
      <h2>Interface Mapping</h2>
      <p className="hint">
        Palo Alto is zone-based; {interfaces.length > 0 ? 'this source device' : 'the source device'} is
        interface-based. Confirm how each detected interface maps to a PAN-OS interface, zone, and
        virtual router before generating — nothing is auto-assumed.
      </p>

      <div className="mapping-table-wrap">
        <table className="mapping-table">
          <thead>
            <tr>
              <th>Source Interface</th>
              <th>PA Interface</th>
              <th>Zone</th>
              <th>Virtual Router</th>
              <th>Type</th>
              <th>IP Address</th>
              <th>Netmask</th>
              <th>Description</th>
              <th>Enabled</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, idx) => {
              const rowIssues = issuesByInterface[row.source_interface] || []
              return (
                <tr key={row.source_interface} className={rowIssues.length ? 'row-error' : ''}>
                  <td>
                    <div className="source-iface-cell">
                      <strong>{row.source_interface}</strong>
                      {row.hardware_name && row.hardware_name !== row.source_interface && (
                        <small>{row.hardware_name}</small>
                      )}
                    </div>
                  </td>
                  <td>
                    <input
                      value={row.pan_interface}
                      onChange={(e) => updateRow(idx, 'pan_interface', e.target.value)}
                      placeholder="ethernet1/1"
                    />
                  </td>
                  <td>
                    <Combobox
                      options={zoneOptions}
                      value={row.zone}
                      onChange={(v) => updateRow(idx, 'zone', v)}
                      placeholder="LAN"
                    />
                  </td>
                  <td>
                    <input
                      value={row.virtual_router}
                      onChange={(e) => updateRow(idx, 'virtual_router', e.target.value)}
                      placeholder="default"
                    />
                  </td>
                  <td>
                    <select
                      value={row.interface_type}
                      onChange={(e) => updateRow(idx, 'interface_type', e.target.value)}
                    >
                      {INTERFACE_TYPES.map((t) => (
                        <option key={t.value} value={t.value}>{t.label}</option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      value={row.ip_address}
                      onChange={(e) => updateRow(idx, 'ip_address', e.target.value)}
                      placeholder="x.x.x.x"
                    />
                  </td>
                  <td>
                    <input
                      value={row.netmask}
                      onChange={(e) => updateRow(idx, 'netmask', e.target.value)}
                      placeholder="255.255.255.0"
                    />
                  </td>
                  <td>
                    <input
                      value={row.description}
                      onChange={(e) => updateRow(idx, 'description', e.target.value)}
                    />
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <input
                      type="checkbox"
                      checked={row.enabled}
                      onChange={(e) => updateRow(idx, 'enabled', e.target.checked)}
                    />
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {validation && validation.issues.length > 0 && (
        <div className="validation-panel">
          {validation.blocking && (
            <div className="validation-heading error">
              Resolve these before generating:
            </div>
          )}
          {!validation.blocking && (
            <div className="validation-heading warning">
              Validation passed — review these warnings if you'd like:
            </div>
          )}
          <ul>
            {validation.issues.map((issue, i) => (
              <li key={i} className={`validation-item ${issue.severity}`}>
                <span className="issue-badge-inline">{issue.severity}</span>
                <span>[{issue.object_type}:{issue.object_name}] {issue.message}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="actions-row">
        <button
          className="btn btn-primary"
          onClick={() => onSubmit(rows)}
          disabled={submitting}
        >
          {submitting ? 'Generating…' : 'Confirm Mapping & Generate'}
        </button>
      </div>
    </div>
  )
}
