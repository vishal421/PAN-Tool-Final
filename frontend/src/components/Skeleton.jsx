import React from 'react'

export function SkeletonRows({ rows = 4, height = 16 }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="skeleton-bar" style={{ height, width: `${85 - i * 8}%` }} />
      ))}
    </div>
  )
}

export function SkeletonTable({ rows = 5, cols = 5 }) {
  return (
    <div className="skeleton-table">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="skeleton-table-row">
          {Array.from({ length: cols }).map((_, c) => (
            <div key={c} className="skeleton-bar" style={{ height: 14, flex: c === 0 ? '0 0 60px' : 1 }} />
          ))}
        </div>
      ))}
    </div>
  )
}

export function SkeletonCards({ count = 4 }) {
  return (
    <div className="stats-grid">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="stat-tile">
          <div className="skeleton-bar" style={{ height: 26, width: '40%', marginBottom: 8 }} />
          <div className="skeleton-bar" style={{ height: 11, width: '70%' }} />
        </div>
      ))}
    </div>
  )
}
