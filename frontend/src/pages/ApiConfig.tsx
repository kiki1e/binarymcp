import { useState } from 'react'

interface ApiConfig {
  provider: string
  apiKey: string
  baseUrl: string
  model: string
}

export default function ApiConfig() {
  const [configs, setConfigs] = useState<ApiConfig[]>(() => {
    try {
      const saved = localStorage.getItem('api_configs')
      return saved ? JSON.parse(saved) : []
    } catch { return [] }
  })
  const [showForm, setShowForm] = useState(false)
  const [editingIndex, setEditingIndex] = useState<number | null>(null)
  const [formData, setFormData] = useState<ApiConfig>({
    provider: '',
    apiKey: '',
    baseUrl: '',
    model: ''
  })

  const openAddForm = () => {
    setEditingIndex(null)
    setFormData({ provider: '', apiKey: '', baseUrl: '', model: '' })
    setShowForm(true)
  }

  const openEditForm = (index: number) => {
    setEditingIndex(index)
    setFormData({ ...configs[index] })
    setShowForm(true)
  }

  const closeForm = () => {
    setShowForm(false)
    setEditingIndex(null)
  }

  const handleSaveConfig = () => {
    if (!formData.apiKey || !formData.model || !formData.baseUrl) {
      alert('请填写完整的配置信息（API Key / Base URL / 模型名称为必填）')
      return
    }

    const entry = { ...formData, provider: formData.provider || 'custom' }
    let saved: ApiConfig[]

    if (editingIndex !== null) {
      saved = configs.map((c, i) => (i === editingIndex ? entry : c))
      alert('✓ API配置已更新')
    } else {
      saved = [...configs, entry]
      alert('✓ API配置已添加')
    }

    setConfigs(saved)
    localStorage.setItem('api_configs', JSON.stringify(saved))
    closeForm()
  }

  const handleDeleteConfig = (index: number) => {
    if (confirm('确定要删除这个配置吗？')) {
      const updated = configs.filter((_, i) => i !== index)
      setConfigs(updated)
      localStorage.setItem('api_configs', JSON.stringify(updated))
    }
  }

  const handleSetDefault = (index: number) => {
    localStorage.setItem('default_api_config', JSON.stringify(configs[index]))
    alert('✓ 已设置为默认配置')
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 py-8 px-4">
      <div className="max-w-5xl mx-auto space-y-6">

        {/* Header */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="w-16 h-16 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-2xl flex items-center justify-center shadow-lg">
                <span className="text-white text-3xl">⚙️</span>
              </div>
              <div>
                <h1 className="text-3xl font-bold text-gray-900 dark:text-white">API 配置</h1>
                <p className="text-gray-600 dark:text-gray-400 mt-1">配置自定义 AI 模型用于赛题分析与对话</p>
              </div>
            </div>
            <button
              onClick={openAddForm}
              className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold rounded-xl transition shadow-lg hover:shadow-xl"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              添加配置
            </button>
          </div>
        </div>

        {/* Config List */}
        {configs.length > 0 ? (
          <div className="space-y-4">
            {configs.map((config, index) => (
              <div key={index} className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 p-6">
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-3">
                      <span className="px-3 py-1 bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg text-sm font-semibold">
                        {config.provider.toUpperCase() || 'CUSTOM'}
                      </span>
                      <span className="text-sm text-gray-600 dark:text-gray-400">
                        模型: <span className="font-mono font-semibold text-gray-900 dark:text-white">{config.model}</span>
                      </span>
                    </div>
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-500 dark:text-gray-400 w-20">API Key:</span>
                        <code className="text-sm font-mono bg-gray-100 dark:bg-gray-900 px-3 py-1 rounded border border-gray-200 dark:border-gray-700">
                          {config.apiKey.slice(0, 20)}...{config.apiKey.slice(-8)}
                        </code>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm text-gray-500 dark:text-gray-400 w-20">Base URL:</span>
                        <span className="text-sm font-mono text-gray-700 dark:text-gray-300">{config.baseUrl}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <button
                      onClick={() => openEditForm(index)}
                      className="px-4 py-2 bg-amber-600 hover:bg-amber-700 text-white text-sm font-medium rounded-lg transition"
                    >
                      编辑
                    </button>
                    <button
                      onClick={() => handleSetDefault(index)}
                      className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition"
                    >
                      设为默认
                    </button>
                    <button
                      onClick={() => handleDeleteConfig(index)}
                      className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium rounded-lg transition"
                    >
                      删除
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-16 text-center">
            <div className="w-24 h-24 mx-auto mb-6 bg-gray-100 dark:bg-gray-900 rounded-full flex items-center justify-center">
              <span className="text-5xl">⚙️</span>
            </div>
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">暂无 API 配置</h3>
            <p className="text-gray-600 dark:text-gray-400 mb-6">添加 API 配置以开始使用赛题分析功能和 AI 对话</p>
            <button
              onClick={openAddForm}
              className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold rounded-xl transition shadow-lg"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              添加第一个配置
            </button>
          </div>
        )}

        {/* Add / Edit Form Modal */}
        {showForm && (
          <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl border border-gray-200 dark:border-gray-700 max-w-2xl w-full p-8 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white">
                  {editingIndex !== null ? '编辑 API 配置' : '添加 API 配置'}
                </h3>
                <button
                  onClick={closeForm}
                  className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition"
                >
                  <svg className="w-6 h-6 text-gray-600 dark:text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>

              <div className="space-y-5">
                {/* Provider name (optional label) */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    服务提供商 <span className="text-gray-400 font-normal">(可选)</span>
                  </label>
                  <input
                    type="text"
                    value={formData.provider}
                    onChange={(e) => setFormData({ ...formData, provider: e.target.value })}
                    placeholder="例如: deepseek, openai, 留空则显示为 CUSTOM"
                    className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    API 密钥 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="password"
                    value={formData.apiKey}
                    onChange={(e) => setFormData({ ...formData, apiKey: e.target.value })}
                    placeholder="sk-..."
                    className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Base URL <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.baseUrl}
                    onChange={(e) => setFormData({ ...formData, baseUrl: e.target.value })}
                    placeholder="https://api.openai.com/v1"
                    className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    模型名称 <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData.model}
                    onChange={(e) => setFormData({ ...formData, model: e.target.value })}
                    placeholder="gpt-4o / deepseek-chat / claude-sonnet-4-20250514"
                    className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                <div className="flex gap-3 pt-4">
                  <button
                    onClick={closeForm}
                    className="flex-1 px-4 py-3 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-900 dark:text-white font-medium rounded-xl transition"
                  >
                    取消
                  </button>
                  <button
                    onClick={handleSaveConfig}
                    className="flex-1 px-4 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white font-semibold rounded-xl transition shadow-lg"
                  >
                    {editingIndex !== null ? '保存修改' : '添加配置'}
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
