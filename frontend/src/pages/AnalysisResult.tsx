import { useEffect, useState, useRef, useMemo, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { fetchAnalysisStatus, stopAnalysis, ncConnect } from '../api/client'
import type { AnalysisTask, AgentStep } from '../types'
import MarkdownRenderer from '../components/MarkdownRenderer'

const PHASE_LABELS: Record<string, string> = {
  detecting: '赛题类型检测',
  static: '静态分析',
  decompiling: '反编译',
  tool_analysis: '专项工具分析',
  ai_analysis: 'AI 深度分析',
  completed: '分析完成',
}

function StepCard({ step, index }: { step: AgentStep; index: number }) {
  const [open, setOpen] = useState(index === 0)

  if (step.type === 'thought') {
    return (
      <details key={index} open={open}
        className="text-xs bg-gray-50 dark:bg-gray-900/50 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <summary onClick={() => setOpen(!open)}
          className="px-3 py-2 cursor-pointer text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 select-none flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-gray-400 shrink-0" />
          <span className="font-medium">💭 思考步骤 {index + 1}</span>
        </summary>
        <div className="px-3 py-2 text-gray-600 dark:text-gray-300 whitespace-pre-wrap max-h-48 overflow-y-auto border-t border-gray-100 dark:border-gray-800">
          {step.content}
        </div>
      </details>
    )
  } else if (step.type === 'action') {
    return (
      <details key={index} open={open}
        className="text-xs bg-orange-50 dark:bg-gray-900/50 rounded-lg border border-orange-200 dark:border-orange-900/30 overflow-hidden">
        <summary onClick={() => setOpen(!open)}
          className="px-3 py-2 cursor-pointer text-orange-700 dark:text-orange-400 hover:bg-orange-100 dark:hover:bg-gray-800 select-none flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-orange-400 shrink-0" />
          <span className="font-medium">🔧 调用工具: {step.name || step.content}</span>
        </summary>
        <div className="px-3 py-2 text-gray-600 dark:text-gray-300 font-mono whitespace-pre-wrap max-h-40 overflow-y-auto border-t border-orange-100 dark:border-orange-900/20">
          {step.input || step.content}
        </div>
      </details>
    )
  } else if (step.type === 'observation') {
    return (
      <details key={index} open={open}
        className="text-xs bg-green-50 dark:bg-gray-900/50 rounded-lg border border-green-200 dark:border-green-900/30 overflow-hidden">
        <summary onClick={() => setOpen(!open)}
          className="px-3 py-2 cursor-pointer text-green-700 dark:text-green-400 hover:bg-green-100 dark:hover:bg-gray-800 select-none flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-green-400 shrink-0" />
          <span className="font-medium">📊 工具结果</span>
          {step.full_length && <span className="text-gray-400 ml-1">({step.full_length} 字符)</span>}
        </summary>
        <div className="px-3 py-2 text-gray-600 dark:text-gray-300 font-mono whitespace-pre-wrap max-h-40 overflow-y-auto border-t border-green-100 dark:border-green-900/20">
          {step.content?.slice(0, 500)}
          {(step.full_length && step.full_length > 500) && <span className="text-gray-400">...（截断）</span>}
        </div>
      </details>
    )
  } else if (step.type === 'hint') {
    return (
      <div key={index}
        className="text-xs bg-blue-50 dark:bg-blue-900/20 rounded-lg border border-blue-200 dark:border-blue-800 px-3 py-2 text-blue-700 dark:text-blue-300 flex items-center gap-2">
        <span>💡 用户提示:</span>
        <span className="italic">{step.content}</span>
      </div>
    )
  } else if (step.type === 'error') {
    return (
      <div key={index}
        className="text-xs bg-red-50 dark:bg-red-900/20 rounded-lg border border-red-200 dark:border-red-800 px-3 py-2 text-red-600 dark:text-red-400">
        ❌ {step.content}
      </div>
    )
  }
  return null
}

function NcModal({
  target, onClose, taskId,
}: { target: string; onClose: () => void; taskId: string }) {
  const [input, setInput] = useState('')
  const [output, setOutput] = useState('')
  const [error, setError] = useState('')
  const [connecting, setConnecting] = useState(false)
  const outputRef = useRef<HTMLDivElement>(null)

  const doConnect = useCallback(async (dataToSend = '') => {
    setConnecting(true)
    setError('')
    try {
      const res = await ncConnect(taskId, target, dataToSend)
      if (res.error) {
        setError(res.error)
      } else {
        setOutput(prev => prev + (res.output || ''))
      }
    } catch (e: any) {
      setError(e.message || '连接失败')
    }
    setConnecting(false)
  }, [taskId, target])

  useEffect(() => { doConnect('') }, [])
  useEffect(() => {
    outputRef.current?.scrollTo(0, outputRef.current.scrollHeight)
  }, [output, error])

  const handleSend = () => {
    if (!input.trim()) return
    setOutput(prev => prev + `\n> ${input}\n`)
    doConnect(input + '\n')
    setInput('')
  }

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <span className="text-lg">🌐</span>
            <span className="font-semibold text-gray-900 dark:text-white font-mono text-sm truncate max-w-md">{target}</span>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-xl">&times;</button>
        </div>
        <div ref={outputRef} className="flex-1 overflow-y-auto p-4 font-mono text-sm bg-gray-950 text-green-400 whitespace-pre-wrap break-words leading-relaxed min-h-[200px] max-h-[50vh]">
          {connecting && !output && !error && (
            <div className="flex items-center gap-2 text-gray-400">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
              连接中...
            </div>
          )}
          {output || ''}
          {error && <div className="text-red-400 mt-2">❌ {error}</div>}
          {!connecting && <span className="animate-pulse">█</span>}
        </div>
        <div className="px-4 py-3 border-t border-gray-200 dark:border-gray-700 flex gap-2">
          <input value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleSend() }}
            placeholder="输入要发送的数据 (Enter 发送)..."
            disabled={connecting}
            className="flex-1 px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:opacity-50" />
          <button onClick={handleSend} disabled={connecting || !input.trim()}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white text-sm rounded-lg transition">发送</button>
          <button onClick={() => doConnect('')} disabled={connecting}
            className="px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50 text-gray-700 dark:text-gray-300 text-sm rounded-lg transition">重新连接</button>
        </div>
      </div>
    </div>
  )
}

