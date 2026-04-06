import { useEffect, useState } from 'react'
import { fetchStats, fetchWeekly, fetchProviderDaily, fetchValidDaily } from '../api/client'
import type { Stats, WeeklyItem, ProviderDailyItem } from '../types'
import StatsPanel from '../components/StatsPanel'

const COLORS = [
  '#10b981', '#3b82f6', '#f59e0b', '#ef4444', '#8b5cf6',
  '#ec4899', '#06b6d4', '#f97316', '#84cc16', '#6366f1',
  '#14b8a6', '#e11d48', '#a855f7', '#0ea5e9', '#d946ef',
]

export default function Leaderboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [weekly, setWeekly] = useState<WeeklyItem[]>([])
  const [providerDaily, setProviderDaily] = useState<ProviderDailyItem[]>([])
  const [validDaily, setValidDaily] = useState<ProviderDailyItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    Promise.all([
      fetchStats().then(setStats),
      fetchWeekly().then(setWeekly),
      fetchProviderDaily().then(setProviderDaily),
      fetchValidDaily().then(setValidDaily),
    ])
      .catch((e) => setError(e instanceof Error ? e.message : 'Failed to load'))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center text-gray-500 py-12">Loading...</div>

  return (
    <div className="space-y-8">
      {error && <div className="text-center text-red-400 py-4 bg-red-900/20 rounded-lg">{error}</div>}
      <StatsPanel stats={stats} />
      <BarChart weekly={weekly} />
      <LineChart data={providerDaily} />
      <ValidKeyLineChart data={validDaily} />
    </div>
  )
}

function BarChart({ weekly }: { weekly: WeeklyItem[] }) {
  const maxCount = Math.max(...weekly.map((w) => w.count), 1)

  const BAR_H = 160 // 柱子区域最大高度 px

  return (
    <section className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <h3 className="font-semibold mb-4">Weekly Leak Activity</h3>
      <div className="flex items-end gap-2" style={{ height: BAR_H + 40 }}>
        {weekly.map((w) => (
          <div key={w.date} className="flex-1 flex flex-col items-center justify-end gap-1 h-full">
            <span className="text-xs text-gray-400 font-mono">{w.count}</span>
            <div
              className="w-full rounded-t"
              style={{
                height: Math.max((w.count / maxCount) * BAR_H, 4),
                background: 'linear-gradient(to top, #059669, #10b981)',
              }}
            />
            <span className="text-xs text-gray-500">
              {new Date(w.date + 'T12:00:00').toLocaleDateString('en', { month: 'short', day: 'numeric' })}
            </span>
          </div>
        ))}
      </div>
    </section>
  )
}

function LineChart({ data }: { data: ProviderDailyItem[] }) {
  if (!data.length) return null

  // 按 provider 分组
  const providers = [...new Set(data.map((d) => d.provider))]
  const dates = [...new Set(data.map((d) => d.date))]
  const byProvider: Record<string, number[]> = {}
  for (const p of providers) {
    byProvider[p] = dates.map((d) => data.find((item) => item.date === d && item.provider === p)?.count ?? 0)
  }

  // 按总量降序排列
  providers.sort((a, b) => {
    const sumA = byProvider[a].reduce((s, v) => s + v, 0)
    const sumB = byProvider[b].reduce((s, v) => s + v, 0)
    return sumB - sumA
  })

  const maxVal = Math.max(...Object.values(byProvider).flat(), 1)

  // SVG 尺寸
  const W = 700, H = 280
  const pad = { top: 20, right: 20, bottom: 30, left: 40 }
  const cw = W - pad.left - pad.right
  const ch = H - pad.top - pad.bottom

  const xStep = dates.length > 1 ? cw / (dates.length - 1) : cw
  const toX = (i: number) => pad.left + i * xStep
  const toY = (v: number) => pad.top + ch - (v / maxVal) * ch

  // Y 轴刻度 (4 条)
  const yTicks = Array.from({ length: 5 }, (_, i) => Math.round((maxVal / 4) * i))

  return (
    <section className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <h3 className="font-semibold mb-4">Provider Daily Trend</h3>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 320 }}>
        {/* 网格线 */}
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={pad.left} y1={toY(t)} x2={W - pad.right} y2={toY(t)} stroke="#374151" strokeDasharray="4" />
            <text x={pad.left - 6} y={toY(t) + 4} textAnchor="end" fill="#6b7280" fontSize={10}>{t}</text>
          </g>
        ))}
        {/* X 轴标签 */}
        {dates.map((d, i) => (
          <text key={d} x={toX(i)} y={H - 6} textAnchor="middle" fill="#6b7280" fontSize={10}>
            {new Date(d + 'T12:00:00').toLocaleDateString('en', { month: 'short', day: 'numeric' })}
          </text>
        ))}
        {/* 折线 */}
        {providers.map((p, pi) => {
          const points = byProvider[p].map((v, i) => `${toX(i)},${toY(v)}`).join(' ')
          const color = COLORS[pi % COLORS.length]
          return (
            <g key={p}>
              <polyline points={points} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
              {byProvider[p].map((v, i) => (
                <circle key={i} cx={toX(i)} cy={toY(v)} r={3} fill={color} />
              ))}
            </g>
          )
        })}
      </svg>
      {/* 图例 */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3">
        {providers.map((p, pi) => (
          <span key={p} className="flex items-center gap-1 text-xs text-gray-400">
            <span className="inline-block w-3 h-[2px]" style={{ backgroundColor: COLORS[pi % COLORS.length] }} />
            {p}
          </span>
        ))}
      </div>
    </section>
  )
}

