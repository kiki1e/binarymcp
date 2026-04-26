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
      setError(e instanceof Error ? e.message : '加载失败')
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
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 py-8 px-4">
      <div className="max-w-7xl mx-auto space-y-6">

        {/* Header */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8">
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 bg-gradient-to-br from-green-500 to-emerald-600 rounded-2xl flex items-center justify-center shadow-lg">
                <span className="text-white text-3xl">🔑</span>
              </div>
              <div>
                <h1 className="text-3xl font-bold text-gray-900 dark:text-white">密钥监控中心</h1>
                <p className="text-gray-600 dark:text-gray-400 mt-1">实时监控 GitHub API 密钥泄露</p>
              </div>
            </div>
            <div className="text-right">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <span className="text-sm text-green-600 dark:text-green-400 font-medium">实时监控中</span>
              </div>
              <div className="text-3xl font-bold bg-gradient-to-r from-green-600 to-emerald-600 bg-clip-text text-transparent">
                {total.toLocaleString()}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">已发现泄露</div>
            </div>
          </div>

          {/* Filters */}
          <div className="flex items-center gap-4 flex-wrap">
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">服务提供商</label>
              <ProviderFilter current={provider} onChange={handleProvider} />
            </div>
            <div className="w-48">
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">密钥状态</label>
              <select
                value={keyStatus}
                onChange={(e) => handleKeyStatus(e.target.value)}
                className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-xl text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-green-500 transition"
              >
                <option value="">全部状态</option>
                <option value="valid">✓ 有效</option>
                <option value="invalid">✗ 无效</option>
                <option value="unchecked">? 未检查</option>
                <option value="unsupported">- 不支持</option>
                <option value="filtered">⊘ 已过滤</option>
              </select>
            </div>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-2xl p-6 flex items-start gap-3">
            <svg className="w-6 h-6 text-red-600 dark:text-red-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <div>
              <h3 className="text-red-800 dark:text-red-300 font-semibold mb-1">加载失败</h3>
              <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>
            </div>
          </div>
        )}

        {/* Loading */}
        {loading ? (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-16 text-center">
            <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-green-600 mx-auto mb-4"></div>
            <p className="text-gray-600 dark:text-gray-400 text-lg">加载密钥数据...</p>
          </div>
        ) : (
          <>
            {/* Leaks List */}
            <div className="space-y-4">
              {leaks.map((l) => <LeakCard key={l.id} leak={l} onUpdate={handleLeakUpdate} />)}
              {leaks.length === 0 && (
                <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-16 text-center">
                  <div className="w-24 h-24 mx-auto mb-6 bg-gray-100 dark:bg-gray-900 rounded-full flex items-center justify-center">
                    <span className="text-5xl">🔍</span>
                  </div>
                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">暂无泄露记录</h3>
                  <p className="text-gray-600 dark:text-gray-400">系统正在实时监控中，发现泄露将立即显示</p>
                </div>
              )}
            </div>

            {/* Pagination */}
            {leaks.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-6">
                <div className="flex items-center justify-between">
                  <button
                    disabled={page <= 1}
                    onClick={() => setPage((p) => p - 1)}
                    className="flex items-center gap-2 px-6 py-3 bg-gray-100 dark:bg-gray-900 hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed rounded-xl transition font-medium text-gray-900 dark:text-white"
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                    </svg>
                    上一页
                  </button>

                  <div className="flex items-center gap-2">
                    <span className="px-4 py-2 bg-gradient-to-r from-green-600 to-emerald-600 text-white rounded-lg font-semibold">
                      第 {page} 页
                    </span>
                    {hasMore && (
                      <span className="text-sm text-gray-500 dark:text-gray-400">还有更多</span>
                    )}
                  </div>

                  <button
                    disabled={!hasMore}
                    onClick={() => setPage((p) => p + 1)}
                    className="flex items-center gap-2 px-6 py-3 bg-gray-100 dark:bg-gray-900 hover:bg-gray-200 dark:hover:bg-gray-700 disabled:opacity-30 disabled:cursor-not-allowed rounded-xl transition font-medium text-gray-900 dark:text-white"
                  >
                    下一页
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                    </svg>
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
