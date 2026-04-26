import { useState } from 'react'
import type { Leak, BalanceInfo } from '../types'
import { validateLeak, fetchBalance } from '../api/client'

function timeAgo(dateStr: string): string {
  const utcStr = dateStr.endsWith('Z') ? dateStr : dateStr + 'Z'
  const diff = Date.now() - new Date(utcStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return '刚刚'
  if (mins < 60) return `${mins}分钟前`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}小时前`
  return `${Math.floor(hrs / 24)}天前`
}

const STATUS_STYLES: Record<string, string> = {
  valid: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 border-green-200 dark:border-green-800',
  invalid: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 border-red-200 dark:border-red-800',
  unchecked: 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-400 border-gray-200 dark:border-gray-600',
  unsupported: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400 border-yellow-200 dark:border-yellow-800',
}

const STATUS_LABELS: Record<string, string> = {
  valid: '✓ 有效',
  invalid: '✗ 无效',
  unchecked: '? 未检查',
  unsupported: '- 不支持',
}

interface Props {
  leak: Leak
  onUpdate?: (updated: Leak) => void
}

export default function LeakCard({ leak, onUpdate }: Props) {
  const [validating, setValidating] = useState(false)
  const [balanceInfos, setBalanceInfos] = useState<BalanceInfo[] | null>(null)
  const [showBalance, setShowBalance] = useState(false)
  const [loadingBalance, setLoadingBalance] = useState(false)
  const [models, setModels] = useState<string[]>([])
  const [showModels, setShowModels] = useState(false)
  const status = leak.key_status || 'unchecked'

  const handleValidate = async () => {
    setValidating(true)
    try {
      const updated = await validateLeak(leak.id)
      onUpdate?.(updated)
    } catch { /* ignore */ }
    setValidating(false)
  }

  const handleCheckBalance = async () => {
    if (showBalance) {
      setShowBalance(false)
      return
    }

    setLoadingBalance(true)
    setShowBalance(true)
    try {
      const data = await fetchBalance(leak.id)
      setBalanceInfos(data.balance_infos)
    } catch (e) {
      setBalanceInfos(null)
    }
    setLoadingBalance(false)
  }

  const handleCheckModels = async () => {
    if (showModels) {
      setShowModels(false)
      return
    }

    setShowModels(true)
    // TODO: 实现获取可用模型的API
    // 暂时显示示例数据
    setModels(['deepseek-chat', 'deepseek-coder'])
  }

  const handleCopyKey = () => {
    navigator.clipboard.writeText(leak.raw_key)
    alert('✓ 密钥已复制到剪贴板')
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 p-6 hover:shadow-xl transition">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 mr-4">
          <div className="flex items-center gap-2 mb-2">
            <code className="text-sm font-mono font-semibold text-gray-900 dark:text-white bg-gray-100 dark:bg-gray-900 px-3 py-2 rounded-lg border border-gray-200 dark:border-gray-700 break-all">
              {leak.raw_key.slice(0, 30)}...{leak.raw_key.slice(-10)}
            </code>
            <button
              onClick={handleCopyKey}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition"
              title="复制密钥"
            >
              <svg className="w-4 h-4 text-gray-600 dark:text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
            </button>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={`text-xs px-3 py-1.5 rounded-lg font-medium border ${STATUS_STYLES[status] || STATUS_STYLES.unchecked}`}>
            {STATUS_LABELS[status] || '未检查'}
          </span>
          <span className="text-xs px-3 py-1.5 rounded-lg bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 font-medium border border-blue-200 dark:border-blue-800">
            {leak.verified_provider || leak.provider}
          </span>
        </div>
      </div>

      {/* Info */}
      <div className="space-y-2 mb-4">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-gray-500 dark:text-gray-400">仓库:</span>
          <a
            href={leak.repo_url}
            target="_blank"
            rel="noreferrer"
            className="text-blue-600 dark:text-blue-400 hover:underline font-medium"
          >
            {leak.repo_owner}/{leak.repo_name}
          </a>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-gray-500 dark:text-gray-400">文件:</span>
          <a
            href={`${leak.repo_url}/blob/HEAD/${leak.file_path}`}
            target="_blank"
            rel="noreferrer"
            className="text-blue-600 dark:text-blue-400 hover:underline text-xs font-mono"
          >
            {leak.file_path}
          </a>
        </div>
        <div className="flex items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
          <span>检测: {timeAgo(leak.leak_detected_at)}</span>
          {leak.leak_introduced_at && (
            <span>提交: {timeAgo(leak.leak_introduced_at)}</span>
          )}
          {leak.validated_at && (
            <span>验证: {timeAgo(leak.validated_at)}</span>
          )}
        </div>
      </div>

      {/* Balance Info */}
      {showBalance && (
        <div className="mb-4 p-4 bg-gradient-to-br from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-xl border border-green-200 dark:border-green-800">
          {loadingBalance ? (
            <div className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-green-600"></div>
              <span>查询余额中...</span>
            </div>
          ) : balanceInfos ? (
            <div className="space-y-2">
              <div className="text-sm font-semibold text-gray-900 dark:text-white mb-2">账户余额</div>
              {balanceInfos.map((b) => {
                const sym = b.currency === 'CNY' ? '¥' : '$'
                const bal = parseFloat(b.total_balance)
                return (
                  <div key={b.currency} className="flex items-center justify-between">
                    <span className="text-sm text-gray-600 dark:text-gray-400">{b.currency}</span>
                    <span className={`text-lg font-bold ${bal > 0 ? 'text-green-600 dark:text-green-400' : 'text-gray-500 dark:text-gray-400'}`}>
                      {sym}{b.total_balance}
                    </span>
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="text-sm text-red-600 dark:text-red-400">查询失败</div>
          )}
        </div>
      )}

      {/* Models Info */}
      {showModels && (
        <div className="mb-4 p-4 bg-gradient-to-br from-purple-50 to-pink-50 dark:from-purple-900/20 dark:to-pink-900/20 rounded-xl border border-purple-200 dark:border-purple-800">
          <div className="text-sm font-semibold text-gray-900 dark:text-white mb-2">可用模型</div>
          <div className="flex flex-wrap gap-2">
            {models.map((model) => (
              <span key={model} className="text-xs px-3 py-1.5 bg-white dark:bg-gray-900 text-purple-700 dark:text-purple-300 rounded-lg border border-purple-200 dark:border-purple-800 font-mono">
                {model}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-2 flex-wrap">
        <button
          onClick={handleValidate}
          disabled={validating}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition"
        >
          {validating ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
              <span>验证中...</span>
            </>
          ) : (
            <>
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>验证</span>
            </>
          )}
        </button>

        {leak.provider === 'deepseek' && status === 'valid' && (
          <button
            onClick={handleCheckBalance}
            className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <span>{showBalance ? '隐藏余额' : '查询余额'}</span>
          </button>
        )}

        {status === 'valid' && (
          <button
            onClick={handleCheckModels}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white text-sm font-medium rounded-lg transition"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            <span>{showModels ? '隐藏模型' : '查看模型'}</span>
          </button>
        )}
      </div>
    </div>
  )
}
