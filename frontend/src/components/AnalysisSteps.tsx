interface Step {
  id: string
  label: string
  status: 'pending' | 'running' | 'completed' | 'failed'
}

interface AnalysisStepsProps {
  currentPhase: string
  status: string
}

const STEPS: Step[] = [
  { id: 'pending', label: '等待中', status: 'pending' },
  { id: 'detecting', label: '检测类型', status: 'pending' },
  { id: 'static', label: '静态分析', status: 'pending' },
  { id: 'decompiling', label: '反编译', status: 'pending' },
  { id: 'tool_analysis', label: '工具分析', status: 'pending' },
  { id: 'ai_analysis', label: 'AI深度分析', status: 'pending' },
  { id: 'exploit_gen', label: '生成利用脚本', status: 'pending' },
]

export default function AnalysisSteps({ currentPhase, status }: AnalysisStepsProps) {
  const getStepStatus = (stepId: string): 'pending' | 'running' | 'completed' | 'failed' => {
    const stepIndex = STEPS.findIndex(s => s.id === stepId)
    const currentIndex = STEPS.findIndex(s => s.id === currentPhase)

    if (status === 'failed' && stepId === currentPhase) return 'failed'
    if (stepId === currentPhase && status === 'running') return 'running'
    if (stepIndex < currentIndex || status === 'completed') return 'completed'
    return 'pending'
  }

  return (
    <div className="relative">
      <div className="flex items-center justify-between">
        {STEPS.map((step, index) => {
          const stepStatus = getStepStatus(step.id)
          return (
            <div key={step.id} className="flex items-center flex-1">
              <div className="flex flex-col items-center relative z-10">
                <div className={`w-10 h-10 rounded-full flex items-center justify-center border-2 transition-all duration-300 ${
                  stepStatus === 'completed' ? 'bg-gray-900 dark:bg-white border-gray-900 dark:border-white' :
                  stepStatus === 'running' ? 'bg-gray-600 dark:bg-gray-400 border-gray-600 dark:border-gray-400 animate-pulse' :
                  stepStatus === 'failed' ? 'bg-red-600 dark:bg-red-500 border-red-600 dark:border-red-500' :
                  'bg-white dark:bg-gray-800 border-gray-300 dark:border-gray-700'
                }`}>
                  {stepStatus === 'completed' ? (
                    <svg className="w-5 h-5 text-white dark:text-gray-900" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  ) : stepStatus === 'failed' ? (
                    <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  ) : stepStatus === 'running' ? (
                    <div className="w-3 h-3 bg-white dark:bg-gray-900 rounded-full animate-ping" />
                  ) : (
                    <span className="text-gray-400 dark:text-gray-500 text-sm font-bold">{index + 1}</span>
                  )}
                </div>
                <span className={`text-xs mt-2 text-center whitespace-nowrap transition-colors ${
                  stepStatus === 'completed' ? 'text-gray-900 dark:text-white font-medium' :
                  stepStatus === 'running' ? 'text-gray-700 dark:text-gray-300 font-medium' :
                  stepStatus === 'failed' ? 'text-red-600 dark:text-red-400 font-medium' :
                  'text-gray-400 dark:text-gray-500'
                }`}>
                  {step.label}
                </span>
              </div>
              {index < STEPS.length - 1 && (
                <div className={`flex-1 h-0.5 mx-2 transition-all duration-300 ${
                  getStepStatus(STEPS[index + 1].id) === 'completed' ||
                  getStepStatus(STEPS[index + 1].id) === 'running' ? 'bg-gray-900 dark:bg-white' : 'bg-gray-300 dark:bg-gray-700'
                }`} />
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
