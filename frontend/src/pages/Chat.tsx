import { useEffect, useRef, useState, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  sendChatMessageStream,
  sendAgentMessageStream,
  fetchSessions,
  createSession,
  deleteSession,
  renameSession,
  fetchSession,
  clearSessionMessages,
} from '../api/client'
import MarkdownRenderer from '../components/MarkdownRenderer'
import type { ChatStreamChunk, ChatSession, ChatMessage } from '../types'

interface AgentStep {
  type: 'thought' | 'action' | 'observation'
  content: string
  name?: string
  input?: string
}

interface DisplayMessage {
  role: 'user' | 'assistant'
  content: string
  streaming?: boolean
  agentMode?: boolean
  agentSteps?: AgentStep[]
}

export default function Chat() {
  const [searchParams, setSearchParams] = useSearchParams()

  // 会话
  const [sessions, setSessions] = useState<ChatSession[]>([])
  const [currentSessionId, setCurrentSessionId] = useState<string>(
    searchParams.get('session') || '',
  )
  const [showSessionList, setShowSessionList] = useState(true)

  // 消息
  const [messages, setMessages] = useState<DisplayMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showNewSessionInput, setShowNewSessionInput] = useState(false)
  const [newSessionName, setNewSessionName] = useState('')
  const [renamingId, setRenamingId] = useState<string | null>(null)
  const [renameValue, setRenameValue] = useState('')

  const [agentMode, setAgentMode] = useState(false)

  // 如果 URL 中有 context=taskId, 自动插入上下文消息
  useEffect(() => {
    const ctx = searchParams.get('context')
    if (ctx && messages.length === 0) {
      setMessages([{
        role: 'assistant',
        content: `📂 当前分析任务 **${ctx}** 的结果已就绪，你可以针对分析结果继续提问，例如：\n- 解释这段 exploit 的原理\n- 如何修复这个漏洞\n- 这个漏洞的 CVSS 评分是多少`,
      }])
    }
  }, [searchParams, messages.length])

  const chatEndRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // 加载会话列表
  const loadSessions = useCallback(async () => {
    try {
      const data = await fetchSessions()
      setSessions(data.sessions || [])
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    loadSessions()
  }, [loadSessions])

  // 加载会话消息
  const loadSessionMessages = useCallback(async (sessionId: string) => {
    try {
      const data = await fetchSession(sessionId)
      const msgs = data.session?.messages || []
      setMessages(
        msgs.map((m: ChatMessage) => ({
          role: m.role as 'user' | 'assistant',
          content: m.content,
        })),
      )
    } catch {
      setMessages([])
    }
  }, [])

  // 切换会话
  useEffect(() => {
    if (currentSessionId) {
      loadSessionMessages(currentSessionId)
      setSearchParams({ session: currentSessionId }, { replace: true })
    } else {
      setMessages([])
    }
  }, [currentSessionId, loadSessionMessages, setSearchParams])

  // 自动滚动
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  // ── 创建新会话 ──
  const handleCreateSession = async () => {
    const name = newSessionName.trim() || '新对话'
    try {
      const data = await createSession(name)
      if (data.session) {
        setSessions(prev => [data.session, ...prev])
        setCurrentSessionId(data.session.session_id)
        setMessages([])
      }
    } catch (e) {
      setError('创建会话失败')
    }
    setShowNewSessionInput(false)
    setNewSessionName('')
  }

  // ── 删除会话 ──
  const handleDeleteSession = async (sessionId: string) => {
    try {
      await deleteSession(sessionId)
      setSessions(prev => prev.filter(s => s.session_id !== sessionId))
      if (currentSessionId === sessionId) {
        setCurrentSessionId('')
        setMessages([])
      }
    } catch {
      setError('删除会话失败')
    }
  }

  // ── 重命名会话 ──
  const handleRename = async (sessionId: string) => {
    if (!renameValue.trim()) return
    try {
      await renameSession(sessionId, renameValue.trim())
      setSessions(prev =>
        prev.map(s =>
          s.session_id === sessionId ? { ...s, name: renameValue.trim() } : s,
        ),
      )
    } catch {
      setError('重命名失败')
    }
    setRenamingId(null)
    setRenameValue('')
  }

  // ── 清空会话 ──
  const handleClear = async () => {
    if (!currentSessionId) return
    try {
      await clearSessionMessages(currentSessionId)
      setMessages([])
    } catch {
      setError('清空失败')
    }
  }

  // ── 发送消息 (流式) ──
  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return

    // 自动创建会话
    let sessionId = currentSessionId
    if (!sessionId) {
      try {
        const data = await createSession(text.slice(0, 20))
        if (data.session) {
          sessionId = data.session.session_id
          setSessions(prev => [data.session, ...prev])
          setCurrentSessionId(sessionId)
        }
      } catch {
        setError('创建会话失败')
        return
      }
    }

    setInput('')
    setError('')

    const userMsg: DisplayMessage = { role: 'user', content: text }
    const assistantMsg: DisplayMessage = {
      role: 'assistant',
      content: '',
      streaming: true,
      agentMode,
      agentSteps: [],
    }
    setMessages(prev => [...prev, userMsg, assistantMsg])
    setLoading(true)

    // 构建消息历史（含当前消息）
    const apiMessages = [
      {
        role: 'system',
        content: agentMode
          ? '你是一个 CTF 安全分析专家，擅长 PWN、逆向工程、密码学分析。使用工具进行分析并给出最终答案。请用中文回答。'
          : '你是一个 CTF 赛题分析助手，擅长回答关于二进制漏洞利用(PWN)、逆向工程(Reverse)、密码学(Crypto)、IoT固件分析等问题。请用中文回答，给出详细的技术分析和指导。',
      },
      ...messages.map(m => ({ role: m.role, content: m.content })),
      { role: 'user', content: text },
    ]

    // 获取 API 配置 — 优先用默认配置，否则从列表取第一个
    let config: any = undefined
    const defaultCfg = localStorage.getItem('default_api_config')
    if (defaultCfg) {
      const parsed = JSON.parse(defaultCfg)
      config = {
        provider: parsed.provider || 'custom',
        apiKey: parsed.apiKey,
        baseUrl: parsed.baseUrl,
        model: parsed.model,
      }
    } else {
      const allCfgs = localStorage.getItem('api_configs')
      if (allCfgs) {
        const parsed = JSON.parse(allCfgs)
        if (parsed.length > 0) {
          const first = parsed[0]
          config = {
            provider: first.provider || 'custom',
            apiKey: first.apiKey,
            baseUrl: first.baseUrl,
            model: first.model,
          }
        }
      }
    }
    // 仍然没有配置则提示用户
    if (!config) {
      setError('请先在导航栏 "API配置" 页面添加 API 密钥和模型配置')
      setMessages(prev => {
        const copy = [...prev]
        copy.pop() // remove the empty assistant message
        copy.pop() // remove the user message
        return copy
      })
      setLoading(false)
      return
    }

    if (agentMode) {
      // ── Agent 模式 ──
      let fullContent = ''
      let agentSteps: AgentStep[] = []

      abortRef.current = sendAgentMessageStream(
        apiMessages,
        (chunk: ChatStreamChunk) => {
          if (chunk.type === 'thought') {
            agentSteps = [...agentSteps, { type: 'thought', content: chunk.content || '' }]
            setMessages(prev => {
              const copy = [...prev]
              const last = copy[copy.length - 1]
              if (last?.streaming) {
                copy[copy.length - 1] = { ...last, agentSteps: [...agentSteps] }
              }
              return copy
            })
          } else if (chunk.type === 'action') {
            agentSteps = [...agentSteps, { type: 'action', content: chunk.name || '', name: chunk.name, input: chunk.input }]
            setMessages(prev => {
              const copy = [...prev]
              const last = copy[copy.length - 1]
              if (last?.streaming) {
                copy[copy.length - 1] = { ...last, agentSteps: [...agentSteps] }
              }
              return copy
            })
          } else if (chunk.type === 'observation') {
            agentSteps = [...agentSteps, { type: 'observation', content: chunk.content || '' }]
            setMessages(prev => {
              const copy = [...prev]
              const last = copy[copy.length - 1]
              if (last?.streaming) {
                copy[copy.length - 1] = { ...last, agentSteps: [...agentSteps] }
              }
              return copy
            })
          } else if (chunk.type === 'text') {
            fullContent += chunk.content || ''
            setMessages(prev => {
              const copy = [...prev]
              const last = copy[copy.length - 1]
              if (last?.streaming) {
                copy[copy.length - 1] = { ...last, content: fullContent, agentSteps: [...agentSteps] }
              }
              return copy
            })
          } else if (chunk.type === 'meta') {
            // model info
          } else if (chunk.type === 'error') {
            setError(chunk.content || '请求失败')
          }
        },
        (err: string) => {
          setError(err)
          setMessages(prev => {
            const copy = [...prev]
            const last = copy[copy.length - 1]
            if (last?.streaming) {
              copy[copy.length - 1] = {
                role: 'assistant',
                content: `**错误**: ${err}\n\n请检查 API 配置是否正确。`,
                agentSteps: last.agentSteps,
              }
            }
            return copy
          })
        },
        (content: string) => {
          setMessages(prev => {
            const copy = [...prev]
            const last = copy[copy.length - 1]
            if (last?.streaming) {
              copy[copy.length - 1] = { role: 'assistant', content, agentSteps: last.agentSteps }
            }
            return copy
          })
          loadSessions()
        },
        config,
        sessionId,
      )
    } else {
      // ── 普通对话模式 ──
      let fullContent = ''
      abortRef.current = sendChatMessageStream(
        apiMessages,
        (chunk: ChatStreamChunk) => {
          if (chunk.type === 'meta') {
            // 可以显示模型信息
          } else if (chunk.type === 'chunk' && chunk.content) {
            fullContent += chunk.content
            setMessages(prev => {
              const copy = [...prev]
              const last = copy[copy.length - 1]
              if (last?.streaming) {
                copy[copy.length - 1] = { ...last, content: fullContent }
              }
              return copy
            })
          } else if (chunk.type === 'error') {
            setError(chunk.content || '请求失败')
          }
        },
        (err: string) => {
          setError(err)
          setMessages(prev => {
            const copy = [...prev]
            const last = copy[copy.length - 1]
            if (last?.streaming) {
              copy[copy.length - 1] = {
                role: 'assistant',
                content: `**错误**: ${err}\n\n请检查 API 配置是否正确。`,
              }
            }
            return copy
          })
        },
        (content: string) => {
          setMessages(prev => {
            const copy = [...prev]
            const last = copy[copy.length - 1]
            if (last?.streaming) {
              copy[copy.length - 1] = { role: 'assistant', content }
            }
            return copy
          })
          loadSessions()
        },
        config,
        sessionId,
      )
    }

    setLoading(false)
  }

  // 取消流式请求
  const handleStop = () => {
    abortRef.current?.abort()
    setMessages(prev => {
      const copy = [...prev]
      const last = copy[copy.length - 1]
      if (last?.streaming) {
        copy[copy.length - 1] = {
          role: 'assistant',
          content: last.content || '（已取消）',
          agentSteps: last.agentSteps,
        }
      }
      return copy
    })
    setLoading(false)
  }

  // 示例问题
  const sampleQuestions = [
    '如何分析一个 PWN 赛题？',
    '什么是 ROP 链？',
    '栈溢出保护机制有哪些？',
    '如何识别加密算法？',
  ]

  return (
    <div className="h-[calc(100vh-64px)] flex bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900">
      {/* ── 会话侧边栏 ── */}
      {showSessionList && (
        <div className="w-72 bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 flex flex-col shrink-0">
          <div className="p-4 border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-between mb-3">
              <h2 className="text-lg font-bold text-gray-900 dark:text-white">对话历史</h2>
              <button
                onClick={() => setShowNewSessionInput(true)}
                className="p-2 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg hover:from-blue-700 hover:to-purple-700 transition text-sm"
                title="新建对话"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              </button>
            </div>
            {showNewSessionInput ? (
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newSessionName}
                  onChange={e => setNewSessionName(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleCreateSession()}
                  placeholder="对话名称..."
                  className="flex-1 px-3 py-2 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  autoFocus
                />
                <button
                  onClick={handleCreateSession}
                  className="px-3 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition"
                >
                  确定
                </button>
              </div>
            ) : null}
          </div>

          <div className="flex-1 overflow-y-auto p-2 space-y-1">
            {sessions.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">
                暂无对话记录
              </p>
            ) : (
              sessions.map(s => (
                <div
                  key={s.session_id}
                  className={`group rounded-xl transition cursor-pointer ${
                    currentSessionId === s.session_id
                      ? 'bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800'
                      : 'hover:bg-gray-100 dark:hover:bg-gray-700 border border-transparent'
                  }`}
                >
                  {renamingId === s.session_id ? (
                    <div className="p-2 flex gap-2">
                      <input
                        type="text"
                        value={renameValue}
                        onChange={e => setRenameValue(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleRename(s.session_id)}
                        className="flex-1 px-2 py-1 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded text-sm"
                        autoFocus
                      />
                      <button
                        onClick={() => handleRename(s.session_id)}
                        className="px-2 py-1 text-xs bg-blue-600 text-white rounded"
                      >
                        保存
                      </button>
                    </div>
                  ) : (
                    <div
                      className="p-3 flex items-center justify-between"
                      onClick={() => setCurrentSessionId(s.session_id)}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 dark:text-white truncate">
                          {s.name || '新对话'}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                          {s.message_count} 条消息
                        </p>
                      </div>
                      <div className="hidden group-hover:flex items-center gap-1 ml-2">
                        <button
                          onClick={e => {
                            e.stopPropagation()
                            setRenamingId(s.session_id)
                            setRenameValue(s.name || '')
                          }}
                          className="p-1 hover:bg-gray-200 dark:hover:bg-gray-600 rounded text-gray-500"
                          title="重命名"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </button>
                        <button
                          onClick={e => {
                            e.stopPropagation()
                            handleDeleteSession(s.session_id)
                          }}
                          className="p-1 hover:bg-red-100 dark:hover:bg-red-900/20 rounded text-red-500"
                          title="删除"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {/* ── 主聊天区域 ── */}
      <div className="flex-1 flex flex-col">
        {/* 顶部栏 */}
        <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 px-6 py-3 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowSessionList(!showSessionList)}
              className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition text-gray-500"
              title="切换侧边栏"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            </button>
            <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${agentMode ? 'bg-gradient-to-br from-orange-500 to-red-600' : 'bg-gradient-to-br from-blue-500 to-cyan-600'}`}>
              <span className="text-white text-sm">{agentMode ? 'AG' : 'AI'}</span>
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900 dark:text-white">
                {agentMode ? 'Agent 分析' : 'AI 对话'}
              </h1>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {agentMode ? 'ReAct 推理-行动循环分析' : 'CTF 赛题技术问答'}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 cursor-pointer">
              <span className="text-xs text-gray-500 dark:text-gray-400">Agent</span>
              <div
                onClick={() => setAgentMode(!agentMode)}
                className={`relative w-10 h-5 rounded-full transition cursor-pointer ${
                  agentMode ? 'bg-orange-500' : 'bg-gray-300 dark:bg-gray-600'
                }`}
              >
                <div
                  className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition ${
                    agentMode ? 'translate-x-5' : 'translate-x-0.5'
                  }`}
                />
              </div>
            </label>
            {currentSessionId && messages.length > 0 && (
              <button
                onClick={handleClear}
                className="px-3 py-1.5 text-xs text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition"
              >
                清空对话
              </button>
            )}
          </div>
        </div>

        {/* 消息区域 */}
        <div className="flex-1 overflow-y-auto">
          <div className="max-w-4xl mx-auto p-6 space-y-6">
            {messages.length === 0 ? (
              <div className="text-center py-16">
                <div className="text-6xl mb-6">💬</div>
                <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
                  CTF 赛题分析助手
                </h2>
                <p className="text-gray-500 dark:text-gray-400 mb-8">
                  上传二进制文件或直接提问，AI 帮你分析
                </p>
                <div className="grid grid-cols-2 gap-3 max-w-xl mx-auto">
                  {sampleQuestions.map((q, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        setInput(q)
                        inputRef.current?.focus()
                      }}
                      className="px-4 py-3 bg-white dark:bg-gray-800 hover:bg-blue-50 dark:hover:bg-blue-900/20 border border-gray-200 dark:border-gray-700 rounded-xl text-sm text-gray-700 dark:text-gray-300 transition text-left"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {msg.role === 'assistant' && (
                    <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-cyan-600 rounded-xl flex items-center justify-center shrink-0 mr-3 mt-1">
                      <span className="text-white text-sm">AI</span>
                    </div>
                  )}
                  <div
                    className={`max-w-[75%] rounded-2xl px-5 py-3 ${
                      msg.role === 'user'
                        ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white'
                        : 'bg-white dark:bg-gray-800 text-gray-900 dark:text-white border border-gray-200 dark:border-gray-700'
                    }`}
                  >
                    {msg.role === 'user' ? (
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    ) : (
                      <div className="text-sm leading-relaxed">
                        {msg.agentSteps && msg.agentSteps.length > 0 && (
                          <div className="space-y-2 mb-3">
                            {msg.agentSteps.map((step, si) => {
                              if (step.type === 'thought') {
                                return (
                                  <details key={si} className="text-xs bg-gray-50 dark:bg-gray-900 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
                                    <summary className="px-3 py-2 cursor-pointer text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 select-none">
                                      <span className="font-medium">💭 思考</span>
                                    </summary>
                                    <div className="px-3 py-2 text-gray-600 dark:text-gray-300 whitespace-pre-wrap max-h-40 overflow-y-auto">
                                      {step.content}
                                    </div>
                                  </details>
                                )
                              } else if (step.type === 'action') {
                                return (
                                  <details key={si} className="text-xs bg-orange-50 dark:bg-gray-900 rounded-lg border border-orange-200 dark:border-orange-900/30 overflow-hidden">
                                    <summary className="px-3 py-2 cursor-pointer text-orange-700 dark:text-orange-400 hover:bg-orange-100 dark:hover:bg-gray-800 select-none">
                                      <span className="font-medium">🔧 调用工具: {step.content}</span>
                                    </summary>
                                    <div className="px-3 py-2 text-gray-600 dark:text-gray-300 font-mono whitespace-pre-wrap max-h-40 overflow-y-auto">
                                      {step.input || step.content}
                                    </div>
                                  </details>
                                )
                              } else if (step.type === 'observation') {
                                return (
                                  <details key={si} className="text-xs bg-green-50 dark:bg-gray-900 rounded-lg border border-green-200 dark:border-green-900/30 overflow-hidden">
                                    <summary className="px-3 py-2 cursor-pointer text-green-700 dark:text-green-400 hover:bg-green-100 dark:hover:bg-gray-800 select-none">
                                      <span className="font-medium">📊 工具结果</span>
                                    </summary>
                                    <div className="px-3 py-2 text-gray-600 dark:text-gray-300 font-mono whitespace-pre-wrap max-h-40 overflow-y-auto">
                                      {step.content.slice(0, 500)}
                                      {step.content.length > 500 && <span className="text-gray-400">...（截断）</span>}
                                    </div>
                                  </details>
                                )
                              }
                              return null
                            })}
                            {msg.streaming && msg.agentSteps.length > 0 && (
                              <div className="flex items-center gap-2 text-xs text-gray-400 px-1">
                                <span className="w-1.5 h-1.5 bg-orange-500 rounded-full animate-pulse" />
                                正在分析...
                              </div>
                            )}
                          </div>
                        )}
                        <MarkdownRenderer content={msg.content || (msg.streaming && !msg.agentSteps?.length ? '⋯' : '')} />
                        {msg.streaming && !msg.agentSteps?.length && (
                          <span className="inline-block w-2 h-4 bg-blue-600 dark:bg-blue-400 animate-pulse ml-1" />
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}

            {error && !loading && (
              <div className="text-center">
                <p className="text-xs text-red-500 bg-red-50 dark:bg-red-900/20 inline-block px-4 py-2 rounded-lg">
                  {error}
                </p>
              </div>
            )}

            <div ref={chatEndRef} />
          </div>
        </div>

        {/* 输入区域 */}
        <div className="bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700 px-6 py-4 shrink-0">
          <div className="max-w-4xl mx-auto">
            <div className="flex gap-3">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    loading ? handleStop() : handleSend()
                  }
                }}
                placeholder="输入你的 CTF 问题..."
                disabled={loading}
                className="flex-1 px-5 py-3.5 bg-gray-50 dark:bg-gray-900 border border-gray-300 dark:border-gray-700 rounded-xl text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
              />
              {loading ? (
                <button
                  onClick={handleStop}
                  className="px-5 py-3.5 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-xl transition shadow-lg text-sm flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                  停止
                </button>
              ) : (
                <button
                  onClick={handleSend}
                  disabled={!input.trim()}
                  className="px-5 py-3.5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-700 hover:to-purple-700 disabled:from-gray-400 disabled:to-gray-500 disabled:cursor-not-allowed text-white font-semibold rounded-xl transition shadow-lg text-sm"
                >
                  发送
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