export default function AnalysisResult() {
  const { taskId } = useParams<{ taskId: string }>()
  const navigate = useNavigate()
  const [task, setTask] = useState<AnalysisTask | null>(null)
  const [error, setError] = useState('')
  const chatEndRef = useRef<HTMLDivElement>(null)
  const streamRef = useRef<HTMLPreElement>(null)

  // Agent 实时步骤和流式内容
  const [liveSteps, setLiveSteps] = useState<AgentStep[]>([])
  const [streamContent, setStreamContent] = useState('')
  const [hintText, setHintText] = useState('')
  const [hintSending, setHintSending] = useState(false)
  const [hintSent, setHintSent] = useState<string[]>([])
  const [stopping, setStopping] = useState(false)

  // nc 连接
  const [showNcModal, setShowNcModal] = useState(false)
  const [ncTarget, setNcTarget] = useState('')

  // 折叠面板
  const [showInfo, setShowInfo] = useState(false)
  const [showScripts, setShowScripts] = useState(false)
  const [showSteps, setShowSteps] = useState(true)

  // ── WebSocket + 轮询 ──

  useEffect(() => {
    if (!taskId) return
    let cancelled = false
    let ws: WebSocket | null = null
    let pollTimer: ReturnType<typeof setTimeout> | null = null

    const connectWebSocket = () => {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.host}/api/analysis/${taskId}/ws`
      try {
        ws = new WebSocket(wsUrl)
        ws.onmessage = (event) => {
          if (cancelled) return
          const data = JSON.parse(event.data)

          if (data.error) { setError(data.error); return }

          if (data.type === 'agent_step' && data.step) {
            setLiveSteps(prev => {
              if (data.step_index !== undefined && prev.some(s => s.step_index === data.step_index)) return prev
              return [...prev, { ...data.step, step_index: data.step_index, total_steps: data.total_steps } as AgentStep]
            })
          }

          if (data.type === 'stream' && data.content) {
            setStreamContent(prev => prev + data.content)
          }

          if (data.status) {
            setTask(prev => {
              const updated = { ...prev, ...data, task_id: taskId } as AnalysisTask
              if (data.agent_steps && Array.isArray(data.agent_steps)) updated.agent_steps = data.agent_steps
              return updated
            })
          }

          if (data.status === 'completed' || data.status === 'failed' || data.status === 'stopped') {
            if (data.agent_steps && Array.isArray(data.agent_steps)) setLiveSteps(data.agent_steps as AgentStep[])
            if (data.status !== 'completed') setStreamContent('')
          }
        }
        ws.onerror = () => { if (!cancelled) fallbackPoll() }
        ws.onclose = () => {
          if (!cancelled && task?.status !== 'completed' && task?.status !== 'failed') fallbackPoll()
        }
      } catch { fallbackPoll() }
    }

    const fallbackPoll = async () => {
      try {
        const data = await fetchAnalysisStatus(taskId)
        if (!cancelled) {
          setTask(data)
          if (data.result?.phases?.ai?.agent_steps) setLiveSteps(data.result.phases.ai.agent_steps as AgentStep[])
          if (data.agent_steps) setLiveSteps(data.agent_steps as AgentStep[])
          if (data.status === 'running') pollTimer = setTimeout(fallbackPoll, 2000)
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : '加载失败')
      }
    }

    connectWebSocket()
    return () => {
      cancelled = true
      if (ws) ws.close()
      if (pollTimer) clearTimeout(pollTimer)
    }
  }, [taskId])

  // ── 自动滚动 ──

  useEffect(() => {
    if (streamRef.current) {
      streamRef.current.scrollTop = streamRef.current.scrollHeight
    }
  }, [streamContent])

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [liveSteps.length])

  // ── 派生数据 ──

  const isAnalyzing = task?.status === 'running'
  const isDone = task?.status === 'completed' || task?.status === 'stopped'

  const agentSteps = useMemo(() => {
    if (liveSteps.length > 0) return liveSteps
    return (task?.result?.phases?.ai?.agent_steps as AgentStep[]) || task?.agent_steps || []
  }, [liveSteps, task])

  const staticInfo = useMemo(() => {
    const s = task?.result?.phases?.static
    if (!s) return null
    const info: Record<string, string> = {}
    try {
      const bi = s.binary_info
      if (typeof bi === 'object' && bi !== null) {
        const b = bi as any
        if (b.result) {
          const lines = String(b.result).split('\n')
          for (const line of lines) {
            if (line.includes(':')) { const [k, ...v] = line.split(':'); info[k.trim()] = v.join(':').trim() }
          }
        }
      }
      const cs = s.checksec
      if (typeof cs === 'object' && cs !== null) {
        const c = cs as any
        if (c.result) info['checksec'] = String(c.result)
      }
    } catch {}
    return info
  }, [task])

  const protections = useMemo(() => {
    const raw = staticInfo?.checksec || ''
    const result: Record<string, string> = {}
    for (const line of raw.split('\n')) {
      const m = line.match(/^\s*(.+?):\s*(.+)$/)
      if (m) result[m[1].trim()] = m[2].trim()
    }
    return result
  }, [staticInfo])

  const aiContent = task?.result?.phases?.ai?.content || ''
  const aiError = task?.result?.phases?.ai?.error || ''

  const extractedFlag = useMemo(() => {
    if (!aiContent && !streamContent) return ''
    const text = aiContent || streamContent
    const m = text.match(/flag\{[^}]+\}/i)
    return m ? m[0] : ''
  }, [aiContent, streamContent])

  const extractedScripts = useMemo(() => {
    if (!aiContent) return []
    const blocks: string[] = []
    const re = /```(?:python|py|bash|sh|zsh)?\n([\s\S]*?)```/g
    let match
    while ((match = re.exec(aiContent)) !== null) {
      if (match[1].trim()) blocks.push(match[1].trim())
    }
    return blocks
  }, [aiContent])

  const targetUrls = task?.target_urls || []
  const isPwn = task?.challenge_type === 'pwn'

  // ── 操作 ──

  const handleSendHint = useCallback(async () => {
    const text = hintText.trim()
    if (!text || !taskId || hintSending) return
    setHintSending(true)
    try {
      const token = localStorage.getItem('token')
      const res = await fetch(`/api/analysis/${taskId}/hint`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ hint: text }),
      })
      if (res.ok) { setHintSent(prev => [...prev, text]); setHintText('') }
    } catch {}
    setHintSending(false)
  }, [hintText, taskId, hintSending])

  const handleStop = useCallback(async () => {
    if (!taskId || stopping) return
    setStopping(true)
    try { await stopAnalysis(taskId) } catch {}
  }, [taskId, stopping])

  const openNcConnect = useCallback((target: string) => {
    setNcTarget(target)
    setShowNcModal(true)
  }, [])

  const downloadReport = () => {
    const md = [
      `# CTF 赛题分析报告`,
      ``,
      `**题目 ID**: ${taskId}`,
      `**类型**: ${task?.challenge_type || '未知'}`,
      `**状态**: ${task?.status}`,
      `**耗时**: ${task?.result?.duration ? `${task.result.duration.toFixed(1)}s` : '未知'}`,
      ``,
      `---`,
      ``,
    ]
    if (staticInfo) {
      md.push(`## 文件信息`, ``)
      for (const [k, v] of Object.entries(staticInfo)) { if (k !== 'checksec') md.push(`- **${k}**: ${v}`) }
      md.push(``, `---`, ``)
    }
    if (Object.keys(protections).length > 0) {
      md.push(`## 保护机制`, ``)
      for (const [k, v] of Object.entries(protections)) md.push(`- **${k}**: ${v}`)
      md.push(``, `---`, ``)
    }
    if (aiContent) { md.push(`## AI 分析`, ``); md.push(aiContent) }
    if (extractedFlag) { md.push(``, `## Flag`, ``); md.push(`\`\`\`\n${extractedFlag}\n\`\`\``) }

    const blob = new Blob([md.join('\n')], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = `analysis-report-${taskId}.md`; a.click()
    URL.revokeObjectURL(url)
  }

  // ── 加载/错误状态 ──

  if (error && !task) return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 flex items-center justify-center p-4">
      <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 p-8 max-w-md text-center space-y-4">
        <div className="w-16 h-16 mx-auto bg-red-100 dark:bg-red-900/20 rounded-full flex items-center justify-center">
          <svg className="w-8 h-8 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
          </svg>
        </div>
        <p className="text-gray-900 dark:text-white font-medium">加载失败</p>
        <p className="text-sm text-gray-500 dark:text-gray-400">{error}</p>
        <button onClick={() => navigate('/analysis')}
          className="px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg transition text-sm">
          返回分析页面
        </button>
      </div>
    </div>
  )

  if (!task) return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto mb-4"></div>
        <div className="text-gray-500 dark:text-gray-400 text-sm">加载分析结果...</div>
      </div>
    </div>
  )

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 py-6 px-4">
      <div className="max-w-4xl mx-auto space-y-5">

        {/* ── Status Bar ── */}
        <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 p-4 sm:p-6">
          <div className="flex items-center justify-between flex-wrap gap-3">
            <div className="flex items-center gap-3">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center text-lg ${
                task.status === 'completed' ? 'bg-green-100 dark:bg-green-900/20' :
                task.status === 'failed' ? 'bg-red-100 dark:bg-red-900/20' :
                task.status === 'stopped' ? 'bg-yellow-100 dark:bg-yellow-900/20' :
                'bg-blue-100 dark:bg-blue-900/20'
              }`}>
                {task.status === 'completed' ? '✅' : task.status === 'failed' ? '❌' : task.status === 'stopped' ? '⏹️' : '⏳'}
              </div>
              <div>
                <h1 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  {task.status === 'completed' ? '分析完成' : task.status === 'failed' ? '分析失败' : task.status === 'stopped' ? '已停止' : 'AI 正在分析...'}
                  {isAnalyzing && <span className="w-2 h-2 bg-blue-500 rounded-full animate-pulse" />}
                </h1>
                <div className="flex items-center gap-2 mt-0.5 flex-wrap">
                  <span className="text-xs font-mono text-gray-500">ID: {taskId}</span>
                  <span className="text-xs px-2 py-0.5 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-300 rounded-md font-medium">
                    {task.challenge_type?.toUpperCase() || 'AUTO'}
                  </span>
                  {task.result?.duration && <span className="text-xs text-gray-400">⏱ {task.result.duration.toFixed(1)}s</span>}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {isDone && (
                <button onClick={() => navigate('/analysis')}
                  className="px-3 py-1.5 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 text-xs font-medium rounded-xl transition">
                  上传新文件
                </button>
              )}
              {isAnalyzing && (
                <button onClick={handleStop} disabled={stopping}
                  className="flex items-center gap-1.5 px-4 py-2 bg-red-100 dark:bg-red-900/30 hover:bg-red-200 dark:hover:bg-red-900/50 text-red-700 dark:text-red-300 text-sm font-medium rounded-xl transition">
                  {stopping
                    ? <><span className="w-4 h-4 border-2 border-red-500 border-t-transparent rounded-full animate-spin" />停止中...</>
                    : <><svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 10a1 1 0 011-1h4a1 1 0 011 1v4a1 1 0 01-1 1h-4a1 1 0 01-1-1v-4z" /></svg>停止分析</>
                  }
                </button>
              )}
              {task.status === 'completed' && (
                <>
                  <button onClick={downloadReport}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-200 text-xs font-medium rounded-xl transition shadow-sm">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" /></svg>
                    下载报告
                  </button>
                  <button onClick={() => navigate(`/chat?context=${taskId}`)}
                    className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 text-white text-xs font-medium rounded-xl transition shadow-lg">
                    <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" /></svg>
                    继续 AI 对话
                  </button>
                </>
              )}
            </div>
          </div>
        </div>

        {/* ── Target URLs Bar ── */}
        {targetUrls.length > 0 && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-sm">🌐</span>
              <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">远程目标</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {targetUrls.map((url, i) => (
                <div key={i} className="flex items-center gap-2 bg-gray-50 dark:bg-gray-900 rounded-xl px-3 py-2 border border-gray-200 dark:border-gray-700">
                  <span className="text-xs font-mono text-gray-700 dark:text-gray-300">{url}</span>
                  <button onClick={() => openNcConnect(url)}
                    className={`px-3 py-1 text-xs font-medium rounded-lg transition ${
                      isPwn
                        ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 hover:bg-green-200 dark:hover:bg-green-900/50'
                        : 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/50'
                    }`}>
                    {isPwn ? '🎯 获取 Flag' : '🔌 连接测试'}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Running State ── */}
        {isAnalyzing && (
          <>
            {/* 实时思考流 (主区域) */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-indigo-200 dark:border-indigo-900/30 overflow-hidden">
              <div className="px-5 py-3 border-b border-indigo-100 dark:border-indigo-900/20 flex items-center gap-2">
                <span className="w-2.5 h-2.5 bg-indigo-500 rounded-full animate-pulse" />
                <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">🤔 AI 实时思考</span>
                <span className="text-xs text-gray-400 ml-auto">
                  {streamContent.length > 0 ? `${(streamContent.length / 1024).toFixed(1)} KB` : '等待中...'}
                </span>
              </div>
              <pre ref={streamRef}
                className="p-5 text-sm text-gray-700 dark:text-gray-200 font-mono whitespace-pre-wrap break-words leading-relaxed max-h-[50vh] overflow-y-auto bg-gray-50 dark:bg-gray-900/50">
                {streamContent || (
                  <span className="text-gray-400 animate-pulse">等待 AI 响应...</span>
                )}
                {streamContent && <span className="text-indigo-500 animate-pulse">█</span>}
              </pre>
            </div>

            {/* Agent 步骤 / 提示输入 */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
              {/* 步骤折叠 */}
              <button onClick={() => setShowSteps(!showSteps)}
                className="w-full px-5 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-750 transition">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">📋 推理步骤</span>
                  <span className="text-xs text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded-full">{agentSteps.length}</span>
                </div>
                <svg className={`w-4 h-4 text-gray-400 transition ${showSteps ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </button>
              {showSteps && agentSteps.length > 0 && (
                <div className="px-5 pb-3 space-y-1.5 max-h-64 overflow-y-auto">
                  {agentSteps.map((step, i) => <StepCard key={i} step={step} index={i} />)}
                </div>
              )}

              {/* 提示输入 */}
              <div className="px-5 py-3 border-t border-gray-200 dark:border-gray-700">
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                  💡 引导 AI 分析方向（例如："检查 stack 保护机制"、"尝试用 ROP"）
                </p>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={hintText}
                    onChange={e => setHintText(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendHint() } }}
                    placeholder="输入提示引导 AI..."
                    className="flex-1 px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-xl text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                  <button onClick={handleSendHint} disabled={!hintText.trim() || hintSending}
                    className="px-4 py-2 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 disabled:from-gray-400 disabled:to-gray-500 disabled:cursor-not-allowed text-white text-sm font-medium rounded-xl transition shadow-lg">
                    {hintSending ? '发送中...' : '发送提示'}
                  </button>
                </div>
                {hintSent.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1">
                    {hintSent.map((h, i) => (
                      <span key={i} className="text-xs bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 px-2 py-1 rounded-lg">
                        💡 {h.slice(0, 30)}{h.length > 30 ? '...' : ''}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* 进度 */}
            <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 p-4">
              <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 overflow-hidden">
                <div className="h-2 rounded-full bg-gradient-to-r from-indigo-500 to-purple-600 transition-all duration-700 ease-out"
                  style={{ width: `${Math.min((task.progress || 0) * 100, 100)}%` }} />
              </div>
              <p className="text-xs text-gray-500 mt-2 text-center">
                {PHASE_LABELS[task.phase] || task.phase} — {task.message || '分析中...'}
              </p>
            </div>
          </>
        )}

        {/* ── Failed State ── */}
        {task.status === 'failed' && (
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-red-200 dark:border-red-800 p-6">
            <div className="flex items-start gap-3">
              <div className="w-10 h-10 bg-red-100 dark:bg-red-900/20 rounded-xl flex items-center justify-center shrink-0">
                <svg className="w-5 h-5 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                </svg>
              </div>
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-white mb-1">分析过程中发生错误</h3>
                <p className="text-sm text-gray-600 dark:text-gray-400">{task.message || '未知错误，请重试'}</p>
                {aiError && <p className="text-xs text-red-500 mt-2 bg-red-50 dark:bg-red-900/10 px-3 py-2 rounded-lg">{aiError}</p>}
                <button onClick={() => navigate('/analysis')}
                  className="mt-4 px-4 py-2 bg-red-50 dark:bg-red-900/20 hover:bg-red-100 dark:hover:bg-red-900/40 text-red-700 dark:text-red-300 text-sm rounded-lg transition">
                  重新上传分析
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Completed / Stopped State ── */}
        {isDone && (
          <>
            {/* 🚩 Flag (找到时) */}
            {extractedFlag && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-amber-200 dark:border-amber-800 overflow-hidden">
                <div className="px-6 py-4 border-b border-amber-100 dark:border-amber-900/20 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-amber-500 to-red-600 rounded-xl flex items-center justify-center">
                      <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9" />
                      </svg>
                    </div>
                    <h2 className="text-xl font-bold text-gray-900 dark:text-white">Flag 已找到</h2>
                  </div>
                  <button onClick={() => navigator.clipboard.writeText(extractedFlag)}
                    className="flex items-center gap-1.5 px-4 py-2 bg-amber-50 dark:bg-amber-900/20 hover:bg-amber-100 dark:hover:bg-amber-900/40 text-amber-700 dark:text-amber-300 text-sm font-medium rounded-xl transition">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>
                    复制
                  </button>
                </div>
                <div className="p-6 text-center">
                  <code className="text-2xl font-bold font-mono text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-900/20 px-6 py-3 rounded-xl border border-rose-200 dark:border-rose-800 break-all inline-block">
                    {extractedFlag}
                  </code>
                  {isPwn && targetUrls.length > 0 && (
                    <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                      <p className="text-sm text-gray-500 mb-2">如果 Flag 不对，尝试直接连接远程靶机获取：</p>
                      <div className="flex flex-wrap gap-2 justify-center">
                        {targetUrls.map((url, i) => (
                          <button key={i} onClick={() => openNcConnect(url)}
                            className="px-4 py-2 bg-green-100 dark:bg-green-900/30 hover:bg-green-200 dark:hover:bg-green-900/50 text-green-700 dark:text-green-300 text-sm font-medium rounded-xl transition">
                            🎯 {url}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* AI 分析报告 */}
            {aiContent && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center gap-3">
                  <div className="w-8 h-8 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                    <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                    </svg>
                  </div>
                  <h2 className="text-lg font-bold text-gray-900 dark:text-white">AI 分析报告</h2>
                  {task.result?.phases?.ai?.model && (
                    <span className="text-xs text-gray-400 ml-auto">模型: {task.result.phases.ai.model}</span>
                  )}
                </div>
                <div className="p-6">
                  <MarkdownRenderer content={aiContent} />
                </div>
              </div>
            )}

            {aiError && !aiContent && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-amber-200 dark:border-amber-800 p-6">
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 bg-amber-100 dark:bg-amber-900/20 rounded-xl flex items-center justify-center shrink-0">
                    <svg className="w-5 h-5 text-amber-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                    </svg>
                  </div>
                  <div>
                    <h3 className="font-semibold text-gray-900 dark:text-white mb-1">AI 分析未执行</h3>
                    <p className="text-sm text-gray-600 dark:text-gray-400">{aiError}</p>
                    <p className="text-xs text-gray-500 mt-2">请先在 <strong>API配置</strong> 页面添加有效的 API 密钥。</p>
                  </div>
                </div>
              </div>
            )}

            {/* 解题脚本 */}
            {extractedScripts.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                <button onClick={() => setShowScripts(!showScripts)}
                  className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-750 transition">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-gradient-to-br from-emerald-500 to-teal-600 rounded-lg flex items-center justify-center">
                      <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                      </svg>
                    </div>
                    <h2 className="text-lg font-bold text-gray-900 dark:text-white">解题脚本</h2>
                    <span className="text-xs text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded-full">{extractedScripts.length} 个</span>
                  </div>
                  <svg className={`w-5 h-5 text-gray-400 transition ${showScripts ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {showScripts && (
                  <div className="px-6 pb-6 space-y-4">
                    {extractedScripts.map((script, i) => (
                      <div key={i} className="relative">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-xs text-gray-400 font-mono">脚本 {i + 1}</span>
                          <button onClick={() => navigator.clipboard.writeText(script)}
                            className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-200 px-2 py-1 bg-gray-100 dark:bg-gray-700 rounded transition">
                            复制
                          </button>
                        </div>
                        <pre className="text-sm text-gray-800 dark:text-gray-200 bg-gray-50 dark:bg-gray-900 p-4 rounded-xl overflow-x-auto font-mono leading-relaxed border border-gray-200 dark:border-gray-700 max-h-96 overflow-y-auto">
                          {script}
                        </pre>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 文件信息+保护机制 */}
            {staticInfo && Object.keys(staticInfo).length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                <button onClick={() => setShowInfo(!showInfo)}
                  className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-750 transition">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-cyan-600 rounded-lg flex items-center justify-center">
                      <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </div>
                    <h2 className="text-lg font-bold text-gray-900 dark:text-white">文件信息</h2>
                  </div>
                  <svg className={`w-5 h-5 text-gray-400 transition ${showInfo ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {showInfo && (
                  <div className="px-6 pb-6">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      {Object.entries(staticInfo).filter(([k]) => k !== 'checksec').map(([k, v]) => (
                        <div key={k} className="bg-gray-50 dark:bg-gray-900 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
                          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{k}</p>
                          <p className="text-sm font-medium text-gray-900 dark:text-white break-all">{v}</p>
                        </div>
                      ))}
                    </div>
                    {Object.keys(protections).length > 0 && (
                      <div className="mt-4">
                        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">保护机制</h3>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                          {Object.entries(protections).map(([k, v]) => (
                            <div key={k} className={`rounded-xl p-3 border text-center ${
                              v === 'Yes' ? 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800' :
                              v === 'No' ? 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800' :
                              'bg-gray-50 dark:bg-gray-900 border-gray-200 dark:border-gray-700'
                            }`}>
                              <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">{k}</p>
                              <p className={`text-sm font-bold ${
                                v === 'Yes' ? 'text-red-600 dark:text-red-400' :
                                v === 'No' ? 'text-green-600 dark:text-green-400' :
                                'text-gray-900 dark:text-white'
                              }`}>{v}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Agent 步骤回放 */}
            {agentSteps.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                <button onClick={() => setShowSteps(!showSteps)}
                  className="w-full px-6 py-4 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-750 transition">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 bg-gradient-to-br from-amber-500 to-orange-600 rounded-lg flex items-center justify-center">
                      <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                    </div>
                    <h2 className="text-lg font-bold text-gray-900 dark:text-white">AI 分析过程</h2>
                    <span className="text-xs text-gray-400 bg-gray-100 dark:bg-gray-700 px-2 py-0.5 rounded-full">{agentSteps.length} 步</span>
                  </div>
                  <svg className={`w-5 h-5 text-gray-400 transition ${showSteps ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>
                {showSteps && (
                  <div className="px-6 pb-6 space-y-2">
                    {agentSteps.map((step, i) => <StepCard key={i} step={step} index={i} />)}
                  </div>
                )}
              </div>
            )}

            {task.result?.phases?.ai?.tokens && (
              <div className="text-center text-xs text-gray-400 dark:text-gray-500">
                消耗 Tokens: {task.result.phases.ai.tokens}
              </div>
            )}
          </>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* ── NC Modal ── */}
      {showNcModal && <NcModal target={ncTarget} onClose={() => setShowNcModal(false)} taskId={taskId || ''} />}
    </div>
  )
}
