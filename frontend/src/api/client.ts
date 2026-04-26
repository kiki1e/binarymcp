import type {
  LeakListResponse, Leak, Stats, WeeklyItem, LeaderboardItem,
  ValidateAllResponse, BalanceResponse, ProviderDailyItem,
  AnalysisTask, UploadResult, ImportKeysResponse, AvailableModelsResponse, IDAStatus,
  ChatSession, SessionListResponse, SessionDetailResponse, ChatStreamChunk,
  NcConnectResponse,
} from '../types'

const BASE = '/api'

async function request<T>(url: string): Promise<T> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(url, { headers })
  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

async function postRequest<T>(url: string): Promise<T> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(url, { method: 'POST', headers })
  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

async function postJsonRequest<T>(url: string, body: any): Promise<T> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) })
  if (res.status === 401) {
    localStorage.removeItem('token')
    localStorage.removeItem('username')
    window.location.href = '/login'
    throw new Error('Unauthorized')
  }
  if (!res.ok) throw new Error(`API ${res.status}: ${res.statusText}`)
  return res.json()
}

export async function fetchLeaks(page = 1, limit = 20, provider?: string, keyStatus?: string, excludeProvider?: string): Promise<LeakListResponse> {
  const params = new URLSearchParams({ page: String(page), limit: String(limit) })
  if (provider) params.set('provider', provider)
  if (keyStatus) params.set('key_status', keyStatus)
  if (excludeProvider) params.set('exclude_provider', excludeProvider)
  return request(`${BASE}/leaks?${params}`)
}

export const fetchStats = () => request<Stats>(`${BASE}/stats`)
export const fetchWeekly = () => request<WeeklyItem[]>(`${BASE}/stats/weekly`)
export const fetchLeaderboard = () => request<LeaderboardItem[]>(`${BASE}/stats/leaderboard`)
export const fetchProviderDaily = () => request<ProviderDailyItem[]>(`${BASE}/stats/provider-daily`)
export const fetchValidDaily = () => request<ProviderDailyItem[]>(`${BASE}/stats/valid-daily`)

export const validateLeak = (id: number) => postRequest<Leak>(`${BASE}/leaks/${id}/validate`)
export const validateAllLeaks = () => postRequest<ValidateAllResponse>(`${BASE}/leaks/validate-all`)
export const fetchBalance = (id: number) => request<BalanceResponse>(`${BASE}/leaks/${id}/balance`)

// ── Key 管理 ──

export async function importKeys(keys: string[]): Promise<ImportKeysResponse> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}/keys/import`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ keys }),
  })
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

export const fetchKeyModels = (keyId: number) =>
  request<{ key_id: number; provider: string; models: any[] }>(`${BASE}/keys/${keyId}/models`)

export const fetchAvailableModels = () =>
  request<AvailableModelsResponse>(`${BASE}/keys/available-models`)

// ── 赛题分析 ──

export async function uploadChallenge(files: File[]): Promise<UploadResult> {
  const token = localStorage.getItem('token')
  const form = new FormData()
  files.forEach(f => form.append('files', f))
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  // 不要设置 Content-Type, 浏览器会自动设置 multipart boundary
  const res = await fetch(`${BASE}/analysis/upload`, { method: 'POST', headers, body: form })
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
  return res.json()
}

export async function startAnalysis(
  taskId: string,
  challengeType = 'auto',
  modelProvider = '',
  modelName = '',
  apiKey = '',
  baseUrl = '',
  targetUrls: string[] = [],
  targetEndpoints: string[] = [],
): Promise<AnalysisTask> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}/analysis/start/${taskId}`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      challenge_type: challengeType,
      model_provider: modelProvider,
      model_name: modelName,
      api_key: apiKey,
      base_url: baseUrl,
      target_urls: targetUrls,
      target_endpoints: targetEndpoints,
    }),
  })
  if (!res.ok) throw new Error(`Start analysis failed: ${res.status}`)
  return res.json()
}

export const fetchAnalysisStatus = (taskId: string) =>
  request<AnalysisTask>(`${BASE}/analysis/${taskId}`)

export const fetchAnalysisList = () =>
  request<{ tasks: AnalysisTask[] }>(`${BASE}/analysis`)

export const stopAnalysis = (taskId: string) =>
  postRequest<{ success: boolean; message: string }>(`${BASE}/analysis/${taskId}/stop`)

