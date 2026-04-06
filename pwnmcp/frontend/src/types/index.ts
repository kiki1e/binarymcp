export interface Leak {
  id: number
  provider: string
  raw_key: string
  repo_url: string
  repo_owner: string
  repo_name: string
  file_path: string
  leak_introduced_at: string | null
  leak_detected_at: string
  key_status: string
  validated_at: string | null
  verified_provider: string
  verified_url: string
}

export interface LeakListResponse {
  leaks: Leak[]
  total: number
  has_more: boolean
}

export interface Stats {
  total_leaks: number
  today_leaks: number
  total_repos: number
  total_events_scanned: number
  total_repos_scanned: number
}

export interface WeeklyItem {
  date: string
  count: number
}

export interface LeaderboardItem {
  repo_owner: string
  leak_count: number
}

export interface ProviderDailyItem {
  date: string
  provider: string
  count: number
}

export interface ValidateAllResponse {
  validated: number
  results: { valid: number; invalid: number; unchecked: number }
}

export interface BalanceInfo {
  currency: string
  total_balance: string
  granted_balance: string
  topped_up_balance: string
}

export interface BalanceResponse {
  is_available: boolean
  balance_infos: BalanceInfo[]
}

// ── 新增: 赛题分析相关 ──

export interface AnalysisTask {
  task_id: string
  status: string
  phase: string
  message: string
  challenge_type: string
  progress: number
  result: Record<string, any> | null
  started_at?: string
}

export interface UploadResult {
  task_id: string
  filename: string
  file_path: string
  size: number
}

export interface KeyInfo {
  id: number
  raw_key: string
  provider: string
  verified_provider: string
  key_status: string
  models: { id: string; owned_by?: string }[]
  validated_at: string | null
}

export interface ImportKeysResponse {
  imported: number
  results: KeyInfo[]
}

export interface AvailableModelsResponse {
  models: { id: string; provider: string; owned_by: string; key_count: number }[]
  total: number
}

export interface IDAStatus {
  status: string
  ida_url?: string
  error?: string
}
