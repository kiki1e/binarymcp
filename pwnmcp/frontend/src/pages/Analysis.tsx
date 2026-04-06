import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { uploadChallenge, startAnalysis, fetchAnalysisList } from '../api/client'
import type { AnalysisTask } from '../types'
import { useEffect } from 'react'

const CHALLENGE_TYPES = [
  { value: 'auto', label: 'Auto Detect', desc: 'Automatically detect challenge type' },
  { value: 'pwn', label: 'PWN', desc: 'Binary exploitation' },
  { value: 'reverse', label: 'Reverse', desc: 'Reverse engineering' },
  { value: 'crypto', label: 'Crypto', desc: 'Cryptography' },
  { value: 'iot', label: 'IoT', desc: 'IoT / Firmware analysis' },
]

export default function Analysis() {
  const [file, setFile] = useState<File | null>(null)
  const [challengeType, setChallengeType] = useState('auto')
  const [uploading, setUploading] = useState(false)
  const [error, setError] = useState('')
  const [tasks, setTasks] = useState<AnalysisTask[]>([])
  const navigate = useNavigate()

  // Load existing tasks
  useEffect(() => {
    fetchAnalysisList()
      .then((data) => setTasks(data.tasks))
      .catch(() => {})
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const f = e.dataTransfer.files[0]
    if (f) setFile(f)
  }, [])

  const handleSubmit = async () => {
    if (!file) return
    setError('')
    setUploading(true)
    try {
      // 1. Upload
      const upload = await uploadChallenge(file)
      // 2. Start analysis
      const task = await startAnalysis(upload.task_id, challengeType)
      // 3. Navigate to result page
      navigate(`/analysis/${task.task_id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setUploading(false)
    }
  }

  const statusColor: Record<string, string> = {
    running: 'text-yellow-400',
    completed: 'text-emerald-400',
    failed: 'text-red-400',
  }

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-emerald-400">CTF Challenge Analysis</h1>

      {/* Upload Area */}
      <div
        onDrop={handleDrop}
        onDragOver={(e) => e.preventDefault()}
        className="border-2 border-dashed border-gray-700 rounded-lg p-12 text-center hover:border-emerald-500 transition"
      >
        {file ? (
          <div className="space-y-2">
            <p className="text-lg text-emerald-400">{file.name}</p>
            <p className="text-sm text-gray-400">{(file.size / 1024).toFixed(1)} KB</p>
            <button
              onClick={() => setFile(null)}
              className="text-xs text-red-400 hover:text-red-300"
            >
              Remove
            </button>
          </div>
        ) : (
          <div className="space-y-2">
            <p className="text-gray-400">Drag & drop binary file here</p>
            <label className="inline-block px-4 py-2 bg-gray-800 rounded cursor-pointer hover:bg-gray-700 text-sm">
              Or click to select
              <input
                type="file"
                className="hidden"
                onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])}
              />
            </label>
          </div>
        )}
      </div>

      {/* Challenge Type Selection */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium text-gray-400">Challenge Type</h3>
        <div className="flex gap-3 flex-wrap">
          {CHALLENGE_TYPES.map((t) => (
            <button
              key={t.value}
              onClick={() => setChallengeType(t.value)}
              className={`px-4 py-2 rounded-lg text-sm transition ${
                challengeType === t.value
                  ? 'bg-emerald-600 text-white'
                  : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
              }`}
            >
              <div className="font-medium">{t.label}</div>
              <div className="text-xs opacity-70">{t.desc}</div>
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="text-red-400 text-sm bg-red-900/20 rounded p-3">{error}</div>
      )}

      {/* Submit Button */}
      <button
        onClick={handleSubmit}
        disabled={!file || uploading}
        className="w-full py-3 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-40 rounded-lg font-medium text-lg transition"
      >
        {uploading ? 'Uploading & Analyzing...' : 'Start Analysis'}
      </button>

      {/* Task History */}
      {tasks.length > 0 && (
        <section className="space-y-3">
          <h3 className="text-sm font-medium text-gray-400">Recent Analyses</h3>
          <div className="space-y-2">
            {tasks.map((t) => (
              <button
                key={t.task_id}
                onClick={() => navigate(`/analysis/${t.task_id}`)}
                className="w-full flex items-center justify-between bg-gray-900 border border-gray-800 rounded-lg p-4 hover:border-gray-700 transition text-left"
              >
                <div>
                  <span className="text-sm font-mono text-emerald-400">{t.task_id}</span>
                  <span className="text-xs text-gray-500 ml-3">{t.challenge_type.toUpperCase()}</span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="w-24 bg-gray-800 rounded-full h-2">
                    <div
                      className="bg-emerald-500 h-2 rounded-full transition-all"
                      style={{ width: `${(t.progress || 0) * 100}%` }}
                    />
                  </div>
                  <span className={`text-xs ${statusColor[t.status] || 'text-gray-400'}`}>
                    {t.status}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  )
}
