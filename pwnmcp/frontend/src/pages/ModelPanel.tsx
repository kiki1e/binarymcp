import { useEffect, useState } from 'react'
import { fetchAvailableModels, fetchIDAStatus } from '../api/client'
import type { AvailableModelsResponse, IDAStatus } from '../types'

export default function ModelPanel() {
  const [models, setModels] = useState<AvailableModelsResponse | null>(null)
  const [ida, setIda] = useState<IDAStatus | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    Promise.all([
      fetchAvailableModels().then(setModels).catch(() => setModels({ models: [], total: 0 })),
      fetchIDAStatus().then(setIda).catch(() => setIda({ status: 'disconnected', error: 'Bridge unreachable' })),
    ]).finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-gray-500 text-center py-12">Loading...</div>

  // Group models by provider
  const byProvider: Record<string, typeof models.models> = {}
  for (const m of models?.models || []) {
    const p = m.provider || 'unknown'
    if (!byProvider[p]) byProvider[p] = []
    byProvider[p].push(m)
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-emerald-400">Model Overview</h1>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-emerald-400">{models?.total || 0}</div>
          <div className="text-xs text-gray-500 mt-1">Available Models</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center">
          <div className="text-2xl font-bold text-blue-400">{Object.keys(byProvider).length}</div>
          <div className="text-xs text-gray-500 mt-1">Providers</div>
        </div>
        <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 text-center">
          <div className={`text-2xl font-bold ${ida?.status === 'connected' ? 'text-emerald-400' : 'text-red-400'}`}>
            {ida?.status === 'connected' ? 'Online' : 'Offline'}
          </div>
          <div className="text-xs text-gray-500 mt-1">IDA Pro</div>
        </div>
      </div>

      {/* IDA Status */}
      <section className="bg-gray-900 border border-gray-800 rounded-lg p-4">
        <h3 className="font-semibold text-sm mb-2">IDA Pro Connection</h3>
        <div className="flex items-center gap-3">
          <div className={`w-3 h-3 rounded-full ${ida?.status === 'connected' ? 'bg-emerald-400' : 'bg-red-400'}`} />
          <span className="text-sm text-gray-300">
            {ida?.status === 'connected'
              ? `Connected to ${ida.ida_url}`
              : `Disconnected${ida?.error ? `: ${ida.error}` : ''}`
            }
          </span>
        </div>
        {ida?.status !== 'connected' && (
          <p className="text-xs text-gray-500 mt-2">
            Start IDA Pro on Windows and load the ida_server.py script to enable IDA decompilation.
          </p>
        )}
      </section>

      {/* Models by Provider */}
      {Object.entries(byProvider)
        .sort((a, b) => b[1].length - a[1].length)
        .map(([provider, providerModels]) => (
          <section key={provider} className="bg-gray-900 border border-gray-800 rounded-lg p-4">
            <h3 className="font-semibold text-sm mb-3">
              <span className="text-emerald-400">{provider}</span>
              <span className="text-gray-500 ml-2">({providerModels.length} models)</span>
            </h3>
            <div className="flex flex-wrap gap-2">
              {providerModels.map((m) => (
                <div
                  key={m.id}
                  className="bg-gray-800 rounded-lg px-3 py-2 text-sm space-y-0.5"
                >
                  <div className="text-gray-200 font-mono text-xs">{m.id}</div>
                  <div className="text-xs text-gray-500">
                    {m.key_count} key{m.key_count > 1 ? 's' : ''}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}

      {models?.total === 0 && (
        <div className="text-center text-gray-500 py-8">
          No models available. Import valid API keys in the Keys page first.
        </div>
      )}
    </div>
  )
}
