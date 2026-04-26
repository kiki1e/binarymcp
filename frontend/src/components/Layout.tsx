import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'
import { useTheme } from '../context/ThemeContext'
import type { ReactNode } from 'react'

const NAV = [
  { path: '/analysis', label: '赛题分析', icon: '🎯' },
  { path: '/chat', label: 'AI对话', icon: '💬' },
  { path: '/explore', label: '密钥监控', icon: '🔑' },
  { path: '/config', label: 'API配置', icon: '⚙️' },
]

export default function Layout({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const { username, logout } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen flex flex-col bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-950 dark:to-gray-900 transition-colors">
      <nav className="bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 shadow-sm sticky top-0 z-50 backdrop-blur-sm bg-opacity-90 dark:bg-opacity-90">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-8">
              <Link to="/" className="flex items-center gap-3 group">
                <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-purple-600 rounded-xl flex items-center justify-center shadow-lg group-hover:shadow-xl transition-all group-hover:scale-105">
                  <span className="text-white text-xl font-bold">🎯</span>
                </div>
                <span className="text-xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  CTF Analysis
                </span>
              </Link>
              <div className="hidden md:flex items-center gap-2">
                {NAV.map((n) => (
                  <Link
                    key={n.path}
                    to={n.path}
                    className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all ${
                      pathname.startsWith(n.path)
                        ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-md'
                        : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800'
                    }`}
                  >
                    <span>{n.icon}</span>
                    <span>{n.label}</span>
                  </Link>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={toggleTheme}
                className="p-2.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 transition-all hover:scale-105"
                title={theme === 'dark' ? '切换到白天模式' : '切换到夜晚模式'}
              >
                {theme === 'dark' ? (
                  <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
                  </svg>
                )}
              </button>
              {username && (
                <>
                  <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-100 dark:bg-gray-800 rounded-lg">
                    <span className="text-sm text-gray-600 dark:text-gray-400">👤</span>
                    <span className="text-sm font-medium text-gray-900 dark:text-white">{username}</span>
                  </div>
                  <button
                    onClick={handleLogout}
                    className="px-4 py-2 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition"
                  >
                    退出
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </nav>
      <main className="flex-1 w-full">
        {children}
      </main>
      <footer className="bg-white dark:bg-gray-900 border-t border-gray-200 dark:border-gray-800 px-6 py-6 text-center">
        <div className="max-w-7xl mx-auto">
          <p className="text-sm text-gray-500 dark:text-gray-400">
            🎯 CTF Analysis Platform - Powered by AI
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            智能分析 • 自动化利用 • 赛题破解
          </p>
        </div>
      </footer>
    </div>
  )
}