function ValidKeyLineChart({ data }: { data: ProviderDailyItem[] }) {
  if (!data.length) return null

  // 分离 total 和各 provider 数据
  const dates = [...new Set(data.map((d) => d.date))]
  const allProviders = [...new Set(data.map((d) => d.provider))]
  const providers = allProviders.filter((p) => p !== 'total')

  const byProvider: Record<string, number[]> = {}
  for (const p of allProviders) {
    byProvider[p] = dates.map((d) => data.find((item) => item.date === d && item.provider === p)?.count ?? 0)
  }

  // provider 按总量降序排列（total 除外）
  providers.sort((a, b) => {
    const sumA = byProvider[a].reduce((s, v) => s + v, 0)
    const sumB = byProvider[b].reduce((s, v) => s + v, 0)
    return sumB - sumA
  })

  const maxVal = Math.max(...Object.values(byProvider).flat(), 1)

  const W = 700, H = 280
  const pad = { top: 20, right: 20, bottom: 30, left: 40 }
  const cw = W - pad.left - pad.right
  const ch = H - pad.top - pad.bottom

  const xStep = dates.length > 1 ? cw / (dates.length - 1) : cw
  const toX = (i: number) => pad.left + i * xStep
  const toY = (v: number) => pad.top + ch - (v / maxVal) * ch

  const yTicks = Array.from({ length: 5 }, (_, i) => Math.round((maxVal / 4) * i))

  return (
    <section className="bg-gray-900 border border-gray-800 rounded-lg p-6">
      <h3 className="font-semibold mb-4">Daily Valid Keys by Provider</h3>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" style={{ maxHeight: 320 }}>
        {/* 网格线 */}
        {yTicks.map((t) => (
          <g key={t}>
            <line x1={pad.left} y1={toY(t)} x2={W - pad.right} y2={toY(t)} stroke="#374151" strokeDasharray="4" />
            <text x={pad.left - 6} y={toY(t) + 4} textAnchor="end" fill="#6b7280" fontSize={10}>{t}</text>
          </g>
        ))}
        {/* X 轴标签 */}
        {dates.map((d, i) => (
          <text key={d} x={toX(i)} y={H - 6} textAnchor="middle" fill="#6b7280" fontSize={10}>
            {new Date(d + 'T12:00:00').toLocaleDateString('en', { month: 'short', day: 'numeric' })}
          </text>
        ))}
        {/* 各 provider 折线 */}
        {providers.map((p, pi) => {
          const points = byProvider[p].map((v, i) => `${toX(i)},${toY(v)}`).join(' ')
          const color = COLORS[pi % COLORS.length]
          return (
            <g key={p}>
              <polyline points={points} fill="none" stroke={color} strokeWidth={2} strokeLinejoin="round" />
              {byProvider[p].map((v, i) => (
                <circle key={i} cx={toX(i)} cy={toY(v)} r={3} fill={color} />
              ))}
            </g>
          )
        })}
        {/* total 折线 - 加粗白色虚线 */}
        {byProvider['total'] && (() => {
          const points = byProvider['total'].map((v, i) => `${toX(i)},${toY(v)}`).join(' ')
          return (
            <g>
              <polyline points={points} fill="none" stroke="#ffffff" strokeWidth={3} strokeLinejoin="round" strokeDasharray="8 4" />
              {byProvider['total'].map((v, i) => (
                <circle key={i} cx={toX(i)} cy={toY(v)} r={4} fill="#ffffff" stroke="#1f2937" strokeWidth={1.5} />
              ))}
            </g>
          )
        })()}
      </svg>
      {/* 图例 */}
      <div className="flex flex-wrap gap-x-4 gap-y-1 mt-3">
        {/* total 图例排在最前 */}
        <span className="flex items-center gap-1 text-xs text-gray-300 font-medium">
          <span className="inline-block w-4 h-[2px] border-t-2 border-dashed border-white" />
          total
        </span>
        {providers.map((p, pi) => (
          <span key={p} className="flex items-center gap-1 text-xs text-gray-400">
            <span className="inline-block w-3 h-[2px]" style={{ backgroundColor: COLORS[pi % COLORS.length] }} />
            {p}
          </span>
        ))}
      </div>
    </section>
  )
}
