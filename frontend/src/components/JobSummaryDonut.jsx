import React, { useMemo } from 'react'

// Read-only "round circle graph" summarizing a migration job's (or the
// combined total across all jobs') object/policy/interface counts.
// Deliberately has no edit affordances - selecting an older job just swaps
// the numbers this renders, it never opens that job for editing.

const SLICES = [
  { key: 'objects', label: 'Objects', color: 'var(--accent)' },
  { key: 'securityPolicy', label: 'Security Policy', color: '#f5a524' },
  { key: 'natPolicy', label: 'NAT Policy', color: '#2dd4bf' },
  { key: 'interfaces', label: 'Interfaces', color: '#a78bfa' },
]

// A completed job's `stats` payload looks like:
//   { addresses, address_groups, services, service_groups, interfaces, policies, routes, nat_rules }
// "Objects" here groups every address/service object together.
export function statsToCounts(stats) {
  const s = stats || {}
  return {
    objects: (Number(s.addresses) || 0) + (Number(s.address_groups) || 0) +
      (Number(s.services) || 0) + (Number(s.service_groups) || 0),
    securityPolicy: Number(s.policies) || 0,
    natPolicy: Number(s.nat_rules) || 0,
    interfaces: Number(s.interfaces) || 0,
  }
}

export default function JobSummaryDonut({ counts, size = 176 }) {
  const total = SLICES.reduce((sum, s) => sum + (counts[s.key] || 0), 0)
  const r = size / 2 - 16
  const circumference = 2 * Math.PI * r

  const arcs = useMemo(() => {
    let offset = 0
    return SLICES.map((s) => {
      const value = counts[s.key] || 0
      const fraction = total > 0 ? value / total : 0
      const dash = fraction * circumference
      const arc = { ...s, value, dashArray: `${dash} ${circumference - dash}`, dashOffset: -offset }
      offset += dash
      return arc
    })
  }, [counts, total, circumference])

  return (
    <div className="job-summary-donut">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label="Migration summary breakdown">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--border)" strokeWidth="16" />
        {total > 0 && arcs.map((a) => (
          <circle
            key={a.key}
            cx={size / 2}
            cy={size / 2}
            r={r}
            fill="none"
            stroke={a.color}
            strokeWidth="16"
            strokeDasharray={a.dashArray}
            strokeDashoffset={a.dashOffset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            strokeLinecap="butt"
          />
        ))}
        <text x="50%" y="47%" textAnchor="middle" className="job-summary-donut-total">{total.toLocaleString()}</text>
        <text x="50%" y="62%" textAnchor="middle" className="job-summary-donut-total-label">Total</text>
      </svg>
      <div className="job-summary-donut-legend">
        {SLICES.map((s) => (
          <div key={s.key} className="job-summary-donut-legend-item">
            <span className="job-summary-donut-dot" style={{ background: s.color }} />
            <span className="job-summary-donut-legend-label">{s.label}</span>
            <span className="job-summary-donut-legend-value">{(counts[s.key] || 0).toLocaleString()}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