export const ncConnect = async (
  taskId: string,
  target: string,
  inputData = '',
  timeout = 10,
): Promise<NcConnectResponse> => {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}/analysis/${taskId}/nc-connect`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ target, input_data: inputData, timeout }),
  })
  if (!res.ok) throw new Error(`nc-connect failed: ${res.status}`)
  return res.json()
}

// ── AI 对话 (非流式) ──

export async function sendChatMessage(
  messages: { role: string; content: string }[],
  config?: { provider: string; apiKey: string; baseUrl: string; model: string }
): Promise<{ content: string; model: string; usage: any }> {
  const token = localStorage.getItem('token')
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const body: any = { messages }

  if (config?.apiKey && config?.model) {
    body.provider = config.provider || 'custom'
    body.api_key = config.apiKey
    body.base_url = config.baseUrl
    body.model = config.model
  }

  const res = await fetch(`${BASE}/analysis/chat`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`Chat API ${res.status}: ${res.statusText}`)
  return res.json()
}

// ── AI 对话 (流式 SSE) ──

export function sendChatMessageStream(
  messages: { role: string; content: string }[],
  onChunk: (chunk: ChatStreamChunk) => void,
  onError: (error: string) => void,
  onDone: (fullContent: string) => void,
  config?: { provider: string; apiKey: string; baseUrl: string; model: string },
  sessionId?: string,
): AbortController {
  const controller = new AbortController()
  const token = localStorage.getItem('token')

  const body: any = { messages, session_id: sessionId || '' }

  if (config?.apiKey && config?.model) {
    body.provider = config.provider || 'custom'
    body.api_key = config.apiKey
    body.base_url = config.baseUrl
    body.model = config.model
  }

  ;(async () => {
    try {
      const res = await fetch(`${BASE}/analysis/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!res.ok) {
        const text = await res.text().catch(() => '')
        onError(`API ${res.status}: ${text || res.statusText}`)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) {
        onError('Response body is not readable')
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const dataStr = line.slice(6).trim()
          if (!dataStr) continue
          try {
            const chunk: ChatStreamChunk = JSON.parse(dataStr)
            if (chunk.type === 'done') {
              onDone(chunk.content || '')
            } else {
              onChunk(chunk)
            }
          } catch {
            // skip malformed JSON
          }
        }
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') return
      onError(err?.message || 'Stream error')
    }
  })()

  return controller
}

// ── 会话管理 ──

export const fetchSessions = (userId = '') =>
  request<SessionListResponse>(`${BASE}/sessions?user_id=${userId}`)

export const createSession = (name = '新对话', userId = '') =>
  postJsonRequest<{ session: ChatSession }>(`${BASE}/sessions`, { name, user_id: userId })

export const fetchSession = (sessionId: string) =>
  request<SessionDetailResponse>(`${BASE}/sessions/${sessionId}`)

export const deleteSession = (sessionId: string) =>
  postRequest<{ success: boolean }>(`${BASE}/sessions/${sessionId}`)

export const renameSession = (sessionId: string, name: string) =>
  postJsonRequest<{ session: ChatSession }>(`${BASE}/sessions/${sessionId}/name`, { name })

export const clearSessionMessages = (sessionId: string) =>
  postRequest<{ success: boolean }>(`${BASE}/sessions/${sessionId}/clear`)

// ── ReAct Agent 流式 ──

export function sendAgentMessageStream(
  messages: { role: string; content: string }[],
  onChunk: (chunk: ChatStreamChunk) => void,
  onError: (error: string) => void,
  onDone: (fullContent: string) => void,
  config?: { provider: string; apiKey: string; baseUrl: string; model: string },
  sessionId?: string,
  filePath?: string,
): AbortController {
  const controller = new AbortController()
  const token = localStorage.getItem('token')

  const body: any = { messages, session_id: sessionId || '', file_path: filePath || '' }

  if (config?.apiKey && config?.model) {
    body.provider = config.provider || 'custom'
    body.api_key = config.apiKey
    body.base_url = config.baseUrl
    body.model = config.model
  }

  ;(async () => {
    try {
      const res = await fetch(`${BASE}/analysis/agent/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      })

      if (!res.ok) {
        const text = await res.text().catch(() => '')
        onError(`API ${res.status}: ${text || res.statusText}`)
        return
      }

      const reader = res.body?.getReader()
      if (!reader) {
        onError('Response body is not readable')
        return
      }

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const dataStr = line.slice(6).trim()
          if (!dataStr) continue
          try {
            const chunk: ChatStreamChunk = JSON.parse(dataStr)
            if (chunk.type === 'done') {
              onDone(chunk.content || '')
            } else {
              onChunk(chunk)
            }
          } catch {
            // skip malformed JSON
          }
        }
      }
    } catch (err: any) {
      if (err?.name === 'AbortError') return
      onError(err?.message || 'Stream error')
    }
  })()

  return controller
}

// ── 自定义 Provider ──

export const fetchProviders = () =>
  request<{ providers: { name: string; default_base_url: string; builtin: boolean }[] }>(`${BASE}/providers`)

export const registerProvider = (name: string, baseUrl: string) =>
  postJsonRequest<{ success: boolean; message: string }>(`${BASE}/providers/register`, { name, base_url: baseUrl })

export const removeProvider = (name: string) =>
  postRequest<{ success: boolean; message: string }>(`${BASE}/providers/${name}`)

// ── IDA Pro ──

export const fetchIDAStatus = () => request<IDAStatus>(`${BASE}/ida/status`)
