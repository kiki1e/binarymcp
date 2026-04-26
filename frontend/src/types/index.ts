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
  status: 'pending' | 'running' | 'completed' | 'failed' | 'stopped'
  phase: string
  message: string
  challenge_type: string
  progress: number
  result?: {
    duration?: number
    phases?: {
      static?: any
      decompile?: {
        source?: string
        decompiled?: Record<string, string> | string
      }
      tools?: any
      ai?: {
        model?: string
        content?: string
        error?: string
        tokens?: number
        agent_steps?: AgentStep[]
      }
    }
  } | null
  agent_steps?: AgentStep[]
  started_at?: string
  target_urls?: string[]
  target_endpoints?: string[]
}

export interface UploadedFile {
  filename: string
  file_path: string
  size: number
  is_archive?: boolean
}

export interface ExtractedArchive {
  archive: string
  extract_dir?: string
  files: string[]
}

export interface UploadResult {
  task_id: string
  files: UploadedFile[]
  extracted?: ExtractedArchive[]
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

// ── 新增: 会话管理 ──

export interface ChatSession {
  session_id: string
  name: string
  user_id: string
  channel: string
  message_count: number
  created_at: string
  updated_at: string
}

export interface SessionListResponse {
  sessions: ChatSession[]
}

export interface SessionDetailResponse {
  session: {
    session_id: string
    name: string
    user_id: string
    channel: string
    messages: ChatMessage[]
    created_at: string
    updated_at: string
  }
}

export interface ChatMessage {
  role: string
  content: string
  timestamp?: string
  metadata?: Record<string, any>
}

export interface ChatStreamChunk {
  type: 'meta' | 'chunk' | 'done' | 'error' | 'thought' | 'action' | 'observation' | 'text' | 'hint'
  content?: string
  provider?: string
  model?: string
  name?: string
  input?: string
}

// ── Agent 步骤 (前端展示) ──

export interface AgentStep {
  type: 'thought' | 'action' | 'observation' | 'text' | 'error' | 'hint'
  content?: string
  name?: string
  input?: string
  full_length?: number
  step_index?: number
  total_steps?: number
}

// ── nc 连接 ──

export interface NcConnectRequest {
  target: string
  input_data?: string
  timeout?: number
}

export interface NcConnectResponse {
  output?: string
  error?: string
}
