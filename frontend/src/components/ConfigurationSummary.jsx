import React, { useState } from 'react'
import { excelExportPath, triggerDownload } from '../api'

const CATEGORIES = [
  { key: 'addresses', label: 'Addresses' },
  { key: 'address_groups', label: 'Address Groups' },
  { key: 'services', label: 'Services' },
  { key: 'service_groups', label: 'Service Groups' },
  { key: 'interfaces', label: 'Interfaces' },
  { key: 'routes', label: 'Routes' },
  { key: 'policies', label: 'Security Policies' },
  { key: 'nat_rules', label: 'NAT Rules' },
]

export default function ConfigurationSummary({ jobId, summary, onContinue, continueLabel = 'Continue to Interface Mapping' }) {
  const [activeTab, setActiveTab] = useState('addresses')
  const counts = summary?.counts || {}
  const tables = summary?.tables || {}
  const activeRows = tables[activeTab] || []

  return (
    <div className="card">
      <h2>Configuration Summary</h2>
      <p className="hint">
        Everything detected in the uploaded file, before any interface mapping is applied.
      </p>

      <div className="stats-grid">
        {CATEGORIES.map((c) => (
          <div
            className={`stat-tile stat-tile-clickable ${activeTab === c.key ? 'stat-tile-active' : ''}`}
            key={c.key}
            onClick={() => setActiveTab(c.key)}
          >
            <div className="value">{counts[c.key] ?? 0}</div>
            <div className="label">{c.label}</div>
          </div>
        ))}
      </div>

      <div className="summary-tabs">
        {CATEGORIES.map((c) => (
          <button
            key={c.key}
            className={`tab-btn ${activeTab === c.key ? 'active' : ''}`}
            onClick={() => setActiveTab(c.key)}
          >
            {c.label} <span className="tab-count">{counts[c.key] ?? 0}</span>
          </button>
        ))}
      </div>

      <div className="summary-table-wrap">
        {activeRows.length === 0 ? (
          <div className="empty-table-note">No {CATEGORIES.find((c) => c.key === activeTab)?.label.toLowerCase()} found in the source config.</div>
        ) : (
          <table className="summary-table">
            <thead>
              <tr>
                {Object.keys(activeRows[0]).map((col) => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {activeRows.map((row, i) => (
                <tr key={i}>
                  {Object.keys(activeRows[0]).map((col) => (
                    <td key={col}>{String(row[col] ?? '')}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="actions-row" style={{ justifyContent: 'space-between' }}>
        <button
          className="btn btn-secondary"
          onClick={() => triggerDownload(excelExportPath(jobId), 'configuration_summary.xlsx')}
        >
          Export to Excel
        </button>
        {onContinue && (
          <button className="btn btn-primary" onClick={onContinue}>
            {continueLabel}
          </button>
        )}
      </div>
    </div>
  )
}
