import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { fetchAnalysisStatus } from '../api/client'
import type { AnalysisTask } from '../types'

const PHASE_LABELS: Record<string, string> = {
  pending: 'Waiting...',
  detecting: 'Detecting challenge type',
  static: 'Static analysis',
  decompiling: 'Decompiling',
  tool_analysis: 'Running analysis tools',
  ai_analysis: 'AI deep analysis',
  exploit_gen: 'Generating exploit',
  completed: 'Completed',
  failed: 'Failed',
}

export default function AnalysisResult() {
  const { taskId } = useParams<{ taskId: string }>()
  const [task, setTask] = useState<AnalysisTask | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!taskId) return
    let cancelled = false

    const poll = async () => {
      try {
        const data = await fetchAnalysisStatus(taskId)
        if (!cancelled) {
          setTask(data)
          if (data.status === 'running') {
            setTimeout(poll, 2000)
          }
        }
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load')
      }
    }

    poll()
    return () => { cancelled = true }
  }, [taskId])

  if (error) return <div className="text-red-400 text-center py-12">{error}</div>
  if (!task) return <div className="text-gray-500 text-center py-12">Loading...</div>

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-emerald-400">Analysis: {taskId}</h1>
          <span className="text-sm text-gray-400">Type: {task.challenge_type?.toUpperCase() || 'AUTO'}</span>
        </div>
        <span className={`text-sm px-3 py-1 rounded-full ${
          task.status === 'completed' ? 'bg-emerald-900/50 text-emerald-400' :
          task.status === 'failed' ? 'bg-red-900/50 text-red-400' :
          'bg-yellow-900/50 text-yellow-400'
        }`}>
          {task.status}
        </span>
      </div>

      {/* Progress Bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm text-gray-400">
          <span>{PHASE_LABELS[task.phase] || task.phase}</span>
          <span>{Math.round((task.progress || 0) * 100)}%</span>
        </div>
        <div className="w-full bg-gray-800 rounded-full h-3">
          <div
            className={`h-3 rounded-full transition-all duration-500 ${
              task.status === 'failed' ? 'bg-red-500' : 'bg-emerald-500'
            }`}
            style={{ width: `${(task.progress || 0) * 100}%` }}
          />
        </div>
        {task.message && (
          <p className="text-xs text-gray-500">{task.message}</p>
        )}
      </div>

      {/* Results */}
      {task.result && (
        <div className="space-y-4">
          {/* Static Analysis */}
          {task.result.phases?.static && (
            <ResultSection title="Static Analysis">
              <pre className="text-xs text-gray-300 bg-gray-800 rounded p-4 overflow-x-auto max-h-64 overflow-y-auto">
                {JSON.stringify(task.result.phases.static, null, 2)}
              </pre>
            </ResultSection>
          )}

          {/* Decompile */}
          {task.result.phases?.decompile && (
            <ResultSection title={`Decompiled Code (${task.result.phases.decompile.source || 'rizin'})`}>
              {task.result.phases.decompile.decompiled &&
                typeof task.result.phases.decompile.decompiled === 'object' ? (
                  Object.entries(task.result.phases.decompile.decompiled).map(([name, code]) => (
                    <div key={name} className="mb-4">
                      <h4 className="text-sm text-emerald-400 mb-1">{name}()</h4>
                      <pre className="text-xs text-gray-300 bg-gray-800 rounded p-4 overflow-x-auto max-h-80 overflow-y-auto">
                        {String(code)}
                      </pre>
                    </div>
                  ))
                ) : (
                  <pre className="text-xs text-gray-300 bg-gray-800 rounded p-4 overflow-x-auto max-h-80 overflow-y-auto">
                    {JSON.stringify(task.result.phases.decompile, null, 2)}
                  </pre>
                )
              }
            </ResultSection>
          )}

          {/* Tool Analysis */}
          {task.result.phases?.tools && (
            <ResultSection title="Tool Analysis">
              <pre className="text-xs text-gray-300 bg-gray-800 rounded p-4 overflow-x-auto max-h-64 overflow-y-auto">
                {JSON.stringify(task.result.phases.tools, null, 2)}
              </pre>
            </ResultSection>
          )}

          {/* AI Analysis */}
          {task.result.phases?.ai && (
            <ResultSection title="AI Analysis">
              {task.result.phases.ai.error ? (
                <div className="text-red-400 text-sm">{task.result.phases.ai.error}</div>
              ) : (
                <div className="prose prose-invert prose-sm max-w-none">
                  <div className="text-xs text-gray-500 mb-2">
                    Model: {task.result.phases.ai.model || 'unknown'}
                  </div>
                  <pre className="text-sm text-gray-200 bg-gray-800 rounded p-4 whitespace-pre-wrap overflow-x-auto max-h-[600px] overflow-y-auto">
                    {task.result.phases.ai.content || JSON.stringify(task.result.phases.ai, null, 2)}
                  </pre>
                </div>
              )}
            </ResultSection>
          )}

          {/* Duration */}
          {task.result.duration && (
            <div className="text-xs text-gray-500 text-right">
              Total time: {task.result.duration.toFixed(1)}s
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function ResultSection({ title, children }: { title: string; children: React.ReactNode }) {
  const [open, setOpen] = useState(true)
  return (
    <section className="bg-gray-900 border border-gray-800 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 hover:bg-gray-800/50 transition"
      >
        <h3 className="font-semibold text-sm">{title}</h3>
        <span className="text-gray-500 text-xs">{open ? '▼' : '▶'}</span>
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </section>
  )
}
