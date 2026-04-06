import type { Stats } from '../types'

export default function StatsPanel({ stats }: { stats: Stats | null }) {
  if (!stats) return null
  const items = [
    { label: 'Leaks Today', value: stats.today_leaks },
    { label: 'Total Leaks', value: stats.total_leaks },
    { label: 'Repos Affected', value: stats.total_repos },
    { label: 'Repos Scanned', value: stats.total_repos_scanned },
  ]
  return (
    <div className="grid grid-cols-4 gap-4">
      {items.map((it) => (
        <div key={it.label} className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-emerald-400">
            {it.value.toLocaleString()}
          </div>
          <div className="text-xs text-gray-500 mt-1">{it.label}</div>
        </div>
      ))}
    </div>
  )
}
