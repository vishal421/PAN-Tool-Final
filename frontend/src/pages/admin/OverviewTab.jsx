import React, { useEffect, useState } from 'react'
import {
  ResponsiveContainer, LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
} from 'recharts'
import { adminCharts, adminOverview } from '../../api'
import { IconLoader } from '../../components/Icons'

const COLORS = ['#ff7a1a', '#5b8cff', '#35d68a', '#f5c542', '#ff5c6a', '#b98cff', '#4dd0e1', '#ffb35c']

const CARD_DEFS = [
  ['total_visitors', 'Total Visitors'],
  ['unique_visitors', 'Unique Visitors'],
  ['registered_users', 'Registered Users'],
  ['active_users_today', 'Active Users Today'],
  ['logged_in_users_today', 'Logged-in Today'],
  ['anonymous_visitors_today', 'Anonymous Today'],
  ['total_page_views', 'Total Page Views'],
  ['avg_session_duration_seconds', 'Avg. Session (s)'],
  ['bounce_rate_pct', 'Bounce Rate (%)'],
  ['returning_visitors', 'Returning Visitors'],
  ['new_users_today', 'New Users Today'],
  ['total_tool_conversions', 'Tool Conversions'],
]

export default function OverviewTab() {
  const [overview, setOverview] = useState(null)
  const [charts, setCharts] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([adminOverview(), adminCharts()])
      .then(([o, c]) => { setOverview(o); setCharts(c) })
      .catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="error-box">{error}</div>
  if (!overview || !charts) return <IconLoader width={24} height={24} />

  return (
    <div>
      <h1 className="admin-h1">Dashboard Overview</h1>

      <div className="admin-cards-grid">
        {CARD_DEFS.map(([key, label]) => (
          <div className="admin-card" key={key}>
            <div className="admin-card-label">{label}</div>
            <div className="admin-card-value">{overview[key]}</div>
          </div>
        ))}
      </div>

      <div className="admin-charts-grid">
        <ChartCard title="Daily Visitors (30d)">
          <LineChart data={charts.daily_visitors}>
            <CartesianGrid strokeDasharray="3 3" stroke="#272c3a" />
            <XAxis dataKey="label" tick={{ fontSize: 10 }} hide />
            <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#ff7a1a" dot={false} strokeWidth={2} />
          </LineChart>
        </ChartCard>

        <ChartCard title="Weekly Visitors (12w)">
          <BarChart data={charts.weekly_visitors}>
            <CartesianGrid strokeDasharray="3 3" stroke="#272c3a" />
            <XAxis dataKey="label" tick={{ fontSize: 9 }} />
            <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="value" fill="#5b8cff" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard title="Monthly Visitors (12mo)">
          <BarChart data={charts.monthly_visitors}>
            <CartesianGrid strokeDasharray="3 3" stroke="#272c3a" />
            <XAxis dataKey="label" tick={{ fontSize: 9 }} />
            <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
            <Tooltip />
            <Bar dataKey="value" fill="#35d68a" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ChartCard>

        <ChartCard title="User Registrations (30d)">
          <LineChart data={charts.user_registrations}>
            <CartesianGrid strokeDasharray="3 3" stroke="#272c3a" />
            <XAxis dataKey="label" tick={{ fontSize: 10 }} hide />
            <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
            <Tooltip />
            <Line type="monotone" dataKey="value" stroke="#f5c542" dot={false} strokeWidth={2} />
          </LineChart>
        </ChartCard>

        <PieCard title="Top Countries" data={charts.top_countries} />
        <PieCard title="Top Cities" data={charts.top_cities} />
        <PieCard title="Traffic Sources" data={charts.traffic_sources} />
        <PieCard title="Most Visited Pages" data={charts.most_visited_pages} />
        <PieCard title="Device Breakdown" data={charts.device_breakdown} />
        <PieCard title="Browser Breakdown" data={charts.browser_breakdown} />
        <PieCard title="OS Breakdown" data={charts.os_breakdown} />
        <PieCard title="Logged-in vs Guest" data={charts.logged_in_vs_guest} />
      </div>
    </div>
  )
}

function ChartCard({ title, children }) {
  return (
    <div className="admin-chart-card">
      <div className="admin-chart-title">{title}</div>
      <ResponsiveContainer width="100%" height={220}>
        {children}
      </ResponsiveContainer>
    </div>
  )
}

function PieCard({ title, data }) {
  if (!data || data.length === 0) {
    return (
      <div className="admin-chart-card">
        <div className="admin-chart-title">{title}</div>
        <div className="hint" style={{ padding: '40px 0', textAlign: 'center' }}>No data yet</div>
      </div>
    )
  }
  return (
    <ChartCard title={title}>
      <PieChart>
        <Pie data={data} dataKey="value" nameKey="label" outerRadius={75} label={({ label }) => label}>
          {data.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
        </Pie>
        <Tooltip />
        <Legend wrapperStyle={{ fontSize: 11 }} />
      </PieChart>
    </ChartCard>
  )
}
