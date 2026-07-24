import React, { useEffect, useState } from 'react'
import { ResponsiveContainer, LineChart, Line, CartesianGrid, XAxis, YAxis, Tooltip } from 'recharts'
import { adminSeoInsights, adminSeoPages } from '../../api'
import { IconLoader } from '../../components/Icons'

export default function SeoTab() {
  const [pages, setPages] = useState(null)
  const [insights, setInsights] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([adminSeoPages(), adminSeoInsights()])
      .then(([p, i]) => { setPages(p); setInsights(i) })
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="error-box">{error}</div>
  if (!pages || !insights) return <IconLoader width={24} height={24} />

  return (
    <div>
      <h1 className="admin-h1">SEO Page Analytics</h1>

      <div className="admin-cards-grid">
        <Card label="Most Visited Landing Page" value={insights.most_visited_landing_page || '—'} />
        <Card label="Best Converting Page" value={insights.best_converting_landing_page || '—'} />
        <Card label="Organic Search Traffic" value={insights.organic_search_traffic} />
        <Card label="Direct Traffic" value={insights.direct_traffic} />
        <Card label="Referral Traffic" value={insights.referral_traffic} />
        <Card label="Email Traffic" value={insights.email_traffic} />
        <Card label="Returning Users %" value={`${insights.returning_users_pct}%`} />
        <Card label="Avg. Session (s)" value={insights.avg_session_duration_seconds} />
        <Card label="Avg. Pages / Session" value={insights.avg_pages_per_session} />
      </div>

      <div className="admin-charts-grid" style={{ marginBottom: 28 }}>
        <TopListCard title="Top Entry Pages" items={insights.top_entry_pages} />
        <TopListCard title="Top Exit Pages" items={insights.top_exit_pages} />
      </div>

      <h2 className="admin-section-title" style={{ fontSize: 16 }}>Per-Page Breakdown</h2>
      {pages.map((p) => <SeoPageCard key={p.path} page={p} />)}
    </div>
  )
}

function Card({ label, value }) {
  return (
    <div className="admin-card">
      <div className="admin-card-label">{label}</div>
      <div className="admin-card-value" style={{ fontSize: 16, wordBreak: 'break-word' }}>{value}</div>
    </div>
  )
}

function TopListCard({ title, items }) {
  return (
    <div className="admin-chart-card">
      <div className="admin-chart-title">{title}</div>
      {items.length === 0 && <div className="hint">No data yet</div>}
      {items.map((item, i) => (
        <div key={i} style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, padding: '4px 0', borderBottom: '1px solid var(--border-soft)' }}>
          <span>{item.label}</span><span>{item.value}</span>
        </div>
      ))}
    </div>
  )
}

function SeoPageCard({ page }) {
  return (
    <div className="admin-seo-page-card">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
        <div>
          <strong>{page.label}</strong>
          <span className="hint" style={{ marginLeft: 8 }}>{page.path}</span>
        </div>
        <div className="hint">{page.total_views} views · {page.unique_visitors} unique</div>
      </div>

      <div className="admin-detail-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <Field label="Returning Visitors" value={page.returning_visitors} />
        <Field label="Logged-in Users" value={page.logged_in_users} />
        <Field label="Anonymous Users" value={page.anonymous_users} />
        <Field label="Bounce Rate" value={`${page.bounce_rate_pct}%`} />
        <Field label="Avg. Time on Page" value={`${page.avg_time_on_page_seconds}s`} />
        <Field label="Avg. Scroll Depth" value={page.avg_scroll_depth_pct != null ? `${page.avg_scroll_depth_pct}%` : '—'} />
        <Field label="Top Country" value={page.top_countries[0]?.label || '—'} />
        <Field label="Top Traffic Source" value={page.traffic_sources[0]?.label || '—'} />
      </div>

      <div style={{ marginTop: 8 }}>
        <div className="admin-chart-title">Daily Views (30d)</div>
        <ResponsiveContainer width="100%" height={140}>
          <LineChart data={page.daily_views}>
            <CartesianGrid strokeDasharray="3 3" stroke="#272c3a" />
            <XAxis dataKey="label" hide />
            <YAxis tick={{ fontSize: 10 }} allowDecimals={false} width={28} />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#ff7a1a" dot={false} strokeWidth={2} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function Field({ label, value }) {
  return (
    <div>
      <dt style={{ display: 'block' }}>{label}</dt>
      <dd>{value ?? '—'}</dd>
    </div>
  )
}
