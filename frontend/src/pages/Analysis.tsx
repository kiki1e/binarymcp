import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadChallenge, startAnalysis, fetchAnalysisList } from '../api/client'
import type { AnalysisTask } from '../types'

const CHALLENGE_TYPES = [
  { value: 'auto', label: '自动检测', desc: 'AI自动识别', icon: '🤖', color: 'blue' },
  { value: 'pwn', label: 'PWN', desc: '二进制漏洞', icon: '💥', color: 'red' },
  { value: 'reverse', label: 'Reverse', desc: '逆向分析', icon: '🔓', color: 'purple' },
  { value: 'crypto', label: 'Crypto', desc: '密码破解', icon: '🔐', color: 'green' },
  { value: 'iot', label: 'IoT', desc: '固件分析', icon: '📡', color: 'orange' },
  { value: 'web', label: 'Web', desc: 'Web 安全', icon: '🌐', color: 'teal' },
  { value: 'misc', label: 'Misc', desc: '杂项', icon: '📦', color: 'gray' },
]

const ARCHIVE_EXTS = ['.zip', '.tar', '.gz', '.tgz', '.tar.gz', '.rar', '.7z']

function isArchive(name: string) {
  const lower = name.toLowerCase()
  return ARCHIVE_EXTS.some(e => lower.endsWith(e))
}

function formatSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

function FileIcon({ name, isArch }: { name: string; isArch: boolean }) {
  if (isArch) return <span className="text-2xl">📦</span>
  const ext = name.split('.').pop()?.toLowerCase()
  if (ext === 'exe' || ext === 'elf' || ext === 'bin') return <span className="text-2xl">⚙️</span>
  if (ext === 'py' || ext === 'js' || ext === 'ts') return <span className="text-2xl">📜</span>
  if (ext === 'so' || ext === 'dll') return <span className="text-2xl">🔗</span>
  if (ext === 'txt' || ext === 'md') return <span className="text-2xl">📄</span>
  return <span className="text-2xl">📎</span>
}

