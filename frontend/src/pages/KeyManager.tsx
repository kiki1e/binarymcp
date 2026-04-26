import { useState } from 'react'
import { importKeys, fetchKeyModels } from '../api/client'
import type { KeyInfo } from '../types'

const STATUS_STYLES: Record<string, string> = {
  valid: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-green-200 dark:border-green-800',
  invalid: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border-red-200 dark:border-red-800',
  unchecked: 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-400 border-gray-200 dark:border-gray-600',
  unsupported: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800',
}

export default function KeyManager() {
  const [input, setInput] = useState('')
  const [keys, setKeys] = useState<KeyInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [expandedModels, setExpandedModels] = useState<Record<number, any[]>>({})

  const handleImport = async () => {
    const keyList = input
      .split('\n')
      .map((k) => k.trim())
      .filter(Boolean)

    if (!keyList.length) return

    setError('')
    setLoading(true)
    try {
      const result = await importKeys(keyList)
      setKeys((prev) => [...result.results, ...prev])
      setInput('')
    } catch (e) {
      setError(e instanceof Error ? e.message : '导入失败')
    } finally {
      setLoading(false)
    }
  }

  const handleShowModels = async (keyId: number) => {
    if (expandedModels[keyId]) {
      setExpandedModels((prev) => {
        const next = { ...prev }
        delete next[keyId]
        return next
      })
      return
    }
    try {
      const data = await fetchKeyModels(keyId)
      setExpandedModels((prev) => ({ ...prev, [keyId]: data.models }))
    } catch {
      setExpandedModels((prev) => ({ ...prev, [keyId]: [] }))
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 py-8 px-4">
      <div className="max-w-6xl mx-auto space-y-6">

        {/* Header */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 bg-gradient-to-br from-amber-500 to-orange-600 rounded-2xl flex items-center justify-center shadow-lg">
              <span className="text-white text-3xl">🔑</span>
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">API 密钥管理</h1>
              <p className="text-gray-600 dark:text-gray-400 mt-1">导入和管理 AI 模型的 API 密钥</p>
            </div>
          </div>
        </div>

        {/* Import Section */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8">
          <div className="flex items-center gap-3 mb-6">
            <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
              </svg>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">导入 API 密钥</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                每行一个密钥，系统将自动检测提供商并验证
              </p>
            </div>
          </div>

          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="sk-proj-xxx&#10;sk-ant-xxx&#10;sk-xxx&#10;&#10;支持 OpenAI、Anthropic、DeepSeek 等"
            className="w-full h-40 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-xl p-4 text-sm text-gray-900 dark:text-white font-mono placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none transition"
          />

          {error && (
            <div className="mt-4 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl flex items-start gap-3">
              <svg className="w-5 h-5 text-red-600 dark:text-red-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span className="text-sm text-red-600 dark:text-red-400">{error}</span>
            </div>
          )}

          <button
            onClick={handleImport}
            disabled={loading || !input.trim()}
            className="mt-4 w-full py-3.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:from-gray-400 disabled:to-gray-500 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition shadow-lg hover:shadow-xl flex items-center justify-center gap-2"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                <span>导入并验证中...</span>
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>导入并验证</span>
              </>
            )}
          </button>
        </div>

        {/* Key List */}
        {keys.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                已导入的密钥 ({keys.length})
              </h3>
            </div>
            <div className="space-y-4">
              {keys.map((k) => (
                <div key={k.id} className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 rounded-xl p-5 border border-gray-200 dark:border-gray-700">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <code className="text-sm font-mono font-semibold text-gray-900 dark:text-white bg-white dark:bg-gray-900 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 break-all inline-block">
                        {k.raw_key.slice(0, 20)}...{k.raw_key.slice(-8)}
                      </code>
                    </div>
                    <div className="flex items-center gap-2 ml-4">
                      <span className={`text-xs px-3 py-1.5 rounded-lg font-medium border ${STATUS_STYLES[k.key_status] || STATUS_STYLES.unchecked}`}>
                        {k.key_status === 'valid' ? '✓ 有效' :
                         k.key_status === 'invalid' ? '✗ 无效' :
                         k.key_status === 'unsupported' ? '- 不支持' : '? 未检查'}
                      </span>
                      <span className="text-xs px-3 py-1.5 rounded-lg bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium border border-blue-200 dark:border-blue-800">
                        {k.verified_provider || k.provider}
                      </span>
                      {k.key_status === 'valid' && (
                        <button
                          onClick={() => handleShowModels(k.id)}
                          className="text-xs px-3 py-1.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-medium transition"
                        >
                          {expandedModels[k.id] ? '隐藏模型' : '查看模型'}
                        </button>
                      )}
                    </div>
                  </div>

                  {/* Inline models preview */}
                  {k.models.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-3">
                      {k.models.slice(0, 5).map((m) => (
                        <span key={m.id} className="text-xs px-2 py-1 bg-white dark:bg-gray-900 text-gray-700 dark:text-gray-300 rounded-lg border border-gray-200 dark:border-gray-700 font-mono">
                          {m.id}
                        </span>
                      ))}
                      {k.models.length > 5 && (
                        <span className="text-xs px-2 py-1 text-gray-500 dark:text-gray-400">
                          +{k.models.length - 5} 个模型
                        </span>
                      )}
                    </div>
                  )}

                  {/* Expanded model list */}
                  {expandedModels[k.id] && (
                    <div className="bg-white dark:bg-gray-900 rounded-xl p-4 mt-3 border border-gray-200 dark:border-gray-700 max-h-60 overflow-y-auto">
                      {expandedModels[k.id].length > 0 ? (
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                          {expandedModels[k.id].map((m: any) => (
                            <div key={m.id || m} className="text-xs px-3 py-2 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 text-green-700 dark:text-green-400 rounded-lg border border-green-200 dark:border-green-800 font-mono">
                              {m.id || m}
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="text-center py-4">
                          <span className="text-sm text-gray-500 dark:text-gray-400">暂无可用模型</span>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {keys.length === 0 && !loading && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-16 text-center">
            <div className="w-24 h-24 mx-auto mb-6 bg-gray-100 dark:bg-gray-900 rounded-full flex items-center justify-center">
              <span className="text-5xl">🔑</span>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">暂无导入的密钥</h3>
            <p className="text-gray-600 dark:text-gray-400">在上方输入框中粘贴 API 密钥并点击导入</p>
          </div>
        )}
      </div>
    </div>
  )
}
