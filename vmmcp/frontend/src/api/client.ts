import type {
  LeakListResponse, Leak, Stats, WeeklyItem, LeaderboardItem,
  ValidateAllResponse, BalanceResponse, ProviderDailyItem,
  AnalysisTask, UploadResult, ImportKeysResponse, AvailableModelsResponse, IDAStatus,
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

// ── 新增: Key 管理 ──

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

// ── 新增: 赛题分析 ──

export async function uploadChallenge(file: File): Promise<UploadResult> {
  const token = localStorage.getItem('token')
  const form = new FormData()
  form.append('file', file)
  const headers: Record<string, string> = {}
  if (token) headers['Authorization'] = `Bearer ${token}`
  const res = await fetch(`${BASE}/analysis/upload`, { method: 'POST', headers, body: form })
  if (!res.ok) throw new Error(`Upload failed: ${res.status}`)
  return res.json()
}

export async function startAnalysis(
  taskId: string,
  challengeType = 'auto',
  modelProvider = '',
  modelName = '',
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
    }),
  })
  if (!res.ok) throw new Error(`Start analysis failed: ${res.status}`)
  return res.json()
}

export const fetchAnalysisStatus = (taskId: string) =>
  request<AnalysisTask>(`${BASE}/analysis/${taskId}`)

export const fetchAnalysisList = () =>
  request<{ tasks: AnalysisTask[] }>(`${BASE}/analysis`)

// ── 新增: IDA Pro ──

export const fetchIDAStatus = () => request<IDAStatus>(`${BASE}/ida/status`)
