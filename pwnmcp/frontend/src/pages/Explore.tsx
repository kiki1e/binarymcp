import { useEffect, useState, useCallback } from 'react'
import { fetchLeaks } from '../api/client'
import type { Leak } from '../types'
import LeakCard from '../components/LeakCard'
import ProviderFilter from '../components/ProviderFilter'

export default function Explore() {
  const [leaks, setLeaks] = useState<Leak[]>([])
  const [total, setTotal] = useState(0)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [provider, setProvider] = useState('')
  const [keyStatus, setKeyStatus] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async (silent = false) => {
    if (!silent) setLoading(true)
    setError('')
    try {
      const excludeGoogle = !provider && keyStatus !== 'filtered' ? 'google' : undefined
      const data = await fetchLeaks(page, 20, provider || undefined, keyStatus || undefined, excludeGoogle)
      setLeaks(data.leaks)
      setTotal(data.total)
      setHasMore(data.has_more)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load leaks')
    } finally {
      if (!silent) setLoading(false)
    }
  }, [page, provider, keyStatus])

  useEffect(() => { load() }, [load])

  // Auto-refresh every 30s
  useEffect(() => {
    const id = setInterval(() => load(true), 30000)
    return () => clearInterval(id)
  }, [load])

  const handleProvider = (p: string) => {
    setProvider(p)
    setPage(1)
  }

  const handleKeyStatus = (s: string) => {
    setKeyStatus(s)
    setPage(1)
  }

  const handleLeakUpdate = (updated: Leak) => {
    setLeaks(prev => prev.map(l => l.id === updated.id ? updated : l))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <span className="text-2xl font-bold text-emerald-400">{total.toLocaleString()}</span>
          <span className="text-gray-400 ml-2 text-sm">leaks found</span>
        </div>
        <span className="text-xs text-emerald-400 animate-pulse">Monitoring Live</span>
      </div>

      <div className="flex items-center gap-4 flex-wrap">
        <ProviderFilter current={provider} onChange={handleProvider} />
        <select
          value={keyStatus}
          onChange={(e) => handleKeyStatus(e.target.value)}
          className="bg-gray-800 text-gray-300 text-xs px-3 py-1.5 rounded border border-gray-700"
        >
          <option value="">All Status</option>
          <option value="valid">Valid</option>
          <option value="invalid">Invalid</option>
          <option value="unchecked">Unchecked</option>
          <option value="unsupported">Unsupported</option>
          <option value="filtered">Filtered</option>
        </select>
      </div>

      {error && (
        <div className="text-center text-red-400 py-4 bg-red-900/20 rounded-lg">{error}</div>
      )}

      {loading ? (
        <div className="text-center text-gray-500 py-12">Loading...</div>
      ) : (
        <div className="space-y-4">
          {leaks.map((l) => <LeakCard key={l.id} leak={l} onUpdate={handleLeakUpdate} />)}
          {leaks.length === 0 && (
            <div className="text-center text-gray-500 py-12">No leaks found</div>
          )}
        </div>
      )}

      <div className="flex justify-center gap-4">
        <button
          disabled={page <= 1}
          onClick={() => setPage((p) => p - 1)}
          className="px-4 py-2 bg-gray-800 rounded disabled:opacity-30 hover:bg-gray-700 text-sm"
        >
          Previous
        </button>
        <span className="px-4 py-2 text-sm text-gray-400">Page {page}</span>
        <button
          disabled={!hasMore}
          onClick={() => setPage((p) => p + 1)}
          className="px-4 py-2 bg-gray-800 rounded disabled:opacity-30 hover:bg-gray-700 text-sm"
        >
          Next
        </button>
      </div>
    </div>
  )
}
