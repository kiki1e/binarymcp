import { useEffect, useState } from 'react'
import { fetchAvailableModels, fetchIDAStatus } from '../api/client'
import type { AvailableModelsResponse, IDAStatus } from '../types'

export default function ModelPanel() {
  const [models, setModels] = useState<AvailableModelsResponse | null>(null)
  const [ida, setIda] = useState<IDAStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [showAddModel, setShowAddModel] = useState(false)
  const [newApiKey, setNewApiKey] = useState('')
  const [newBaseUrl, setNewBaseUrl] = useState('')
  const [newProvider, setNewProvider] = useState('openai')

  useEffect(() => {
    loadData()
  }, [])

  const loadData = () => {
    setLoading(true)
    Promise.all([
      fetchAvailableModels().then(setModels).catch(() => setModels({ models: [], total: 0 })),
      fetchIDAStatus().then(setIda).catch(() => setIda({ status: 'disconnected', error: 'Bridge unreachable' })),
    ]).finally(() => setLoading(false))
  }

  const handleAddModel = async () => {
    // TODO: 实现添加模型API
    alert('添加模型功能开发中')
    setShowAddModel(false)
  }

  if (loading) return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-blue-600 mx-auto mb-4"></div>
        <p className="text-gray-600 dark:text-gray-400 text-lg">加载模型配置...</p>
      </div>
    </div>
  )

  // Group models by provider
  const byProvider: Record<string, Array<{ id: string; provider: string; owned_by: string; key_count: number }>> = {}
  for (const m of models?.models || []) {
    const p = m.provider || 'unknown'
    if (!byProvider[p]) byProvider[p] = []
    byProvider[p].push(m)
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 py-8 px-4">
      <div className="max-w-7xl mx-auto space-y-6">

        {/* Header */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 bg-gradient-to-br from-purple-500 to-pink-600 rounded-2xl flex items-center justify-center shadow-lg">
                <span className="text-white text-3xl">🤖</span>
              </div>
              <div>
                <h1 className="text-3xl font-bold text-gray-900 dark:text-white">AI 模型管理</h1>
                <p className="text-gray-600 dark:text-gray-400 mt-1">配置和管理分析使用的 AI 模型</p>
              </div>
            </div>
            <button
              onClick={() => setShowAddModel(true)}
              className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-xl transition shadow-lg hover:shadow-xl"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              添加模型
            </button>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-blue-500 to-blue-600 rounded-xl flex items-center justify-center">
                <span className="text-white text-2xl">📊</span>
              </div>
              <div className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                {models?.total || 0}
              </div>
            </div>
            <h3 className="text-sm font-medium text-gray-600 dark:text-gray-400">可用模型</h3>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-purple-500 to-purple-600 rounded-xl flex items-center justify-center">
                <span className="text-white text-2xl">🏢</span>
              </div>
              <div className="text-3xl font-bold bg-gradient-to-r from-purple-600 to-pink-600 bg-clip-text text-transparent">
                {Object.keys(byProvider).length}
              </div>
            </div>
            <h3 className="text-sm font-medium text-gray-600 dark:text-gray-400">服务提供商</h3>
          </div>

          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center justify-between mb-4">
              <div className="w-12 h-12 bg-gradient-to-br from-green-500 to-emerald-600 rounded-xl flex items-center justify-center">
                <span className="text-white text-2xl">🔧</span>
              </div>
              <div className={`text-3xl font-bold ${ida?.status === 'connected' ? 'text-green-600' : 'text-red-600'}`}>
                {ida?.status === 'connected' ? '在线' : '离线'}
              </div>
            </div>
            <h3 className="text-sm font-medium text-gray-600 dark:text-gray-400">IDA Pro 状态</h3>
          </div>
        </div>

        {/* IDA Status */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className={`w-3 h-3 rounded-full ${ida?.status === 'connected' ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">IDA Pro 连接</h3>
          </div>
          <div className="bg-gray-50 dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
            <p className="text-sm text-gray-700 dark:text-gray-300 mb-2">
              {ida?.status === 'connected'
                ? `✓ 已连接到 ${ida.ida_url}`
                : `✗ 未连接${ida?.error ? `: ${ida.error}` : ''}`
              }
            </p>
            {ida?.status !== 'connected' && (
              <p className="text-xs text-gray-500 dark:text-gray-400">
                💡 在 Windows 上启动 IDA Pro 并加载 ida_server.py 脚本以启用 IDA 反编译功能
              </p>
            )}
          </div>
        </div>

        {/* Models by Provider */}
        {Object.entries(byProvider)
          .sort((a, b) => b[1].length - a[1].length)
          .map(([provider, providerModels]) => (
            <div key={provider} className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-6">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
                  <span className="px-3 py-1 bg-gradient-to-r from-purple-600 to-pink-600 text-white rounded-lg text-sm">
                    {provider}
                  </span>
                  <span className="text-gray-500 dark:text-gray-400 text-sm">
                    {providerModels.length} 个模型
                  </span>
                </h3>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {providerModels.map((m) => (
                  <div
                    key={m.id}
                    className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 hover:shadow-lg transition"
                  >
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex-1">
                        <h4 className="text-sm font-mono font-semibold text-gray-900 dark:text-white mb-1 break-all">
                          {m.id}
                        </h4>
                        <p className="text-xs text-gray-500 dark:text-gray-400">
                          {m.owned_by || 'Unknown'}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 bg-white dark:bg-gray-900 rounded-lg px-3 py-2 border border-gray-200 dark:border-gray-700">
                        <div className="text-xs text-gray-500 dark:text-gray-400">API 密钥</div>
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">
                          {m.key_count} 个
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}

        {models?.total === 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-16 text-center">
            <div className="w-24 h-24 mx-auto mb-6 bg-gray-100 dark:bg-gray-900 rounded-full flex items-center justify-center">
              <span className="text-5xl">🤖</span>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">暂无可用模型</h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">请先在密钥管理页面导入有效的 API 密钥</p>
            <button
              onClick={() => setShowAddModel(true)}
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-xl transition shadow-lg"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              添加第一个模型
            </button>
          </div>
        )}

        {/* Add Model Modal */}
        {showAddModel && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 max-w-md w-full p-8">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white">添加 AI 模型</h3>
                <button
                  onClick={() => setShowAddModel(false)}
                  className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition"
                >
                  <svg className="w-6 h-6 text-gray-600 dark:text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    服务提供商
                  </label>
                  <select
                    value={newProvider}
                    onChange={(e) => setNewProvider(e.target.value)}
                    className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
                  >
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                    <option value="deepseek">DeepSeek</option>
                    <option value="custom">自定义</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    API 密钥
                  </label>
                  <input
                    type="password"
                    value={newApiKey}
                    onChange={(e) => setNewApiKey(e.target.value)}
                    placeholder="sk-..."
                    className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Base URL (可选)
                  </label>
                  <input
                    type="text"
                    value={newBaseUrl}
                    onChange={(e) => setNewBaseUrl(e.target.value)}
                    placeholder="https://api.openai.com/v1"
                    className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  />
                </div>

                <div className="flex gap-3 pt-4">
                  <button
                    onClick={() => setShowAddModel(false)}
                    className="flex-1 px-4 py-3 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-900 dark:text-white font-medium rounded-xl transition"
                  >
                    取消
                  </button>
                  <button
                    onClick={handleAddModel}
                    className="flex-1 px-4 py-3 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white font-semibold rounded-xl transition shadow-lg"
                  >
                    添加
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