export default function Analysis() {
  const [files, setFiles] = useState<File[]>([])
  const [challengeType, setChallengeType] = useState('auto')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [tasks, setTasks] = useState<AnalysisTask[]>([])
  const [dragActive, setDragActive] = useState(false)

  // URL / Endpoint 输入
  const [targetUrls, setTargetUrls] = useState<string[]>([''])
  const [targetEndpoints, setTargetEndpoints] = useState<string[]>([''])
  const [showUrls, setShowUrls] = useState(false)
  const [showEndpoints, setShowEndpoints] = useState(false)

  const navigate = useNavigate()

  useEffect(() => {
    fetchAnalysisList()
      .then((data) => setTasks(data.tasks))
      .catch(() => {})
  }, [])

  // ── 拖拽 ──

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation()
    if (e.type === 'dragenter' || e.type === 'dragover') setDragActive(true)
    else if (e.type === 'dragleave') setDragActive(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault(); e.stopPropagation()
    setDragActive(false)
    const dropped = Array.from(e.dataTransfer.files)
    if (dropped.length > 0) {
      setFiles(prev => [...prev, ...dropped])
    }
  }, [])

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || [])
    if (selected.length > 0) {
      setFiles(prev => [...prev, ...selected])
    }
    // 重置 input 以允许重复选择同名文件
    e.target.value = ''
  }, [])

  const removeFile = useCallback((index: number) => {
    setFiles(prev => prev.filter((_, i) => i !== index))
  }, [])

  // ── URL/Endpoint 管理 ──

  const updateUrl = (index: number, value: string) => {
    setTargetUrls(prev => prev.map((v, i) => i === index ? value : v))
  }
  const addUrl = () => setTargetUrls(prev => [...prev, ''])
  const removeUrl = (index: number) => {
    setTargetUrls(prev => prev.filter((_, i) => i !== index))
  }

  const updateEndpoint = (index: number, value: string) => {
    setTargetEndpoints(prev => prev.map((v, i) => i === index ? value : v))
  }
  const addEndpoint = () => setTargetEndpoints(prev => [...prev, ''])
  const removeEndpoint = (index: number) => {
    setTargetEndpoints(prev => prev.filter((_, i) => i !== index))
  }

  // ── 提交流程 ──

  const handleSubmit = async () => {
    if (files.length === 0) return
    setError('')
    setUploading(true)

    // 读取前端 API 配置
    let apiKey = '', baseUrl = '', apiProvider = '', apiModel = ''
    const defaultCfg = localStorage.getItem('default_api_config')
    if (defaultCfg) {
      try {
        const parsed = JSON.parse(defaultCfg)
        apiKey = parsed.apiKey || ''
        baseUrl = parsed.baseUrl || ''
        apiProvider = parsed.provider || ''
        apiModel = parsed.model || ''
      } catch {}
    }
    if (!apiKey) {
      try {
        const allCfgs = localStorage.getItem('api_configs')
        if (allCfgs) {
          const parsed = JSON.parse(allCfgs)
          if (parsed.length > 0) {
            apiKey = parsed[0].apiKey || ''
            baseUrl = parsed[0].baseUrl || ''
            apiProvider = parsed[0].provider || ''
            apiModel = parsed[0].model || ''
          }
        }
      } catch {}
    }

    // 过滤空值
    const urls = targetUrls.map(s => s.trim()).filter(Boolean)
    const endpoints = targetEndpoints.map(s => s.trim()).filter(Boolean)

    try {
      const upload = await uploadChallenge(files)
      const task = await startAnalysis(
        upload.task_id, challengeType,
        apiProvider, apiModel, apiKey, baseUrl,
        urls, endpoints,
      )
      navigate(`/analysis/${task.task_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : '上传失败，请重试')
    } finally {
      setUploading(false)
    }
  }

  const totalSize = files.reduce((sum, f) => sum + f.size, 0)

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 py-8 px-4">
      <div className="max-w-6xl mx-auto space-y-8">

        {/* Header */}
        <div className="text-center space-y-3">
          <div className="inline-flex items-center gap-3 bg-white dark:bg-gray-800 px-6 py-3 rounded-full shadow-lg border border-gray-200 dark:border-gray-700">
            <span className="text-3xl">🎯</span>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              CTF 赛题智能分析平台
            </h1>
          </div>
          <p className="text-gray-600 dark:text-gray-400 text-lg">
            上传二进制文件、脚本或压缩包，AI 深度分析漏洞，自动生成 Exploit
          </p>
        </div>

        <div className="grid grid-cols-1 gap-8">
          <div className="space-y-8">
            {/* Main Upload Card */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 overflow-hidden">

              {/* Upload Zone */}
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                className={`relative p-8 transition-all duration-300 ${
                  dragActive
                    ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-500'
                    : files.length > 0
                    ? 'bg-gray-50 dark:bg-gray-900/50'
                    : 'bg-white dark:bg-gray-800'
                }`}
              >
                {files.length > 0 ? (
                  /* ── 已选文件列表 ── */
                  <div className="space-y-3">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-semibold text-gray-700 dark:text-gray-300">
                        已选择 {files.length} 个文件（共 {formatSize(totalSize)}）
                      </p>
                      <button onClick={() => setFiles([])}
                        className="text-xs text-red-500 hover:text-red-700 dark:hover:text-red-400 px-2 py-1 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition">
                        清空全部
                      </button>
                    </div>
                    <div className="grid gap-2 max-h-64 overflow-y-auto pr-1">
                      {files.map((f, i) => (
                        <div key={i}
                          className="flex items-center justify-between bg-white dark:bg-gray-800 rounded-xl px-4 py-2.5 border border-gray-200 dark:border-gray-700 shadow-sm">
                          <div className="flex items-center gap-3 min-w-0">
                            <FileIcon name={f.name} isArch={isArchive(f.name)} />
                            <div className="min-w-0">
                              <p className="text-sm font-medium text-gray-900 dark:text-white truncate max-w-[300px] sm:max-w-[400px]">
                                {f.name}
                              </p>
                              <p className="text-xs text-gray-500 dark:text-gray-400">
                                {formatSize(f.size)}
                                {isArchive(f.name) && <span className="ml-2 text-amber-500 font-medium">📦 压缩包（将自动解压）</span>}
                              </p>
                            </div>
                          </div>
                          <button onClick={() => removeFile(i)}
                            className="shrink-0 w-7 h-7 flex items-center justify-center text-gray-400 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition">
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                    <label className="inline-flex items-center gap-1.5 text-sm text-blue-600 dark:text-blue-400 cursor-pointer hover:text-blue-700 dark:hover:text-blue-300 transition">
                      + 继续添加文件
                      <input type="file" multiple className="hidden" onChange={handleFileSelect} />
                    </label>
                  </div>
                ) : (
                  /* ── 空状态: 拖拽或选择 ── */
                  <div className="text-center space-y-4 py-4">
                    <div className="w-20 h-20 mx-auto bg-gradient-to-br from-gray-100 to-gray-200 dark:from-gray-700 dark:to-gray-800 rounded-2xl flex items-center justify-center">
                      <svg className="w-10 h-10 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                      </svg>
                    </div>
                    <p className="text-lg font-medium text-gray-700 dark:text-gray-300">
                      拖拽文件到此处 或 点击上传
                    </p>
                    <p className="text-sm text-gray-400 dark:text-gray-500">
                      支持多个文件、压缩包（zip/tar.gz）、二进制（exe/elf/bin）
                    </p>
                    <label className="inline-flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white font-medium rounded-xl cursor-pointer transition shadow-lg">
                      选择文件
                      <input type="file" multiple className="hidden" onChange={handleFileSelect} />
                    </label>
                  </div>
                )}
              </div>

              {/* ── 远程目标地址 (可折叠) ── */}
              <div className="border-t border-gray-200 dark:border-gray-700">
                <button onClick={() => setShowUrls(!showUrls)}
                  className="w-full px-6 py-3 flex items-center justify-between text-sm hover:bg-gray-50 dark:hover:bg-gray-750 transition">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🌐</span>
                    <span className="font-medium text-gray-700 dark:text-gray-300">远程目标地址</span>
                    {targetUrls.filter(Boolean).length > 0 && (
                      <span className="text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 px-2 py-0.5 rounded-full">
                        {targetUrls.filter(Boolean).length}
                      </span>
                    )}
                    <span className="text-xs text-gray-400">（如 nc host port）</span>
                  </div>
                  <svg className={`w-4 h-4 text-gray-400 transition ${showUrls ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {showUrls && (
                  <div className="px-6 pb-4 space-y-2">
                    {targetUrls.map((url, i) => (
                      <div key={i} className="flex gap-2">
                        <input type="text" value={url}
                          onChange={(e) => updateUrl(i, e.target.value)}
                          placeholder="例如: nc challenge.example.com 1337"
                          className="flex-1 px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                        {targetUrls.length > 1 && (
                          <button onClick={() => removeUrl(i)}
                            className="px-2 text-gray-400 hover:text-red-500 transition">✕</button>
                        )}
                      </div>
                    ))}
                    <button onClick={addUrl}
                      className="text-xs text-blue-600 dark:text-blue-400 hover:text-blue-700 dark:hover:text-blue-300 transition">
                      + 添加地址
                    </button>
                  </div>
                )}
              </div>

              {/* ── API 接口 (可折叠) ── */}
              <div className="border-t border-gray-200 dark:border-gray-700">
                <button onClick={() => setShowEndpoints(!showEndpoints)}
                  className="w-full px-6 py-3 flex items-center justify-between text-sm hover:bg-gray-50 dark:hover:bg-gray-750 transition">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🔌</span>
                    <span className="font-medium text-gray-700 dark:text-gray-300">API 接口</span>
                    {targetEndpoints.filter(Boolean).length > 0 && (
                      <span className="text-xs bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300 px-2 py-0.5 rounded-full">
                        {targetEndpoints.filter(Boolean).length}
                      </span>
                    )}
                    <span className="text-xs text-gray-400">（如 /api/login）</span>
                  </div>
                  <svg className={`w-4 h-4 text-gray-400 transition ${showEndpoints ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {showEndpoints && (
                  <div className="px-6 pb-4 space-y-2">
                    {targetEndpoints.map((ep, i) => (
                      <div key={i} className="flex gap-2">
                        <input type="text" value={ep}
                          onChange={(e) => updateEndpoint(i, e.target.value)}
                          placeholder="例如: /api/flag"
                          className="flex-1 px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500" />
                        {targetEndpoints.length > 1 && (
                          <button onClick={() => removeEndpoint(i)}
                            className="px-2 text-gray-400 hover:text-red-500 transition">✕</button>
                        )}
                      </div>
                    ))}
                    <button onClick={addEndpoint}
                      className="text-xs text-purple-600 dark:text-purple-400 hover:text-purple-700 dark:hover:text-purple-300 transition">
                      + 添加接口
                    </button>
                  </div>
                )}
              </div>

              {/* Challenge Type Selection */}
              <div className="border-t border-gray-200 dark:border-gray-700 p-6 bg-gray-50 dark:bg-gray-900/50">
                <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-4 flex items-center gap-2">
                  <span className="w-1.5 h-5 bg-gradient-to-b from-blue-500 to-purple-600 rounded-full"></span>
                  选择赛题类型
                </h3>
                <div className="grid grid-cols-4 sm:grid-cols-7 gap-2">
                  {CHALLENGE_TYPES.map((t) => (
                    <button key={t.value}
                      onClick={() => setChallengeType(t.value)}
                      className={`group p-3 rounded-xl text-center transition-all duration-200 ${
                        challengeType === t.value
                          ? 'bg-gradient-to-br from-blue-500 to-purple-600 text-white shadow-lg scale-105'
                          : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 border border-gray-200 dark:border-gray-700'
                      }`}>
                      <div className="text-2xl mb-1">{t.icon}</div>
                      <div className={`text-xs font-semibold ${challengeType === t.value ? 'text-white' : 'text-gray-900 dark:text-white'}`}>{t.label}</div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Error */}
              {error && (
                <div className="mx-6 mb-6 p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-xl text-sm text-red-600 dark:text-red-400">
                  {error}
                </div>
              )}

              {/* Submit */}
              <div className="p-6 pt-0">
                <button onClick={handleSubmit}
                  disabled={files.length === 0 || uploading}
                  className="w-full py-4 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:from-gray-300 disabled:to-gray-400 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition shadow-lg flex items-center justify-center gap-3 text-lg">
                  {uploading ? (
                    <><div className="animate-spin rounded-full h-6 w-6 border-b-2 border-white"></div><span>正在上传并分析...</span></>
                  ) : (
                    <><svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg><span>开始智能分析</span></>
                  )}
                </button>
              </div>
            </div>

            {/* Recent Analysis */}
            {tasks.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-200 dark:border-gray-700 p-6">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                  <span className="w-1.5 h-6 bg-gradient-to-b from-blue-500 to-purple-600 rounded-full"></span>
                  最近分析记录
                </h3>
                <div className="space-y-2">
                  {tasks.slice(0, 5).map((t) => (
                    <button key={t.task_id} onClick={() => navigate(`/analysis/${t.task_id}`)}
                      className="w-full flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900/50 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-xl transition border border-gray-200 dark:border-gray-700 group">
                      <div className="flex items-center gap-3 flex-1">
                        <span className="text-2xl">{t.challenge_type === 'pwn' ? '💥' : t.challenge_type === 'reverse' ? '🔓' : t.challenge_type === 'crypto' ? '🔐' : t.challenge_type === 'iot' ? '📡' : t.challenge_type === 'web' ? '🌐' : t.challenge_type === 'misc' ? '📦' : '🤖'}</span>
                        <div className="flex-1 text-left">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-sm font-mono font-semibold text-gray-900 dark:text-white">{t.task_id}</span>
                            <span className="text-xs px-2 py-0.5 bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded">{t.challenge_type?.toUpperCase() || 'AUTO'}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <div className="flex-1 max-w-[120px] bg-gray-200 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
                              <div className={`h-2 rounded-full ${t.status === 'completed' ? 'bg-green-500' : t.status === 'failed' ? 'bg-red-500' : t.status === 'stopped' ? 'bg-yellow-500' : 'bg-blue-500 animate-pulse'}`}
                                style={{ width: `${(t.progress || 0) * 100}%` }} />
                            </div>
                            <span className={`text-xs font-medium ${t.status === 'completed' ? 'text-green-600 dark:text-green-400' : t.status === 'failed' ? 'text-red-600 dark:text-red-400' : t.status === 'stopped' ? 'text-yellow-600 dark:text-yellow-400' : 'text-blue-600 dark:text-blue-400'}`}>
                              {t.status === 'completed' ? '✓ 完成' : t.status === 'failed' ? '✗ 失败' : t.status === 'stopped' ? '⏹ 已停止' : '⟳ 分析中'}
                            </span>
                          </div>
                        </div>
                      </div>
                      <svg className="w-5 h-5 text-gray-400 group-hover:text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" /></svg>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
