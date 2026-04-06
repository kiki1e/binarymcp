import { useState } from 'react'
import { importKeys, fetchKeyModels } from '../api/client'
import type { KeyInfo } from '../types'

const STATUS_STYLES: Record<string, string> = {
  valid: 'bg-emerald-900/50 text-emerald-400',
  invalid: 'bg-red-900/50 text-red-400',
  unchecked: 'bg-gray-700 text-gray-400',
  unsupported: 'bg-yellow-900/50 text-yellow-400',
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
      setError(e instanceof Error ? e.message : 'Import failed')
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
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-emerald-400">API Key Manager</h1>

      {/* Import Section */}
      <div className="bg-gray-900 border border-gray-800 rounded-lg p-6 space-y-4">
        <h3 className="font-semibold text-sm">Import API Keys</h3>
        <p className="text-xs text-gray-500">
          Paste API keys below (one per line). The system will auto-detect the provider and validate each key.
        </p>
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="sk-proj-xxx&#10;sk-ant-xxx&#10;sk-xxx"
          className="w-full h-32 bg-gray-800 border border-gray-700 rounded-lg p-3 text-sm text-gray-200 font-mono focus:border-emerald-500 focus:outline-none resize-none"
        />
        {error && (
          <div className="text-red-400 text-sm bg-red-900/20 rounded p-2">{error}</div>
        )}
        <button
          onClick={handleImport}
          disabled={loading || !input.trim()}
          className="px-6 py-2 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 rounded text-sm font-medium"
        >
          {loading ? 'Importing...' : 'Import & Validate'}
        </button>
      </div>

      {/* Key List */}
      {keys.length > 0 && (
        <div className="space-y-3">
          <h3 className="font-semibold text-sm text-gray-400">Imported Keys ({keys.length})</h3>
          {keys.map((k) => (
            <div key={k.id} className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-2">
              <div className="flex items-center justify-between">
                <code className="text-sm text-amber-400 bg-gray-800 px-2 py-1 rounded break-all">
                  {k.raw_key.slice(0, 20)}...{k.raw_key.slice(-8)}
                </code>
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-1 rounded-full ${STATUS_STYLES[k.key_status] || STATUS_STYLES.unchecked}`}>
                    {k.key_status}
                  </span>
                  <span className="text-xs px-2 py-1 rounded-full bg-gray-800 text-gray-300">
                    {k.verified_provider || k.provider}
                  </span>
                  {k.key_status === 'valid' && (
                    <button
                      onClick={() => handleShowModels(k.id)}
                      className="text-xs px-2 py-1 rounded-full bg-blue-700 hover:bg-blue-600 text-white"
                    >
                      {expandedModels[k.id] ? 'Hide Models' : 'Show Models'}
                    </button>
                  )}
                </div>
              </div>

              {/* Inline models */}
              {k.models.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-1">
                  {k.models.slice(0, 5).map((m) => (
                    <span key={m.id} className="text-xs px-2 py-0.5 bg-gray-800 text-gray-300 rounded">
                      {m.id}
                    </span>
                  ))}
                  {k.models.length > 5 && (
                    <span className="text-xs text-gray-500">+{k.models.length - 5} more</span>
                  )}
                </div>
              )}

              {/* Expanded model list */}
              {expandedModels[k.id] && (
                <div className="bg-gray-800 rounded p-3 mt-2 max-h-40 overflow-y-auto">
                  {expandedModels[k.id].length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                      {expandedModels[k.id].map((m: any) => (
                        <span key={m.id || m} className="text-xs px-2 py-0.5 bg-gray-700 text-emerald-400 rounded">
                          {m.id || m}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <span className="text-xs text-gray-500">No models available</span>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
