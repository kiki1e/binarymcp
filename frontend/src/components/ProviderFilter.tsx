import { useState, useRef, useEffect } from 'react'

// 常用 provider 快捷按钮
const HOT_PROVIDERS = [
  'openai', 'anthropic', 'deepseek', 'dashscope', 'google',
  'groq', 'xai', 'github', 'huggingface', 'newapi',
  'openrouter', 'cerebras', 'siliconflow', 'minimax', 'kimi',
]

// 所有已知 provider（搜索建议）
const ALL_PROVIDERS = [
  ...HOT_PROVIDERS,
  'openrouter', 'cerebras', 'siliconflow', 'minimax', 'kimi',
  'aws', 'stripe', 'twilio', 'sendgrid', 'mailgun', 'slack',
  'pinecone', 'livekit', 'moonshot', 'modelscope',
]

interface Props {
  current: string
  onChange: (p: string) => void
}

export default function ProviderFilter({ current, onChange }: Props) {
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  const suggestions = search.trim()
    ? ALL_PROVIDERS.filter(p => p.includes(search.trim().toLowerCase()))
    : []

  const select = (p: string) => {
    onChange(p)
    setSearch('')
    setOpen(false)
  }

  const isHot = HOT_PROVIDERS.includes(current)

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button
        onClick={() => { onChange(''); setSearch('') }}
        className={`px-3 py-1 rounded-full text-xs font-medium transition ${
          !current ? 'bg-emerald-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
        }`}
      >
        All
      </button>
      {HOT_PROVIDERS.map((p) => (
        <button
          key={p}
          onClick={() => select(p)}
          className={`px-3 py-1 rounded-full text-xs font-medium transition ${
            p === current ? 'bg-emerald-500 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
          }`}
        >
          {p}
        </button>
      ))}
      {current && !isHot && (
        <span className="px-3 py-1 rounded-full text-xs font-medium bg-emerald-500 text-white">
          {current}
        </span>
      )}
      <div ref={ref} className="relative">
        <input
          type="text"
          value={search}
          placeholder="Search..."
          onChange={(e) => { setSearch(e.target.value); setOpen(true) }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && search.trim()) { select(search.trim().toLowerCase()); }
            if (e.key === 'Escape') { setOpen(false); setSearch('') }
          }}
          className="w-28 px-3 py-1 rounded-full text-xs bg-gray-800 text-gray-300 border border-gray-700 focus:border-emerald-500 focus:outline-none"
        />
        {open && suggestions.length > 0 && (
          <div className="absolute top-full mt-1 left-0 w-40 bg-gray-800 border border-gray-700 rounded-lg shadow-lg z-10 max-h-48 overflow-y-auto">
            {suggestions.map((p) => (
              <button
                key={p}
                onClick={() => select(p)}
                className="w-full text-left px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-700 hover:text-emerald-400"
              >
                {p}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
