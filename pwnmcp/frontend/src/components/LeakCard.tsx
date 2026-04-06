import { useState } from 'react'
import type { Leak, BalanceInfo } from '../types'
import { validateLeak, fetchBalance } from '../api/client'

function timeAgo(dateStr: string): string {
  const utcStr = dateStr.endsWith('Z') ? dateStr : dateStr + 'Z'
  const diff = Date.now() - new Date(utcStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

const STATUS_STYLES: Record<string, string> = {
  valid: 'bg-emerald-900/50 text-emerald-400',
  invalid: 'bg-red-900/50 text-red-400',
  unchecked: 'bg-gray-700 text-gray-400',
  unsupported: 'bg-yellow-900/50 text-yellow-400',
}

const STATUS_LABELS: Record<string, string> = {
  valid: 'Valid',
  invalid: 'Invalid',
  unchecked: 'Unchecked',
  unsupported: 'Unsupported',
}

interface Props {
  leak: Leak
  onUpdate?: (updated: Leak) => void
}

export default function LeakCard({ leak, onUpdate }: Props) {
  const [validating, setValidating] = useState(false)
  const [balanceInfos, setBalanceInfos] = useState<BalanceInfo[] | null>(null)
  const status = leak.key_status || 'unchecked'

  const handleValidate = async () => {
    setValidating(true)
    try {
      const updated = await validateLeak(leak.id)
      onUpdate?.(updated)
      if (updated.provider === 'deepseek' && updated.key_status === 'valid') {
        const data = await fetchBalance(leak.id)
        setBalanceInfos(data.balance_infos)
      }
    } catch { /* ignore */ }
    setValidating(false)
  }

  return (
    <div className="bg-gray-900 border border-gray-800 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <code className="text-sm text-amber-400 bg-gray-800 px-2 py-1 rounded break-all">
          {leak.raw_key}
        </code>
        <div className="flex items-center gap-2 ml-2 shrink-0">
          <span className={`text-xs px-2 py-1 rounded-full ${STATUS_STYLES[status] || STATUS_STYLES.unchecked}`}>
            {STATUS_LABELS[status] || 'Unchecked'}
          </span>
          <span className="text-xs px-2 py-1 rounded-full bg-gray-800 text-gray-300">
            {leak.verified_provider || leak.provider}
          </span>
          <button
              onClick={handleValidate}
              disabled={validating}
              className="text-xs px-2 py-1 rounded-full bg-blue-700 hover:bg-blue-600 disabled:bg-gray-700 disabled:cursor-wait text-white"
            >
              {validating ? '...' : 'Validate'}
            </button>
        </div>
      </div>
      <div className="text-sm text-gray-400 space-y-1">
        <div>
          Repo:{' '}
          <a
            href={leak.repo_url}
            target="_blank"
            rel="noreferrer"
            className="text-emerald-400 hover:underline"
          >
            {leak.repo_owner}/{leak.repo_name}
          </a>
        </div>
        <div>
          Path:{' '}
          <a
            href={`${leak.repo_url}/blob/HEAD/${leak.file_path}`}
            target="_blank"
            rel="noreferrer"
            className="text-xs text-emerald-400 hover:underline"
          >
            {leak.file_path}
          </a>
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-500">
          <span>Detected: {timeAgo(leak.leak_detected_at)}</span>
          {leak.leak_introduced_at && (
            <span>Added: {timeAgo(leak.leak_introduced_at)}</span>
          )}
          {leak.validated_at && (
            <span>Validated: {timeAgo(leak.validated_at)}</span>
          )}
        </div>
        {leak.verified_url && (leak.verified_provider || leak.provider) !== 'deepseek' && (
          <div className="text-xs">
            API:{' '}
            <span className="text-cyan-400">{leak.verified_url}</span>
          </div>
        )}
        {balanceInfos && (
          <div className="flex items-center gap-3 text-xs">
            {balanceInfos.map((b) => {
              const sym = b.currency === 'CNY' ? '\u00a5' : '$'
              const bal = parseFloat(b.total_balance)
              return bal > 0 ? (
                <span key={b.currency} className="text-emerald-400 font-medium">
                  {sym}{b.total_balance} {b.currency}
                </span>
              ) : (
                <span key={b.currency} className="text-gray-500">
                  {sym}{b.total_balance} {b.currency}
                </span>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}
